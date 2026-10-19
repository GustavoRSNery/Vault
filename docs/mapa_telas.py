"""Cruza o inventario das 57 telas do documento de arquitetura com o que existe.

Uso:  python docs/mapa_telas.py

Classifica cada tela como:
  PAGINA   - rota propria na aplicacao
  EMBUTIDA - entregue dentro de outra tela (ex.: lixeira no detalhe do cofre)
  ABERTA   - nao existe

A tabela ESTADO e mantida a mao: e um julgamento sobre o que conta como
entregue, nao algo que da para extrair do codigo. "EMBUTIDA" quer dizer que a
funcao existe dentro de outra tela — a lixeira vive no detalhe do cofre, e
espalha-la numa rota propria so para bater a contagem do papel seria pior.
"""

import pathlib

INVENTARIO = pathlib.Path(__file__).with_name("inventario-telas.md")

# tela -> (situacao, onde)
ESTADO = {
    # Autenticacao
    "Login": ("PAGINA", "/login"),
    "Desafio MFA": ("EMBUTIDA", "no próprio login, quando o MFA está ativo"),
    "Configurar MFA": ("EMBUTIDA", "/perfil"),
    "Esqueci a senha": ("ABERTA", "exige envio de e-mail"),
    "Redefinir senha": ("ABERTA", "exige envio de e-mail"),
    "Sistema selado": ("EMBUTIDA", "aviso no detalhe do cofre + alerta"),
    # Dashboard
    "Dashboard pessoal": ("PAGINA", "/"),
    "Dashboard de segurança": ("EMBUTIDA", "/alertas"),
    # Cofres & Segredos
    "Lista de cofres": ("PAGINA", "/cofres"),
    "Novo/editar cofre": ("EMBUTIDA", "formulário em /cofres"),
    "Detalhe do cofre": ("PAGINA", "/cofres/:nome"),
    "Permissões do cofre": ("EMBUTIDA", "/admin/politicas, por caminho"),
    "Detalhe do segredo": ("EMBUTIDA", "linha expansível no detalhe do cofre"),
    "Criar/editar segredo": ("EMBUTIDA", "formulário no detalhe do cofre"),
    "Versões do segredo": ("EMBUTIDA", "histórico no detalhe do cofre"),
    "Lixeira do cofre": ("EMBUTIDA", "seção no detalhe do cofre"),
    "Busca global": ("PAGINA", "/busca"),
    # Dispositivos
    "Dispositivos": ("PAGINA", "/dispositivos"),
    "Cadastro de dispositivo": ("EMBUTIDA", "formulário em /dispositivos"),
    "Credenciais": ("PAGINA", "/credenciais"),
    "Detalhe da credencial": ("EMBUTIDA", "histórico de custódia em /credenciais"),
    "Check-out": ("EMBUTIDA", "formulário de retirada em /credenciais"),
    "Políticas de rotação": ("EMBUTIDA", "prazo por credencial; agenda automática em aberto"),
    # Aprovacoes
    "Minhas solicitações": ("PAGINA", "/solicitacoes"),
    "Nova solicitação": ("EMBUTIDA", "formulário em /solicitacoes"),
    "Fila de aprovação": ("EMBUTIDA", "seção em /solicitacoes"),
    "Detalhe da solicitação": ("EMBUTIDA", "cartão de decisão em /solicitacoes"),
    # Acesso de aplicacao (fase 2)
    "Aplicações": ("ABERTA", "fase 2 — acesso de máquina"),
    "Detalhe da aplicação": ("ABERTA", "fase 2"),
    "Credenciais AppRole": ("ABERTA", "fase 2"),
    "Tokens e leases": ("ABERTA", "fase 2"),
    "Consumo": ("ABERTA", "fase 2"),
    # Certificados
    "Certificados": ("PAGINA", "/certificados"),
    "Detalhe/upload": ("EMBUTIDA", "formulário em /certificados"),
    "Expirações": ("EMBUTIDA", "faixas acumuladas em /certificados + /alertas"),
    # Sessoes (fase 3)
    "Sessões ativas": ("ABERTA", "fase 3 — gravação de sessão"),
    "Gravações": ("ABERTA", "fase 3"),
    "Player de sessão": ("ABERTA", "fase 3"),
    # Auditoria
    "Trilha de auditoria": ("PAGINA", "/auditoria"),
    "Detalhe do evento": ("EMBUTIDA", "linha da trilha"),
    "Relatórios": ("EMBUTIDA", "/alertas cobre o essencial"),
    "Relatório de expirações": ("EMBUTIDA", "/certificados + /alertas"),
    # Alertas
    "Central de alertas": ("PAGINA", "/alertas"),
    "Regras de notificação": ("ABERTA", "exige canal de envio (SES/WhatsApp)"),
    # Pessoas & Grupos
    "Usuários": ("PAGINA", "/admin/usuarios"),
    "Detalhe/convite": ("EMBUTIDA", "editor de papéis; convite por e-mail em aberto"),
    "Grupos": ("EMBUTIDA", "papéis em /admin/usuarios"),
    "Papéis e políticas": ("PAGINA", "/admin/politicas"),
    "Editor de política": ("PAGINA", "/admin/politicas, com simulador"),
    # Administracao
    "Configurações": ("ABERTA", "prazos e retenção ainda por variável de ambiente"),
    "Integrações": ("ABERTA", "fase 3"),
    "Selagem e chaves": ("EMBUTIDA", "selar/desselar no detalhe do cofre; KMS em aberto"),
    "Backups": ("ABERTA", "responsabilidade de infraestrutura"),
    "Saúde do sistema": ("EMBUTIDA", "/saude na API"),
    # Comuns
    "Perfil": ("PAGINA", "/perfil"),
    "Estados vazios e erro": ("EMBUTIDA", "componentes Vazio/Alerta/Carregando"),
    "404": ("PAGINA", "rota curinga"),
}

texto = INVENTARIO.read_text(encoding="utf-8")
linhas = [l for l in texto.splitlines() if l.startswith("| ") and "---" not in l]
telas = []
for linha in linhas:
    partes = [p.strip() for p in linha.strip("|").split("|")]
    if len(partes) >= 3 and partes[0] not in ("Tela",):
        telas.append(partes[0])

print(f"Telas no inventario: {len(telas)}")
print()

faltando_no_mapa = [t for t in telas if t not in ESTADO]
if faltando_no_mapa:
    print("NAO MAPEADAS:", faltando_no_mapa)
    print()

contagem = {"PAGINA": 0, "EMBUTIDA": 0, "ABERTA": 0}
for tela in telas:
    situacao, onde = ESTADO.get(tela, ("ABERTA", "?"))
    contagem[situacao] += 1

total = len(telas)
entregues = contagem["PAGINA"] + contagem["EMBUTIDA"]
print(f"  PAGINA propria : {contagem['PAGINA']:>2}")
print(f"  EMBUTIDA       : {contagem['EMBUTIDA']:>2}")
print(f"  ABERTA         : {contagem['ABERTA']:>2}")
print(f"  --------------------")
print(f"  ENTREGUES      : {entregues:>2} de {total}  ({entregues*100//total}%)")
print()
print("EM ABERTO:")
for tela in telas:
    situacao, onde = ESTADO.get(tela, ("ABERTA", "?"))
    if situacao == "ABERTA":
        print(f"  - {tela:28} {onde}")
