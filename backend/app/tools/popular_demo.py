"""Popula o banco local com dados de demonstração.

Cria cofres, segredos e um usuário de carteira limitada, para que a interface
possa ser conferida com conteúdo realista e para que o RBAC seja visível na
prática — o usuário limitado enxerga menos que o administrador.

Os valores aqui são fictícios e servem só para desenvolvimento local.

Uso:  python -m app.tools.popular_demo
"""

from __future__ import annotations

import secrets

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from ..domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ..domain.shared.value_objects import Slug
from ..domain.vaults.entities import Secret, SecretKind, Vault
from ..infrastructure.crypto.envelope import EnvelopeCryptoService, LocalKeyProvider
from ..infrastructure.crypto.passwords import Argon2PasswordHasher
from ..infrastructure.db.models import (
    Base,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)
from ..infrastructure.db.repositories import (
    AuditRepository,
    SecretRepository,
    VaultRepository,
)

COFRES = [
    ("contabil", "Contábil", "Credenciais dos sistemas contábeis e fiscais."),
    ("infraestrutura", "Infraestrutura", "Acessos de servidores, bancos e rede."),
    ("rh", "Recursos Humanos", "Sistemas de folha e benefícios."),
]

SEGREDOS = {
    "contabil": [
        ("dominio-escrita", SecretKind.PASSWORD, "Usuário de escrituração do Domínio"),
        ("certificado-ecnpj", SecretKind.CERTIFICATE, "Senha do e-CNPJ da matriz"),
        ("token-sefaz", SecretKind.TOKEN, "Token de consulta da SEFAZ"),
    ],
    "infraestrutura": [
        ("postgres-producao", SecretKind.PASSWORD, "Banco de produção"),
        ("chave-deploy", SecretKind.SSH_KEY, "Chave SSH do pipeline de deploy"),
        ("api-monitoramento", SecretKind.API_KEY, "Chave da API de monitoramento"),
    ],
    "rh": [
        ("portal-folha", SecretKind.PASSWORD, "Portal da folha de pagamento"),
    ],
}


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, future=True)()

    crypto = EnvelopeCryptoService(LocalKeyProvider(settings.master_key))
    vaults = VaultRepository(session)
    secrets_repo = SecretRepository(session)
    audit = AuditRepository(session)

    admin = session.scalar(select(UserModel).where(UserModel.full_name == "Administrador"))
    if admin is None:
        print("Crie o administrador antes: python -m app.tools.criar_admin <email> <senha>")
        raise SystemExit(1)

    criados = 0
    for nome, titulo, descricao in COFRES:
        from ..domain.shared.errors import ConflictError

        try:
            cofre = vaults.add(
                Vault(name=Slug(nome), display_name=titulo, description=descricao)
            )
        except ConflictError:
            # Idempotente: rodar de novo não duplica nem apaga nada.
            session.rollback()
            continue

        audit.append(
            AuditEvent(
                action=AuditAction.VAULT_CREATED,
                actor_id=admin.id,
                actor_label=admin.email,
                target_path=f"cofres/{nome}",
                outcome=AuditOutcome.SUCCESS,
                ip_address="127.0.0.1",
            )
        )

        for segredo_nome, tipo, desc in SEGREDOS.get(nome, []):
            segredo = Secret(
                name=Slug(segredo_nome), vault_id=cofre.id, kind=tipo, description=desc
            )
            # Valor fictício, forte, diferente a cada execução.
            segredo.add_version(
                crypto.encrypt(f"{segredo_nome}-{secrets.token_urlsafe(12)}"),
                created_by=admin.id,
            )
            secrets_repo.add(segredo)
            audit.append(
                AuditEvent(
                    action=AuditAction.SECRET_CREATED,
                    actor_id=admin.id,
                    actor_label=admin.email,
                    target_path=f"cofres/{nome}/segredos/{segredo_nome}",
                    outcome=AuditOutcome.SUCCESS,
                    ip_address="127.0.0.1",
                )
            )
            criados += 1

        session.commit()

    _criar_usuario_limitado(session)
    _conceder_auditoria_ao_admin(session, admin)
    session.commit()

    print(f"{criados} segredos criados em {len(COFRES)} cofres.")
    print("Usuário de carteira limitada: contador@exemplo.com.br / SenhaDoContador2026")
    print("  (enxerga apenas o cofre Contábil, sem permissão de revelar o token)")


def _criar_usuario_limitado(session: Session) -> None:
    """Usuário que só enxerga um cofre — torna o RBAC visível na interface."""
    if session.scalar(
        select(UserModel).where(UserModel.email == "contador@exemplo.com.br")
    ):
        return

    politica = PolicyModel(
        name="contabil-leitura",
        description="Leitura e revelação no cofre Contábil, exceto o token da SEFAZ.",
    )
    politica.rules = [
        PolicyRuleModel(
            path="cofres/contabil",
            capabilities=["read", "list"],
            effect="allow",
        ),
        PolicyRuleModel(
            path="cofres/contabil/*",
            capabilities=["read", "list", "reveal"],
            effect="allow",
        ),
        # Negação pontual: mostra na prática que deny derruba o allow acima.
        PolicyRuleModel(
            path="cofres/contabil/segredos/token-sefaz",
            capabilities=["reveal"],
            effect="deny",
        ),
    ]
    papel = RoleModel(name="contador", description="Equipe contábil.")
    papel.policies.append(politica)

    usuario = UserModel(
        email="contador@exemplo.com.br",
        full_name="Ana Contadora",
        password_hash=Argon2PasswordHasher().hash("SenhaDoContador2026"),
        is_active=True,
    )
    usuario.roles.append(papel)
    session.add_all([politica, papel, usuario])
    session.flush()


def _conceder_auditoria_ao_admin(session: Session, admin: UserModel) -> None:
    """Sem isto, o administrador não enxerga a trilha completa."""
    if session.scalar(select(PolicyModel).where(PolicyModel.name == "auditoria-total")):
        return

    politica = PolicyModel(
        name="auditoria-total", description="Leitura e verificação da trilha."
    )
    politica.rules = [
        PolicyRuleModel(path="auditoria", capabilities=["read", "list", "admin"],
                        effect="allow")
    ]
    session.add(politica)
    session.flush()

    papel = session.scalar(select(RoleModel).where(RoleModel.name == "administrador"))
    if papel is not None:
        papel.policies.append(politica)
    session.flush()


if __name__ == "__main__":
    main()
