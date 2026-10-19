# Diário do Vault

Registro do que foi feito em modo autônomo (`/afk`), para retomada. Mais
recente primeiro. O "porquê" de cada decisão importa mais que o "o quê" — o
código já conta o quê.

---

## 2026-10-19 — Consumo por segredo (fecha a fase 2)

**Decidi:** derivar o consumo da trilha de auditoria, em vez de criar tabela
de contadores.
**Porque:** a trilha já é a fonte de verdade do que foi lido. Um contador
paralelo divergiria dela no primeiro erro de escrita, e aí haveria dois
números e nenhuma certeza sobre qual vale.
**Descartei:** tabela `consumo` com incremento a cada leitura — mais rápida de
consultar, mas é a segunda fonte de verdade que sempre diverge.
**Custo aceito:** uma agregação por consulta. É tela de análise, ninguém abre
em laço.

**Feito:** `GET /aplicacoes/{nome}/consumo` com o que foi lido, o que foi
negado, o escopo atual e — o que justifica a tela — os caminhos concedidos e
**nunca usados**.

**Validado:** 496 testes em SQLite e Postgres, 4 mutantes mortos. No ambiente
real: 10 leituras contadas por caminho, 6 negativas em `token-sefaz`
(negado na política) e o alerta de escopo ocioso sem falso positivo.
**Commit:** `0eb0778` Consumo por segredo das aplicações

**Surpresa (duas):**

1. O cofre era resolvido **antes** da checagem de escopo, então a resposta
   distinguia "cofre não existe" (404) de "fora do escopo" (403). Um robô
   comprometido mapearia todos os cofres pela mensagem de erro, sem permissão
   para ler nenhum. Só apareceu porque o teste de negativas usou um cofre
   inexistente por acaso.
2. `nunca_lidos` acusava falso positivo: `cofres/contabil` (sem curinga) casa
   só com o caminho exato, e as leituras vão para `cofres/contabil/segredos/x`
   — o cofre aparecia como ocioso com tudo sendo lido dentro dele. Alerta
   falso é pior que alerta nenhum: ensina a ignorar o aviso.

---

## 2026-10-19 — Acesso de máquina para RPAs (fase 2)

**Decidi:** AppRole (`role_id` público + `secret_id` segredo) com leases
curtos, em vez de dar ao robô uma conta de usuário.
**Porque:** usuário-robô é conta de pessoa sem pessoa — ninguém desliga quando
o robô é aposentado, e a auditoria não distingue de gente. Separar os dois
fatores permite rotacionar a credencial sem deploy.
**Descartei:** token permanente por aplicação (é a senha eterna no código com
outro nome).

**Decidi também:** a aplicação recebe política pelo mesmo mecanismo das
pessoas, via papel.
**Porque:** um sistema de permissão paralelo só para robôs é o que ninguém
lembraria de revisar. A primeira versão usava convenção de nome de política,
que quebraria em silêncio num rename — trocado por vínculo explícito.

**Feito:** domínio `machines`, 3 tabelas, 7 endpoints e a tela de Aplicações
com emissão de credencial, acessos em uso e botão de encerrar todos.

**Validado:** 484 testes em SQLite e Postgres. No ambiente real, 10 etapas do
ciclo de um RPA: cadastrar, emitir, autenticar, ler no escopo, recusar fora
dele, recusar o negado, mensagens idênticas para credencial errada e role_id
inexistente, encerrar acessos, e a trilha registrando `maquina:<nome>` como
ator sem `actor_id`.
**Commit:** `85eb6ce` Acesso de máquina para RPAs: AppRole e leases

**Surpresa (duas):**

1. **GRAVE** — o lease descartava as regras `deny` ao montar o escopo. Com
   `allow` em `cofres/contabil/*` e `deny` em `token-sefaz`, o robô LIA o
   token-sefaz: tinha mais acesso que a pessoa a quem a mesma política se
   aplica. Só apareceu validando no ambiente com a política real da
   contadora; os testes usavam políticas só de allow ou só de deny. O lease
   agora carrega as negações.
2. A API informava `papel: null` com o vínculo persistido certo — bug de
   exibição que faria diagnosticar o problema errado.

Dois mutantes sobreviveram e apontaram lacunas reais: nenhum teste cobria
aplicação com `deny`, e `compare_digest` vs `==` não é distinguível por teste
funcional (a diferença é temporal). O segundo virou teste estrutural.

---

## 2026-10-19 — Quórum Shamir para desselar

**Decidi:** os quinhões protegem um **token de desselagem**, não a chave-mestra.
**Porque:** partir a KEK seria o óbvio e é errado — no KMS ela não existe neste
processo para ser partida, e com chave local toda rotação invalidaria os
quinhões já distribuídos (as pessoas receberiam envelopes novos a cada
rotação). Com token independente, selar e rotacionar não se atrapalham.
**Descartei:** partir a KEK; e também guardar o token (só o hash vai ao banco,
senão quem lê o banco abre o cofre).

**Decidi também:** manter `/desselar` simples ao lado do com quórum, mas fazer
a rota simples **recusar** cofre com selo ativo.
**Porque:** forçar quórum em todo cofre inviabilizaria selagem de emergência.
Mas deixar a rota simples abrir tornaria o quórum contornável por quem tem
ADMIN — exatamente quem ele existe para conter.
**Reversível:** se quiser quórum obrigatório, é remover a rota simples.

**Feito:** Shamir sobre GF(256) implementado do zero, entidade `SeloComQuorum`,
3 rotas (`selar-com-quorum`, `desselar-com-quorum`, `selo`) e a cerimônia na
tela de detalhe do cofre, com confirmação explícita antes de fechar os
quinhões.

**Validado:** 436 testes em SQLite e Postgres. GF(256) conferido contra
implementação independente nos 65.536 pares. No ambiente real, 8 etapas:
selar, cofre fecha (423), admin não contorna (403), quinhão repetido não
soma, quinhões alheios não abrem, quórum correto abre, selo usado não reabre,
e a trilha registra tudo.
**Commit:** `c143ad3` Quórum Shamir para desselar cofre

**Surpresa:** um mutante **sobreviveu** — a validação de limiar 1 só era
exercitada via `selar_com_quorum`, onde o Shamir barra antes de o selo ser
construído. A regra não estava morta; o teste é que nunca chegava nela. Agora
a entidade é testada direto, o que importa porque o repositório a reconstrói
ao ler do banco (um registro adulterado com limiar 1 voltaria como selo que
não protege nada).

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

- [ ] **Destino inviolável de verdade** para a exportação — o arquivo local
      não é (quem tem o disco reescreve os dois lados). Precisa de Splunk HEC,
      CloudWatch ou bucket com Object Lock. **BLOQUEADO:** exige serviço
      externo e credencial.
- [ ] **Recuperação de senha e convite de usuário** — **BLOQUEADO:** exige
      envio de e-mail (SES ou equivalente).
- [ ] **Regras de notificação** — **BLOQUEADO:** exige canal de envio.
- [ ] **Rotação automática do secret_id** — hoje é emitir/revogar à mão.
- [ ] **Fase 3: gravação de sessão** — 3 telas. Escopo grande, avaliar se vale.
- [ ] **Configurações na interface** — prazos e retenção hoje por variável de
      ambiente. Baixo valor enquanto o sistema tem um administrador só.
