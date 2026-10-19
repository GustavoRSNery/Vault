"""Prova empirica: a ancora detecta a recostura que o encadeamento sozinho aprova.

Uso (de dentro do container, contra o banco real):

    docker compose cp scripts/prova_ancora.py api:/tmp/prova_ancora.py
    docker compose exec -e PYTHONPATH=/app -w /app api python /tmp/prova_ancora.py

Exige ao menos uma ancora: exporte a trilha antes (POST /auditoria/exportar).

Roda DENTRO do container, contra o Postgres real. Simula o atacante que altera
um evento e recalcula todos os hashes seguintes — a adulteracao "caprichada"
que uma cadeia verificada contra ela mesma sempre aprova.

Nao altera o banco: a adulteracao acontece em memoria, sobre a leitura.
"""

from dataclasses import replace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.domain.audit.events import verify_chain
from app.infrastructure.db.repositories import AuditRepository

engine = create_engine(get_settings().database_url, future=True)
session = sessionmaker(bind=engine, future=True)()
repo = AuditRepository(session)

eventos = repo.list_chain()
ancoras = repo.anchors()
print(f"trilha real: {len(eventos)} eventos, {len(ancoras)} ancora(s)")
print(f"  ancoras em: {[a.sequence for a in ancoras]}")

print()
print("1) estado atual")
print(f"   sem ancora : {len(verify_chain(eventos))} quebra(s)")
print(f"   com ancora : {len(verify_chain(eventos, anchors=ancoras))} quebra(s)")

print()
print("2) ATAQUE: alterar o evento 1 e recosturar TODOS os hashes seguintes")
adulterados = list(eventos)
original = adulterados[1].target_path
adulterados[1] = replace(adulterados[1], target_path="cofres/apagando-o-rastro")
for i in range(2, len(adulterados)):
    adulterados[i] = replace(
        adulterados[i], previous_hash=adulterados[i - 1].fingerprint()
    )
print(f"   evento 1: '{original}' -> '{adulterados[1].target_path}'")
print(f"   e {len(adulterados) - 2} elos seguintes recalculados")

sem = verify_chain(adulterados)
com = verify_chain(adulterados, anchors=ancoras)
print()
print("3) resultado")
print(f"   sem ancora : {len(sem)} quebra(s)  <- a cadeia 'confere' sozinha")
print(f"   com ancora : {len(com)} quebra(s)  <- o registro externo denuncia")
if com:
    print(f"   primeira: evento #{com[0].sequence}: {com[0].detail[:80]}")

print()
if not sem and com:
    print("PROVADO: so a ancora externa pega a recostura completa.")
else:
    print("INESPERADO: revisar.")
