"""Gera uma chave-mestra para desenvolvimento.

Uso:  python -m app.tools.gerar_chave

A saída vai para VAULT_MASTER_KEY_B64 no .env. Em produção a chave vive no
KMS e esta ferramenta não é usada.
"""

import base64
import os


def main() -> None:
    chave = base64.b64encode(os.urandom(32)).decode()
    print(f"VAULT_MASTER_KEY_B64={chave}")


if __name__ == "__main__":
    main()
