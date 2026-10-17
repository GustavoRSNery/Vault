"""Testes de autenticação.

Cobrem as três formas de um login vazar informação: mensagem diferente por
causa, tempo de resposta diferente, e MFA contornável.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy.orm import Session

from app.application.access.login import (
    MENSAGEM_GENERICA,
    Login,
    LoginCommand,
    LoginResult,
)
from app.domain.audit.events import AuditAction, AuditOutcome
from app.domain.shared.errors import AuthenticationError
from app.infrastructure.auth.tokens import REFRESH, TokenService
from app.infrastructure.auth.totp import TotpService
from app.infrastructure.crypto.envelope import EnvelopeCryptoService
from app.infrastructure.crypto.passwords import Argon2PasswordHasher
from app.infrastructure.db.models import UserModel
from app.infrastructure.db.repositories import AuditRepository

SENHA = "senha-forte-do-ana.souza-2026"
EMAIL = "ana.souza@exemplo.com.br"


@pytest.fixture
def hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


@pytest.fixture
def tokens() -> TokenService:
    return TokenService(secret="segredo-de-teste-nao-usar-em-producao")


def _criar_usuario(
    session: Session, hasher: Argon2PasswordHasher, *, ativo: bool = True
) -> UserModel:
    user = UserModel(
        id="u1", email=EMAIL, full_name="Ana Souza",
        password_hash=hasher.hash(SENHA), is_active=ativo,
    )
    session.add(user)
    session.flush()
    return user


def _caso(session: Session, hasher, tokens, crypto: EnvelopeCryptoService) -> Login:
    return Login(session, hasher, tokens, TotpService(crypto), AuditRepository(session))


class TestLoginSuccess:
    def test_credenciais_corretas_devolvem_tokens(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        _criar_usuario(session, hasher)
        resultado = _caso(session, hasher, tokens, crypto).execute(
            LoginCommand(email=EMAIL, password=SENHA)
        )
        assert resultado.tokens is not None
        assert resultado.mfa_required is False
        assert resultado.user_id == "u1"

    def test_email_e_normalizado(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        _criar_usuario(session, hasher)
        resultado = _caso(session, hasher, tokens, crypto).execute(
            LoginCommand(email="  ANA.SOUZA@Exemplo.COM.BR  ", password=SENHA)
        )
        assert resultado.tokens is not None

    def test_sucesso_gera_auditoria(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        _criar_usuario(session, hasher)
        audit = AuditRepository(session)
        Login(session, hasher, tokens, TotpService(crypto), audit).execute(
            LoginCommand(email=EMAIL, password=SENHA, ip_address="10.0.0.9")
        )
        evento = audit.list_chain()[-1]
        assert evento.action is AuditAction.LOGIN_SUCCESS
        assert evento.ip_address == "10.0.0.9"


class TestLoginFailure:
    def test_senha_errada_e_recusada(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        _criar_usuario(session, hasher)
        with pytest.raises(AuthenticationError, match=MENSAGEM_GENERICA):
            _caso(session, hasher, tokens, crypto).execute(
                LoginCommand(email=EMAIL, password="errada")
            )

    def test_email_inexistente_da_a_mesma_mensagem(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        """Mensagem diferente entregaria a lista de e-mails válidos."""
        _criar_usuario(session, hasher)
        with pytest.raises(AuthenticationError, match=MENSAGEM_GENERICA):
            _caso(session, hasher, tokens, crypto).execute(
                LoginCommand(email="ninguem@exemplo.com.br", password=SENHA)
            )

    def test_conta_inativa_da_a_mesma_mensagem(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        _criar_usuario(session, hasher, ativo=False)
        with pytest.raises(AuthenticationError, match=MENSAGEM_GENERICA):
            _caso(session, hasher, tokens, crypto).execute(
                LoginCommand(email=EMAIL, password=SENHA)
            )

    def test_falha_gera_auditoria_com_o_email_tentado(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        """É assim que se enxerga alguém varrendo endereços."""
        audit = AuditRepository(session)
        caso = Login(session, hasher, tokens, TotpService(crypto), audit)
        with pytest.raises(AuthenticationError):
            caso.execute(LoginCommand(email="varredura@exemplo.com.br", password="x"))

        evento = audit.list_chain()[-1]
        assert evento.action is AuditAction.LOGIN_FAILURE
        assert evento.outcome is AuditOutcome.FAILURE
        assert evento.actor_label == "varredura@exemplo.com.br"

    def test_auditoria_de_falha_nao_guarda_a_senha(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        audit = AuditRepository(session)
        caso = Login(session, hasher, tokens, TotpService(crypto), audit)
        with pytest.raises(AuthenticationError):
            caso.execute(LoginCommand(email=EMAIL, password="minha-senha-secreta"))

        evento = audit.list_chain()[-1]
        assert "minha-senha-secreta" not in evento.reason
        assert "minha-senha-secreta" not in str(evento.metadata)


class TestConstantTime:
    def test_email_inexistente_gasta_tempo_comparavel(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        """Resposta instantânea denunciaria o e-mail inexistente.

        O limiar é frouxo (fator 3) de propósito: a máquina de CI oscila, e um
        teste de tempo apertado vira falha intermitente. O que se quer pegar é
        a diferença de ordem de grandeza — microssegundos contra dezenas de
        milissegundos — que aconteceria se o hash descartável sumisse.
        """
        _criar_usuario(session, hasher)
        caso = _caso(session, hasher, tokens, crypto)

        def medir(email: str) -> float:
            inicio = time.perf_counter()
            for _ in range(3):
                with pytest.raises(AuthenticationError):
                    caso.execute(LoginCommand(email=email, password="senha-errada-qualquer"))
            return (time.perf_counter() - inicio) / 3

        t_existente = medir(EMAIL)
        t_inexistente = medir("ninguem@exemplo.com.br")

        assert t_inexistente > t_existente / 3, (
            f"e-mail inexistente respondeu rápido demais "
            f"({t_inexistente*1000:.1f}ms contra {t_existente*1000:.1f}ms): "
            "o tempo denuncia que a conta não existe"
        )


class TestMfa:
    def _ativar_mfa(self, session: Session, user: UserModel, totp: TotpService) -> None:
        cifrado, _uri = totp.enroll(user.email)
        user.mfa_secret_ciphertext = cifrado.ciphertext
        user.mfa_secret_nonce = cifrado.nonce
        user.mfa_secret_wrapped_dek = cifrado.wrapped_dek
        user.mfa_key_id = cifrado.key_id
        user.mfa_enabled = True
        session.flush()

    def test_com_mfa_ativo_a_senha_sozinha_nao_da_token(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        totp = TotpService(crypto)
        user = _criar_usuario(session, hasher)
        self._ativar_mfa(session, user, totp)

        resultado = Login(session, hasher, tokens, totp, AuditRepository(session)).execute(
            LoginCommand(email=EMAIL, password=SENHA)
        )
        assert resultado.mfa_required is True
        assert resultado.tokens is None

    def test_codigo_correto_completa_o_login(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        from app.domain.vaults.entities import EncryptedValue

        totp = TotpService(crypto)
        user = _criar_usuario(session, hasher)
        self._ativar_mfa(session, user, totp)

        cifrado = EncryptedValue(
            ciphertext=user.mfa_secret_ciphertext,
            nonce=user.mfa_secret_nonce,
            wrapped_dek=user.mfa_secret_wrapped_dek,
            key_id=user.mfa_key_id,
        )
        codigo = totp.current_code(cifrado)

        resultado = Login(session, hasher, tokens, totp, AuditRepository(session)).execute(
            LoginCommand(email=EMAIL, password=SENHA, totp_code=codigo)
        )
        assert resultado.tokens is not None
        assert resultado.mfa_required is False

    def test_codigo_errado_e_recusado(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        totp = TotpService(crypto)
        user = _criar_usuario(session, hasher)
        self._ativar_mfa(session, user, totp)

        caso = Login(session, hasher, tokens, totp, AuditRepository(session))
        with pytest.raises(AuthenticationError, match="Código"):
            caso.execute(LoginCommand(email=EMAIL, password=SENHA, totp_code="000000"))

    def test_mfa_ativo_sem_segredo_e_negado(
        self, session: Session, hasher, tokens, crypto: EnvelopeCryptoService
    ) -> None:
        """Estado inconsistente nega, nunca libera."""
        user = _criar_usuario(session, hasher)
        user.mfa_enabled = True  # sem gravar o segredo
        session.flush()

        caso = Login(session, hasher, tokens, TotpService(crypto), AuditRepository(session))
        with pytest.raises(AuthenticationError):
            caso.execute(LoginCommand(email=EMAIL, password=SENHA, totp_code="123456"))


class TestTokenService:
    def test_token_de_acesso_verifica(self, tokens: TokenService) -> None:
        par = tokens.issue("u1", EMAIL)
        assert tokens.verify(par.access_token).user_id == "u1"

    def test_refresh_nao_vale_como_acesso(self, tokens: TokenService) -> None:
        """Confusão de tipo: um refresh roubado não pode virar sessão."""
        par = tokens.issue("u1", EMAIL)
        with pytest.raises(AuthenticationError):
            tokens.verify(par.refresh_token)  # expected_type=access por padrão

    def test_refresh_verifica_como_refresh(self, tokens: TokenService) -> None:
        par = tokens.issue("u1", EMAIL)
        assert tokens.verify(par.refresh_token, expected_type=REFRESH).user_id == "u1"

    def test_token_de_outro_segredo_e_recusado(self, tokens: TokenService) -> None:
        par = tokens.issue("u1", EMAIL)
        outro = TokenService(secret="outro-segredo-completamente-diferente-e-longo")
        with pytest.raises(AuthenticationError):
            outro.verify(par.access_token)

    def test_token_adulterado_e_recusado(self, tokens: TokenService) -> None:
        par = tokens.issue("u1", EMAIL)
        adulterado = par.access_token[:-4] + ("aaaa" if par.access_token[-4:] != "aaaa" else "bbbb")
        with pytest.raises(AuthenticationError):
            tokens.verify(adulterado)

    def test_token_expirado_e_recusado(self) -> None:
        servico = TokenService(secret="x" * 32, access_minutes=-1)  # já nasce vencido
        with pytest.raises(AuthenticationError, match="expirada"):
            servico.verify(servico.issue("u1", EMAIL).access_token)


class TestNoLeakInRepr:
    def test_repr_do_resultado_nao_mostra_tokens(self, tokens: TokenService) -> None:
        resultado = LoginResult(
            tokens=tokens.issue("u1", EMAIL), mfa_required=False,
            user_id="u1", email=EMAIL,
        )
        assert resultado.tokens is not None
        assert resultado.tokens.access_token not in repr(resultado)
        assert "<omitido>" in repr(resultado)


class TestWeakSecretRejected:
    def test_segredo_curto_e_recusado(self) -> None:
        """Chave HMAC curta enfraquece a assinatura (RFC 7518 §3.2)."""
        with pytest.raises(RuntimeError, match="32 bytes"):
            TokenService(secret="curto-demais")

    def test_segredo_vazio_e_recusado(self) -> None:
        with pytest.raises(RuntimeError):
            TokenService(secret="")
