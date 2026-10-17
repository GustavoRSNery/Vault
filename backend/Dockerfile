# Imagem do backend do Vault.
FROM python:3.12-slim

# Não gravar .pyc e não bufferizar a saída: log aparece na hora no docker logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# As dependências vêm antes do código para que uma alteração em app/ não
# invalide a camada de instalação.
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
        "fastapi>=0.115" "uvicorn[standard]>=0.32" \
        "pydantic[email]>=2.9" "pydantic-settings>=2.6" \
        "sqlalchemy>=2.0" "alembic>=1.14" "psycopg[binary]>=3.2" \
        "argon2-cffi>=23.1" "cryptography>=43.0" \
        "pyjwt>=2.10" "pyotp>=2.9" "python-multipart>=0.0.12"

COPY app ./app

# Usuário sem privilégios: um cofre de senhas não roda como root.
RUN useradd --create-home --uid 10001 vault && chown -R vault:vault /app
USER vault

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/saude', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
