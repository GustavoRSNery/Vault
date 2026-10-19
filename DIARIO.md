# Diário do Vault

Registro do que foi feito em modo autônomo (`/afk`), para retomada. Mais
recente primeiro. O "porquê" de cada decisão importa mais que o "o quê" — o
código já conta o quê.

---

## 2026-10-19 — KMS e rotação de chave-mestra

**Decidi:** implementar o adaptador AWS KMS de verdade (boto3), com testes
contra um KMS simulado, em vez de deixar só o comentário "em produção vem do
KMS".
**Porque:** a porta existia mas o `EnvelopeCryptoService` estava acoplado ao
tipo concreto — a troca exigiria mexer nele, que é o que a porta evita. E sem
a rotação, o `key_id` gravado em cada segredo não servia para nada.
**Descartei:** esperar uma conta AWS. O adaptador é testável com cliente
simulado, e o que importa é o contrato, não a AWS.

**Decidi também:** produção recusa subir sem `VAULT_KMS_KEY_ID`.
**Porque:** configuração que "funciona" com a chave no processo é pior que uma
que falha ao subir — o erro só apareceria no vazamento.
**Reversível:** se incomodar, é remover o `model_validator` em `config.py`.

**Feito:** porta `KeyProvider`, adaptador `KmsKeyProvider`, seleção por
configuração e `app.tools.rotacionar_kek` (com `--conferir`, `--nova-chave`
e `--kms`). boto3 é extra opcional com import tardio.

**Validado:** 364 testes em SQLite e Postgres. Cinco mutantes mortos. No
ambiente real: rotacionei a KEK, reiniciei a API, e os 7 segredos continuaram
legíveis com o mesmo conteúdo (sha256 conferido um a um).
**Commit:** `794a598` KMS como provedor da chave-mestra, com rotação de KEK

**Surpresa:** o `key_id` vinha do nome (`local-dev` → `local-dev-2`), então
rotacionar de volta para a chave anterior gerava o mesmo identificador e a
checagem de "já rotacionado" **pulava registros protegidos por outra chave** —
eles ficariam ilegíveis depois da troca. Só apareceu rotacionando de ida e
volta no ambiente real; nenhum teste unitário pegaria. Agora o identificador é
a impressão digital do material.

---

## 2026-10-19 — Skill AFK e este diário

**Decidi:** criar `/afk` com as preferências já estabelecidas, em vez de
re-perguntar a cada sessão.
**Porque:** ele pediu para eu decidir por ele e registrar. A skill fixa o que
já foi decidido (tudo local, commit sem pedir, mutação obrigatória, Postgres
ao mexer em SQL, validar no navegador, honestidade acima de tela bonita) e a
regra central: decidir e anotar, nunca perguntar.
**Commit:** `4e22ec6`

---

## 2026-10-19 — Exportação da trilha para destino externo

**Decidi:** Exportar com porta (`SiemExporter`) + arquivo local como primeira
implementação, em vez de integrar direto com um SIEM real.
**Porque:** não há SIEM disponível no ambiente local, e o valor está na
*mecânica* da ancoragem, não no destino. Trocar o destino depois é uma linha
em `get_siem_exporter`.
**Descartei:** esperar um SIEM de verdade — deixaria o aviso amarelo da tela
de integridade indefinidamente, e ele era o último buraco estrutural da
auditoria.

**Feito:** `POST /auditoria/exportar` envia os eventos pendentes e grava a
âncora na última sequência do lote. A ordem é envio → âncora (nunca o
inverso: ancorar antes criaria âncora para evento que não saiu, e a
verificação acusaria fraude onde houve falha de rede). A tela ganhou o botão
e mostra "N de M ancorados".

**Validado:** 340 testes em SQLite e Postgres. Três mutantes mortos (ancorar
antes de enviar, retomada em 0, registrar toda exportação). No navegador:
87 de 87 ancorados, aviso de trecho pendente some ao convergir.
`scripts/prova_ancora.py` demonstra contra o Postgres real — 0 quebras sem
âncora, 3 com.
**Commit:** `6fcf3c0` Exportação da trilha para destino externo, com ancoragem

**Surpresa:** a exportação se auto-alimentava. Cada rodada gerava um evento
`trilha_exportada` que virava pendência da próxima, para sempre — uma
exportação agendada a cada 5 min encheria a trilha sozinha num sistema
ocioso. Corrigido: só registra quando exportou algo além do próprio rastro.

---

## 2026-10-19 — `vault.local` como endereço

**Decidi:** manter os três endereços (`vault.local`, `vault.localhost`,
`localhost:8080`) em vez de trocar por um só.
**Porque:** `vault.local` exige linha no `hosts` — que custou quatro
tentativas e elevação manual. `vault.localhost` resolve sozinho e mantém
`docker compose up` suficiente numa máquina nova da equipe.
**Descartei:** só `vault.local` — quebraria para quem clonar o projeto.

**Commit:** `467233f` Atende também em vault.local

---

## 2026-10-19 — Quatro ondas de telas (6 → 43 de 57)

**Decidi:** construir em ondas por domínio completo (domínio → persistência →
rota → tela → teste), em vez de fazer todas as telas rasas primeiro.
**Porque:** tela sem backend é maquete, e maquete não é "pronto". Cada onda
entrega função de verdade.

**Feito:**
- **Administração** — pessoas, papéis, políticas com simulador de efeito
- **Inventário** — dispositivos, credenciais com custódia exclusiva e
  rotação, certificados com faixas de expiração
- **Aprovações** — acesso temporário que caduca sozinho
- **Busca e alertas** — ambos filtrados por permissão no servidor; 404 honesto

**Decisões de segurança que podem ser questionadas depois:**
- Concessão temporária **soma**, nunca derruba um `deny` explícito. Compor com
  OR deixaria uma aprovação de emergência furar proibição deliberada.
- Credencial **nunca rotacionada conta como atrasada** — é o pior caso (senha
  de fábrica) e tratá-la como "sem informação" a esconderia do relatório.
- Busca **não casa pelo valor** do segredo: permitiria extraí-lo por tentativa
  e erro, caractere a caractere.
- Alertas **derivados, não gravados**: alerta persistido precisa ser apagado
  quando a causa some, e esquecer produz alarme falso.

**Commits:** `da1a9d3`, `2a41b79`, `0fc6a61`, `e0ee8eb`, `09e102d`, `6a2a406`,
`92a6b92`

**Surpresa:** o SQLite devolve `datetime` **sem** timezone mesmo em coluna
`DateTime(timezone=True)`, e o Postgres devolve **com**. Ler um certificado
estourava `TypeError` num dialeto só. Terceira vez que essa divergência morde
neste projeto — normalizado na fronteira (`_aware`), com três testes nomeados.

---

## Em aberto

- [ ] **Quórum Shamir para desselar cofre** — hoje desselar é ação de um
      administrador só. Partir a operação entre N pessoas é o que resta da
      selagem. Não depende de nada externo.
- [ ] **Destino inviolável de verdade** para a exportação — o arquivo local
      não é (quem tem o disco reescreve os dois lados). Precisa de Splunk HEC,
      CloudWatch ou bucket com Object Lock. **BLOQUEADO:** exige serviço
      externo e credencial.
- [ ] **Recuperação de senha e convite de usuário** — **BLOQUEADO:** exige
      envio de e-mail (SES ou equivalente).
- [ ] **Regras de notificação** — **BLOQUEADO:** exige canal de envio.
- [ ] **Fase 2: acesso de máquina para RPAs** — AppRole, leases, consumo.
      5 telas do inventário.
- [ ] **Fase 3: gravação de sessão** — 3 telas. Escopo grande, avaliar se vale.
- [ ] **Configurações na interface** — prazos e retenção hoje por variável de
      ambiente. Baixo valor enquanto o sistema tem um administrador só.
