"""Testes dos repositórios de inventário, com foco na fronteira banco↔domínio.

A regressão que estes testes guardam: **o SQLite devolve `datetime` sem
timezone mesmo em coluna `DateTime(timezone=True)`, e o Postgres devolve com.**
O domínio recusa datetime ingênuo, então ler de volta um certificado quebrava
com `TypeError: can't subtract offset-naive and offset-aware datetimes` — num
dialeto só. É a mesma divergência que já produziu o bug do hash da auditoria
aqui, e por isso vale teste nomeado em vez de confiança.

Rode também contra Postgres quando mexer nestas colunas:
    VAULT_TEST_DATABASE_URL=postgresql+psycopg://... pytest tests/
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.domain.inventory.entities import (
    Certificate,
    CertificateState,
    Credential,
    CredentialStatus,
    Device,
    DeviceKind,
)
from app.domain.shared.errors import ConflictError, NotFoundError
from app.domain.shared.value_objects import Slug
from app.infrastructure.db.models import UserModel
from app.infrastructure.db.repositories import (
    CertificateRepository,
    CredentialRepository,
    DeviceRepository,
)


@pytest.fixture
def dispositivo(session: Session) -> Device:
    repo = DeviceRepository(session)
    d = repo.add(
        Device(
            name=Slug("fw-matriz"),
            display_name="Firewall Matriz",
            kind=DeviceKind.FIREWALL,
            address="10.0.0.1",
            tags=["produção"],
        )
    )
    session.flush()
    return d


@pytest.fixture
def pessoa(session: Session) -> UserModel:
    user = UserModel(
        id="uc1",
        email="ana@exemplo.com.br",
        full_name="Ana",
        password_hash="x",
        is_active=True,
    )
    session.add(user)
    session.flush()
    return user


class TestFronteiraDeTimezone:
    """Toda data que sai do banco volta com timezone, em qualquer dialeto."""

    def test_certificado_lido_de_volta_tem_timezone(
        self, session: Session
    ) -> None:
        agora = datetime.now(UTC)
        repo = CertificateRepository(session)
        repo.add(
            Certificate(
                name=Slug("api"),
                display_name="api.exemplo.com.br",
                subject="CN=api.exemplo.com.br",
                issuer="CA",
                not_before=agora - timedelta(days=60),
                not_after=agora + timedelta(days=30),
            )
        )
        session.flush()

        lido = repo.get_by_name(Slug("api"))
        assert lido.not_after.tzinfo is not None
        assert lido.not_before.tzinfo is not None
        assert lido.created_at.tzinfo is not None
        # A conta que estourava: subtrair aware de naive.
        assert lido.days_remaining() == 29
        assert lido.state() is CertificateState.EXPIRING

    def test_credencial_lida_de_volta_tem_timezone(
        self, session: Session, dispositivo: Device
    ) -> None:
        agora = datetime.now(UTC)
        repo = CredentialRepository(session)
        repo.add(
            Credential(
                name=Slug("senha-admin"),
                device_id=dispositivo.id,
                rotation_days=90,
                last_rotated_at=agora - timedelta(days=10),
            )
        )
        session.flush()

        lida = repo.list_all()[0]
        assert lida.last_rotated_at is not None
        assert lida.last_rotated_at.tzinfo is not None
        assert lida.created_at.tzinfo is not None
        assert lida.is_overdue() is False
        assert lida.days_until_due() == 79

    def test_custodia_lida_de_volta_tem_timezone(
        self, session: Session, dispositivo: Device, pessoa: UserModel
    ) -> None:
        repo = CredentialRepository(session)
        credencial = repo.add(
            Credential(name=Slug("senha-admin"), device_id=dispositivo.id)
        )
        credencial.check_out(pessoa.id, pessoa.email, "Manutenção", hours=4)
        repo.save(credencial)
        session.flush()

        lida = repo.get(credencial.id)
        aberta = lida.open_checkout
        assert aberta is not None
        assert aberta.due_at.tzinfo is not None
        assert aberta.taken_at.tzinfo is not None
        # A conta que estourava no cálculo de atraso.
        assert aberta.is_late() is False


class TestDeviceRepository:
    def test_nome_repetido_e_conflito(self, session: Session) -> None:
        repo = DeviceRepository(session)
        repo.add(Device(name=Slug("srv-01"), display_name="Servidor 01"))
        session.flush()
        with pytest.raises(ConflictError):
            repo.add(Device(name=Slug("srv-01"), display_name="Outro"))

    def test_inexistente_levanta_not_found(self, session: Session) -> None:
        with pytest.raises(NotFoundError):
            DeviceRepository(session).get_by_name(Slug("nao-existe"))

    def test_filtro_de_inativos(self, session: Session) -> None:
        repo = DeviceRepository(session)
        ativo = repo.add(Device(name=Slug("ativo"), display_name="Ativo"))
        inativo = repo.add(Device(name=Slug("inativo"), display_name="Inativo"))
        session.flush()
        repo.set_active(inativo.id, False)
        session.flush()

        assert len(repo.list_all()) == 2
        somente_ativos = repo.list_all(include_inactive=False)
        assert [str(d.name) for d in somente_ativos] == [str(ativo.name)]


class TestCredentialRepository:
    def test_mesmo_nome_em_dispositivos_diferentes(
        self, session: Session, dispositivo: Device
    ) -> None:
        """"senha-root" existe em vários equipamentos: a unicidade é por par."""
        devices = DeviceRepository(session)
        outro = devices.add(Device(name=Slug("srv-02"), display_name="Servidor 02"))
        session.flush()

        repo = CredentialRepository(session)
        repo.add(Credential(name=Slug("senha-root"), device_id=dispositivo.id))
        repo.add(Credential(name=Slug("senha-root"), device_id=outro.id))
        session.flush()
        assert len(repo.list_all()) == 2

    def test_nome_repetido_no_mesmo_dispositivo_e_conflito(
        self, session: Session, dispositivo: Device
    ) -> None:
        repo = CredentialRepository(session)
        repo.add(Credential(name=Slug("senha-root"), device_id=dispositivo.id))
        session.flush()
        with pytest.raises(ConflictError):
            repo.add(Credential(name=Slug("senha-root"), device_id=dispositivo.id))

    def test_devolucao_preserva_a_retirada(
        self, session: Session, dispositivo: Device, pessoa: UserModel
    ) -> None:
        """Devolver fecha a retirada; nunca apaga o fato de ter acontecido."""
        repo = CredentialRepository(session)
        credencial = repo.add(
            Credential(name=Slug("senha-admin"), device_id=dispositivo.id)
        )
        credencial.check_out(pessoa.id, pessoa.email, "Manutenção", hours=4)
        repo.save(credencial)
        session.flush()

        credencial.check_in(pessoa.id)
        salva = repo.save(credencial)
        session.flush()

        assert salva.status is CredentialStatus.ACTIVE
        assert salva.open_checkout is None
        assert len(salva.checkouts) == 1
        assert salva.checkouts[0].returned_at is not None

    def test_historico_acumula_retiradas(
        self, session: Session, dispositivo: Device, pessoa: UserModel
    ) -> None:
        repo = CredentialRepository(session)
        credencial = repo.add(
            Credential(name=Slug("senha-admin"), device_id=dispositivo.id)
        )
        for i in range(3):
            credencial.check_out(pessoa.id, pessoa.email, f"Uso {i}", hours=2)
            repo.save(credencial)
            credencial.check_in(pessoa.id)
            repo.save(credencial)
        session.flush()

        lida = repo.get(credencial.id)
        assert len(lida.checkouts) == 3
        assert all(c.returned_at is not None for c in lida.checkouts)

    def test_rotacao_persiste(
        self, session: Session, dispositivo: Device
    ) -> None:
        repo = CredentialRepository(session)
        credencial = repo.add(
            Credential(name=Slug("senha-admin"), device_id=dispositivo.id)
        )
        session.flush()
        assert repo.get(credencial.id).is_overdue() is True

        credencial.mark_rotated()
        repo.save(credencial)
        session.flush()
        assert repo.get(credencial.id).is_overdue() is False


class TestCertificateRepository:
    def test_ordena_pelo_que_vence_primeiro(self, session: Session) -> None:
        agora = datetime.now(UTC)
        repo = CertificateRepository(session)
        for nome, dias in [("longe", 200), ("perto", 5), ("medio", 60)]:
            repo.add(
                Certificate(
                    name=Slug(nome),
                    display_name=nome,
                    subject=f"CN={nome}",
                    issuer="CA",
                    not_before=agora - timedelta(days=1),
                    not_after=agora + timedelta(days=dias),
                )
            )
        session.flush()
        assert [str(c.name) for c in repo.list_all()] == ["perto", "medio", "longe"]

    def test_nome_repetido_e_conflito(self, session: Session) -> None:
        agora = datetime.now(UTC)
        repo = CertificateRepository(session)
        base = {
            "display_name": "x",
            "subject": "CN=x",
            "issuer": "CA",
            "not_before": agora - timedelta(days=1),
            "not_after": agora + timedelta(days=30),
        }
        repo.add(Certificate(name=Slug("api"), **base))
        session.flush()
        with pytest.raises(ConflictError):
            repo.add(Certificate(name=Slug("api"), **base))
