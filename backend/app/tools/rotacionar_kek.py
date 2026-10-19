"""Rotaciona a chave-mestra (KEK) sem reescrever os segredos.

Uso:
    python -m app.tools.rotacionar_kek --conferir
    python -m app.tools.rotacionar_kek --nova-chave <base64>
    python -m app.tools.rotacionar_kek --kms <arn-ou-alias> [--region <região>]

É a razão de existir do envelope. A KEK não cifra dado diretamente: ela só
protege as DEKs. Então rotacionar significa desembrulhar cada DEK com a chave
antiga e reembrulhar com a nova — o **texto cifrado de cada segredo fica
intacto**. Sem envelope, trocar a chave-mestra exigiria decifrar e recifrar
todos os segredos, o que é caro e, pior, põe todos os valores em claro na
memória de um processo só.

Rotaciona-se a KEK quando ela pode ter vazado, quando alguém com acesso a ela
deixa a equipe, ou por calendário. O `key_id` gravado em cada versão é o que
torna a operação retomável: dá para interromper no meio e continuar depois,
porque cada registro diz qual chave o protege.

O processo aqui é tudo-ou-nada dentro de uma transação. Para cofres muito
grandes, o caminho seria lotes por `key_id` — a estrutura já suporta, porque
versões com chaves diferentes coexistem sem problema.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
from collections import Counter

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from ..application.ports.keys import KeyProvider
from ..config import get_settings
from ..domain.shared.errors import ValidationError
from ..infrastructure.crypto.envelope import LocalKeyProvider
from ..infrastructure.crypto.kms import KmsKeyProvider
from ..infrastructure.db.models import SecretVersionModel, UserModel


def _provedor_atual(settings) -> KeyProvider:  # noqa: ANN001
    if settings.usa_kms:
        return KmsKeyProvider(
            settings.kms_key_id, region=settings.kms_region or None
        )
    return LocalKeyProvider(settings.master_key)


def _conferir(session: Session) -> int:
    """Mostra a distribuição de chaves sem alterar nada."""
    versoes = session.scalars(select(SecretVersionModel)).all()
    usuarios = session.scalars(
        select(UserModel).where(UserModel.mfa_key_id.is_not(None))
    ).all()

    por_chave = Counter(v.key_id for v in versoes)
    por_chave_mfa = Counter(u.mfa_key_id for u in usuarios)

    print(f"Versões de segredo: {len(versoes)}")
    for chave, quantas in sorted(por_chave.items()):
        print(f"  {chave}: {quantas}")
    print(f"Segredos de MFA: {len(usuarios)}")
    for chave, quantas in sorted(por_chave_mfa.items()):
        print(f"  {chave}: {quantas}")

    distintas = set(por_chave) | set(por_chave_mfa)
    if len(distintas) > 1:
        print()
        print(
            f"ATENÇÃO: {len(distintas)} chaves em uso. Uma rotação foi "
            "interrompida no meio, ou está em andamento."
        )
    return 0


def _rotacionar(session: Session, antigo: KeyProvider, novo: KeyProvider) -> int:
    """Reembrulha todas as DEKs da chave antiga para a nova.

    O texto cifrado não é tocado: só o campo `wrapped_dek` e o `key_id`.
    """
    if antigo.key_id == novo.key_id:
        # Com o id derivado do material, isto significa literalmente a MESMA
        # chave — não apenas o mesmo nome.
        print(f"A chave nova é idêntica à atual ({antigo.key_id}). Nada a fazer.")
        return 1

    versoes = list(session.scalars(select(SecretVersionModel)).all())
    usuarios = list(
        session.scalars(
            select(UserModel).where(UserModel.mfa_secret_wrapped_dek.is_not(None))
        ).all()
    )

    print(f"Rotacionando {len(versoes)} versão(ões) e {len(usuarios)} segredo(s) de MFA")
    print(f"  de : {antigo.key_id}")
    print(f"  para: {novo.key_id}")
    print()

    reembrulhadas = 0
    puladas = 0

    for versao in versoes:
        if versao.key_id == novo.key_id:
            puladas += 1  # já rotacionada; retomada depois de interrupção
            continue
        try:
            dek = antigo.unwrap(versao.wrapped_dek)
        except ValidationError:
            print(
                f"  FALHA na versão {versao.id}: a chave antiga não desembrulha. "
                "Nada foi gravado."
            )
            session.rollback()
            return 1
        versao.wrapped_dek = novo.wrap(dek)
        versao.key_id = novo.key_id
        reembrulhadas += 1

    for usuario in usuarios:
        if usuario.mfa_key_id == novo.key_id:
            puladas += 1
            continue
        try:
            dek = antigo.unwrap(usuario.mfa_secret_wrapped_dek)
        except ValidationError:
            print(f"  FALHA no MFA de {usuario.email}. Nada foi gravado.")
            session.rollback()
            return 1
        usuario.mfa_secret_wrapped_dek = novo.wrap(dek)
        usuario.mfa_key_id = novo.key_id
        reembrulhadas += 1

    session.commit()
    print(f"Pronto: {reembrulhadas} reembrulhada(s), {puladas} já estavam na chave nova.")
    print()
    print("O texto cifrado dos segredos NÃO foi alterado — só as DEKs.")
    if isinstance(novo, LocalKeyProvider):
        print(
            "Atualize VAULT_MASTER_KEY_B64 com a chave nova ANTES de reiniciar "
            f"(as DEKs agora respondem a {novo.key_id})."
        )
    else:
        print(f"Atualize VAULT_KMS_KEY_ID para {novo.key_id} antes de reiniciar.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rotaciona a chave-mestra sem reescrever os segredos."
    )
    grupo = parser.add_mutually_exclusive_group(required=True)
    grupo.add_argument(
        "--conferir",
        action="store_true",
        help="Mostra quais chaves estão em uso, sem alterar nada.",
    )
    grupo.add_argument(
        "--nova-chave", metavar="BASE64", help="Rotaciona para uma chave local."
    )
    grupo.add_argument(
        "--kms", metavar="ARN", help="Rotaciona para uma chave do AWS KMS."
    )
    parser.add_argument("--region", help="Região do KMS.")
    args = parser.parse_args()

    settings = get_settings()
    engine = create_engine(settings.database_url, future=True)
    session: Session = sessionmaker(bind=engine, future=True)()

    if args.conferir:
        raise SystemExit(_conferir(session))

    atual = _provedor_atual(settings)

    if args.nova_chave:
        try:
            material = base64.b64decode(args.nova_chave, validate=True)
        except Exception:  # noqa: BLE001
            print("A chave nova não é base64 válido.", file=sys.stderr)
            raise SystemExit(1) from None
        if len(material) != 32:
            print("A chave nova deve decodificar para 32 bytes.", file=sys.stderr)
            raise SystemExit(1)
        # O identificador precisa diferir do atual, senão a retomada não
        # distingue o que já foi rotacionado do que falta.
        novo: KeyProvider = LocalKeyProvider(material, key_id=_id_da_chave(material))
    else:
        novo = KmsKeyProvider(args.kms, region=args.region)

    raise SystemExit(_rotacionar(session, atual, novo))


def _id_da_chave(material: bytes) -> str:
    """Identificador derivado do MATERIAL da chave, não de um contador.

    Corrige um bug real: com um contador (`local-dev` -> `local-dev-2`),
    rotacionar de volta para a chave anterior produzia de novo `local-dev-2`,
    e a checagem de "já rotacionado" pulava registros que na verdade estavam
    protegidos por outra chave — deixando segredos ilegíveis depois da troca.

    Derivar do material torna a afirmação verdadeira: mesmo identificador
    significa mesma chave. São 12 hex de SHA-256 — o suficiente para
    distinguir chaves, e não é segredo: só identifica, não revela.
    """
    digest = hashlib.sha256(material).hexdigest()[:12]
    return f"local-{digest}"


if __name__ == "__main__":
    main()
