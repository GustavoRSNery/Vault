"""Injeção de dependências da API.

Tudo que um router precisa vem daqui, montado por requisição. A sessão de
banco abre e fecha no escopo da requisição, com commit no sucesso e rollback
em qualquer erro — um caso de uso nunca commita por conta própria.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ..application.access.login import Login
from ..config import Settings, get_settings
from ..domain.shared.errors import AuthenticationError
from ..application.ports.webhooks import EntregadorDeWebhook
from ..application.ports.sessions import (
    ArmazenamentoDeGravacao,
    CapturaDeSessao,
)
from ..application.ports.siem import SiemExporter
from ..infrastructure.audit.exporters import JsonlExporter
from ..infrastructure.auth.tokens import TokenService
from ..infrastructure.sessions.adapters import (
    ArmazenamentoLocal,
    ArmazenamentoS3,
    CapturaManual,
    ProxySsh,
)
from ..infrastructure.auth.totp import TotpService
from ..infrastructure.crypto.envelope import EnvelopeCryptoService, LocalKeyProvider
from ..infrastructure.crypto.kms import KmsKeyProvider
from ..infrastructure.crypto.passwords import Argon2PasswordHasher
from ..infrastructure.db.models import UserModel
from ..infrastructure.integrations.entregadores import EntregadorDeEnsaio
from ..infrastructure.db.repositories import (
    DestinoWebhookRepository,
    EntregaWebhookRepository,
    AuditRepository,
    PolicyRepository,
    SecretRepository,
    SessaoRepository,
    VaultRepository,
    VaultSealRepository,
)

_engine = None
_session_factory = None


def _get_session_factory(settings: Settings):
    """Engine e factory únicos por processo, criados na primeira requisição."""
    global _engine, _session_factory
    if _session_factory is None:
        connect_args = (
            {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
        )
        _engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
        _session_factory = sessionmaker(bind=_engine, future=True, expire_on_commit=False)
    return _session_factory


def get_db(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[Session]:
    """Sessão por requisição: commit no fim, rollback em qualquer exceção.

    O rollback alcança também os erros de domínio. Uma negação de permissão
    que já tenha gravado o evento de auditoria perderia esse registro — por
    isso os routers que precisam do evento fazem commit explícito antes de
    propagar. Ver `commit_audit_then_raise` em v1/secrets.py.
    """
    factory = _get_session_factory(settings)
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_crypto(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EnvelopeCryptoService:
    """Monta a criptografia sobre o provedor de chave configurado.

    Com `VAULT_KMS_KEY_ID` definido, a chave-mestra nunca entra neste
    processo: o KMS embrulha e desembrulha a DEK do lado dele. Sem ele, cai
    na chave local — que só é aceitável fora de produção, e a configuração
    recusa subir em produção sem KMS.
    """
    if settings.usa_kms:
        return EnvelopeCryptoService(
            KmsKeyProvider(settings.kms_key_id, region=settings.kms_region or None)
        )
    return EnvelopeCryptoService(LocalKeyProvider(settings.master_key))


def get_tokens(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenService:
    return TokenService(
        secret=settings.effective_jwt_secret,
        algorithm=settings.jwt_algorithm,
        access_minutes=settings.access_token_minutes,
        refresh_days=settings.refresh_token_days,
    )


def get_totp(
    crypto: Annotated[EnvelopeCryptoService, Depends(get_crypto)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TotpService:
    return TotpService(crypto, window=settings.totp_window)


def get_login(
    db: Annotated[Session, Depends(get_db)],
    tokens: Annotated[TokenService, Depends(get_tokens)],
    totp: Annotated[TotpService, Depends(get_totp)],
) -> Login:
    return Login(db, Argon2PasswordHasher(), tokens, totp, AuditRepository(db))


@dataclass(frozen=True, slots=True)
class CurrentUser:
    """Quem está fazendo a requisição, mais o contexto para a auditoria."""

    id: str
    email: str
    ip_address: str | None
    user_agent: str | None


def get_current_user(
    request: Request,
    tokens: Annotated[TokenService, Depends(get_tokens)],
    db: Annotated[Session, Depends(get_db)],
    authorization: Annotated[str | None, Header()] = None,
) -> CurrentUser:
    """Valida o token e confirma que a conta ainda vale.

    Reconsultar o usuário a cada requisição é deliberado: um token continua
    criptograficamente válido depois de a conta ser desativada, e sem esta
    checagem um desligado seguiria usando o sistema até o token vencer.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AuthenticationError("Credenciais inválidas.")

    claims = tokens.verify(authorization.split(" ", 1)[1].strip())
    user = db.get(UserModel, claims.user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("Credenciais inválidas.")

    return CurrentUser(
        id=user.id,
        email=user.email,
        ip_address=_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )


def _client_ip(request: Request) -> str | None:
    """IP do cliente.

    X-Forwarded-For só é lido porque a aplicação roda atrás de um balanceador
    que o reescreve. Num deploy sem proxy confiável este cabeçalho é forjável
    e não deveria ser usado para nada além de registro informativo.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def get_vaults(db: Annotated[Session, Depends(get_db)]) -> VaultRepository:
    return VaultRepository(db)


def get_secrets(db: Annotated[Session, Depends(get_db)]) -> SecretRepository:
    return SecretRepository(db)


def get_policies(db: Annotated[Session, Depends(get_db)]) -> PolicyRepository:
    return PolicyRepository(db)


def get_seals(db: Annotated[Session, Depends(get_db)]) -> VaultSealRepository:
    return VaultSealRepository(db)


def get_audit(db: Annotated[Session, Depends(get_db)]) -> AuditRepository:
    return AuditRepository(db)


def get_captura(
    settings: Annotated[Settings, Depends(get_settings)],
) -> CapturaDeSessao:
    """De onde os eventos de sessao vem.

    Trocar o proxy SSH de producao e trocar esta linha: as rotas conhecem a
    porta `CapturaDeSessao`, nunca a tecnologia.
    """
    if settings.sessao_captura == "proxy-ssh":
        return ProxySsh(settings.sessao_proxy_host)
    return CapturaManual()


def get_gravacoes(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ArmazenamentoDeGravacao:
    """Onde a gravacao fechada fica guardada.

    O local nao e imutavel e diz isso; o S3 com Object Lock e, e tambem diz.
    A interface usa a declaracao para nao anunciar prova onde ha so registro.
    """
    if settings.sessao_armazenamento == "s3":
        return ArmazenamentoS3(settings.sessao_s3_bucket)
    return ArmazenamentoLocal(settings.sessao_gravacoes_path)


def get_sessoes(db: Annotated[Session, Depends(get_db)]) -> SessaoRepository:
    return SessaoRepository(db)


def get_siem_exporter(
    settings: Annotated[Settings, Depends(get_settings)],
) -> SiemExporter:
    """Destino da exportacao da trilha.

    Trocar o SIEM de producao e trocar esta linha: o caso de uso so conhece a
    porta `SiemExporter`, nao o arquivo.
    """
    return JsonlExporter(settings.audit_export_path)


def get_destinos_webhook(
    db: Annotated[Session, Depends(get_db)],
) -> DestinoWebhookRepository:
    return DestinoWebhookRepository(db)


def get_entregas_webhook(
    db: Annotated[Session, Depends(get_db)],
) -> EntregaWebhookRepository:
    return EntregaWebhookRepository(db)


def get_entregador_webhook() -> EntregadorDeWebhook:
    """Como os webhooks saem daqui.

    O ensaio e o padrao de proposito: um sistema recem-instalado que
    comecasse a disparar requisicoes para fora, com eventos de cofre, seria
    uma surpresa desagradavel. Para entregar de verdade, troque por
    `EntregadorHttp()` — o resto do sistema nao muda, porque so conhece a
    porta `EntregadorDeWebhook`.
    """
    return EntregadorDeEnsaio()
