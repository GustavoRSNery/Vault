"""Testes do acesso de máquina, de ponta a ponta.

O teste que justifica o arquivo é `test_ciclo_completo_do_rpa`: cadastrar,
emitir credencial, autenticar, ler segredo. Sem ele, as rotas poderiam existir
e o robô não conseguir ler nada.

O segundo é `test_escopo_congelado_nao_amplia_com_a_politica`: alterar a
política não pode ampliar um lease já emitido, senão um robô autenticado
escala privilégio em silêncio, sem reautenticar.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AuditEventModel,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)

from .conftest import conceder

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
SEGREDO = "senha-do-dominio-2026"


def _papel_da_aplicacao(
    db: Session, nome: str, caminho: str, capacidades: list[str]
) -> RoleModel:
    """Cria papel + política para uma aplicação, como a tela faria."""
    politica = PolicyModel(name=f"pol-{nome}", description="")
    politica.rules = [
        PolicyRuleModel(path=caminho, capabilities=capacidades, effect="allow")
    ]
    papel = RoleModel(name=nome, description="Papel de aplicação.")
    papel.policies.append(politica)
    db.add_all([politica, papel])
    db.commit()
    return papel


def _cenario(client: TestClient, headers: dict[str, str]) -> None:
    client.post(
        "/api/v1/cofres",
        headers=headers,
        json={"name": "contabil", "display_name": "Contábil"},
    )
    client.post(
        "/api/v1/cofres/contabil/segredos",
        headers=headers,
        json={"name": "dominio-escrita", "value": SEGREDO},
    )
    client.post(
        "/api/v1/cofres",
        headers=headers,
        json={"name": "rh", "display_name": "RH"},
    )
    client.post(
        "/api/v1/cofres/rh/segredos",
        headers=headers,
        json={"name": "folha", "value": "outro-segredo"},
    )


class TestCicloCompleto:
    def test_ciclo_completo_do_rpa(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Cadastrar → emitir credencial → autenticar → ler segredo."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, autenticado)
        _papel_da_aplicacao(
            db_session, "rpa-fiscal", "cofres/contabil/*", ["read", "reveal"]
        )

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-fiscal",
                "display_name": "RPA Fiscal",
                "owner_label": "ti@exemplo.com.br",
                "papel": "rpa-fiscal",
                "lease_minutos": 30,
            },
        )
        assert criada.status_code == 201
        role_id = criada.json()["role_id"]

        credencial = client.post(
            "/api/v1/aplicacoes/rpa-fiscal/credenciais",
            headers=autenticado,
            json={"label": "produção"},
        )
        assert credencial.status_code == 201
        secret_id = credencial.json()["secret_id"]
        assert "uma única vez" in credencial.json()["aviso"]

        # O robô autentica — sem usuário, sem MFA, sem sessão.
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": role_id, "secret_id": secret_id},
        )
        assert lease.status_code == 200
        token = lease.json()["token"]
        assert lease.json()["caminhos"] == ["cofres/contabil/*"]

        # E lê o segredo com o lease.
        leitura = client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )
        assert leitura.status_code == 200
        assert leitura.json()["valor"] == SEGREDO

    def test_leitura_por_maquina_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Quem leu foi o robô, e a trilha precisa dizer isso."""
        token = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "segredo_revelado",
                AuditEventModel.actor_label.like("maquina:%"),
            )
        ).one()
        assert evento.actor_label == "maquina:rpa-fiscal"
        assert evento.actor_id is None  # não há pessoa
        assert SEGREDO not in evento.reason

    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session, caminho: str = "cofres/contabil/*",
    ) -> str:
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, headers)
        _papel_da_aplicacao(db, "rpa-fiscal", caminho, ["read", "reveal"])

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-fiscal",
                "display_name": "RPA Fiscal",
                "owner_label": "ti@exemplo.com.br",
                "papel": "rpa-fiscal",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-fiscal/credenciais",
            headers=headers,
            json={"label": "p"},
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        return lease.json()["token"]


class TestEscopo:
    def test_lease_nao_alcanca_fora_do_escopo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )

        fora = client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "rh", "segredo": "folha"},
        )
        assert fora.status_code == 403
        assert "escopo" in fora.text

    def test_escopo_congelado_nao_amplia_com_a_politica(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A invariante: robô autenticado não escala privilégio em silêncio."""
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "rh", "segredo": "folha"},
        ).status_code == 403

        # Alguém amplia a política da aplicação.
        politica = db_session.scalar(
            select(PolicyModel).where(PolicyModel.name == "pol-rpa-fiscal")
        )
        politica.rules.append(
            PolicyRuleModel(
                policy_id=politica.id,
                path="cofres/*",
                capabilities=["read", "reveal"],
                effect="allow",
            )
        )
        db_session.commit()

        # O lease JÁ EMITIDO continua sem alcançar.
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "rh", "segredo": "folha"},
        ).status_code == 403

    def test_tentativa_fora_do_escopo_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "rh", "segredo": "folha"},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_negado",
                AuditEventModel.actor_label.like("maquina:%"),
            )
        ).one()
        assert "Fora do escopo" in evento.reason

    def test_aplicacao_sem_papel_nao_autentica(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Lease sem escopo não serviria para nada — melhor recusar."""
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-orfao",
                "display_name": "RPA sem papel",
                "owner_label": "ti@exemplo.com.br",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-orfao/credenciais",
            headers=autenticado,
            json={},
        )
        resposta = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        assert resposta.status_code == 403
        assert "política" in resposta.text


class TestAutenticacao:
    def test_role_id_desconhecido_e_secret_errado_dizem_o_mesmo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Distinguir contaria ao atacante que o role_id existe."""
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _papel_da_aplicacao(db_session, "rpa-x", "cofres/*", ["read"])
        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-x", "display_name": "X",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-x",
            },
        )

        inexistente = client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": "nao-existe", "secret_id": "qualquer"},
        )
        errado = client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": criada.json()["role_id"], "secret_id": "errado"},
        )
        assert inexistente.status_code == errado.status_code == 401
        assert inexistente.json()["erro"]["mensagem"] == errado.json()["erro"]["mensagem"]

    def test_credencial_revogada_nao_autentica(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _papel_da_aplicacao(db_session, "rpa-y", "cofres/*", ["read", "reveal"])
        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-y", "display_name": "Y",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-y",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-y/credenciais", headers=autenticado, json={}
        )
        secret_id = credencial.json()["secret_id"]
        role_id = criada.json()["role_id"]

        assert client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": role_id, "secret_id": secret_id},
        ).status_code == 200

        client.post(
            f"/api/v1/aplicacoes/rpa-y/credenciais/{credencial.json()['id']}/revogar",
            headers=autenticado,
        )
        assert client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": role_id, "secret_id": secret_id},
        ).status_code == 401

    def test_tentativa_com_role_id_desconhecido_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str]
    ) -> None:
        """Varredura de role_id é sinal que a revisão quer encontrar."""
        client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": "varredura-123", "secret_id": "x"},
        )
        # O evento foi gravado mesmo sem usuário autenticado.

    def test_sem_token_nao_le_segredo(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/maquina/segredo",
            json={"cofre": "contabil", "segredo": "x"},
        ).status_code == 401

    def test_token_invalido_nao_le_segredo(self, client: TestClient) -> None:
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": "Bearer token-inventado"},
            json={"cofre": "contabil", "segredo": "x"},
        ).status_code == 401


class TestRevogacao:
    def test_revogar_todos_fecha_os_leases_ativos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Botão de emergência: robô comprometido perde acesso agora."""
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        ).status_code == 200

        resposta = client.post(
            "/api/v1/aplicacoes/rpa-fiscal/leases/revogar-todos", headers=autenticado
        )
        assert resposta.json()["revogados"] == 1

        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        ).status_code == 401

    def test_leases_aparecem_na_listagem(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        TestCicloCompleto()._preparar(client, autenticado, usuario, db_session)
        leases = client.get(
            "/api/v1/aplicacoes/rpa-fiscal/leases", headers=autenticado
        )
        assert leases.status_code == 200
        assert len(leases.json()) == 1
        assert leases.json()[0]["ativo"] is True
        # O token não volta na listagem.
        assert "token" not in leases.text


class TestPermissao:
    def test_sem_admin_nao_administra_aplicacoes(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        for metodo, rota in [
            ("get", "/api/v1/aplicacoes"),
            ("post", "/api/v1/aplicacoes"),
        ]:
            chamada = getattr(client, metodo)
            resposta = (
                chamada(rota, headers=autenticado, json={
                    "name": "x", "display_name": "X", "owner_label": "y@z.com"
                })
                if metodo == "post"
                else chamada(rota, headers=autenticado)
            )
            assert resposta.status_code == 403, rota


class TestDenyNaPoliticaDaAplicacao:
    """Uma regra `deny` NÃO pode virar escopo do lease.

    Descoberto por um mutante que sobreviveu: nenhum teste cobria aplicação
    com política de negação. Se o `deny` entrasse no escopo, o robô receberia
    exatamente o acesso que a política nega — a inversão completa da regra.
    """

    def test_regra_deny_nao_entra_no_escopo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, autenticado)

        # Política com allow no contábil e deny explícito no RH.
        politica = PolicyModel(name="pol-rpa-misto", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil/*",
                capabilities=["read", "reveal"],
                effect="allow",
            ),
            PolicyRuleModel(
                path="cofres/rh/*", capabilities=["reveal"], effect="deny"
            ),
        ]
        papel = RoleModel(name="rpa-misto", description="")
        papel.policies.append(politica)
        db_session.add_all([politica, papel])
        db_session.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-misto", "display_name": "Misto",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-misto",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-misto/credenciais", headers=autenticado, json={}
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        assert lease.status_code == 200

        # O caminho negado NÃO está no escopo.
        assert "cofres/rh/*" not in lease.json()["caminhos"]
        assert lease.json()["caminhos"] == ["cofres/contabil/*"]

        token = lease.json()["token"]
        # E a leitura do caminho negado é recusada.
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "rh", "segredo": "folha"},
        ).status_code == 403
        # Enquanto o permitido segue funcionando.
        assert client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        ).status_code == 200

    def test_politica_so_de_deny_nao_concede_lease(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Só negações = escopo vazio = recusa, não lease que não serve."""
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")

        politica = PolicyModel(name="pol-rpa-negado", description="")
        politica.rules = [
            PolicyRuleModel(path="cofres/*", capabilities=["reveal"], effect="deny")
        ]
        papel = RoleModel(name="rpa-negado", description="")
        papel.policies.append(politica)
        db_session.add_all([politica, papel])
        db_session.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-negado", "display_name": "Negado",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-negado",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-negado/credenciais", headers=autenticado, json={}
        )
        resposta = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        assert resposta.status_code == 403


class TestNegacaoVenceNoLease:
    """Regressão de um bug REAL encontrado validando no ambiente.

    Uma política com `allow` em `cofres/contabil/*` e `deny` em
    `cofres/contabil/segredos/token-sefaz` dava ao robô acesso ao token-sefaz:
    o `allow` amplo entrava no escopo e o `deny` era descartado.

    Resultado: a máquina tinha MAIS acesso que a pessoa a quem a mesma
    política se aplica — a inversão completa do "negação vence".

    Nenhum teste pegava porque os cenários anteriores usavam políticas só de
    `allow` ou só de `deny`, nunca as duas no mesmo caminho.
    """

    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> str:
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, headers)
        client.post(
            "/api/v1/cofres/contabil/segredos",
            headers=headers,
            json={"name": "token-sefaz", "value": "token-muito-sensivel"},
        )

        # Exatamente a forma da política real: allow amplo + deny pontual.
        politica = PolicyModel(name="pol-rpa-deny", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil/*",
                capabilities=["read", "reveal", "list"],
                effect="allow",
            ),
            PolicyRuleModel(
                path="cofres/contabil/segredos/token-sefaz",
                capabilities=["reveal"],
                effect="deny",
            ),
        ]
        papel = RoleModel(name="rpa-deny", description="")
        papel.policies.append(politica)
        db.add_all([politica, papel])
        db.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-deny", "display_name": "RPA com deny",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-deny",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-deny/credenciais", headers=headers, json={}
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        assert lease.status_code == 200
        # O lease declara as negações: quem configura o robô precisa saber.
        assert "cofres/contabil/segredos/token-sefaz" in lease.json()["negados"]
        return lease.json()["token"]

    def test_allow_amplo_nao_engole_deny_especifico(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)

        # O segredo NEGADO é recusado, apesar do allow em cofres/contabil/*.
        negado = client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "token-sefaz"},
        )
        assert negado.status_code == 403, (
            "o deny foi engolido pelo allow: o robô teria mais acesso que a "
            "pessoa a quem a mesma política se aplica"
        )
        assert "token-muito-sensivel" not in negado.text

    def test_o_resto_do_cofre_continua_acessivel(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A negação é pontual: não pode fechar o cofre inteiro."""
        token = self._preparar(client, autenticado, usuario, db_session)

        permitido = client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )
        assert permitido.status_code == 200
        assert permitido.json()["valor"] == SEGREDO

    def test_tentativa_no_caminho_negado_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "token-sefaz"},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_negado",
                AuditEventModel.actor_label == "maquina:rpa-deny",
            )
        ).one()
        assert "token-sefaz" in evento.target_path
