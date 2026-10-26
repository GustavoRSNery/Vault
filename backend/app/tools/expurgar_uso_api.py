"""Apaga do registro de uso da API o que passou da retencao.

Uso:  python -m app.tools.expurgar_uso_api [dias]

Sem argumento, usa `VAULT_API_USO_RETENCAO_DIAS` (90 por padrao). Feito para
rodar por agendador (cron, Task Scheduler) uma vez por dia.

Ferramenta separada e nao expurgo automatico no boot: apagar dado em
background, sem ninguem pedir, e como registros somem sem explicacao. Aqui a
remocao tem um comando, um responsavel e uma saida que diz quanto saiu.

NAO toca na trilha de auditoria (`auditoria_eventos`), que nao expira.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta

from ..api.deps import get_session_factory
from ..config import get_settings
from ..infrastructure.db.apiusage_repo import RegistroDeUsoSql


def main() -> int:
    settings = get_settings()

    if len(sys.argv) > 1:
        try:
            dias = int(sys.argv[1])
        except ValueError:
            print(f"dias invalido: {sys.argv[1]!r}")
            return 2
    else:
        dias = settings.api_uso_retencao_dias

    if dias <= 0:
        print("Retencao desligada (dias <= 0). Nada foi apagado.")
        return 0

    corte = datetime.now(UTC) - timedelta(days=dias)
    sessao = get_session_factory(settings)()
    try:
        quantas = RegistroDeUsoSql(sessao).expurgar(corte)
    finally:
        sessao.close()

    print(f"Retencao de {dias} dia(s): {quantas} chamada(s) apagada(s).")
    print(f"Corte: {corte.isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
