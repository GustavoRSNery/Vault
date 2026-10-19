"""Políticas de acesso e sua avaliação.

Regra central, igual à das referências (Vault/Segura): **negação vence**.
Uma regra DENY que case com o caminho derruba qualquer ALLOW, não importa
quão específica seja a regra que permitiu. Isso torna a revogação confiável:
basta uma política de negação para fechar um acesso, sem auditar todas as
concessões existentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ..shared.errors import ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id


class Capability(StrEnum):
    """O que se pode fazer sobre um caminho."""

    READ = "read"          # ver metadados do recurso
    REVEAL = "reveal"      # revelar o valor de um segredo (mais forte que READ)
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    APPROVE = "approve"    # aprovar solicitações de acesso
    ADMIN = "admin"        # administrar o recurso (permissões, selagem)


class Effect(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class PolicyRule:
    path: PolicyPath
    capabilities: frozenset[Capability]
    effect: Effect = Effect.ALLOW

    def __post_init__(self) -> None:
        if not self.capabilities:
            raise ValidationError("A regra precisa de ao menos uma capacidade.")

    def covers(self, path: PolicyPath, capability: Capability) -> bool:
        return capability in self.capabilities and self.path.matches(path)


@dataclass(slots=True)
class Policy:
    """Conjunto nomeado de regras, atribuível a papéis."""

    name: Slug
    rules: list[PolicyRule] = field(default_factory=list)
    description: str = ""
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.rules:
            raise ValidationError("A política precisa de ao menos uma regra.")


@dataclass(slots=True)
class Role:
    """Papel: agrupa políticas. Usuários e grupos recebem papéis, nunca regras soltas."""

    name: Slug
    policies: list[Policy] = field(default_factory=list)
    description: str = ""
    id: str = field(default_factory=new_id)


def evaluate(
    policies: list[Policy],
    path: PolicyPath,
    capability: Capability,
) -> bool:
    """Decide se as políticas permitem `capability` sobre `path`.

    Negação vence, e a ausência de regra é negação (default deny).
    """
    allowed = False
    for policy in policies:
        for rule in policy.rules:
            if not rule.covers(path, capability):
                continue
            if rule.effect is Effect.DENY:
                return False
            allowed = True
    return allowed


def explain(
    policies: list[Policy],
    path: PolicyPath,
    capability: Capability,
    *,
    nomear_politica: bool = True,
) -> tuple[bool, str]:
    """Como `evaluate`, mas devolve também o motivo — para a tela de permissões.

    O motivo é texto de interface: nomeia a política responsável pela decisão.

    `nomear_politica=False` serve à simulação de um rascunho ainda não salvo:
    ali a política não existe para quem edita, e citar um nome interno faria a
    tela parecer referir-se a algo que o usuário não reconhece. A decisão é a
    mesma; muda só como ela é dita.
    """

    def origem(policy: Policy, rule: PolicyRule) -> str:
        if nomear_politica:
            return f"pela política {policy.name} em {rule.path}"
        return f"pela regra em {rule.path}"

    matched_allow: str | None = None
    for policy in policies:
        for rule in policy.rules:
            if not rule.covers(path, capability):
                continue
            if rule.effect is Effect.DENY:
                return False, f"Negado {origem(policy, rule)}."
            if matched_allow is None:
                matched_allow = f"Permitido {origem(policy, rule)}."
    if matched_allow is not None:
        return True, matched_allow
    return False, "Nenhuma política concede esta capacidade neste caminho."
