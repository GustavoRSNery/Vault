"""Revisao adversarial contra o sistema no ar.

Uso:  docker compose up -d && python scripts/revisao_seguranca.py

Procura o que QUEBRA, nao confirma o que funciona: cada bloco e uma tentativa
de furar uma garantia que o produto promete. Complementa a suite de testes, que
exercita o codigo isoladamente — aqui o alvo e o sistema montado, atras do
nginx, com os dados de demonstracao.

Sai com as falhas listadas no fim. Depende do ambiente de demonstracao
(criar_admin + popular_demo + popular_inventario) e nao altera nada que nao
restaure: a conta desativada no bloco 8 e reativada em seguida.
"""

import json
import urllib.error
import urllib.request

BASE = "http://vault.localhost/api/v1"
falhas = []


def chamar(caminho, token=None, metodo="GET", corpo=None):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(BASE + caminho, data=dados, method=metodo)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read() or b"").decode("utf-8", "replace")


def login(email, senha):
    s, d = chamar("/auth/login", metodo="POST", corpo={"email": email, "password": senha})
    assert s == 200, (s, d)
    return json.loads(d)["tokens"]["access_token"]


def checar(nome, condicao, detalhe=""):
    marca = "ok  " if condicao else "FALHA"
    print(f"  [{marca}] {nome}")
    if not condicao:
        falhas.append(f"{nome} — {detalhe}")
        if detalhe:
            print(f"          {detalhe}")


admin = login("ana.souza@exemplo.com.br", "SenhaForteDeDev2026")
cont = login("contador@exemplo.com.br", "SenhaDoContador2026")

print("=== 1. Escalada de privilegio pela administracao ===")
for rota, metodo, corpo in [
    ("/admin/usuarios", "GET", None),
    ("/admin/politicas", "GET", None),
    ("/admin/papeis", "GET", None),
    ("/admin/politicas/contabil-leitura/regras", "PUT",
     {"rules": [{"path": "cofres/*", "capabilities": ["reveal"], "effect": "allow"}]}),
]:
    s, _ = chamar(rota, cont, metodo, corpo)
    checar(f"{metodo} {rota} negado para carteira limitada", s == 403, f"status {s}")

print()
print("=== 2. Reescrever a propria politica para ganhar acesso ===")
s, _ = chamar("/admin/politicas/contabil-leitura/regras", cont, "PUT", {
    "rules": [{"path": "cofres/*", "capabilities": ["reveal", "admin"], "effect": "allow"}]
})
checar("contadora nao reescreve a propria politica", s == 403, f"status {s}")
s, corpo = chamar("/cofres", cont)
cofres = [c["name"] for c in json.loads(corpo)]
checar("e segue vendo so o cofre dela", cofres == ["contabil"], f"ve {cofres}")

print()
print("=== 3. Furar o deny com concessao temporaria ===")
s, corpo = chamar("/solicitacoes", cont, "POST", {
    "path": "cofres/contabil/segredos/token-sefaz",
    "capabilities": ["reveal"], "reason": "Tentativa de furar o deny", "hours": 4,
})
pid = json.loads(corpo)["id"] if s == 201 else None
if pid:
    s2, _ = chamar(f"/solicitacoes/{pid}/aprovar", admin, "POST", {"note": "aprovado"})
    s3, c3 = chamar("/cofres/contabil/segredos/token-sefaz/revelar", cont, "POST")
    checar("deny explicito resiste a concessao aprovada", s3 == 403, f"status {s3}")
    checar("e o valor nao vaza no corpo do erro",
           "token" not in c3.lower() or "sefaz" in c3.lower(), c3[:80])

print()
print("=== 4. Auto-aprovacao ===")
s, corpo = chamar("/solicitacoes", admin, "POST", {
    "path": "cofres/rh/segredos/portal-folha",
    "capabilities": ["reveal"], "reason": "Pedido do proprio admin", "hours": 1,
})
if s == 201:
    meu = json.loads(corpo)["id"]
    s2, c2 = chamar(f"/solicitacoes/{meu}/aprovar", admin, "POST", {"note": "eu mesmo"})
    checar("admin nao aprova o proprio pedido", s2 == 409, f"status {s2}")

print()
print("=== 5. Custodia: roubar credencial de outra pessoa ===")
s, corpo = chamar("/credenciais", admin)
creds = json.loads(corpo)
em_custodia = next((c for c in creds if c["custodia_aberta"]), None)
if em_custodia:
    s2, _ = chamar(f"/credenciais/{em_custodia['id']}/retirar", admin, "POST",
                   {"reason": "segunda retirada", "hours": 1})
    checar("segunda retirada bloqueada", s2 == 409, f"status {s2}")

print()
print("=== 6. Busca como vetor de descoberta ===")
s, corpo = chamar("/busca?termo=postgres", cont)
dados = json.loads(corpo)
checar("busca nao revela recurso fora do alcance", dados["total"] == 0, str(dados))
s, corpo = chamar("/busca?termo=producao", cont)
checar("nem por termo generico", json.loads(corpo)["total"] == 0, corpo[:120])

print()
print("=== 7. Enumeracao de usuario pelo login ===")
import time
tempos = {}
for rotulo, email, senha in [
    ("inexistente", "nao-existe-zzz@exemplo.com.br", "qualquer-senha-123456"),
    ("existente", "contador@exemplo.com.br", "senha-errada-propositalmente"),
]:
    inicio = time.monotonic()
    s, corpo = chamar("/auth/login", metodo="POST", corpo={"email": email, "password": senha})
    tempos[rotulo] = time.monotonic() - inicio
    msg = json.loads(corpo).get("erro", {}).get("mensagem", "")
    print(f"     {rotulo:12} status={s} msg={msg!r} tempo={tempos[rotulo]:.3f}s")
razao = max(tempos.values()) / max(min(tempos.values()), 0.001)
checar("tempo de resposta nao denuncia a existencia", razao < 3.0, f"razao {razao:.1f}x")

print()
print("=== 8. Token de conta desativada ===")
s, corpo = chamar("/admin/usuarios", admin)
usuarios = json.loads(corpo)
alvo = next((u for u in usuarios if u["email"] == "contador@exemplo.com.br"), None)
if alvo:
    s1, _ = chamar(f"/admin/usuarios/{alvo['id']}/desativar", admin, "POST")
    s2, _ = chamar("/auth/me", cont)
    checar("token de conta desativada para de valer", s2 == 401, f"status {s2}")
    chamar(f"/admin/usuarios/{alvo['id']}/ativar", admin, "POST")

print()
print("=== 9. Auditoria: a carteira limitada ve so os proprios eventos ===")
cont = login("contador@exemplo.com.br", "SenhaDoContador2026")
s, corpo = chamar("/auditoria?limite=100", cont)
trilha = json.loads(corpo)
atores = {e["actor_label"] for e in trilha["eventos"]}
checar("escopo proprio na trilha", trilha["escopo"] == "proprios", trilha["escopo"])
checar("e nenhum evento de terceiro", atores <= {"contador@exemplo.com.br"}, str(atores))

print()
print("=" * 60)
if falhas:
    print(f"{len(falhas)} FALHA(S):")
    for f in falhas:
        print("  -", f)
else:
    print("Nenhuma falha encontrada nas 9 frentes testadas.")
