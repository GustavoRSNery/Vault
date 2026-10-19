"""Garante que a política `administracao` cubra o caminho `admin`.

Uso:  python -m app.tools.conceder_admin

Existe porque `criar_admin` é idempotente e sai cedo quando o usuário já
existe: num banco criado antes das telas de administração, a política ficou
sem as regras de `admin` e o menu não apareceria. Idempotente — rodar duas
vezes não duplica regra.
"""

from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from ..config import get_settings
from ..infrastructure.db.models import PolicyModel, PolicyRuleModel

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]
CAMINHOS = ["admin", "admin/*", "aplicacoes", "aplicacoes/*", "sessoes"]


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    session = sessionmaker(bind=engine, future=True)()

    politica = session.scalar(
        select(PolicyModel).where(PolicyModel.name == "administracao")
    )
    if politica is None:
        print("Política 'administracao' não existe. Rode criar_admin primeiro.")
        return

    existentes = {r.path for r in politica.rules}
    novas = [c for c in CAMINHOS if c not in existentes]
    if not novas:
        print("A política já cobre 'admin'. Nada a fazer.")
        return

    for caminho in novas:
        politica.rules.append(
            PolicyRuleModel(
                policy_id=politica.id,
                path=caminho,
                capabilities=TODAS,
                effect="allow",
            )
        )
    session.commit()
    print(f"Regras adicionadas à política 'administracao': {', '.join(novas)}")


if __name__ == "__main__":
    main()
