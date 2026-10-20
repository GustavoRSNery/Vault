"""Repositórios: traduzem entre models (banco) e entidades (domínio).

A tradução é explícita de propósito. O domínio não deve conhecer SQLAlchemy,
e o banco não deve ditar a forma das entidades — quando um dos dois mudar, a
costura fica num lugar só.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

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
from ...domain.apikeys.entities import (
    AmbienteDaChave,
    ChaveDeApi,
    EstadoDaChave,
    FormatoDaChave,
)
from ...domain.approvals.entities import AccessRequest, RequestStatus
from ...domain.machines.entities import (
    Application,
    ApplicationStatus,
    Lease,
    SecretId,
)
from ...domain.inventory.entities import (
    AcessoRemoto,
    Certificate,
    Checkout,
    Credential,
    CredentialStatus,
    Device,
    DeviceKind,
    MetodoDeAcesso,
)
from ...domain.onboarding.entities import (
    Convite,
    EstadoDoConvite,
    PedidoDeRedefinicao,
    TipoDeConvite,
)
from ...domain.integrations.entities import (
    Destino,
    Entrega,
    EstadoDaEntrega,
    EstadoDoDestino,
)
from ...domain.sessions.entities import (
    ConsumoDaSessao,
    EstadoDaSessao,
    EventoDeSessao,
    OrigemDaSessao,
    Sessao,
    TipoDeConsumo,
    TipoDeEvento,
    TipoDeSessao,
)
from ...domain.settings.entities import ConfiguracaoOperacional
from ...domain.shared.errors import ConflictError, NotFoundError
from ...domain.vaults.quorum import SeloComQuorum
from ...domain.shared.value_objects import Email, PolicyPath, Slug, utcnow
from ...domain.vaults.entities import (
    EncryptedValue,
    Secret,
    SecretKind,
    SecretVersion,
    Vault,
    VaultState,
)
from .models import (
    DestinoWebhookModel,
    EntregaWebhookModel,
    AccessRequestModel,
    ApplicationModel,
    ConfiguracaoModel,
    AuditAnchorModel,
    AuditEventModel,
    CertificateModel,
    ChaveApiModel,
    CheckoutModel,
    ConviteModel,
    CredentialModel,
    DeviceModel,
    LeaseModel,
    PedidoRedefinicaoModel,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    SecretModel,
    EventoSessaoModel,
    SecretIdModel,
    SecretVersionModel,
    SessaoModel,
    UserModel,
    VaultModel,
    VaultSealModel,
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

    def tipos_por_caminho(self) -> dict[str, tuple[str, str]]:
        """Mapa `cofres/<cofre>/segredos/<nome>` -> (tipo, nome do cofre).

        Existe para a tela de aplicações responder *que tipo* de segredo o
        robô consome, não só o caminho. Saber que um RPA lê três senhas e uma
        chave de API é a diferença entre uma lista de strings e uma revisão
        de escopo que alguém consegue julgar.

        Uma consulta só, com join: resolver caminho por caminho faria N+1
        numa tela que lista dezenas deles.
        """
        linhas = self._session.execute(
            select(
                VaultModel.name,
                SecretModel.name,
                SecretModel.kind,
            ).join(VaultModel, SecretModel.vault_id == VaultModel.id)
        ).all()
        return {
            f"cofres/{cofre}/segredos/{segredo}": (kind, cofre)
            for cofre, segredo, kind in linhas
        }

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

    def policies_for_application(self, papel_id: str | None) -> list[Policy]:
        """Politicas que alcancam uma aplicacao, pelo papel dela.

        Mesmo caminho das pessoas (`policies_for_user`), para que o editor de
        politicas valha para os dois. Sem papel, a aplicacao nao tem acesso
        nenhum — default deny, como em todo o resto.
        """
        if papel_id is None:
            return []
        papel = self._session.get(RoleModel, papel_id)
        if papel is None:
            return []
        return [_to_policy(p) for p in papel.policies]

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

    def desde_sequencia(self, sequencia: int, limite: int = 200) -> list[AuditEvent]:
        """Eventos da trilha com sequencia MAIOR que a informada.

        E assim que as integracoes descobrem o que aconteceu desde a ultima
        vez: a trilha ja e a fonte de verdade do que o sistema fez, e um
        segundo registro paralelo divergiria dela no primeiro erro de
        escrita. A `sequence` e monotonica e unica, entao serve de marcador
        de leitura sem precisar de estado proprio.
        """
        models = self._session.scalars(
            select(AuditEventModel)
            .where(AuditEventModel.sequence > sequencia)
            .order_by(AuditEventModel.sequence)
            .limit(limite)
        ).all()
        return [_to_audit_event(m) for m in models]

    def consumo_por_ator(
        self, actor_label: str, *, desde: datetime | None = None
    ) -> list[tuple[str, int, datetime]]:
        """Quantas leituras este ator fez, por caminho.

        Derivado da trilha, nao de contador proprio: a trilha ja e a fonte de
        verdade do que foi lido, e um contador paralelo divergiria dela no
        primeiro erro de escrita.

        Devolve (caminho, quantidade, ultima_leitura), do mais lido ao menos.
        """
        consulta = (
            select(
                AuditEventModel.target_path,
                func.count().label("quantas"),
                func.max(AuditEventModel.occurred_at).label("ultima"),
            )
            .where(
                AuditEventModel.actor_label == actor_label,
                AuditEventModel.action == str(AuditAction.SECRET_REVEALED),
                AuditEventModel.outcome == str(AuditOutcome.SUCCESS),
            )
            .group_by(AuditEventModel.target_path)
            .order_by(func.count().desc())
        )
        if desde is not None:
            consulta = consulta.where(AuditEventModel.occurred_at >= desde)

        return [
            (linha.target_path, linha.quantas, _aware(linha.ultima))
            for linha in self._session.execute(consulta).all()
        ]

    def negados_por_ator(
        self, actor_label: str, *, desde: datetime | None = None
    ) -> list[tuple[str, int, datetime]]:
        """O que este ator TENTOU ler e nao pôde.

        Tao importante quanto o consumo: caminho negado com frequencia e
        escopo mal dimensionado — ou robo pedindo o que nao deveria.
        """
        consulta = (
            select(
                AuditEventModel.target_path,
                func.count().label("quantas"),
                func.max(AuditEventModel.occurred_at).label("ultima"),
            )
            .where(
                AuditEventModel.actor_label == actor_label,
                AuditEventModel.action == str(AuditAction.ACCESS_DENIED),
            )
            .group_by(AuditEventModel.target_path)
            .order_by(func.count().desc())
        )
        if desde is not None:
            consulta = consulta.where(AuditEventModel.occurred_at >= desde)

        return [
            (linha.target_path, linha.quantas, _aware(linha.ultima))
            for linha in self._session.execute(consulta).all()
        ]

    def serie_por_dia(
        self, *, desde: datetime
    ) -> list[tuple[date, str, str, int]]:
        """Contagem de eventos por (dia, acao, desfecho), do mais antigo ao mais novo.

        A agregacao por dia acontece em Python, nao em SQL, de proposito. Um
        `occurred_at::date` no Postgres usa a timezone da SESSAO: um evento de
        02:30 UTC cai no dia 19 numa conexao em America/Sao_Paulo e no dia 20
        numa conexao em UTC. A barra do grafico mudaria de lugar conforme quem
        abriu a conexao, que e exatamente a classe de divergencia entre
        dialetos que ja custou um incidente aqui.

        O `astimezone(UTC)` abaixo nao e redundante com `_aware`: aquele so
        PREENCHE timezone ausente (o caso do SQLite), enquanto o Postgres
        devolve o valor ja convertido para a timezone da sessao — com offset
        -03, `.date()` cru entregaria o dia anterior. A conversao explicita e
        o que faz o dia sair igual nos dois bancos.

        O filtro por data continua no SQL, onde o indice de `occurred_at`
        trabalha; so o agrupamento sobe.
        """
        linhas = self._session.execute(
            select(
                AuditEventModel.occurred_at,
                AuditEventModel.action,
                AuditEventModel.outcome,
            ).where(AuditEventModel.occurred_at >= desde)
        ).all()

        baldes: dict[tuple[date, str, str], int] = {}
        for linha in linhas:
            momento = _aware(linha.occurred_at)
            assert momento is not None  # occurred_at e NOT NULL
            chave = (momento.astimezone(UTC).date(), linha.action, linha.outcome)
            baldes[chave] = baldes.get(chave, 0) + 1

        return [
            (dia, acao, desfecho, quantas)
            for (dia, acao, desfecho), quantas in sorted(baldes.items())
        ]

    def ranking(
        self,
        coluna: str,
        *,
        acoes: tuple[str, ...],
        desde: datetime,
        limite: int = 8,
        desfecho: str | None = None,
    ) -> list[tuple[str, int]]:
        """Top `limite` valores de `coluna` para as acoes informadas.

        `coluna` e escolhida de um mapa fechado, nunca interpolada: aceitar
        nome de coluna vindo da rota seria injecao de SQL pela porta da frente.
        """
        alvos = {
            "ator": AuditEventModel.actor_label,
            "caminho": AuditEventModel.target_path,
        }
        if coluna not in alvos:
            raise ValueError(f"coluna nao permitida no ranking: {coluna!r}")
        alvo = alvos[coluna]

        consulta = (
            select(alvo, func.count().label("quantas"))
            .where(
                AuditEventModel.action.in_(acoes),
                AuditEventModel.occurred_at >= desde,
            )
            .group_by(alvo)
            # O desempate por nome evita que duas linhas empatadas troquem de
            # posicao entre uma leitura e outra: ORDER BY com empate nao e
            # estavel, e no Postgres a ordem pode mudar entre execucoes.
            .order_by(func.count().desc(), alvo)
            .limit(limite)
        )
        if desfecho is not None:
            consulta = consulta.where(AuditEventModel.outcome == desfecho)

        return [(linha[0], linha.quantas) for linha in self._session.execute(consulta).all()]

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
                acessos=[_de_acesso(a) for a in device.acessos],
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

    def save_acessos(self, device_id: str, acessos: list[AcessoRemoto]) -> Device:
        """Substitui as formas de acesso do dispositivo.

        E substituicao e nao merge: o formulario envia o conjunto completo, e
        aplicar diferenca parcial deixaria um acesso orfao apontando para uma
        maquina que ja nao e alcancada por ali.
        """
        model = self._session.get(DeviceModel, device_id)
        if model is None:
            raise NotFoundError("Dispositivo nao encontrado.")
        model.acessos = [_de_acesso(a) for a in acessos]
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


def _de_acesso(acesso: AcessoRemoto) -> dict:
    return {
        "metodo": str(acesso.metodo),
        "identificador": acesso.identificador,
        "porta": acesso.porta,
        "usuario_sugerido": acesso.usuario_sugerido,
        "observacao": acesso.observacao,
    }


def _to_acesso(bruto: dict) -> AcessoRemoto:
    return AcessoRemoto(
        metodo=MetodoDeAcesso(bruto.get("metodo", "outro")),
        identificador=bruto.get("identificador", ""),
        porta=bruto.get("porta"),
        usuario_sugerido=bruto.get("usuario_sugerido", ""),
        observacao=bruto.get("observacao", ""),
    )


def _to_device(model: DeviceModel) -> Device:
    return Device(
        name=Slug(model.name),
        display_name=model.display_name,
        kind=DeviceKind(model.kind),
        address=model.address,
        tags=list(model.tags or []),
        description=model.description,
        acessos=[_to_acesso(a) for a in (model.acessos or [])],
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


class VaultSealRepository:
    """Selos com quorum. O token nunca passa por aqui — so o hash."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, selo: SeloComQuorum) -> SeloComQuorum:
        self._session.add(
            VaultSealModel(
                id=selo.id,
                vault_id=selo.vault_id,
                limiar=selo.limiar,
                total_quinhoes=selo.total_quinhoes,
                token_hash=selo.token_hash,
                portadores=list(selo.portadores),
                selado_por=selo.selado_por,
                selado_em=selo.selado_em,
            )
        )
        try:
            self._session.flush()
        except IntegrityError as erro:
            self._session.rollback()
            # O indice parcial pegou uma segunda selagem concorrente.
            raise ConflictError(
                "Este cofre acabou de ser selado por outra pessoa."
            ) from erro
        return selo

    def ativo_do_cofre(self, vault_id: str) -> SeloComQuorum | None:
        model = self._session.scalar(
            select(VaultSealModel).where(
                VaultSealModel.vault_id == vault_id,
                VaultSealModel.desselado_em.is_(None),
            )
        )
        return _to_selo(model) if model is not None else None

    def historico_do_cofre(self, vault_id: str) -> list[SeloComQuorum]:
        models = self._session.scalars(
            select(VaultSealModel)
            .where(VaultSealModel.vault_id == vault_id)
            .order_by(VaultSealModel.selado_em.desc())
        ).all()
        return [_to_selo(m) for m in models]

    def encerrar(self, selo_id: str, desselado_por: str) -> None:
        """Marca o selo como usado. NAO apaga: a auditoria quer o historico."""
        model = self._session.get(VaultSealModel, selo_id)
        if model is None:
            raise NotFoundError("Selo nao encontrado.")
        model.desselado_em = utcnow()
        model.desselado_por = desselado_por
        self._session.flush()


def _to_selo(model: VaultSealModel) -> SeloComQuorum:
    return SeloComQuorum(
        vault_id=model.vault_id,
        limiar=model.limiar,
        total_quinhoes=model.total_quinhoes,
        token_hash=model.token_hash,
        portadores=list(model.portadores or []),
        selado_por=model.selado_por,
        selado_em=_aware(model.selado_em),
        id=model.id,
    )


class ApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, app: Application) -> Application:
        existente = self._session.scalar(
            select(ApplicationModel).where(ApplicationModel.name == str(app.name))
        )
        if existente is not None:
            raise ConflictError(f"Ja existe uma aplicacao chamada {app.name}.")
        self._session.add(
            ApplicationModel(
                id=app.id,
                name=str(app.name),
                display_name=app.display_name,
                description=app.description,
                owner_label=app.owner_label,
                status=str(app.status),
                lease_minutos=app.lease_minutos,
                role_id=app.role_id,
                application_role_id=app.papel_id,
                created_at=app.created_at,
            )
        )
        self._session.flush()
        return app

    def get_by_name(self, name: Slug) -> Application:
        model = self._session.scalar(
            select(ApplicationModel).where(ApplicationModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Aplicacao {name} nao encontrada.")
        return _to_application(model)

    def get_by_role_id(self, role_id: str) -> Application | None:
        """Devolve None em vez de levantar: quem autentica nao deve distinguir
        role_id inexistente de credencial errada."""
        model = self._session.scalar(
            select(ApplicationModel).where(ApplicationModel.role_id == role_id)
        )
        return _to_application(model) if model is not None else None

    def list_all(self) -> list[Application]:
        models = self._session.scalars(
            select(ApplicationModel).order_by(ApplicationModel.display_name)
        ).all()
        return [_to_application(m) for m in models]

    def save(self, app: Application) -> Application:
        model = self._session.get(ApplicationModel, app.id)
        if model is None:
            raise NotFoundError("Aplicacao nao encontrada.")
        model.display_name = app.display_name
        model.description = app.description
        model.owner_label = app.owner_label
        model.status = str(app.status)
        model.lease_minutos = app.lease_minutos
        model.application_role_id = app.papel_id
        self._session.flush()
        return _to_application(model)


class SecretIdRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, secret_id: SecretId) -> SecretId:
        self._session.add(
            SecretIdModel(
                id=secret_id.id,
                application_id=secret_id.application_id,
                secret_hash=secret_id.secret_hash,
                label=secret_id.label,
                created_by=secret_id.created_by,
                expires_at=secret_id.expires_at,
                created_at=secret_id.created_at,
            )
        )
        self._session.flush()
        return secret_id

    def list_for_application(self, application_id: str) -> list[SecretId]:
        models = self._session.scalars(
            select(SecretIdModel)
            .where(SecretIdModel.application_id == application_id)
            .order_by(SecretIdModel.created_at.desc())
        ).all()
        return [_to_secret_id(m) for m in models]

    def find_valid(self, application_id: str, apresentado: str) -> SecretId | None:
        """Procura a credencial que casa com o valor apresentado.

        Compara pelo hash, mas a busca percorre as credenciais da aplicacao:
        indexar por hash e comparar diretamente seria mais rapido, porem
        entregaria a comparacao ao banco, que nao faz tempo constante.
        """
        for secret_id in self.list_for_application(application_id):
            if secret_id.is_valid() and secret_id.matches(apresentado):
                return secret_id
        return None

    def save(self, secret_id: SecretId) -> SecretId:
        model = self._session.get(SecretIdModel, secret_id.id)
        if model is None:
            raise NotFoundError("Credencial nao encontrada.")
        model.revoked_at = secret_id.revoked_at
        model.last_used_at = secret_id.last_used_at
        model.usos = secret_id.usos
        self._session.flush()
        return _to_secret_id(model)


class LeaseRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, lease: Lease) -> Lease:
        self._session.add(
            LeaseModel(
                id=lease.id,
                application_id=lease.application_id,
                secret_id_usado=lease.secret_id_usado,
                token_hash=lease.token_hash,
                caminhos=list(lease.caminhos),
                capacidades=[str(c) for c in lease.capacidades],
                negados=list(lease.negados),
                expires_at=lease.expires_at,
                created_at=lease.created_at,
            )
        )
        self._session.flush()
        return lease

    def find_by_token(self, token: str) -> Lease | None:
        import hashlib

        digest = hashlib.sha256(token.encode()).hexdigest()
        model = self._session.scalar(
            select(LeaseModel).where(LeaseModel.token_hash == digest)
        )
        return _to_lease(model) if model is not None else None

    def list_for_application(self, application_id: str) -> list[Lease]:
        models = self._session.scalars(
            select(LeaseModel)
            .where(LeaseModel.application_id == application_id)
            .order_by(LeaseModel.created_at.desc())
        ).all()
        return [_to_lease(m) for m in models]

    def save(self, lease: Lease) -> Lease:
        model = self._session.get(LeaseModel, lease.id)
        if model is None:
            raise NotFoundError("Lease nao encontrado.")
        model.revoked_at = lease.revoked_at
        model.leituras = lease.leituras
        self._session.flush()
        return _to_lease(model)

    def revogar_todos(self, application_id: str) -> int:
        """Revoga os leases ativos de uma aplicacao de uma vez.

        E o botao de emergencia: suspeita de comprometimento do robo fecha
        todos os acessos agora, sem esperar a expiracao natural.
        """
        agora = utcnow()
        models = self._session.scalars(
            select(LeaseModel).where(
                LeaseModel.application_id == application_id,
                LeaseModel.revoked_at.is_(None),
                LeaseModel.expires_at > agora,
            )
        ).all()
        for model in models:
            model.revoked_at = agora
        self._session.flush()
        return len(models)


def _to_application(model: ApplicationModel) -> Application:
    return Application(
        name=Slug(model.name),
        display_name=model.display_name,
        description=model.description,
        owner_label=model.owner_label,
        status=ApplicationStatus(model.status),
        lease_minutos=model.lease_minutos,
        role_id=model.role_id,
        papel_id=model.application_role_id,
        created_at=_aware(model.created_at),
        id=model.id,
    )


def _to_secret_id(model: SecretIdModel) -> SecretId:
    return SecretId(
        application_id=model.application_id,
        secret_hash=model.secret_hash,
        label=model.label,
        created_by=model.created_by,
        expires_at=_aware(model.expires_at),
        revoked_at=_aware(model.revoked_at),
        last_used_at=_aware(model.last_used_at),
        usos=model.usos,
        created_at=_aware(model.created_at),
        id=model.id,
    )


def _to_lease(model: LeaseModel) -> Lease:
    return Lease(
        application_id=model.application_id,
        secret_id_usado=model.secret_id_usado,
        token_hash=model.token_hash,
        caminhos=list(model.caminhos or []),
        capacidades=[Capability(c) for c in (model.capacidades or [])],
        negados=list(model.negados or []),
        expires_at=_aware(model.expires_at),
        revoked_at=_aware(model.revoked_at),
        leituras=model.leituras,
        created_at=_aware(model.created_at),
        id=model.id,
    )


class ConfiguracaoRepository:
    """Linha unica de configuracao, criada na primeira leitura."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def atual(self) -> ConfiguracaoOperacional:
        """A configuracao vigente, com os padroes quando nunca foi salva.

        Criar a linha na primeira leitura evita um estado "sem configuracao"
        que cada chamador teria de tratar — e tratar diferente em cada lugar
        e como nascem divergencias.
        """
        model = self._session.get(ConfiguracaoModel, "unica")
        if model is None:
            padrao = ConfiguracaoOperacional()
            model = ConfiguracaoModel(
                id="unica",
                segundos_segredo_visivel=padrao.segundos_segredo_visivel,
                custodia_horas_padrao=padrao.custodia_horas_padrao,
                alerta_certificado_dias=padrao.alerta_certificado_dias,
                rotacao_dias_padrao=padrao.rotacao_dias_padrao,
                trilha_limite_padrao=padrao.trilha_limite_padrao,
                capacidade_do_ranking=padrao.capacidade_do_ranking,
            )
            self._session.add(model)
            self._session.flush()
        return _to_configuracao(model)

    def salvar(self, config: ConfiguracaoOperacional) -> ConfiguracaoOperacional:
        model = self._session.get(ConfiguracaoModel, "unica")
        if model is None:
            self.atual()
            model = self._session.get(ConfiguracaoModel, "unica")
        assert model is not None

        model.segundos_segredo_visivel = config.segundos_segredo_visivel
        model.custodia_horas_padrao = config.custodia_horas_padrao
        model.alerta_certificado_dias = config.alerta_certificado_dias
        model.rotacao_dias_padrao = config.rotacao_dias_padrao
        model.trilha_limite_padrao = config.trilha_limite_padrao
        model.capacidade_do_ranking = config.capacidade_do_ranking
        model.atualizado_por = config.atualizado_por
        model.atualizado_em = config.atualizado_em
        self._session.flush()
        return _to_configuracao(model)


def _to_configuracao(model: ConfiguracaoModel) -> ConfiguracaoOperacional:
    return ConfiguracaoOperacional(
        segundos_segredo_visivel=model.segundos_segredo_visivel,
        custodia_horas_padrao=model.custodia_horas_padrao,
        alerta_certificado_dias=model.alerta_certificado_dias,
        rotacao_dias_padrao=model.rotacao_dias_padrao,
        trilha_limite_padrao=model.trilha_limite_padrao,
        capacidade_do_ranking=model.capacidade_do_ranking,
        atualizado_por=model.atualizado_por,
        atualizado_em=_aware(model.atualizado_em),
        id=model.id,
    )


class SessaoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, sessao: Sessao, capturado_por: str, automatica: bool) -> Sessao:
        self._session.add(
            SessaoModel(
                id=sessao.id,
                usuario_id=sessao.usuario_id,
                usuario_label=sessao.usuario_label,
                tipo=str(sessao.tipo),
                alvo=sessao.alvo,
                motivo=sessao.motivo,
                segredo_path=sessao.segredo_path,
                estado=str(sessao.estado),
                capturado_por=capturado_por,
                captura_automatica=automatica,
                ip_address=sessao.ip_address,
                origem_hostname=sessao.origem.hostname,
                origem_user_agent=sessao.origem.user_agent,
                origem_dispositivo=sessao.origem.dispositivo_name,
                consumo_tipo=str(sessao.consumo.tipo),
                consumo_nome=sessao.consumo.nome,
                consumo_caminho=sessao.consumo.caminho,
                consumo_pertence_a=sessao.consumo.pertence_a,
                iniciada_em=sessao.iniciada_em,
                ultima_atividade_em=sessao.ultima_atividade_em,
            )
        )
        self._session.flush()
        return sessao

    def get(self, sessao_id: str) -> Sessao:
        model = self._session.get(SessaoModel, sessao_id)
        if model is None:
            raise NotFoundError("Sessao nao encontrada.")
        return _to_sessao(model)

    def ativas(self) -> list[Sessao]:
        models = self._session.scalars(
            select(SessaoModel)
            .where(SessaoModel.estado == "ativa")
            .order_by(SessaoModel.iniciada_em.desc())
        ).all()
        return [_to_sessao(m) for m in models]

    def ativas_do_usuario(self, usuario_id: str) -> list[Sessao]:
        models = self._session.scalars(
            select(SessaoModel).where(
                SessaoModel.usuario_id == usuario_id,
                SessaoModel.estado == "ativa",
            )
        ).all()
        return [_to_sessao(m) for m in models]

    def historico(
        self,
        *,
        termo: str | None = None,
        usuario_label: str | None = None,
        limite: int = 100,
    ) -> list[Sessao]:
        """Sessoes encerradas, filtradas.

        O filtro por termo casa no ALVO e no MOTIVO, nao no conteudo dos
        eventos: buscar dentro da gravacao e operacao de outra natureza (uma
        sessao tem milhares de eventos) e vive em `buscar_em`.
        """
        consulta = select(SessaoModel).where(SessaoModel.estado != "ativa")
        if termo:
            alvo = f"%{termo.strip().lower()}%"
            consulta = consulta.where(
                func.lower(SessaoModel.alvo).like(alvo)
                | func.lower(SessaoModel.motivo).like(alvo)
            )
        if usuario_label:
            consulta = consulta.where(SessaoModel.usuario_label == usuario_label)
        consulta = consulta.order_by(SessaoModel.iniciada_em.desc()).limit(limite)
        return [_to_sessao(m) for m in self._session.scalars(consulta).all()]

    def buscar_em(self, sessao_id: str, termo: str) -> list[EventoDeSessao]:
        """Procura dentro da gravacao de UMA sessao.

        Separado do historico de proposito: aqui a consulta varre eventos, e
        fazer isso para todas as sessoes de uma vez seria varredura completa
        da maior tabela do sistema.
        """
        alvo = termo.strip().lower()
        if not alvo:
            return []
        models = self._session.scalars(
            select(EventoSessaoModel)
            .where(
                EventoSessaoModel.sessao_id == sessao_id,
                func.lower(EventoSessaoModel.conteudo).like(f"%{alvo}%"),
            )
            .order_by(EventoSessaoModel.deslocamento_ms)
        ).all()
        return [_to_evento_sessao(m) for m in models]

    def registrar_evento(self, sessao_id: str, evento: EventoDeSessao) -> None:
        self._session.add(
            EventoSessaoModel(
                id=evento.id,
                sessao_id=sessao_id,
                deslocamento_ms=evento.deslocamento_ms,
                tipo=str(evento.tipo),
                conteudo=evento.conteudo,
            )
        )
        model = self._session.get(SessaoModel, sessao_id)
        if model is not None:
            model.ultima_atividade_em = utcnow()
        self._session.flush()

    def save_estado(
        self, sessao: Sessao, *, gravacao_ref: str | None = None,
        gravacao_destino: str = "",
    ) -> Sessao:
        model = self._session.get(SessaoModel, sessao.id)
        if model is None:
            raise NotFoundError("Sessao nao encontrada.")
        model.estado = str(sessao.estado)
        model.encerrada_em = sessao.encerrada_em
        model.encerrada_por = sessao.encerrada_por
        model.motivo_encerramento = sessao.motivo_encerramento
        model.ultima_atividade_em = sessao.ultima_atividade_em
        if gravacao_ref is not None:
            model.gravacao_ref = gravacao_ref
            model.gravacao_destino = gravacao_destino
        self._session.flush()
        return _to_sessao(model)

    def metadados(self, sessao_id: str) -> tuple[str, bool, str | None, str]:
        """(capturado_por, automatica, gravacao_ref, destino) — sem os eventos.

        A tela de historico precisa disto para cada linha; carregar os eventos
        junto faria a listagem puxar a gravacao inteira de cada sessao.
        """
        model = self._session.get(SessaoModel, sessao_id)
        if model is None:
            raise NotFoundError("Sessao nao encontrada.")
        return (
            model.capturado_por,
            model.captura_automatica,
            model.gravacao_ref,
            model.gravacao_destino,
        )


def _to_evento_sessao(model: EventoSessaoModel) -> EventoDeSessao:
    return EventoDeSessao(
        deslocamento_ms=model.deslocamento_ms,
        tipo=TipoDeEvento(model.tipo),
        conteudo=model.conteudo,
        id=model.id,
    )


def _to_sessao(model: SessaoModel) -> Sessao:
    return Sessao(
        usuario_id=model.usuario_id,
        usuario_label=model.usuario_label,
        tipo=TipoDeSessao(model.tipo),
        alvo=model.alvo,
        motivo=model.motivo,
        segredo_path=model.segredo_path,
        estado=EstadoDaSessao(model.estado),
        eventos=[
            _to_evento_sessao(e)
            for e in sorted(model.eventos, key=lambda e: e.deslocamento_ms)
        ],
        ip_address=model.ip_address,
        origem=OrigemDaSessao(
            ip_address=model.ip_address,
            hostname=model.origem_hostname or "",
            user_agent=model.origem_user_agent or "",
            dispositivo_name=model.origem_dispositivo or "",
        ),
        consumo=ConsumoDaSessao(
            tipo=TipoDeConsumo(model.consumo_tipo or "nao_identificado"),
            nome=model.consumo_nome or "",
            caminho=model.consumo_caminho or "",
            pertence_a=model.consumo_pertence_a or "",
        ),
        iniciada_em=_aware(model.iniciada_em),
        ultima_atividade_em=_aware(model.ultima_atividade_em),
        encerrada_em=_aware(model.encerrada_em),
        encerrada_por=model.encerrada_por,
        motivo_encerramento=model.motivo_encerramento,
        id=model.id,
    )


class ConviteRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, convite: Convite) -> Convite:
        self._session.add(
            ConviteModel(
                id=convite.id,
                email=str(convite.email),
                tipo=str(convite.tipo),
                token_hash=convite.token_hash,
                estado=str(convite.estado),
                nome_sugerido=convite.nome_sugerido,
                papeis=list(convite.papeis),
                criado_por=convite.criado_por,
                expira_em=convite.expira_em,
                criado_em=convite.criado_em,
            )
        )
        self._session.flush()
        return convite

    def por_token(self, token: str) -> Convite | None:
        """Procura pelo hash do token apresentado.

        A busca e por hash, no indice: varrer todos os convites comparando um
        a um seria O(n) a cada tentativa, e um atacante usaria isso.
        """
        import hashlib

        digest = hashlib.sha256(token.encode()).hexdigest()
        model = self._session.scalar(
            select(ConviteModel).where(ConviteModel.token_hash == digest)
        )
        return _to_convite(model) if model is not None else None

    def get(self, convite_id: str) -> Convite:
        model = self._session.get(ConviteModel, convite_id)
        if model is None:
            raise NotFoundError("Convite nao encontrado.")
        return _to_convite(model)

    def pendentes(self) -> list[Convite]:
        models = self._session.scalars(
            select(ConviteModel)
            .where(ConviteModel.estado == "pendente")
            .order_by(ConviteModel.criado_em.desc())
        ).all()
        return [_to_convite(m) for m in models]

    def save(self, convite: Convite) -> Convite:
        model = self._session.get(ConviteModel, convite.id)
        if model is None:
            raise NotFoundError("Convite nao encontrado.")
        model.estado = str(convite.estado)
        model.usado_em = convite.usado_em
        self._session.flush()
        return _to_convite(model)


class PedidoRedefinicaoRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, pedido: PedidoDeRedefinicao) -> PedidoDeRedefinicao:
        self._session.add(
            PedidoRedefinicaoModel(
                id=pedido.id,
                email=str(pedido.email),
                motivo=pedido.motivo,
                ip_address=pedido.ip_address,
                criado_em=pedido.criado_em,
            )
        )
        self._session.flush()
        return pedido

    def pendentes(self) -> list[PedidoDeRedefinicao]:
        models = self._session.scalars(
            select(PedidoRedefinicaoModel)
            .where(PedidoRedefinicaoModel.atendido.is_(False))
            .order_by(PedidoRedefinicaoModel.criado_em)
        ).all()
        return [_to_pedido(m) for m in models]

    def get(self, pedido_id: str) -> PedidoDeRedefinicao:
        model = self._session.get(PedidoRedefinicaoModel, pedido_id)
        if model is None:
            raise NotFoundError("Pedido nao encontrado.")
        return _to_pedido(model)

    def save(self, pedido: PedidoDeRedefinicao) -> PedidoDeRedefinicao:
        model = self._session.get(PedidoRedefinicaoModel, pedido.id)
        if model is None:
            raise NotFoundError("Pedido nao encontrado.")
        model.atendido = pedido.atendido
        model.atendido_por = pedido.atendido_por
        model.atendido_em = pedido.atendido_em
        self._session.flush()
        return _to_pedido(model)


def _to_convite(model: ConviteModel) -> Convite:
    return Convite(
        email=Email(model.email),
        tipo=TipoDeConvite(model.tipo),
        token_hash=model.token_hash,
        expira_em=_aware(model.expira_em),
        criado_por=model.criado_por,
        nome_sugerido=model.nome_sugerido,
        papeis=list(model.papeis or []),
        estado=EstadoDoConvite(model.estado),
        usado_em=_aware(model.usado_em),
        criado_em=_aware(model.criado_em),
        id=model.id,
    )


def _to_pedido(model: PedidoRedefinicaoModel) -> PedidoDeRedefinicao:
    return PedidoDeRedefinicao(
        email=Email(model.email),
        motivo=model.motivo,
        ip_address=model.ip_address,
        atendido=model.atendido,
        atendido_por=model.atendido_por,
        atendido_em=_aware(model.atendido_em),
        criado_em=_aware(model.criado_em),
        id=model.id,
    )


class ChaveApiRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, chave: ChaveDeApi) -> ChaveDeApi:
        existente = self._session.scalar(
            select(ChaveApiModel).where(ChaveApiModel.name == str(chave.name))
        )
        if existente is not None:
            raise ConflictError(f"Ja existe uma chave chamada {chave.name}.")
        self._session.add(
            ChaveApiModel(
                id=chave.id,
                name=str(chave.name),
                display_name=chave.display_name,
                servico=chave.servico,
                ambiente=str(chave.ambiente),
                formato=str(chave.formato),
                nome_do_campo=chave.nome_do_campo,
                escopo=chave.escopo,
                usada_em=list(chave.usada_em),
                responsavel=chave.responsavel,
                documentacao_url=chave.documentacao_url,
                secret_id=chave.secret_id,
                vault_name=chave.vault_name,
                secret_name=chave.secret_name,
                expira_em=chave.expira_em,
                estado=str(chave.estado),
                criado_por=chave.criado_por,
                created_at=chave.created_at,
            )
        )
        self._session.flush()
        return chave

    def get_by_name(self, name: Slug) -> ChaveDeApi:
        model = self._session.scalar(
            select(ChaveApiModel).where(ChaveApiModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Chave {name} nao encontrada.")
        return _to_chave_api(model)

    def list_all(self) -> list[ChaveDeApi]:
        """Ordena pelo que vence primeiro; sem prazo vai para o fim."""
        models = self._session.scalars(
            select(ChaveApiModel).order_by(
                ChaveApiModel.expira_em.is_(None), ChaveApiModel.expira_em
            )
        ).all()
        return [_to_chave_api(m) for m in models]

    def save(self, chave: ChaveDeApi) -> ChaveDeApi:
        model = self._session.get(ChaveApiModel, chave.id)
        if model is None:
            raise NotFoundError("Chave nao encontrada.")
        model.display_name = chave.display_name
        model.servico = chave.servico
        model.ambiente = str(chave.ambiente)
        model.formato = str(chave.formato)
        model.nome_do_campo = chave.nome_do_campo
        model.escopo = chave.escopo
        model.usada_em = list(chave.usada_em)
        model.responsavel = chave.responsavel
        model.documentacao_url = chave.documentacao_url
        model.expira_em = chave.expira_em
        model.estado = str(chave.estado)
        model.revogada_em = chave.revogada_em
        model.secret_id = chave.secret_id
        model.vault_name = chave.vault_name
        model.secret_name = chave.secret_name
        self._session.flush()
        return _to_chave_api(model)

    def delete(self, chave_id: str) -> None:
        model = self._session.get(ChaveApiModel, chave_id)
        if model is None:
            raise NotFoundError("Chave nao encontrada.")
        self._session.delete(model)
        self._session.flush()


def _to_chave_api(model: ChaveApiModel) -> ChaveDeApi:
    return ChaveDeApi(
        name=Slug(model.name),
        display_name=model.display_name,
        servico=model.servico,
        ambiente=AmbienteDaChave(model.ambiente),
        formato=FormatoDaChave(model.formato),
        nome_do_campo=model.nome_do_campo,
        escopo=model.escopo,
        usada_em=list(model.usada_em or []),
        responsavel=model.responsavel,
        documentacao_url=model.documentacao_url,
        secret_id=model.secret_id,
        vault_name=model.vault_name,
        secret_name=model.secret_name,
        expira_em=_aware(model.expira_em),
        estado=EstadoDaChave(model.estado),
        revogada_em=_aware(model.revogada_em),
        criado_por=model.criado_por,
        created_at=_aware(model.created_at),
        id=model.id,
    )


class DestinoWebhookRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, destino: Destino) -> Destino:
        if self._session.scalar(
            select(DestinoWebhookModel).where(
                DestinoWebhookModel.name == str(destino.name)
            )
        ):
            raise ConflictError(f"Ja existe um destino chamado {destino.name}.")
        self._session.add(
            DestinoWebhookModel(
                id=destino.id,
                name=str(destino.name),
                display_name=destino.display_name,
                url=destino.url,
                eventos=list(destino.eventos),
                segredo=destino.segredo,
                estado=str(destino.estado),
                descricao=destino.descricao,
                falhas_seguidas=destino.falhas_seguidas,
                ultima_sequencia=destino.ultima_sequencia,
                ultima_entrega_em=destino.ultima_entrega_em,
                ultimo_erro=destino.ultimo_erro,
                criado_por=destino.criado_por,
                created_at=destino.created_at,
            )
        )
        self._session.flush()
        return destino

    def get_by_name(self, name: Slug) -> Destino:
        model = self._session.scalar(
            select(DestinoWebhookModel).where(DestinoWebhookModel.name == str(name))
        )
        if model is None:
            raise NotFoundError(f"Destino {name} nao encontrado.")
        return _to_destino(model)

    def list_all(self) -> list[Destino]:
        models = self._session.scalars(
            select(DestinoWebhookModel).order_by(DestinoWebhookModel.display_name)
        ).all()
        return [_to_destino(m) for m in models]

    def ativos(self) -> list[Destino]:
        models = self._session.scalars(
            select(DestinoWebhookModel).where(DestinoWebhookModel.estado == "ativo")
        ).all()
        return [_to_destino(m) for m in models]

    def save(self, destino: Destino) -> Destino:
        model = self._session.get(DestinoWebhookModel, destino.id)
        if model is None:
            raise NotFoundError("Destino nao encontrado.")
        model.display_name = destino.display_name
        model.url = destino.url
        model.eventos = list(destino.eventos)
        model.segredo = destino.segredo
        model.estado = str(destino.estado)
        model.descricao = destino.descricao
        model.falhas_seguidas = destino.falhas_seguidas
        model.ultima_sequencia = destino.ultima_sequencia
        model.ultima_entrega_em = destino.ultima_entrega_em
        model.ultimo_erro = destino.ultimo_erro
        self._session.flush()
        return _to_destino(model)

    def delete(self, destino_id: str) -> None:
        model = self._session.get(DestinoWebhookModel, destino_id)
        if model is None:
            raise NotFoundError("Destino nao encontrado.")
        self._session.delete(model)
        self._session.flush()


class EntregaWebhookRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entrega: Entrega) -> Entrega:
        self._session.add(
            EntregaWebhookModel(
                id=entrega.id,
                destino_id=entrega.destino_id,
                id_evento=entrega.id_evento,
                tipo=entrega.tipo,
                corpo=entrega.corpo,
                estado=str(entrega.estado),
                tentativas=entrega.tentativas,
                proxima_em=entrega.proxima_em,
                ultimo_status=entrega.ultimo_status,
                ultimo_erro=entrega.ultimo_erro,
                entregue_em=entrega.entregue_em,
                created_at=entrega.created_at,
            )
        )
        self._session.flush()
        return entrega

    def prontas(self, agora: datetime, limite: int = 50) -> list[Entrega]:
        """As que ja passaram da hora de tentar de novo.

        Ordena pela mais antiga: uma entrega que falhou cedo nao deve ficar
        atras de outra que acabou de entrar na fila.
        """
        models = self._session.scalars(
            select(EntregaWebhookModel)
            .where(
                EntregaWebhookModel.estado.in_(("pendente", "falhou")),
                EntregaWebhookModel.proxima_em <= agora,
            )
            .order_by(EntregaWebhookModel.proxima_em)
            .limit(limite)
        ).all()
        return [_to_entrega(m) for m in models]

    def list_for_destino(self, destino_id: str, limite: int = 50) -> list[Entrega]:
        models = self._session.scalars(
            select(EntregaWebhookModel)
            .where(EntregaWebhookModel.destino_id == destino_id)
            .order_by(EntregaWebhookModel.created_at.desc())
            .limit(limite)
        ).all()
        return [_to_entrega(m) for m in models]

    def save(self, entrega: Entrega) -> Entrega:
        model = self._session.get(EntregaWebhookModel, entrega.id)
        if model is None:
            raise NotFoundError("Entrega nao encontrada.")
        model.estado = str(entrega.estado)
        model.tentativas = entrega.tentativas
        model.proxima_em = entrega.proxima_em
        model.ultimo_status = entrega.ultimo_status
        model.ultimo_erro = entrega.ultimo_erro
        model.entregue_em = entrega.entregue_em
        self._session.flush()
        return _to_entrega(model)


def _to_destino(model: DestinoWebhookModel) -> Destino:
    return Destino(
        name=Slug(model.name),
        display_name=model.display_name,
        url=model.url,
        eventos=list(model.eventos or []),
        segredo=model.segredo,
        estado=EstadoDoDestino(model.estado),
        descricao=model.descricao,
        falhas_seguidas=model.falhas_seguidas,
        ultima_sequencia=model.ultima_sequencia or 0,
        ultima_entrega_em=_aware(model.ultima_entrega_em),
        ultimo_erro=model.ultimo_erro,
        criado_por=model.criado_por,
        created_at=_aware(model.created_at),
        id=model.id,
    )


def _to_entrega(model: EntregaWebhookModel) -> Entrega:
    return Entrega(
        destino_id=model.destino_id,
        tipo=model.tipo,
        corpo=model.corpo,
        id_evento=model.id_evento,
        estado=EstadoDaEntrega(model.estado),
        tentativas=model.tentativas,
        proxima_em=_aware(model.proxima_em),
        ultimo_status=model.ultimo_status,
        ultimo_erro=model.ultimo_erro,
        entregue_em=_aware(model.entregue_em),
        created_at=_aware(model.created_at),
        id=model.id,
    )
