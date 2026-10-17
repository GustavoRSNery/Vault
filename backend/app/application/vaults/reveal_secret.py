"""Caso de uso: revelar o valor de um segredo.

É a operação mais sensível do sistema inteiro, e por isso concentra as quatro
verificações que o resto do código assume terem acontecido:

1. O cofre não pode estar selado.
2. A política precisa conceder REVEAL — que é mais forte que READ: ver que um
   segredo existe não é o mesmo que ver seu valor.
3. Toda revelação vira evento de auditoria, inclusive as negadas. Negativa sem
   registro é justamente o que um atacante tentando permissões quer.
4. O valor em claro só existe no retorno; nada dele vai para log ou auditoria.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.access.policy import Capability
from ...domain.audit.events import AuditAction, AuditEvent, AuditOutcome
from ...domain.shared.errors import PermissionDeniedError
from ...domain.shared.value_objects import Slug
from ..ports.crypto import CryptoService


@dataclass(frozen=True, slots=True)
class RevealSecretCommand:
    actor_id: str
    actor_label: str
    vault_name: str
    secret_name: str
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass(frozen=True, slots=True)
class RevealedSecret:
    """O valor em claro, mais o mínimo para a tela mostrar contexto.

    Deliberadamente sem __repr__ customizado: um dataclass comum imprimiria o
    valor num traceback. Por isso `__repr__` é sobrescrito abaixo.
    """

    secret_id: str
    secret_name: str
    version: int
    value: str

    def __repr__(self) -> str:
        """Mascara o valor em qualquer repr — traceback, log, debugger.

        Sem isto, um erro não tratado num endpoint imprimiria a senha no log
        de produção. Já aconteceu em sistemas sérios; aqui é barato evitar.
        """
        return (
            f"RevealedSecret(secret_id={self.secret_id!r}, "
            f"secret_name={self.secret_name!r}, version={self.version!r}, "
            "value='***')"
        )


class RevealSecret:
    def __init__(
        self,
        vaults,          # VaultRepository
        secrets,         # SecretRepository
        policies,        # PolicyRepository
        audit,           # AuditRepository
        crypto: CryptoService,
    ) -> None:
        self._vaults = vaults
        self._secrets = secrets
        self._policies = policies
        self._audit = audit
        self._crypto = crypto

    def execute(self, command: RevealSecretCommand) -> RevealedSecret:
        vault = self._vaults.get_by_name(Slug(command.vault_name))
        secret_name = Slug(command.secret_name)
        path = vault.secret_path(secret_name)

        user_policies = self._policies.policies_for_user(command.actor_id)

        from ...domain.access.policy import evaluate

        if not evaluate(user_policies, path, Capability.REVEAL):
            self._record(command, path, AuditAction.ACCESS_DENIED, AuditOutcome.FAILURE,
                         "A política não concede revelação neste caminho.")
            raise PermissionDeniedError("Você não tem permissão para revelar este segredo.")

        # O selo é checado DEPOIS da política, de propósito: quem não tem
        # acesso não deve descobrir, pela mensagem de erro, se o cofre existe
        # e em que estado está.
        vault.ensure_usable()

        secret = self._secrets.get_in_vault(vault.id, secret_name)
        if secret.is_deleted:
            self._record(command, path, AuditAction.ACCESS_DENIED, AuditOutcome.FAILURE,
                         "O segredo está na lixeira.")
            raise PermissionDeniedError("Este segredo está na lixeira.")

        version = secret.current_version
        plaintext = self._crypto.decrypt(version.value)

        self._record(command, path, AuditAction.SECRET_REVEALED, AuditOutcome.SUCCESS, "")

        return RevealedSecret(
            secret_id=secret.id,
            secret_name=str(secret.name),
            version=version.version,
            value=plaintext,
        )

    def _record(
        self,
        command: RevealSecretCommand,
        path,
        action: AuditAction,
        outcome: AuditOutcome,
        reason: str,
    ) -> None:
        """Registra o evento. `metadata` fica vazio: nada de valor aqui."""
        self._audit.append(
            AuditEvent(
                action=action,
                actor_id=command.actor_id,
                actor_label=command.actor_label,
                target_path=str(path),
                outcome=outcome,
                reason=reason,
                ip_address=command.ip_address,
                user_agent=command.user_agent,
            )
        )
