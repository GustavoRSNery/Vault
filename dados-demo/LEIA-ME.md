# Dados de demonstração

`vault_demo.sql` é um dump do Postgres com o cofre já povoado: cofres,
segredos, credenciais, certificados, dispositivos, aplicações e a trilha
de auditoria. Todos os dados são fictícios.

## Como restaurar

Com os containers no ar (`docker compose up -d`):

```bash
docker compose exec -T db psql -U vault -d vault < dados-demo/vault_demo.sql
```

O dump usa `--clean --if-exists`, então sobrescreve o que estiver lá. Para
começar do zero sem ele, basta subir os containers: o schema é criado no
boot e as ferramentas de `backend/app/tools/` populam o resto.

## Contas

As senhas **não** vêm no dump — só os hashes Argon2, que são
irreversíveis. Para entrar, crie um administrador:

```bash
docker compose exec api python -m app.tools.criar_admin admin@exemplo.com.br "sua-senha-forte"
```

## Sobre os segredos cifrados

Os valores guardados nos cofres estão cifrados com a chave-mestra de
**desenvolvimento**, que é o valor padrão embutido no `docker-compose.yml`
(`VAULT_MASTER_KEY_B64`). Com os containers padrão eles decifram
normalmente.

Se você definir uma chave própria, os segredos deste dump deixam de ser
legíveis — o que é o comportamento correto, e a razão de a chave de
produção nunca viver no repositório.

## Para popular do zero, sem o dump

```bash
docker compose exec api python -m app.tools.criar_admin admin@exemplo.com.br "senha-forte"
docker compose exec api python -m app.tools.popular_demo
docker compose exec api python -m app.tools.popular_inventario
```
