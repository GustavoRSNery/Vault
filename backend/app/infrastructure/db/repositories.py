"""Repositórios: traduzem entre models (banco) e entidades (domínio).

A tradução é explícita de propósito. O domínio não deve conhecer SQLAlchemy,
e o banco não deve ditar a forma das entidades — quando um dos dois mudar, a
costura fica num lugar só.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, Effect, Policy, PolicyRule
from ...domain.audit.events import (
    GENESIS_HASH,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    ChainAnchor,
)
from ...domain.shared.errors import ConflictError, NotFoundError
from ...domain.shared.value_objects import PolicyPath, Slug
from ...domain.vaults.entities import (
    EncryptedValue,
    Secret,
    SecretKind,
    SecretVersion,
    Vault,
    VaultState,
)
from .models import (
    AuditAnchorModel,
    AuditEventModel,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    SecretModel,
    SecretVersionModel,
    UserModel,
    VaultModel,
)


class VaultRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, vault: Vault) -> Vault:
        if self._session.scalar(select(VaultModel).where(VaultModel.name == str(vault.name))):
            raise ConflictError(f"Já existe um cofre com o identificador {vault.name}.")
        self._session.add(
            VaultModel(
                id=vault.id,
                name=str(vault.name),
                display_name=vault.display_name,
                description=vault.description,
                state=str(vault.state),
                created_at=vault.created_at,
            )
        )
        self._session.flush()
        return vault

    def get_by_name(self, name: Slug) -> Vault:
        model = self._session.scalar(select(VaultModel).where(VaultModel.name == str(name)))
        if model is None:
            raise NotFoundError(f"Cofre {name} não encontrado.")
        return _to_vault(model)

    def get_by_id(self, vault_id: str) -> Vault:
        model = self._session.get(VaultModel, vault_id)
        if model is None:
            raise NotFoundError("Cofre não encontrado.")
        return _to_vault(model)

    def list_all(self) -> list[Vault]:
        models = self._session.scalars(select(VaultModel).order_by(VaultModel.name)).all()
        return [_to_vault(m) for m in models]

    def save_state(self, vault: Vault) -> None:
        model = self._session.get(VaultModel, vault.id)
        if model is None:
            raise NotFoundError("Cofre não encontrado.")
        model.state = str(vault.state)
        self._session.flush()


class SecretRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, secret: Secret) -> Secret:
        clash = self._session.scalar(
            select(SecretModel).where(
                SecretModel.vault_id == secret.vault_id,
                SecretModel.name == str(secret.name),
            )
        )
        if clash is not None:
            raise ConflictError(f"Já existe um segredo chamado {secret.name} neste cofre.")

        self._session.add(
            SecretModel(
                id=secret.id,
                vault_id=secret.vault_id,
                name=str(secret.name),
                kind=str(secret.kind),
                description=secret.description,
                deleted_at=secret.deleted_at,
            )
        )
        for version in secret.versions:
            self._session.add(_version_model(secret.id, version))
        self._session.flush()
        return secret

    def get(self, secret_id: str) -> Secret:
        model = self._session.get(SecretModel, secret_id)
        if model is None:
            raise NotFoundError("Segredo não encontrado.")
        return _to_secret(model)

    def get_in_vault(self, vault_id: str, name: Slug) -> Secret:
        model = self._session.scalar(
            select(SecretModel).where(
                SecretModel.vault_id == vault_id,
                SecretModel.name == str(name),
            )
        )
        if model is None:
            raise NotFoundError(f"Segredo {name} não encontrado neste cofre.")
        return _to_secret(model)

    def list_in_vault(self, vault_id: str, *, include_deleted: bool = False) -> list[Secret]:
        stmt = select(SecretModel).where(SecretModel.vault_id == vault_id)
        if not include_deleted:
            stmt = stmt.where(SecretModel.deleted_at.is_(None))
        models = self._session.scalars(stmt.order_by(SecretModel.name)).all()
        return [_to_secret(m) for m in models]

    def add_version(self, secret_id: str, version: SecretVersion) -> None:
        self._session.add(_version_model(secret_id, version))
        self._session.flush()

    def save_trash_state(self, secret: Secret) -> None:
        model = self._session.get(SecretModel, secret.id)
        if model is None:
            raise NotFoundError("Segredo não encontrado.")
        model.deleted_at = secret.deleted_at
        self._session.flush()


class PolicyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, policy: Policy) -> Policy:
        model = PolicyModel(
            id=policy.id,
            name=str(policy.name),
            description=policy.description,
        )
        model.rules = [
            PolicyRuleModel(
                policy_id=policy.id,
                path=str(rule.path),
                capabilities=sorted(str(c) for c in rule.capabilities),
                effect=str(rule.effect),
            )
            for rule in policy.rules
        ]
        self._session.add(model)
        self._session.flush()
        return policy

    def policies_for_user(self, user_id: str) -> list[Policy]:
        """Todas as políticas que alcançam o usuário, via seus papéis."""
        user = self._session.get(UserModel, user_id)
        if user is None:
            raise NotFoundError("Usuário não encontrado.")
        seen: dict[str, Policy] = {}
        for role in user.roles:
            for policy_model in role.policies:
                if policy_model.id not in seen:
                    seen[policy_model.id] = _to_policy(policy_model)
        return list(seen.values())

    def list_all(self) -> list[Policy]:
        """Todas as politicas cadastradas, para a tela de administracao."""
        models = self._session.scalars(
            select(PolicyModel).order_by(PolicyModel.name)
        ).all()
        return [_to_policy(m) for m in models]

    def get_by_name(self, name: Slug) -> Policy:
        model = self._session.scalar(
            select(PolicyModel).where(PolicyModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Politica '{name}' nao encontrada.")
        return _to_policy(model)

    def roles_of_policy(self, policy_id: str) -> list[str]:
        """Nomes dos papeis que carregam esta politica."""
        model = self._session.get(PolicyModel, policy_id)
        if model is None:
            raise NotFoundError("Politica nao encontrada.")
        return sorted(role.name for role in model.roles)

    def replace_rules(self, policy_id: str, rules: list[PolicyRule]) -> Policy:
        """Troca as regras da politica inteira.

        E substituicao, nao merge: o editor da tela envia o conjunto completo,
        e aplicar diferenca parcial deixaria regra orfa concedendo acesso que
        ninguem mais ve na interface.
        """
        if not rules:
            raise ConflictError("A politica precisa de ao menos uma regra.")
        model = self._session.get(PolicyModel, policy_id)
        if model is None:
            raise NotFoundError("Politica nao encontrada.")
        model.rules = [
            PolicyRuleModel(
                policy_id=policy_id,
                path=str(rule.path),
                capabilities=sorted(str(c) for c in rule.capabilities),
                effect=str(rule.effect),
            )
            for rule in rules
        ]
        self._session.flush()
        return _to_policy(model)


class UserRepository:
    """Leitura e administracao de contas.

    Nao expoe password_hash nem o segredo de MFA: quem precisa autenticar usa
    o caso de uso de login, que le o model diretamente. Aqui so trafega o que
    a tela de administracao mostra.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[UserModel]:
        return list(
            self._session.scalars(select(UserModel).order_by(UserModel.full_name)).all()
        )

    def get(self, user_id: str) -> UserModel:
        user = self._session.get(UserModel, user_id)
        if user is None:
            raise NotFoundError("Usuario nao encontrado.")
        return user

    def get_by_email(self, email: str) -> UserModel | None:
        return self._session.scalar(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )

    def set_active(self, user_id: str, active: bool) -> UserModel:
        user = self.get(user_id)
        user.is_active = active
        self._session.flush()
        return user

    def reset_mfa(self, user_id: str) -> UserModel:
        """Desliga o MFA e descarta o segredo cifrado.

        Usado quando alguem perde o dispositivo. Zerar o material e nao apenas
        o booleano evita que reativar reaproveite um segredo que pode ter
        vazado junto com o aparelho.
        """
        user = self.get(user_id)
        user.mfa_enabled = False
        user.mfa_secret_ciphertext = None
        user.mfa_secret_nonce = None
        user.mfa_secret_wrapped_dek = None
        user.mfa_key_id = None
        self._session.flush()
        return user

    def list_roles(self) -> list[RoleModel]:
        return list(
            self._session.scalars(select(RoleModel).order_by(RoleModel.name)).all()
        )

    def set_roles(self, user_id: str, role_names: list[str]) -> UserModel:
        """Substitui os papeis do usuario pelo conjunto informado."""
        user = self.get(user_id)
        if role_names:
            papeis = list(
                self._session.scalars(
                    select(RoleModel).where(RoleModel.name.in_(role_names))
                ).all()
            )
            encontrados = {r.name for r in papeis}
            faltando = sorted(set(role_names) - encontrados)
            if faltando:
                raise NotFoundError(f"Papel inexistente: {', '.join(faltando)}.")
            user.roles = papeis
        else:
            user.roles = []
        self._session.flush()
        return user


class AuditRepository:
    """Append-only por contrato: não existe update nem delete aqui."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def append(self, event: AuditEvent) -> AuditEvent:
        """Encadeia o evento ao fim da trilha, dentro da transação corrente.

        A sequência vem de um MAX() lido agora. Sob concorrência real, dois
        processos poderiam ler o mesmo MAX; a UniqueConstraint em `sequence`
        transforma isso em erro de integridade em vez de cadeia corrompida —
        quem chamar deve tratar o conflito e repetir.
        """
        last = self._session.scalar(
            select(AuditEventModel).order_by(AuditEventModel.sequence.desc()).limit(1)
        )
        if last is None:
            sequence, previous_hash = 0, GENESIS_HASH
        else:
            sequence = last.sequence + 1
            previous_hash = _to_audit_event(last).fingerprint()

        linked = AuditEvent(
            action=event.action,
            actor_id=event.actor_id,
            actor_label=event.actor_label,
            target_path=event.target_path,
            outcome=event.outcome,
            reason=event.reason,
            ip_address=event.ip_address,
            user_agent=event.user_agent,
            metadata=event.metadata,
            occurred_at=event.occurred_at,
            sequence=sequence,
            previous_hash=previous_hash,
            id=event.id,
        )
        self._session.add(
            AuditEventModel(
                id=linked.id,
                sequence=linked.sequence,
                previous_hash=linked.previous_hash,
                action=str(linked.action),
                actor_id=linked.actor_id,
                actor_label=linked.actor_label,
                target_path=linked.target_path,
                outcome=str(linked.outcome),
                reason=linked.reason,
                ip_address=linked.ip_address,
                user_agent=linked.user_agent,
                event_metadata=linked.metadata,
                occurred_at=linked.occurred_at,
            )
        )
        self._session.flush()
        return linked

    def list_chain(self, *, limit: int | None = None) -> list[AuditEvent]:
        stmt = select(AuditEventModel).order_by(AuditEventModel.sequence)
        if limit is not None:
            stmt = stmt.limit(limit)
        return [_to_audit_event(m) for m in self._session.scalars(stmt).all()]

    def count(self) -> int:
        return self._session.scalar(select(func.count()).select_from(AuditEventModel)) or 0

    def anchors(self) -> list[ChainAnchor]:
        models = self._session.scalars(
            select(AuditAnchorModel).order_by(AuditAnchorModel.sequence)
        ).all()
        return [ChainAnchor(sequence=m.sequence, fingerprint=m.fingerprint) for m in models]

    def add_anchor(self, anchor: ChainAnchor, exported_to: str) -> None:
        self._session.add(
            AuditAnchorModel(
                sequence=anchor.sequence,
                fingerprint=anchor.fingerprint,
                exported_to=exported_to,
            )
        )
        self._session.flush()


# --- tradutores model -> entidade ------------------------------------------


def _to_vault(model: VaultModel) -> Vault:
    return Vault(
        name=Slug(model.name),
        display_name=model.display_name,
        description=model.description,
        state=VaultState(model.state),
        created_at=model.created_at,
        id=model.id,
    )


def _to_secret(model: SecretModel) -> Secret:
    return Secret(
        name=Slug(model.name),
        vault_id=model.vault_id,
        kind=SecretKind(model.kind),
        description=model.description,
        versions=[
            SecretVersion(
                version=v.version,
                value=EncryptedValue(
                    ciphertext=v.ciphertext,
                    nonce=v.nonce,
                    wrapped_dek=v.wrapped_dek,
                    key_id=v.key_id,
                ),
                created_by=v.created_by,
                created_at=v.created_at,
                id=v.id,
            )
            for v in sorted(model.versions, key=lambda v: v.version)
        ],
        deleted_at=model.deleted_at,
        id=model.id,
    )


def _version_model(secret_id: str, version: SecretVersion) -> SecretVersionModel:
    return SecretVersionModel(
        id=version.id,
        secret_id=secret_id,
        version=version.version,
        ciphertext=version.value.ciphertext,
        nonce=version.value.nonce,
        wrapped_dek=version.value.wrapped_dek,
        key_id=version.value.key_id,
        created_by=version.created_by,
        created_at=version.created_at,
    )


def _to_policy(model: PolicyModel) -> Policy:
    return Policy(
        name=Slug(model.name),
        rules=[
            PolicyRule(
                path=PolicyPath(r.path),
                capabilities=frozenset(Capability(c) for c in r.capabilities),
                effect=Effect(r.effect),
            )
            for r in model.rules
        ],
        description=model.description,
        id=model.id,
    )


def _to_audit_event(model: AuditEventModel) -> AuditEvent:
    return AuditEvent(
        action=AuditAction(model.action),
        actor_id=model.actor_id,
        actor_label=model.actor_label,
        target_path=model.target_path,
        outcome=AuditOutcome(model.outcome),
        reason=model.reason,
        ip_address=model.ip_address,
        user_agent=model.user_agent,
        metadata=model.event_metadata or {},
        occurred_at=model.occurred_at,
        sequence=model.sequence,
        previous_hash=model.previous_hash,
        id=model.id,
    )
