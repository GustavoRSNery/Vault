"""Repositórios: traduzem entre models (banco) e entidades (domínio).

A tradução é explícita de propósito. O domínio não deve conhecer SQLAlchemy,
e o banco não deve ditar a forma das entidades — quando um dos dois mudar, a
costura fica num lugar só.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...domain.access.policy import Capability, Effect, Policy, PolicyRule
from ...domain.audit.events import (
    GENESIS_HASH,
    AuditAction,
    AuditEvent,
    AuditOutcome,
    ChainAnchor,
)
from ...domain.approvals.entities import AccessRequest, RequestStatus
from ...domain.inventory.entities import (
    Certificate,
    Checkout,
    Credential,
    CredentialStatus,
    Device,
    DeviceKind,
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
    AccessRequestModel,
    AuditAnchorModel,
    AuditEventModel,
    CertificateModel,
    CheckoutModel,
    CredentialModel,
    DeviceModel,
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


class DeviceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, device: Device) -> Device:
        existente = self._session.scalar(
            select(DeviceModel).where(DeviceModel.name == str(device.name))
        )
        if existente is not None:
            raise ConflictError(f"Ja existe um dispositivo chamado {device.name}.")
        self._session.add(
            DeviceModel(
                id=device.id,
                name=str(device.name),
                display_name=device.display_name,
                kind=str(device.kind),
                address=device.address,
                tags=device.tags,
                description=device.description,
                is_active=device.is_active,
                created_at=device.created_at,
            )
        )
        self._session.flush()
        return device

    def get_by_name(self, name: Slug) -> Device:
        model = self._session.scalar(
            select(DeviceModel).where(DeviceModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Dispositivo {name} nao encontrado.")
        return _to_device(model)

    def list_all(self, *, include_inactive: bool = True) -> list[Device]:
        consulta = select(DeviceModel).order_by(DeviceModel.display_name)
        if not include_inactive:
            consulta = consulta.where(DeviceModel.is_active.is_(True))
        return [_to_device(m) for m in self._session.scalars(consulta).all()]

    def set_active(self, device_id: str, active: bool) -> Device:
        model = self._session.get(DeviceModel, device_id)
        if model is None:
            raise NotFoundError("Dispositivo nao encontrado.")
        model.is_active = active
        self._session.flush()
        return _to_device(model)


class CredentialRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, credential: Credential) -> Credential:
        self._session.add(
            CredentialModel(
                id=credential.id,
                name=str(credential.name),
                device_id=credential.device_id,
                secret_id=credential.secret_id,
                username=credential.username,
                description=credential.description,
                rotation_days=credential.rotation_days,
                last_rotated_at=credential.last_rotated_at,
                status=str(credential.status),
                created_at=credential.created_at,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as erro:
            self._session.rollback()
            raise ConflictError(
                f"O dispositivo ja tem uma credencial chamada {credential.name}."
            ) from erro
        return credential

    def get(self, credential_id: str) -> Credential:
        model = self._session.get(CredentialModel, credential_id)
        if model is None:
            raise NotFoundError("Credencial nao encontrada.")
        return _to_credential(model)

    def list_all(self) -> list[Credential]:
        models = self._session.scalars(
            select(CredentialModel).order_by(CredentialModel.name)
        ).all()
        return [_to_credential(m) for m in models]

    def list_for_device(self, device_id: str) -> list[Credential]:
        models = self._session.scalars(
            select(CredentialModel)
            .where(CredentialModel.device_id == device_id)
            .order_by(CredentialModel.name)
        ).all()
        return [_to_credential(m) for m in models]

    def save(self, credential: Credential) -> Credential:
        """Grava o estado da credencial e as retiradas que ainda nao existem.

        Retirada e fato consumado: nunca se reescreve uma existente, so se
        acrescenta a nova e se fecha a aberta com a data de devolucao.
        """
        model = self._session.get(CredentialModel, credential.id)
        if model is None:
            raise NotFoundError("Credencial nao encontrada.")

        model.username = credential.username
        model.description = credential.description
        model.rotation_days = credential.rotation_days
        model.last_rotated_at = credential.last_rotated_at
        model.status = str(credential.status)
        model.secret_id = credential.secret_id

        existentes = {c.id: c for c in model.checkouts}
        for checkout in credential.checkouts:
            atual = existentes.get(checkout.id)
            if atual is None:
                model.checkouts.append(
                    CheckoutModel(
                        id=checkout.id,
                        credential_id=credential.id,
                        user_id=checkout.user_id,
                        user_label=checkout.user_label,
                        reason=checkout.reason,
                        due_at=checkout.due_at,
                        taken_at=checkout.taken_at,
                        returned_at=checkout.returned_at,
                    )
                )
            elif atual.returned_at is None and checkout.returned_at is not None:
                atual.returned_at = checkout.returned_at

        try:
            self._session.flush()
        except IntegrityError as erro:
            self._session.rollback()
            # O indice parcial pegou uma segunda retirada aberta: duas
            # requisicoes concorrentes tentaram retirar a mesma credencial.
            raise ConflictError(
                "A credencial acabou de ser retirada por outra pessoa."
            ) from erro
        return _to_credential(model)


class CertificateRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, certificate: Certificate) -> Certificate:
        existente = self._session.scalar(
            select(CertificateModel).where(
                CertificateModel.name == str(certificate.name)
            )
        )
        if existente is not None:
            raise ConflictError(
                f"Ja existe um certificado chamado {certificate.name}."
            )
        self._session.add(
            CertificateModel(
                id=certificate.id,
                name=str(certificate.name),
                display_name=certificate.display_name,
                subject=certificate.subject,
                issuer=certificate.issuer,
                serial=certificate.serial,
                owner_label=certificate.owner_label,
                not_before=certificate.not_before,
                not_after=certificate.not_after,
                secret_id=certificate.secret_id,
                description=certificate.description,
                created_at=certificate.created_at,
            )
        )
        self._session.flush()
        return certificate

    def get_by_name(self, name: Slug) -> Certificate:
        model = self._session.scalar(
            select(CertificateModel).where(CertificateModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Certificado {name} nao encontrado.")
        return _to_certificate(model)

    def list_all(self) -> list[Certificate]:
        """Ordena por vencimento: o que vence primeiro aparece primeiro."""
        models = self._session.scalars(
            select(CertificateModel).order_by(CertificateModel.not_after)
        ).all()
        return [_to_certificate(m) for m in models]

    def delete(self, certificate_id: str) -> None:
        model = self._session.get(CertificateModel, certificate_id)
        if model is None:
            raise NotFoundError("Certificado nao encontrado.")
        self._session.delete(model)
        self._session.flush()


def _aware(momento: datetime | None) -> datetime | None:
    """Garante timezone na saida do banco.

    O SQLite devolve datetime ingenuo mesmo em coluna DateTime(timezone=True),
    e o Postgres devolve com offset. O dominio recusa datetime ingenuo, entao a
    conversao mora aqui, na fronteira — e nao em cada entidade. Sem isto, a
    mesma leitura funciona num dialeto e levanta TypeError no outro, que e a
    classe de bug que ja apareceu no hash da auditoria.
    """
    if momento is None:
        return None
    return momento if momento.tzinfo is not None else momento.replace(tzinfo=UTC)


def _to_device(model: DeviceModel) -> Device:
    return Device(
        name=Slug(model.name),
        display_name=model.display_name,
        kind=DeviceKind(model.kind),
        address=model.address,
        tags=list(model.tags or []),
        description=model.description,
        is_active=model.is_active,
        created_at=_aware(model.created_at),
        id=model.id,
    )


def _to_credential(model: CredentialModel) -> Credential:
    return Credential(
        name=Slug(model.name),
        device_id=model.device_id,
        secret_id=model.secret_id,
        username=model.username,
        description=model.description,
        rotation_days=model.rotation_days,
        last_rotated_at=_aware(model.last_rotated_at),
        status=CredentialStatus(model.status),
        checkouts=[
            Checkout(
                credential_id=c.credential_id,
                user_id=c.user_id,
                user_label=c.user_label,
                reason=c.reason,
                due_at=_aware(c.due_at),
                taken_at=_aware(c.taken_at),
                returned_at=_aware(c.returned_at),
                id=c.id,
            )
            for c in sorted(model.checkouts, key=lambda c: _aware(c.taken_at))
        ],
        created_at=_aware(model.created_at),
        id=model.id,
    )


def _to_certificate(model: CertificateModel) -> Certificate:
    return Certificate(
        name=Slug(model.name),
        display_name=model.display_name,
        subject=model.subject,
        issuer=model.issuer,
        not_before=_aware(model.not_before),
        not_after=_aware(model.not_after),
        owner_label=model.owner_label,
        serial=model.serial,
        secret_id=model.secret_id,
        description=model.description,
        created_at=_aware(model.created_at),
        id=model.id,
    )


class AccessRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, pedido: AccessRequest) -> AccessRequest:
        self._session.add(
            AccessRequestModel(
                id=pedido.id,
                requester_id=pedido.requester_id,
                requester_label=pedido.requester_label,
                path=str(pedido.path),
                capabilities=sorted(str(c) for c in pedido.capabilities),
                reason=pedido.reason,
                hours=pedido.hours,
                status=str(pedido.status),
                decided_by_id=pedido.decided_by_id,
                decided_by_label=pedido.decided_by_label,
                decision_note=pedido.decision_note,
                decided_at=pedido.decided_at,
                granted_until=pedido.granted_until,
                created_at=pedido.created_at,
            )
        )
        self._session.flush()
        return pedido

    def get(self, request_id: str) -> AccessRequest:
        model = self._session.get(AccessRequestModel, request_id)
        if model is None:
            raise NotFoundError("Solicitacao nao encontrada.")
        return _to_access_request(model)

    def list_all(self) -> list[AccessRequest]:
        models = self._session.scalars(
            select(AccessRequestModel).order_by(AccessRequestModel.created_at.desc())
        ).all()
        return [_to_access_request(m) for m in models]

    def list_for_requester(self, user_id: str) -> list[AccessRequest]:
        models = self._session.scalars(
            select(AccessRequestModel)
            .where(AccessRequestModel.requester_id == user_id)
            .order_by(AccessRequestModel.created_at.desc())
        ).all()
        return [_to_access_request(m) for m in models]

    def list_pending(self) -> list[AccessRequest]:
        """Fila do aprovador: mais antigas primeiro, que e a ordem de atender."""
        models = self._session.scalars(
            select(AccessRequestModel)
            .where(AccessRequestModel.status == "pendente")
            .order_by(AccessRequestModel.created_at)
        ).all()
        return [_to_access_request(m) for m in models]

    def active_grants_for(self, user_id: str) -> list[AccessRequest]:
        """Concessoes que podem estar valendo agora para este usuario.

        Filtra por status no banco; o prazo e conferido no dominio, para que a
        regra de "ainda vale" exista num lugar so.
        """
        models = self._session.scalars(
            select(AccessRequestModel).where(
                AccessRequestModel.requester_id == user_id,
                AccessRequestModel.status == "aprovada",
            )
        ).all()
        return [_to_access_request(m) for m in models]

    def save(self, pedido: AccessRequest) -> AccessRequest:
        model = self._session.get(AccessRequestModel, pedido.id)
        if model is None:
            raise NotFoundError("Solicitacao nao encontrada.")
        model.status = str(pedido.status)
        model.decided_by_id = pedido.decided_by_id
        model.decided_by_label = pedido.decided_by_label
        model.decision_note = pedido.decision_note
        model.decided_at = pedido.decided_at
        model.granted_until = pedido.granted_until
        self._session.flush()
        return _to_access_request(model)


def _to_access_request(model: AccessRequestModel) -> AccessRequest:
    return AccessRequest(
        requester_id=model.requester_id,
        requester_label=model.requester_label,
        path=PolicyPath(model.path),
        capabilities=frozenset(Capability(c) for c in model.capabilities),
        reason=model.reason,
        hours=model.hours,
        status=RequestStatus(model.status),
        decided_by_id=model.decided_by_id,
        decided_by_label=model.decided_by_label,
        decision_note=model.decision_note,
        decided_at=_aware(model.decided_at),
        granted_until=_aware(model.granted_until),
        created_at=_aware(model.created_at),
        id=model.id,
    )
