# Diário do Vault

Registro do que foi feito em modo autônomo (`/afk`), para retomada. Mais
recente primeiro. O "porquê" de cada decisão importa mais que o "o quê" — o
código já conta o quê.

---

## 2026-10-19 — Gravação de sessão (fase 3), em ports and adapters

**Pedido explícito:** fazer agora, com o que depende de externo deixado em
aberto para conectar, no padrão ports and adapters.

**Decidi:** DUAS portas, não uma — `CapturaDeSessao` e
`ArmazenamentoDeGravacao`.
**Porque:** respondem a perguntas diferentes (de onde os eventos vêm × onde a
gravação fica) e tendem a ter tecnologias diferentes. Juntá-las forçaria quem
troca o armazenamento a mexer na captura.
**Descartei:** porta única `GravadorDeSessao`.

**Decidi também:** os esqueletos (`ProxySsh`, `ArmazenamentoS3`) levantam
`NotImplementedError` em vez de devolver vazio.
**Porque:** um stub silencioso viraria "a gravação está ligada" numa
auditoria, e descobrir que não estava é a pior hora para descobrir.

**Decidi ainda:** os adaptadores declaram o que são — `captura_automatica` e
`imutavel`.
**Porque:** "gravação completa" e "o que a pessoa anotou" não podem parecer a
mesma coisa numa investigação. A tela usa a declaração para avisar.

**Feito:** domínio `sessions` (sem saber que SSH existe), 2 portas, 4
adaptadores (2 funcionando, 2 esboçados), 7 endpoints e as 3 telas do
inventário — ativas com encerrar/derrubar, histórico pesquisável e player com
timeline, velocidade e busca que salta para o instante.

**Validado:** 577 testes em SQLite e Postgres, 2 mutantes mortos. No ambiente
real, 10 etapas: abrir, registrar, recusar escrita alheia, isolar por
usuário, encerrar e arquivar, recusar evento tardio, reproduzir, buscar
dentro da gravação, e o admin revisando com rastro na trilha.
**Commits:** `107e7c3` gravação de sessão; `39275cf` documento de conexão

**Surpresa:** o volume `/gravacoes` nascia de root e o processo sem
privilégio não conseguia escrever — encerrar sessão dava 500. O Docker só
herda a propriedade quando o diretório já existe na imagem com o dono certo.
O mesmo já valia para `/exportacoes`, que funcionava por ter sido criado
antes; o Dockerfile agora cria as duas antes do `USER`. É o tipo de erro que
nenhum teste pega, porque só existe no container.

**Para conectar depois:** `docs/conectar-adaptadores.md` lista, para cada
porta, o que falta concretamente (token, bucket, credencial) e o trecho que
preenche o método.

---

## 2026-10-19 — Configurações operacionais pela interface

**Decidi:** expor só os prazos que são decisão operacional, e deixar os
limites de segurança como constantes no código.
**Porque:** a pergunta que separa os dois é *se alguém escolher o pior valor
possível, isso enfraquece a segurança?* Quórum mínimo de 2 ajustável viraria
1 na primeira vez que alguém se irritasse com a cerimônia. Configuração que
permite desligar a própria proteção é pior que configuração nenhuma: dá
impressão de flexibilidade e entrega um sistema que se desarma na pressa.
**Descartei:** expor tudo o que é constante hoje (incluindo `TOKEN_BYTES`,
`LIMIAR_MINIMO`, teto do lease).
**Na tela:** há um cartão explicando cada exclusão — senão alguém abre um
chamado pedindo para ajustar, e a resposta fica perdida numa conversa.

**Decidi também:** linha única por instalação, não por cofre.
**Porque:** configuração por cofre produziria combinações que ninguém revisa,
e "qual prazo vale aqui?" deixaria de ter resposta única.
**Reversível:** a chave primária é fixa em "unica"; passar a ter uma por
cofre exigiria migration, mas o domínio não impede.

**Feito:** domínio `settings` com faixas que recusam o absurdo (explicando o
porquê), 2 rotas, tela de Configurações, e os valores LIGADOS onde importam —
certificados, custódia, trilha e o tempo de exibição no front.

**Validado:** 527 testes em SQLite e Postgres, 2 mutantes mortos (ambos
tornando a configuração decorativa). No ambiente real: contadora lê e não
altera, limites recusam valores absurdos, e ampliar a faixa mudou
`api-rede` de "válido" para "vencendo" — a configuração surte efeito.
**Commit:** `6a7c889` Configurações operacionais pela interface

**Princípio que vale repetir:** configuração decorativa é pior que
inexistente. Alguém ajusta, acha que mudou algo, e só descobre o contrário
num incidente. Por isso cada ajuste tem um teste que prova a mudança de
comportamento, não só a persistência do número.

---

## 2026-10-19 — Rotação de credencial pelo próprio robô

**Decidi:** NÃO criar agendador interno de rotação.
**Porque:** um processo de rotação dentro do Vault competiria com o
orquestrador que a empresa já tem, e um cofre com cron embutido é mais uma
coisa para monitorar e mais um ponto de falha. Quem sabe quando é seguro
trocar é o próprio robô — entre dois ciclos, não no meio de um.
**Descartei:** job interno que rotaciona por calendário.
**Em troca:** endpoint `/maquina/renovar` (o robô se vira) + relatório de
vencimentos (quem quiser automatizar por fora tem os dados).

**Decidi também:** a credencial antiga ganha **10 minutos de graça** em vez
de morrer na hora.
**Porque:** matar na hora derrubaria um robô com a credencial velha em
memória no meio de um ciclo — a rotação existe para evitar incidente, não
para causar um. Curto de propósito: graça longa é credencial velha viva.
**Reversível:** `GRACA_PADRAO_MINUTOS` em `domain/machines/entities.py`.

**Feito:** `aposentar_com_graca` e `dias_para_vencer` no domínio, duas rotas,
e dois alertas no topo da tela de Aplicações.

**Validado:** 511 testes em SQLite e Postgres, 2 mutantes mortos. No ambiente
real: robô trocou a própria credencial, as duas autenticaram durante a graça,
credencial errada recusada (401), relatório pegou a que vence em 9 dias.
**Commit:** `7b73aa5` Rotação de credencial pelo próprio robô

**Detalhe que vale lembrar:** a nova credencial é emitida ANTES de a antiga
ser aposentada. Se a emissão falhar, a antiga continua intacta e o robô segue
funcionando — mesma lógica da exportação da trilha (enviar antes de ancorar).

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
- [ ] **Captura automática por proxy SSH** — a porta está pronta e o
      esqueleto escrito; falta o servidor intermediário. **BLOQUEADO** só
      pela infraestrutura, não pelo código. Ver docs/conectar-adaptadores.md.
