"""Cria o primeiro usuário administrador e as políticas base.

Uso:  python -m app.tools.criar_admin <email> <senha>

Idempotente: rodar duas vezes não duplica nada.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..config import get_settings
from ..infrastructure.crypto.passwords import Argon2PasswordHasher
from ..infrastructure.db.models import (
    Base,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]


def main() -> None:
    if len(sys.argv) != 3:
        print("uso: python -m app.tools.criar_admin <email> <senha>")
        raise SystemExit(1)

    email, senha = sys.argv[1].strip().lower(), sys.argv[2]
    if len(senha) < 12:
        print("A senha do administrador deve ter ao menos 12 caracteres.")
        raise SystemExit(1)

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, future=True)()

    if session.scalar(select(UserModel).where(UserModel.email == email)):
        print(f"O usuário {email} já existe. Nada a fazer.")
        return

    politica = session.scalar(select(PolicyModel).where(PolicyModel.name == "administracao"))
    if politica is None:
        politica = PolicyModel(
            name="administracao",
            description="Acesso total a cofres e segredos.",
        )
        politica.rules = [
            PolicyRuleModel(path="cofres", capabilities=TODAS, effect="allow"),
            PolicyRuleModel(path="cofres/*", capabilities=TODAS, effect="allow"),
        ]
        session.add(politica)
        session.flush()

    papel = session.scalar(select(RoleModel).where(RoleModel.name == "administrador"))
    if papel is None:
        papel = RoleModel(name="administrador", description="Administrador do Vault.")
        papel.policies.append(politica)
        session.add(papel)
        session.flush()

    usuario = UserModel(
        email=email,
        full_name="Administrador",
        password_hash=Argon2PasswordHasher().hash(senha),
        is_active=True,
    )
    usuario.roles.append(papel)
    session.add(usuario)
    session.commit()

    print(f"Administrador criado: {email}")
    print("Ative o MFA no primeiro acesso.")


if __name__ == "__main__":
    main()
