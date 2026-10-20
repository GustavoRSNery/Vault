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

## 2026-10-20 — Chaves de API, acesso remoto e exportações

**Decidi:** tratar identificador de acesso remoto (código do AnyDesk, host do
RDP) como **dado comum, visível e copiável**, e nunca embutir senha no arquivo
`.rdp`.
**Porque:** o identificador diz *onde* a máquina está, não *como* entrar nela
— quem tem o número e não tem a senha não entra. Mascará-lo atrapalharia o uso
diário (alguém precisa ditar o número no telefone) sem proteger nada. Já a
senha dentro de um `.rdp` é senha no disco de quem baixou, fora do cofre e
fora da auditoria; é o padrão que as ferramentas do ramo seguem.

**Feito:**
- **Chaves de API** — governo completo (serviço, ambiente, formato de envio,
  escopo, onde é usada, responsável, vencimento). Tela nova, 6 rotas.
- **Acesso remoto nos dispositivos** — RDP por botão (arquivo gerado sob
  demanda), AnyDesk e Google Remote Desktop com código visível. Acesso que o
  sistema não intermedia tem botão de "registrar acesso".
- **Certificados** — ver detalhes, exportar JSON, excluir.
- **Credenciais** — exportar JSON, no mesmo tratamento.
- **`evoluir_schema`** — ferramenta de evolução de schema, no boot do compose.

**Decisões de segurança que podem ser questionadas depois:**
- O `.rdp` sai **sem senha e sem redirecionar disco local**: copiar-colar
  basta, e montar o disco de quem conecta numa máquina de produção é
  superfície de ataque sem ganho.
- **Exportação nunca carrega valor de segredo** — nem chave privada de
  certificado, nem senha de credencial. Um "exportar tudo" que os incluísse
  transformaria um clique de conveniência num vazamento que ninguém audita.
- **Excluir o governo não apaga o segredo** do cofre: um clique não pode
  remover a chave e o rastro ao mesmo tempo.
- **Revogar mantém o registro** — a auditoria quer saber que a chave existiu.
- Chave **revogada vence o relógio**: decisão humana não vira "expirada"
  depois.

**Surpresas (todas achadas com o sistema no ar, nenhuma pela suíte):**

1. **`create_all` nunca altera tabela existente.** A coluna
   `dispositivos.acessos` foi declarada, 651 testes ficaram verdes e a API
   subiu quebrada: `UndefinedColumn: column dispositivos.acessos does not
   exist`. Os testes montam o banco do zero a cada execução, então nenhum
   deles podia ver o problema — o verde era real e inútil ao mesmo tempo.
   Daí a ferramenta `evoluir_schema`, idempotente, no boot. Ela recusa
   remover coluna ou mudar tipo: isso perde dado e merece decisão humana.

2. **Default de lista nascendo como `{}`.** Na primeira versão da ferramenta,
   `acessos` ganhou `DEFAULT '{}'` porque o SQLAlchemy embrulha `default=list`
   num wrapper e `arg is list` dá falso. A linha antiga devolveria dict onde o
   código espera list, e o estouro aconteceria longe dali. Corrigido chamando
   o callable e serializando o que ele produz.

3. **O PUT de chave de API ignorava `expira_em`.** O formulário enviava a
   data, o schema não declarava o campo e o Pydantic descartava em silêncio:
   a chave ficava "sem vencimento" para sempre — o oposto do que a tela existe
   para fazer. De quebra, `exclude_none` tornava impossível *limpar* um
   vencimento, porque "mandei nulo" era indistinguível de "não mandei".
   Agora é `exclude_unset`.

4. **O seed de políticas só criava, nunca convergia.** `chaves-api` é entidade
   nova; em banco que já rodara o seed antes, a política ficava parada na
   versão antiga e a tela devolvia 403 — o RBAC estava certo, o seed é que
   ficara para trás. Mesma classe de problema do schema.

**Mutantes mortos:** `.rdp` com senha embutida; exportação de credencial com o
valor; `ORDER BY` sem `IS NULL` (passa no Postgres e **quebra no SQLite** — a
demonstração ao vivo de por que a suíte roda nos dois); default de lista como
dict; `expira_em` fora do schema; `exclude_none` de volta.

**Validação:** 659 testes nos **dois dialetos**; lint com `--max-warnings 0`
(config de ESLint criada — o script existia e falhava, o que é pior que não
ter); `npm run build` limpo; e verificação no navegador, com o `.rdp` real
baixado e conferido linha a linha (sem `password`) e os dois JSON exportados
sem nenhum campo de segredo.

---

## 2026-10-20 — Sessões, aplicações e integrações (itens 6, 7 e 8)

**Decidi:** separar "de onde partiu" de "o que consumiu" em dois campos da
sessão, e guardar do consumo apenas o **nome e o caminho** do segredo.
**Porque:** são duas perguntas diferentes que a revisão faz sobre a mesma
sessão — qual máquina abriu, e com que credencial. E porque saber que a
sessão usou `cofres/infra/segredos/senha-root` responde à auditoria sem
revelar nada: quem quiser o valor passa pela rota de revelar, que registra
evento próprio. Um campo de valor ali transformaria a lista de sessões num
despejo de segredos.

**Feito:**
- **Sessões** — `origem` (IP, hostname, dispositivo do inventário,
  user-agent) e `consumo` (credencial, chave de API, certificado, própria,
  não identificado). Colunas novas na tela: "De onde" e "Usou".
- **Aplicações** — o consumo do robô agora diz o **tipo** de cada segredo
  lido, com resumo "3 senhas, 1 chave de API". O tipo vem do cadastro do
  segredo, resolvido numa consulta só.
- **Integrações** — webhooks no padrão **Standard Webhooks**, com tela,
  fila visível, teste de ping e rotação de segredo.

**Por que Standard Webhooks.** O usuário pediu "o padrão mais robusto de
mercado". É a especificação aberta que Svix, Resend e Clerk adotaram, e
resolve os quatro problemas que derrubam uma integração caseira:
assinatura HMAC-SHA256 sobre `id.timestamp.corpo` (autenticidade), o
timestamp dentro da assinatura (repetição), reentrega com backoff e jitter
por ~75 horas (entrega), e `webhook-id` estável entre tentativas para o
destino deduplicar (duplicata).

**Decisões de segurança que podem ser questionadas depois:**
- **O segredo de assinatura aparece uma vez**, no cadastro e na rotação.
  Repeti-lo numa listagem o espalharia por log de proxy, histórico de
  navegador e captura de tela de quem só conferia uma URL.
- **A fila de entregas não mostra o corpo do evento** — ele carrega
  caminhos de segredos.
- **`http` simples é recusado**: a assinatura prova a origem, não esconde o
  conteúdo.
- **O entregador padrão é o de ensaio**, que não sai para a rede. Um
  sistema recém-instalado que começasse a disparar eventos de cofre para
  fora seria uma surpresa desagradável; `EntregadorHttp` está pronto e a
  troca é uma linha, porque o resto só conhece a porta.
- **Publicar não faz rede.** Se fizesse, revelar um segredo passaria a
  depender de um servidor de terceiro estar no ar. Enfileira e devolve; o
  despacho é outra operação, chamada por um agendador.
- **Rotacionar invalida o segredo anterior na hora.** A especificação
  permite enviar duas assinaturas na transição, mas isso exigiria guardar o
  segredo antigo "por via das dúvidas" — o oposto de rotacionar. A tela
  avisa que as entregas falham até os dois lados trocarem.
- **O consumo conta caminhos, não leituras.** Um robô que lê a mesma senha
  mil vezes usa *uma* senha; somar leituras faria essa senha parecer o
  grosso do escopo.

**Surpresas:**

1. **Um mutante ficou no código e os testes passaram.** A bateria de
   mutação tinha um backup gerado depois de uma execução interrompida, e a
   verificação de janela de tempo voltou como `pass`. Os testes de
   repetição continuaram verdes — ou seja, não cobriam o que eu supunha. O
   episódio vale mais que o bug: *bateria de mutação precisa provar que o
   código está íntegro antes de começar*, senão ela mede o mutante contra
   si mesmo.

2. **Mutante do jitter sobreviveu por causa de `int()`.** O teste exercitava
   a primeira falha, onde a base é 5 segundos: `int(5 * 0.2 * x)` arredonda
   para zero e o jitter nem atua. Trocar `+` por `-` não quebrava nada.
   Reancorado na terceira falha, mais um teste provando que o jitter de fato
   varia — uma constante passaria no primeiro.

**Mutantes mortos:** 8 nas invariantes de webhook (janela de tempo,
`compare_digest`, id com ponto, http simples, id estável entre tentativas,
jitter, contador de falhas, corpo como texto), 1 na contagem por tipo, 2 na
ligação com a trilha (destino novo recebendo o histórico; marcador que não
avança sem assinante) e 1 no adaptador HTTP (410 que não desliga o destino).

**A ligação com os eventos reais.** Terminada a infraestrutura, percebi que
`publicar` só era chamado pela rota de teste: havia uma tela de integrações
que não publicava nada. A trilha virou a fonte — ela já é o registro de
tudo que o sistema faz, e um segundo registro paralelo de "o que falta
publicar" divergiria dela no primeiro erro de escrita. Cada destino guarda
sua própria `ultima_sequencia`, então:

- um destino **novo começa no presente**, não recebe o histórico inteiro do
  cofre de uma vez — seriam eventos antigos que ninguém pediu, e os mais
  sensíveis entre eles;
- um destino que ficou **pausado uma semana recebe o que perdeu** quando
  volta, sem reenviar nada aos demais;
- o marcador **avança mesmo sem assinante**, senão o sistema reprocessaria
  para sempre os mesmos eventos que ninguém quer.

O mapa de ação da trilha → tipo publicado é explícito, não derivado do nome
interno: renomear uma ação no código quebraria integrações de terceiros em
silêncio. Na primeira versão eu escrevi três nomes que não existiam
(`segredo_alterado`, `solicitacao_criada`, `solicitacao_aprovada`) — falha
silenciosa clássica: o evento simplesmente nunca casaria. Agora há teste
que confere o mapa contra os dois enums.

**Validação:** 777 testes nos **dois dialetos**; lint com `--max-warnings 0`;
`npm run build` limpo; verificação no navegador — destino cadastrado pela
tela, https validado, evento de teste entregue, fila conferida, destino
excluído. E o ciclo real no ar: **revelar um segredo no cofre chegou ao
destino como `segredo.revelado`, sem o valor**, com o segundo despacho não
reprocessando. O script de validação fez o papel do destino e **recalculou a
assinatura HMAC com o segredo recebido**, provando que os dois lados
combinam.

---

## Em aberto

- [ ] **Destino inviolável de verdade** para a exportação — o arquivo local
      não é (quem tem o disco reescreve os dois lados). Precisa de Splunk HEC,
      CloudWatch ou bucket com Object Lock. **BLOQUEADO:** exige serviço
      externo e credencial.
- [x] **Recuperação de senha e convite de usuário** — feito por TOTP e link
      de uso único, sem depender de e-mail. O envio por e-mail continua em
      aberto como *conveniência*, não como requisito: hoje o administrador
      entrega o link.
- [x] **Regras de notificação** — feito como integração por webhook
      (Standard Webhooks), com porta `EntregadorDeWebhook`. O adaptador HTTP
      está escrito; o padrão é o de ensaio, que não sai para a rede. Para
      entregar de verdade, trocar uma linha em `deps.get_entregador_webhook`.
- [ ] **Notificação por e-mail** — a porta de entrega serve, mas falta um
      adaptador SMTP/SES e um canal configurado. **BLOQUEADO** pela
      infraestrutura, não pelo código.
- [ ] **Agendador do despacho** — a rota `POST /integracoes/despachar`
      existe e processa a fila; falta quem a chame de tempos em tempos. Um
      cron externo resolve. Deliberadamente não há processo de fundo próprio:
      esconderia do operador quando as entregas acontecem.
- [ ] **Captura automática por proxy SSH** — a porta está pronta e o
      esqueleto escrito; falta o servidor intermediário. **BLOQUEADO** só
      pela infraestrutura, não pelo código. Ver docs/conectar-adaptadores.md.
