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


class TestConsumo:
    """Consumo derivado da trilha, não de contador próprio.

    O campo que justifica a tela é `nunca_lidos`: caminho concedido que o robô
    nunca leu é escopo a enxugar. Permissão que ninguém usa é só superfície de
    ataque esperando um comprometimento.
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
            json={"name": "outro-segredo", "value": "valor-qualquer"},
        )

        politica = PolicyModel(name="pol-rpa-consumo", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil/*",
                capabilities=["read", "reveal"],
                effect="allow",
            ),
            PolicyRuleModel(
                path="cofres/rh/*", capabilities=["read", "reveal"], effect="allow"
            ),
        ]
        papel = RoleModel(name="rpa-consumo", description="")
        papel.policies.append(politica)
        db.add_all([politica, papel])
        db.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-consumo", "display_name": "RPA Consumo",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-consumo",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-consumo/credenciais", headers=headers, json={}
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        return lease.json()["token"]

    def test_conta_leituras_por_caminho(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        cabecalho = {"Authorization": f"Bearer {token}"}

        for _ in range(3):
            client.post(
                "/api/v1/maquina/segredo",
                headers=cabecalho,
                json={"cofre": "contabil", "segredo": "dominio-escrita"},
            )
        client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "contabil", "segredo": "outro-segredo"},
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        )
        assert consumo.status_code == 200
        lidos = {
            linha["caminho"]: linha["leituras"] for linha in consumo.json()["lidos"]
        }
        assert lidos["cofres/contabil/segredos/dominio-escrita"] == 3
        assert lidos["cofres/contabil/segredos/outro-segredo"] == 1

    def test_ordena_do_mais_lido_ao_menos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        cabecalho = {"Authorization": f"Bearer {token}"}
        client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "contabil", "segredo": "outro-segredo"},
        )
        for _ in range(4):
            client.post(
                "/api/v1/maquina/segredo",
                headers=cabecalho,
                json={"cofre": "contabil", "segredo": "dominio-escrita"},
            )

        lidos = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        ).json()["lidos"]
        assert [linha["leituras"] for linha in lidos] == [4, 1]

    def test_escopo_nunca_usado_aparece(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O campo que justifica a tela: permissão concedida e nunca usada."""
        token = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        ).json()

        # O escopo tem contábil e RH; só o contábil foi usado.
        assert "cofres/rh/*" in consumo["caminhos_no_escopo"]
        assert consumo["nunca_lidos"] == ["cofres/rh/*"]

    def test_caminho_usado_sai_de_nunca_lidos(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        cabecalho = {"Authorization": f"Bearer {token}"}
        client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )
        client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "rh", "segredo": "folha"},
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        ).json()
        assert consumo["nunca_lidos"] == []

    def test_negativas_aparecem_separadas(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Caminho negado com frequência é escopo mal dimensionado."""
        token = self._preparar(client, autenticado, usuario, db_session)
        cabecalho = {"Authorization": f"Bearer {token}"}
        for _ in range(2):
            client.post(
                "/api/v1/maquina/segredo",
                headers=cabecalho,
                json={"cofre": "infraestrutura", "segredo": "x"},
            )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        ).json()
        assert len(consumo["negados"]) >= 1
        assert consumo["lidos"] == []

    def test_consumo_nao_mistura_aplicacoes(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Cada robô responde pelo seu: misturar inutilizaria a análise."""
        token = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )

        politica = PolicyModel(name="pol-rpa-dois", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil/*", capabilities=["reveal"], effect="allow"
            )
        ]
        papel = RoleModel(name="rpa-dois", description="")
        papel.policies.append(politica)
        db_session.add_all([politica, papel])
        db_session.commit()
        client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-dois", "display_name": "Dois",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-dois",
            },
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-dois/consumo", headers=autenticado
        ).json()
        assert consumo["lidos"] == []

    def test_leitura_de_pessoa_nao_entra_no_consumo_da_maquina(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """O ator é o robô; leitura humana no mesmo caminho não conta."""
        self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/cofres/contabil/segredos/dominio-escrita/revelar",
            headers=autenticado,
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-consumo/consumo", headers=autenticado
        ).json()
        assert consumo["lidos"] == []

    def test_sem_admin_nao_ve_consumo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        assert client.get(
            "/api/v1/aplicacoes/qualquer/consumo", headers=autenticado
        ).status_code == 403


class TestOrdemDasChecagens:
    """O escopo é checado antes de resolver o cofre.

    Descoberto escrevendo o teste de consumo: resolver o cofre primeiro fazia
    a resposta distinguir "cofre não existe" (404) de "fora do seu escopo"
    (403). Um robô comprometido mapearia todos os cofres da empresa pela
    mensagem de erro, sem ter permissão para ler nenhum deles.
    """

    def test_cofre_inexistente_e_fora_do_escopo_respondem_igual(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )
        cabecalho = {"Authorization": f"Bearer {token}"}

        # Cofre que EXISTE, mas está fora do escopo do lease.
        existente = client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "rh", "segredo": "folha"},
        )
        # Cofre que NÃO existe.
        inventado = client.post(
            "/api/v1/maquina/segredo",
            headers=cabecalho,
            json={"cofre": "inventado", "segredo": "qualquer"},
        )

        assert existente.status_code == inventado.status_code == 403, (
            "respostas diferentes permitiriam mapear os cofres existentes "
            "pela mensagem de erro"
        )
        assert (
            existente.json()["erro"]["mensagem"]
            == inventado.json()["erro"]["mensagem"]
        )

    def test_tentativa_em_cofre_inexistente_tambem_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Varredura de nomes de cofre é sinal que a revisão quer encontrar."""
        token = TestCicloCompleto()._preparar(
            client, autenticado, usuario, db_session
        )
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "varredura", "segredo": "x"},
        )

        eventos = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "acesso_negado",
                AuditEventModel.actor_label == "maquina:rpa-fiscal",
            )
        ).all()
        assert any("varredura" in e.target_path for e in eventos)


class TestNuncaLidosSemFalsoPositivo:
    """Um caminho sem curinga não pode aparecer como "nunca lido" quando o
    que foi lido está SOB ele.

    Descoberto validando no ambiente: a política concede `cofres/contabil` e
    `cofres/contabil/*`; as leituras acontecem em
    `cofres/contabil/segredos/x`. O primeiro padrão casa só com o caminho
    exato, então aparecia como nunca usado — um alerta mandando enxugar
    escopo em uso. Alerta falso é pior que alerta nenhum: ensina a ignorar
    o aviso.
    """

    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> str:
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, headers)

        # A forma real: o cofre E o curinga sob ele.
        politica = PolicyModel(name="pol-rpa-exato", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil",
                capabilities=["read", "list"],
                effect="allow",
            ),
            PolicyRuleModel(
                path="cofres/contabil/*",
                capabilities=["read", "reveal"],
                effect="allow",
            ),
        ]
        papel = RoleModel(name="rpa-exato", description="")
        papel.policies.append(politica)
        db.add_all([politica, papel])
        db.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-exato", "display_name": "Exato",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-exato",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-exato/credenciais", headers=headers, json={}
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        return lease.json()["token"]

    def test_cofre_com_leitura_dentro_nao_e_nunca_lido(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        token = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {token}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-exato/consumo", headers=autenticado
        ).json()

        assert "cofres/contabil" in consumo["caminhos_no_escopo"]
        assert consumo["nunca_lidos"] == [], (
            "o cofre apareceu como nunca lido apesar das leituras dentro dele"
        )

    def test_escopo_de_fato_nao_usado_continua_aparecendo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """A correção não pode engolir o alerta de verdade."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, autenticado)

        politica = PolicyModel(name="pol-rpa-largo", description="")
        politica.rules = [
            PolicyRuleModel(
                path="cofres/contabil/*",
                capabilities=["read", "reveal"],
                effect="allow",
            ),
            PolicyRuleModel(
                path="cofres/rh", capabilities=["read", "list"], effect="allow"
            ),
        ]
        papel = RoleModel(name="rpa-largo", description="")
        papel.policies.append(politica)
        db_session.add_all([politica, papel])
        db_session.commit()

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-largo", "display_name": "Largo",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-largo",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-largo/credenciais", headers=autenticado, json={}
        )
        lease = client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": credencial.json()["secret_id"],
            },
        )
        client.post(
            "/api/v1/maquina/segredo",
            headers={"Authorization": f"Bearer {lease.json()['token']}"},
            json={"cofre": "contabil", "segredo": "dominio-escrita"},
        )

        consumo = client.get(
            "/api/v1/aplicacoes/rpa-largo/consumo", headers=autenticado
        ).json()
        # O RH foi concedido e nunca tocado: o alerta precisa aparecer.
        assert consumo["nunca_lidos"] == ["cofres/rh"]


class TestRenovacaoPeloRobo:
    """O robô troca a própria credencial, sem agendador interno.

    Um processo de rotação dentro do Vault competiria com o orquestrador que
    a empresa já tem. Quem sabe quando é seguro trocar é o robô — entre dois
    ciclos, não no meio de um.
    """

    def _preparar(
        self, client: TestClient, headers: dict[str, str], usuario: UserModel,
        db: Session,
    ) -> tuple[str, str]:
        conceder(db, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _cenario(client, headers)
        _papel_da_aplicacao(db, "rpa-rota", "cofres/contabil/*", ["read", "reveal"])

        criada = client.post(
            "/api/v1/aplicacoes",
            headers=headers,
            json={
                "name": "rpa-rota", "display_name": "RPA Rotação",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-rota",
            },
        )
        credencial = client.post(
            "/api/v1/aplicacoes/rpa-rota/credenciais",
            headers=headers,
            json={"label": "inicial"},
        )
        return criada.json()["role_id"], credencial.json()["secret_id"]

    def test_robo_troca_a_propria_credencial(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        role_id, antiga = self._preparar(client, autenticado, usuario, db_session)

        renovacao = client.post(
            "/api/v1/maquina/renovar",
            json={"role_id": role_id, "secret_id": antiga},
        )
        assert renovacao.status_code == 200
        nova = renovacao.json()["secret_id"]
        assert nova != antiga

        # A nova autentica.
        assert client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": role_id, "secret_id": nova},
        ).status_code == 200

    def test_a_antiga_ainda_vale_no_periodo_de_graca(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Matar na hora derrubaria um ciclo em andamento."""
        role_id, antiga = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/renovar",
            json={"role_id": role_id, "secret_id": antiga},
        )

        # Logo depois da troca, a antiga ainda autentica.
        assert client.post(
            "/api/v1/maquina/autenticar",
            json={"role_id": role_id, "secret_id": antiga},
        ).status_code == 200

    def test_credencial_errada_nao_renova(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Renovar exige a credencial atual: senão qualquer um se emitiria."""
        role_id, _ = self._preparar(client, autenticado, usuario, db_session)

        resposta = client.post(
            "/api/v1/maquina/renovar",
            json={"role_id": role_id, "secret_id": "inventado"},
        )
        assert resposta.status_code == 401

    def test_renovacao_fica_na_trilha(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        role_id, antiga = self._preparar(client, autenticado, usuario, db_session)
        client.post(
            "/api/v1/maquina/renovar",
            json={"role_id": role_id, "secret_id": antiga},
        )

        evento = db_session.scalars(
            select(AuditEventModel).where(
                AuditEventModel.action == "aplicacao_credencial_rotacionada"
            )
        ).one()
        assert evento.actor_label == "maquina:rpa-rota"
        # Jamais o valor da credencial.
        assert antiga not in evento.reason

    def test_credencial_revogada_nao_renova(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        role_id, antiga = self._preparar(client, autenticado, usuario, db_session)
        credenciais = client.get(
            "/api/v1/aplicacoes/rpa-rota/credenciais", headers=autenticado
        ).json()
        client.post(
            f"/api/v1/aplicacoes/rpa-rota/credenciais/{credenciais[0]['id']}/revogar",
            headers=autenticado,
        )

        assert client.post(
            "/api/v1/maquina/renovar",
            json={"role_id": role_id, "secret_id": antiga},
        ).status_code == 401


class TestVencimentos:
    def test_lista_o_que_vence_no_periodo(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _papel_da_aplicacao(db_session, "rpa-venc", "cofres/*", ["read"])
        client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-venc", "display_name": "Venc",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-venc",
            },
        )
        client.post(
            "/api/v1/aplicacoes/rpa-venc/credenciais",
            headers=autenticado,
            json={"label": "curta", "dias_de_validade": 5},
        )
        client.post(
            "/api/v1/aplicacoes/rpa-venc/credenciais",
            headers=autenticado,
            json={"label": "longa", "dias_de_validade": 300},
        )

        relatorio = client.get(
            "/api/v1/aplicacoes-vencimentos?dias=30", headers=autenticado
        ).json()
        rotulos = [c["label"] for c in relatorio["vencendo"]]
        assert rotulos == ["curta"]

    def test_nunca_usadas_vem_em_lista_propria(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        """Credencial emitida e esquecida autentica do mesmo jeito."""
        conceder(db_session, usuario, "cofres/*", TODAS, nome_politica="p-cofres")
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _papel_da_aplicacao(db_session, "rpa-ociosa", "cofres/*", ["read"])
        criada = client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-ociosa", "display_name": "Ociosa",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-ociosa",
            },
        )
        usada = client.post(
            "/api/v1/aplicacoes/rpa-ociosa/credenciais",
            headers=autenticado,
            json={"label": "em-uso"},
        )
        client.post(
            "/api/v1/aplicacoes/rpa-ociosa/credenciais",
            headers=autenticado,
            json={"label": "esquecida"},
        )
        # Só a primeira é usada.
        client.post(
            "/api/v1/maquina/autenticar",
            json={
                "role_id": criada.json()["role_id"],
                "secret_id": usada.json()["secret_id"],
            },
        )

        relatorio = client.get(
            "/api/v1/aplicacoes-vencimentos", headers=autenticado
        ).json()
        rotulos = [c["label"] for c in relatorio["nunca_usadas"]]
        assert "esquecida" in rotulos
        assert "em-uso" not in rotulos

    def test_revogada_nao_aparece(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "aplicacoes", TODAS, nome_politica="p-apps")
        _papel_da_aplicacao(db_session, "rpa-rev", "cofres/*", ["read"])
        client.post(
            "/api/v1/aplicacoes",
            headers=autenticado,
            json={
                "name": "rpa-rev", "display_name": "Rev",
                "owner_label": "ti@exemplo.com.br", "papel": "rpa-rev",
            },
        )
        cred = client.post(
            "/api/v1/aplicacoes/rpa-rev/credenciais",
            headers=autenticado,
            json={"label": "revogada", "dias_de_validade": 3},
        )
        client.post(
            f"/api/v1/aplicacoes/rpa-rev/credenciais/{cred.json()['id']}/revogar",
            headers=autenticado,
        )

        relatorio = client.get(
            "/api/v1/aplicacoes-vencimentos", headers=autenticado
        ).json()
        assert all(c["label"] != "revogada" for c in relatorio["vencendo"])
        assert all(c["label"] != "revogada" for c in relatorio["nunca_usadas"])

    def test_sem_admin_nao_ve(
        self, client: TestClient, autenticado: dict[str, str], usuario: UserModel,
        db_session: Session,
    ) -> None:
        conceder(db_session, usuario, "cofres/*", TODAS)
        assert client.get(
            "/api/v1/aplicacoes-vencimentos", headers=autenticado
        ).status_code == 403
