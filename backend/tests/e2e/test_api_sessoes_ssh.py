"""Sessão SSH: alvo da lista de máquinas, motivo da lista fechada.

O que se protege aqui:

1. **Motivo mensurável.** Como texto livre, "motivo" vira "manutenção",
   "Manutenção", "manut." e "ver uma coisa" — e a pergunta "quantas sessões
   de incidente tivemos no mês?" deixa de ter resposta.
2. **Uma única lista de máquinas.** O alvo vem de Dispositivos, não de um
   cadastro paralelo: duas listas divergem, e aí "qual é o IP do srv-db-01?"
   passa a ter duas respostas.
3. **O valor do segredo nunca aparece**, nem na listagem de máquinas.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import UserModel

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list"]


def _maquina_ssh(client: TestClient, headers, *, com_credencial: bool = True) -> None:
    """Cadastra um dispositivo com acesso SSH — e, se pedido, a credencial."""
    client.post(
        "/api/v1/dispositivos",
        headers=headers,
        json={
            "name": "srv-db-01",
            "display_name": "Banco de produção",
            "kind": "servidor",
            "address": "10.0.0.5",
        },
    )
    resposta = client.put(
        "/api/v1/dispositivos/srv-db-01/acessos",
        headers=headers,
        json={
            "acessos": [
                {
                    "metodo": "ssh",
                    "identificador": "10.0.0.5",
                    "porta": 2222,
                    "usuario_sugerido": "deploy",
                }
            ]
        },
    )
    assert resposta.status_code == 200, resposta.text
    if com_credencial:
        client.post(
            "/api/v1/dispositivos/srv-db-01/credenciais",
            headers=headers,
            json={"name": "senha-root", "username": "root", "rotation_days": 90},
        )


class TestMotivo:
    def test_lista_fechada_vem_do_servidor(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """A tela não duplica o enum: duplicado, ele diverge."""
        resposta = client.get("/api/v1/sessoes/motivos", headers=autenticado)

        assert resposta.status_code == 200, resposta.text
        valores = [m["valor"] for m in resposta.json()]
        assert "incidente" in valores
        assert "manutencao" in valores
        # Todo motivo tem rótulo de interface, senão a tela mostraria o valor
        # técnico.
        assert all(m["rotulo"] for m in resposta.json())

    def test_motivo_fora_da_lista_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        resposta = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv", "motivo": "ver uma coisa"},
        )
        assert resposta.status_code == 422

    def test_sem_motivo_e_recusado(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Sessão sem motivo é registro que não responde a nada depois."""
        resposta = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv"},
        )
        assert resposta.status_code == 422

    def test_detalhe_continua_livre_ao_lado_da_categoria(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """A categoria serve ao relatório; o detalhe serve à auditoria."""
        resposta = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={
                "tipo": "ssh",
                "alvo": "srv-db-01",
                "motivo": "incidente",
                "motivo_detalhe": "ticket #4417 — lentidão no banco",
            },
        )

        assert resposta.status_code == 201, resposta.text
        corpo = resposta.json()
        assert corpo["motivo"] == "incidente"
        assert corpo["motivo_detalhe"] == "ticket #4417 — lentidão no banco"

    def test_motivo_e_detalhe_vao_para_a_trilha(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """A trilha precisa dizer por que a pessoa entrou na máquina."""
        conceder(db_session, usuario, "auditoria", ["admin"])
        client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={
                "tipo": "ssh",
                "alvo": "srv-db-01",
                "motivo": "deploy",
                "motivo_detalhe": "release 4.2",
            },
        )

        trilha = client.get("/api/v1/auditoria", headers=autenticado).json()["eventos"]
        aberturas = [e for e in trilha if e["action"] == "sessao_aberta"]
        assert aberturas, "a abertura gerou evento"
        assert "deploy" in aberturas[0]["reason"]
        assert "release 4.2" in aberturas[0]["reason"]


class TestMaquinas:
    def test_lista_so_as_que_tem_acesso_ssh(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Dispositivo sem SSH não é alvo possível de sessão SSH."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)
        # Este fica só com RDP e não deve aparecer.
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "pc-ana", "display_name": "PC da Ana", "kind": "outro"},
        )
        client.put(
            "/api/v1/dispositivos/pc-ana/acessos",
            headers=autenticado,
            json={"acessos": [{"metodo": "rdp", "identificador": "10.0.0.9"}]},
        )

        maquinas = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()

        assert [m["name"] for m in maquinas] == ["srv-db-01"]
        assert maquinas[0]["host"] == "10.0.0.5"
        assert maquinas[0]["porta"] == 2222
        assert maquinas[0]["usuario_sugerido"] == "deploy"

    def test_porta_padrao_quando_nao_informada(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """22 é o padrão do protocolo; deixar nulo passaria a decisão adiante."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-web", "display_name": "Web", "kind": "servidor"},
        )
        client.put(
            "/api/v1/dispositivos/srv-web/acessos",
            headers=autenticado,
            json={"acessos": [{"metodo": "ssh", "identificador": "10.0.0.7"}]},
        )

        maquinas = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()
        assert maquinas[0]["porta"] == 22

    def test_aponta_a_credencial_sem_revelar_o_valor(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """O caminho identifica o segredo; o valor continua no cofre."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)

        resposta = client.get("/api/v1/sessoes/maquinas", headers=autenticado)
        maquina = resposta.json()[0]

        assert maquina["tem_credencial"] is True
        assert maquina["segredo_path"] == "credenciais/senha-root"
        assert '"value"' not in resposta.text

    def test_maquina_sem_credencial_e_sinalizada(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """A tela precisa saber que não há senha no cofre para esta máquina."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        _maquina_ssh(client, autenticado, com_credencial=False)

        maquina = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()[0]
        assert maquina["tem_credencial"] is False
        assert maquina["segredo_path"] == ""

    def test_dispositivo_fora_do_alcance_nao_aparece(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Listar a máquina revelaria a existência dela."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        _maquina_ssh(client, autenticado, com_credencial=False)
        conceder(
            db_session,
            usuario,
            "dispositivos/srv-db-01",
            ["read", "list"],
            efeito="deny",
            nome_politica="p-nega",
        )

        resposta = client.get("/api/v1/sessoes/maquinas", headers=autenticado)
        assert resposta.json() == []
        assert "srv-db-01" not in resposta.text

    def test_rota_fixa_nao_colide_com_id_de_sessao(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """`/sessoes/maquinas` não pode ser lido como `/sessoes/{id}`.

        As duas rotas competem pelo mesmo padrão, e a ordem de registro é o
        que decide. Se a dinâmica vencesse, "maquinas" viraria um id
        inexistente e a tela receberia 404 em vez da lista.
        """
        for fixa in ("maquinas", "motivos"):
            resposta = client.get(f"/api/v1/sessoes/{fixa}", headers=autenticado)
            assert resposta.status_code == 200, f"{fixa}: {resposta.text}"
            assert isinstance(resposta.json(), list)


class TestConexaoPronta:
    """A conexão vem montada do servidor, não remontada em cada tela.

    Host, porta e usuário já estão em Dispositivos. Deixar a tela concatenar
    isso espalharia a regra por cada lugar que precisa dela — e cada um
    erraria a seu modo: a porta some, o usuário vira "root" chumbado.
    """

    def test_comando_traz_usuario_host_e_porta(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        _maquina_ssh(client, autenticado, com_credencial=False)

        maquina = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()[0]

        assert maquina["comando"] == "ssh deploy@10.0.0.5 -p 2222"
        assert maquina["url"] == "ssh://deploy@10.0.0.5:2222"

    def test_porta_padrao_nao_polui_o_comando(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """`-p 22` é ruído num comando que a pessoa lê antes de colar."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-web", "display_name": "Web", "kind": "servidor"},
        )
        client.put(
            "/api/v1/dispositivos/srv-web/acessos",
            headers=autenticado,
            json={
                "acessos": [
                    {
                        "metodo": "ssh",
                        "identificador": "10.0.0.7",
                        "usuario_sugerido": "ana",
                    }
                ]
            },
        )

        maquina = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()[0]

        assert maquina["comando"] == "ssh ana@10.0.0.7"
        # Na URL a porta vai sempre: ali ela não custa leitura, e o cliente
        # não precisa saber qual é o padrão.
        assert maquina["url"] == "ssh://ana@10.0.0.7:22"

    def test_sem_usuario_sugerido_o_comando_fica_so_com_o_host(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Inventar "root" seria pior que deixar a pessoa completar."""
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        client.post(
            "/api/v1/dispositivos",
            headers=autenticado,
            json={"name": "srv-x", "display_name": "X", "kind": "servidor"},
        )
        client.put(
            "/api/v1/dispositivos/srv-x/acessos",
            headers=autenticado,
            json={"acessos": [{"metodo": "ssh", "identificador": "10.0.0.8"}]},
        )

        maquina = client.get("/api/v1/sessoes/maquinas", headers=autenticado).json()[0]

        assert maquina["comando"] == "ssh 10.0.0.8"
        assert "@" not in maquina["comando"]

    def test_comando_nunca_carrega_a_senha(
        self,
        client: TestClient,
        db_session: Session,
        usuario: UserModel,
        autenticado: dict[str, str],
    ) -> None:
        """Senha em comando é senha no histórico do shell de quem colou.

        A pessoa revela a senha no cofre — o que vira evento — e o cliente
        SSH a pede. É a mesma regra do arquivo .rdp, que também sai sem
        senha.
        """
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)

        resposta = client.get("/api/v1/sessoes/maquinas", headers=autenticado)
        maquina = resposta.json()[0]

        assert "sshpass" not in maquina["comando"]
        assert "-p senha" not in maquina["comando"]
        # O caminho do segredo identifica; o valor continua no cofre.
        assert maquina["segredo_path"] == "credenciais/senha-root"
        assert '"value"' not in resposta.text


class TestMotivoLegado:
    """Sessões gravadas antes de a lista de motivos fechar.

    **O incidente que este teste trava.** Um registro com motivo livre
    (`"Validacao"`, de antes da lista fechada) fazia a rota de gravações
    devolver 422 e a tela inteira aparecer vazia. Não era uma linha com
    problema entre outras boas: era a listagem inteira caindo por causa de
    uma linha — e as corretas sumiam junto.

    A regra continua valendo para **criação**: motivo novo vem da lista. O
    que já está gravado é fato consumado e precisa ser legível, senão a
    validação conserta o cadastro e quebra a auditoria.
    """

    def test_motivo_antigo_nao_derruba_a_listagem(
        self, client: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        from app.infrastructure.db.models import SessaoModel

        conceder(db_session, usuario, "sessoes", TODAS)
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")

        # Uma sessão válida de hoje...
        _maquina_ssh(client, autenticado)
        atual = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv-db-01", "motivo": "incidente"},
        )
        assert atual.status_code == 201, atual.text
        client.post(
            f"/api/v1/sessoes/{atual.json()['id']}/encerrar",
            headers=autenticado,
            json={"motivo": "fim"},
        )

        # ...e uma de antes da lista fechar, escrita direto no banco porque
        # a API de hoje (corretamente) não aceitaria criá-la.
        antiga = db_session.scalar(select(SessaoModel))
        assert antiga is not None
        antiga.motivo = "Conferencia do fechamento"
        db_session.commit()

        resposta = client.get("/api/v1/sessoes/gravacoes", headers=autenticado)

        assert resposta.status_code == 200, resposta.text
        motivos = [s["motivo"] for s in resposta.json()]
        # O registro antigo aparece como está — sem reescrever o passado.
        assert "Conferencia do fechamento" in motivos

    def test_criar_com_motivo_fora_da_lista_continua_recusado(
        self, client: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """A tolerância é só na leitura. Criar segue preso à lista.

        Sem este teste, "aceitar o legado" viraria "aceitar qualquer coisa"
        no primeiro refactor — e a lista fechada perderia o sentido.
        """
        conceder(db_session, usuario, "sessoes", TODAS)
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)

        resposta = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv-db-01", "motivo": "Validacao"},
        )
        assert resposta.status_code == 422, resposta.text
        # A recusa pode vir do schema (Pydantic valida o enum antes) ou do
        # domínio; as duas listam as opções válidas. O que importa é que
        # "Validacao" não entra e a lista aparece na resposta.
        assert "Validacao" not in resposta.json().get("erro", {}).get("mensagem", "")
        assert "manutencao" in resposta.text and "incidente" in resposta.text

    def test_encerrar_sessao_legada_preserva_o_motivo_original(
        self, client: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """A trilha não pode ganhar um motivo que ninguém escreveu.

        Encerrar grava estado e horário, nunca o motivo. Se um refactor
        passasse a reescrever o registro inteiro, a sessão antiga apareceria
        como "manutenção" — um valor plausível que **nenhuma pessoa digitou**,
        e que a auditoria leria como declaração de quem abriu a sessão.
        """
        from app.infrastructure.db.models import SessaoModel

        conceder(db_session, usuario, "sessoes", TODAS)
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)

        aberta = client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv-db-01", "motivo": "incidente"},
        )
        assert aberta.status_code == 201, aberta.text
        sessao_id = aberta.json()["id"]

        # Vira registro legado, como os que existem desde antes da lista.
        model = db_session.get(SessaoModel, sessao_id)
        assert model is not None
        model.motivo = "Conferencia do fechamento"
        db_session.commit()

        encerrada = client.post(
            f"/api/v1/sessoes/{sessao_id}/encerrar",
            headers=autenticado,
            json={"motivo": "fim do trabalho"},
        )

        assert encerrada.status_code == 200, encerrada.text
        # O motivo da SESSÃO é o original; "fim do trabalho" é o motivo do
        # ENCERRAMENTO, que é outro campo e não substitui o primeiro.
        assert encerrada.json()["motivo"] == "Conferencia do fechamento"
        assert encerrada.json()["motivo_encerramento"] == "fim do trabalho"

        db_session.expire_all()
        relido = db_session.get(SessaoModel, sessao_id)
        assert relido is not None
        assert relido.motivo == "Conferencia do fechamento"

    def test_sessao_ativa_com_motivo_antigo_tambem_lista(
        self, client: TestClient, autenticado: dict[str, str],
        usuario: UserModel, db_session: Session,
    ) -> None:
        """A listagem de ativas tem o mesmo risco e a mesma correção."""
        from app.infrastructure.db.models import SessaoModel

        conceder(db_session, usuario, "sessoes", TODAS)
        conceder(db_session, usuario, "dispositivos/*", TODAS, nome_politica="p-d")
        conceder(db_session, usuario, "credenciais/*", TODAS, nome_politica="p-c")
        _maquina_ssh(client, autenticado)
        client.post(
            "/api/v1/sessoes",
            headers=autenticado,
            json={"tipo": "ssh", "alvo": "srv-db-01", "motivo": "incidente"},
        )

        antiga = db_session.scalar(select(SessaoModel))
        assert antiga is not None
        antiga.motivo = "Validacao"
        db_session.commit()

        resposta = client.get("/api/v1/sessoes", headers=autenticado)
        assert resposta.status_code == 200, resposta.text
        assert len(resposta.json()) == 1
