"""Popula o inventário de demonstração: dispositivos, credenciais, certificados.

Os dados são escolhidos para que as telas mostrem os casos que importam, e não
apenas linhas bonitas:

- uma credencial **nunca rotacionada** (o pior caso, que precisa aparecer);
- uma **atrasada** há meses;
- uma em dia;
- uma com rotação **desligada** por decisão explícita;
- uma **em custódia aberta**, para a exclusividade ficar visível;
- certificados **vencido**, **vencendo** e **válido**.

Também concede ao papel de administrador as permissões nos caminhos novos
(`dispositivos`, `credenciais`, `certificados`), que são separados de `cofres`
de propósito.

Uso:  python -m app.tools.popular_inventario   (idempotente)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ..config import get_settings
from ..domain.inventory.entities import Certificate, Credential, Device, DeviceKind
from ..domain.shared.errors import NotFoundError
from ..domain.shared.value_objects import Slug
from ..infrastructure.db.models import (
    Base,
    PolicyModel,
    PolicyRuleModel,
    RoleModel,
    UserModel,
)
from ..infrastructure.db.repositories import (
    CertificateRepository,
    CredentialRepository,
    DeviceRepository,
)

TODAS = ["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]

DISPOSITIVOS = [
    ("fw-matriz", "Firewall Matriz", DeviceKind.FIREWALL, "10.0.0.1",
     ["produção", "crítico"], "Firewall de borda do escritório central."),
    ("srv-dominio", "Servidor Domínio", DeviceKind.SERVER, "10.0.1.20",
     ["produção", "contábil"], "Servidor de aplicação do ERP Domínio."),
    ("pg-producao", "Postgres Produção", DeviceKind.DATABASE, "10.0.2.10",
     ["produção", "crítico"], "Banco principal."),
    ("sw-acesso", "Switch de Acesso", DeviceKind.SWITCH, "10.0.0.20",
     ["rede"], "Switch do andar administrativo."),
]

# (dispositivo, nome, usuário, prazo, dias desde a última rotação ou None)
CREDENCIAIS = [
    ("fw-matriz", "senha-admin", "admin", 90, None),      # nunca rotacionada
    ("srv-dominio", "usuario-servico", "svc_dominio", 90, 140),  # atrasada
    ("pg-producao", "senha-postgres", "postgres", 60, 15),       # em dia
    ("sw-acesso", "senha-enable", "enable", 0, None),            # não rotaciona
    ("pg-producao", "replicador", "replicator", 180, 30),        # em dia
]

# (nome, emissor, responsável, dias até vencer)
CERTIFICADOS = [
    ("api-rede", "Let's Encrypt", "Infraestrutura", 74),
    ("portal-cliente", "DigiCert", "Infraestrutura", 21),
    ("ecnpj-matriz", "AC Certisign", "Contabilidade", -8),
    ("vpn-interna", "AC interna", "Infraestrutura", 320),
]


def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, future=True)()

    _conceder_inventario_ao_admin(session)

    devices = DeviceRepository(session)
    credentials = CredentialRepository(session)
    certificates = CertificateRepository(session)
    agora = datetime.now(UTC)

    por_nome: dict[str, Device] = {}
    for nome, visivel, tipo, endereco, tags, descricao in DISPOSITIVOS:
        try:
            por_nome[nome] = devices.get_by_name(Slug(nome))
            continue
        except NotFoundError:
            pass
        por_nome[nome] = devices.add(
            Device(
                name=Slug(nome),
                display_name=visivel,
                kind=tipo,
                address=endereco,
                tags=tags,
                description=descricao,
            )
        )
    session.commit()

    existentes = {
        (c.device_id, str(c.name)) for c in credentials.list_all()
    }
    criadas: list[Credential] = []
    for dispositivo, nome, usuario, prazo, desde in CREDENCIAIS:
        device = por_nome[dispositivo]
        if (device.id, nome) in existentes:
            continue
        criadas.append(
            credentials.add(
                Credential(
                    name=Slug(nome),
                    device_id=device.id,
                    username=usuario,
                    rotation_days=prazo,
                    last_rotated_at=(
                        None if desde is None else agora - timedelta(days=desde)
                    ),
                )
            )
        )
    session.commit()

    # Uma retirada aberta, para a exclusividade aparecer na tela.
    admin = session.scalar(
        select(UserModel).where(UserModel.full_name == "Administrador")
    )
    if admin is not None:
        for credencial in credentials.list_all():
            if str(credencial.name) != "senha-postgres":
                continue
            if credencial.open_checkout is not None:
                break
            credencial.check_out(
                admin.id,
                admin.email,
                "Investigação de lentidão no banco",
                hours=8,
            )
            credentials.save(credencial)
            break
    session.commit()

    for nome, emissor, responsavel, dias in CERTIFICADOS:
        try:
            certificates.get_by_name(Slug(nome))
            continue
        except NotFoundError:
            pass
        certificates.add(
            Certificate(
                name=Slug(nome),
                display_name=f"{nome.replace('-', '.')}.com.br",
                subject=f"CN={nome.replace('-', '.')}.com.br",
                issuer=emissor,
                owner_label=responsavel,
                not_before=agora - timedelta(days=90),
                not_after=agora + timedelta(days=dias),
            )
        )
    session.commit()

    print(f"Inventário: {len(por_nome)} dispositivos, "
          f"{len(credentials.list_all())} credenciais, "
          f"{len(certificates.list_all())} certificados.")


def _conceder_inventario_ao_admin(session: Session) -> None:
    """Dá ao papel de administrador acesso aos caminhos do inventário.

    Caminhos separados de `cofres` de propósito: acesso amplo a segredos não
    deveria, por si, entregar o governo do inventário.
    """
    nome = "inventario-total"
    caminhos = (
        "dispositivos",
        "dispositivos/*",
        "credenciais",
        "credenciais/*",
        "certificados",
        "certificados/*",
        "chaves-api",
        "chaves-api/*",
        "integracoes",
        "integracoes/*",
    )

    politica = session.scalar(select(PolicyModel).where(PolicyModel.name == nome))
    if politica is None:
        politica = PolicyModel(
            name=nome,
            description="Gestão de dispositivos, credenciais, certificados, chaves de API e integrações.",
        )
        session.add(politica)
        session.flush()

    # Acrescenta os caminhos que faltam em vez de só criar a política quando
    # ela não existe. Entidade nova (foi o caso de `chaves-api`) não nasce no
    # banco de quem já rodou o seed antes: a política fica parada na versão
    # antiga e a tela devolve 403 sem que nada esteja quebrado — o RBAC está
    # certo, o seed é que ficou para trás.
    ja_cobertos = {regra.path for regra in politica.rules}
    for caminho in caminhos:
        if caminho not in ja_cobertos:
            politica.rules.append(
                PolicyRuleModel(path=caminho, capabilities=TODAS, effect="allow")
            )
    session.flush()

    papel = session.scalar(select(RoleModel).where(RoleModel.name == "administrador"))
    if papel is not None and politica not in papel.policies:
        papel.policies.append(politica)
    session.commit()


if __name__ == "__main__":
    main()
