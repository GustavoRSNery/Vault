# Diário do Vault

Registro do que foi feito em modo autônomo (`/afk`), para retomada. Mais
recente primeiro. O "porquê" de cada decisão importa mais que o "o quê" — o
código já conta o quê.

---

## 2026-10-26 — Proxy SSH, S3 imutável, KMS provado e perfil editável

### Governança da API: quem consome o Vault de fora

Aba nova em Administração. A trilha de auditoria responde *o que foi
feito* ("segredo revelado"); esta responde **quem está batendo na API, em
quais rotas, com que resultado** — e a segunda não se extrai da primeira:
uma varredura que leva 401 em todas as tentativas não gera nenhum evento
de negócio, e é justamente o que mais interessa ver.

**O recorte, decidido pelo usuário:** registrar o consumo de fora
(aplicações, robôs, scripts) e deixar de fora as chamadas da própria tela
do Vault. Decide o `Sec-Fetch-Site`, não o `Origin`: aquele é preenchido
pelo navegador e JavaScript não altera, enquanto `curl` escolhe o `Origin`
que quiser. Script que forje `Origin` continua no relatório.

**O corpo da requisição não é guardado em lugar nenhum**, também por
decisão do usuário ("nem no back"). Vale em três camadas: a entidade não
tem campo, a tabela não tem coluna, e o middleware nunca chama
`request.body()`. Esta última é a que importa mais: ler o corpo no
middleware o consome do stream e obriga a bufferizá-lo, fazendo o conteúdo
de toda escrita — senha inclusive — existir numa variável do processo. O
caminho é não ter o dado.

**Dois bugs meus, os dois achados fora da suíte.**

O primeiro: o teste que varria a senha em todas as colunas **passava
varrendo tabela vazia**. O middleware usava a fábrica de sessão das
settings reais em vez da injetada, então gravava num banco que o teste não
lia. Descobri porque desconfiei de um teste que passou de primeira e rodei
uma checagem imprimindo quantas linhas ele via: zero. A asserção
`assert linhas` agora impede a reincidência.

O segundo só apareceu **na tela, com o sistema no ar**: a navegação
inteira entrava no relatório como externa. Em produção front e API são
same-origin atrás do nginx, e o navegador **omite** `Origin` em GET
same-origin — eu o exigia. O caso normal de produção era o que eu tratava
como anomalia. Nenhum teste pegaria: todos mandavam `Origin`, porque eu os
escrevi com a mesma suposição errada do código.

Retenção de 90 dias por ferramenta com comando próprio
(`app.tools.expurgar_uso_api`), não expurgo automático no boot: dado que
some sozinho some sem explicação. Documentado em
`docs/governanca-da-api.md`.

### Tutoriais reescritos

Os textos dos tours tinham, nas palavras do usuário, "muita cara de IA".
Reli os 32 passos e o padrão era claro e repetido: título que é tese em
vez de rótulo ("Selado é diferente de vazio"), travessão emendando uma
sentença de efeito no fim (em 15 dos 32), frase de palestra ("o que
transforma uma conta invadida em desastre"), e doutrina de segurança antes
de dizer para que serve a tela.

A regra nova, registrada no topo de `passos.ts`: o título diz **o que é**,
em palavras que a pessoa usaria; o texto diz **o que ela faz ali**, e só
então por quê, se o porquê mudar a decisão dela.

### Menu superior: a navegação virou dois níveis

Os cinco grupos que viviam empilhados na lateral subiram para uma barra no
topo. A barra escolhe a **área**; a lateral navega **dentro** dela. Os vinte
itens tomavam a coluna inteira e obrigavam a rolar para alcançar
"Configurações"; agora a lateral mostra no máximo seis, todos visíveis.

A inspiração veio de um sistema cujos ícones do topo são **módulos
diferentes**. Copiar aquilo literalmente aqui criaria uma fileira de ícones
sem destino — o Vault é um sistema só. O que foi copiado é a mecânica (topo
escolhe o contexto, lateral navega nele), aplicada à divisão que já existia.

**`areaDoCaminho` casa por prefixo e fica com o mais longo.** Ordem de
declaração não serve: `/sessoes/gravacoes` casa com `/sessoes` e consigo
mesmo, e varrer na ordem acertaria por sorte. O prefixo tem de terminar em
`/`, senão `/cofres-antigos` abriria a área de `/cofres`.

**O que a mutação ensinou.** Quatro mutantes; dois sobreviveram na primeira
rodada. Um deles porque o teste que eu havia escrito **reimplementava a
regra de casamento dentro do próprio teste** — teste que recalcula o que
deveria verificar não verifica nada. O outro revelou algo melhor que um
teste faltando: a raiz só não estraga o resultado porque está na *primeira*
área, a mesma que o fallback devolve. Reordenar `AREAS` quebraria isso em
silêncio, então o teste agora põe a raiz na segunda posição de propósito.

**Verificado na tela**, não só na suíte: login real no container, as cinco
áreas trocando, `/cofres/ciclo` mantendo "Segredos" marcada, e os
breakpoints medidos em iframe de largura controlada — 961→960 esconde os
rótulos, 721→720 empilha, e nada vaza horizontalmente até 360px. As contas
de teste criadas para isso foram removidas depois.

### Os dois esqueletos viraram adaptadores de verdade

`ProxySsh` e `ArmazenamentoS3` levantavam `NotImplementedError`. Agora
funcionam, e foram provados **contra os serviços reais** — LocalStack para
S3 e KMS, container OpenSSH como alvo do proxy. O KMS já tinha adaptador e
fiação; o que faltava era prova contra KMS de verdade, porque cliente falso
devolve o que foi programado para devolver.

**O proxy SSH grava de verdade.** A prova fim a fim: o cliente conecta no
proxy com a senha *do proxy*, o proxy busca a credencial do alvo no cofre,
conecta por fora e copia os dois sentidos. 10 eventos gravados, o comando
digitado presente na gravação, a saída do alvo também — e a senha do alvo
**nunca** passou por quem acessou, que é o ponto inteiro do cofre.

**Um bug que só o teste real pegaria:** `asyncssh.connect("servidor:2222")`
não reclama. Trata tudo como nome de host, tenta a porta 22 e falha com
"não foi possível conectar" — mensagem que manda investigar rede e firewall
quando a causa era a porta ter sido ignorada. Daí `separar_host_e_porta`,
com IPv6 entre colchetes e 12 testes.

**`imutavel` deixou de mentir.** O esqueleto devolvia `True` fixo, com o
argumento de que "conectado, o destino é de fato imutável". O argumento tem
um furo: bucket sem Object Lock aceita `PutObject` igual e nada falha — a
aplicação anunciaria prova por anos, e a primeira auditoria descobriria que
dava para apagar. Agora confere no bucket, e GOVERNANCE conta como **não**
imutável, porque é contornável por quem tem a permissão de bypass.

### Perfil editável (pedido do dono)

Nome, apelido, foto, e-mail e senha. Duas colunas novas em `usuarios`
(`apelido`, `foto`), aplicadas por `evoluir_schema`.

**Trocar e-mail ou senha exige a senha atual.** Não é burocracia: um token
roubado — de um XSS, de um laptop aberto, de um histórico de shell —
permitiria trocar as duas coisas e **tomar a conta**, deixando a pessoa
fora do próprio cofre. Com a senha, roubo de token vira acesso temporário
em vez de perda definitiva.

**A foto é validada em camadas, e SVG fica fora.** SVG carrega script: foto
de perfil que executa JavaScript na tela de quem olha é XSS armazenado com
o rosto de alguém em cima. Além do tipo, confere a **assinatura dos bytes**
contra o tipo declarado — o cabeçalho do data URI é escrito por quem chama,
e dizer `image/png` mandando outra coisa é trivial. O navegador reduz a
imagem antes de subir, senão foto de celular (3–8 MB) seria recusada e a
pessoa precisaria de um editor para usar o próprio sistema.

**O apelido não substitui o nome completo.** Ele aparece nas telas; a
trilha de auditoria e as sessões seguem com o nome completo, porque "Gu"
não identifica ninguém numa investigação meses depois.

### Um bug meu, que o teste pegou

Eu gravava o evento da tentativa recusada e levantava a exceção em seguida.
O rollback levava o evento junto: **tentativa de tomar a conta não deixava
rastro.** O projeto já tinha resolvido isso em `admin.py`, com o comentário
explicando exatamente o motivo — eu não tinha lido antes de escrever. Dois
`db.commit()` antes do `raise` consertaram; a mutação confirma que
revertê-los derruba dois testes.

### Tutoriais de API em todas as telas

Antes: 6 telas. Agora **17** — toda tela com endpoint de leitura. Os
endpoints saíram do OpenAPI real (`create_app().openapi()`), não de
memória. Mais tours nas quatro telas de Uso e histórico e no perfil.

**Um invariante do próprio projeto me corrigiu:** o teste exige que o
primeiro passo de todo tour **não** tenha âncora, para a tela ser explicada
antes de qualquer destaque. Meu tour do perfil começava apontando para um
cartão. A regra está certa — arrumei o tour, não o teste.

`Card` passou a repassar `data-tour` ao `<section>`. Antes engolia o
atributo em silêncio, e o passo virava balão centralizado sem nada indicar
o motivo — o tipo de falha que passa por "o tour é assim mesmo".

### Gates

- **SQLite: 934 verdes** (eram 858) + 12 ignorados sem LocalStack
- **Mutação: 24 mutantes, 24 mortos, zero sobreviventes**
- **Front: 77 testes**, `tsc` limpo, lint `--max-warnings 0`, build real
- **12 testes de integração** contra S3/KMS reais, que *skipam* sem
  `VAULT_TEST_S3_ENDPOINT` — prova reproduzível, não script perdido
- **Postgres: 934 verdes** em 9min33s. Obrigatório nesta rodada porque
  houve `ADD COLUMN` (`usuarios.apelido`, `usuarios.foto`): a suíte roda em
  SQLite por padrão, e a divergência de dialeto já causou incidente.

### Dívida que encontrei (não criei)

`main.py` e `deps.py` **já falhavam** ruff I001 antes desta rodada, por
causa do `settings as settings_router`. Conferi contra `HEAD` em vez de
supor. Não corrigi: embutiria mudança alheia no meio desta.

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

## 2026-10-20 — Gráficos com eixo no painel e nos alertas (item 9)

O pedido veio com uma referência concreta: as quatro abas do Orquestrador em
`indicadores.exemplo.com.br`. Abri as quatro e o padrão que as
atravessa é densidade alta, eixo nenhum e número sempre legível — heatmap de
bot × dia com o valor dentro da célula, esteira de etapas com anel de
progresso, e, na aba de erros, nenhum gráfico: os "top tipos" são **chips
clicáveis que filtram**.

O usuário pediu dois desvios dessa referência: **menos densidade** e **com
eixo**. Os dois se justificam pelo volume. O Orquestrador tem 20 dias × 35
bots = 700 células; o Vault tinha 336 eventos em 3 dias. Um heatmap aqui
seria uma faixa quase vazia.

### O que a trilha já permitia

Nada de tabela nova. `auditoria_eventos` tem `occurred_at` indexado, `action`,
`outcome`, `actor_label` e `target_path` — tudo que uma série temporal
precisa. Medi antes de desenhar, e a medição mudou o desenho: `acesso_negado`
era o **segundo** evento mais frequente (75), logo atrás de `login_sucesso`
(85). Num cofre de senhas, negação em série é o sinal mais importante que
existe, então virou faixa própria no gráfico em vez de número solto.

### Decisões

- **Agregação por dia em Python, não em SQL.** `occurred_at::date` no
  Postgres usa a timezone da **sessão**. Provei no banco: um evento de 02:30
  UTC sai como `2026-10-19` numa conexão em `America/Sao_Paulo` e como
  `2026-10-20` em UTC. A barra mudaria de lugar conforme quem abriu a
  conexão. O filtro por data continua no SQL, onde o índice trabalha; só o
  agrupamento subiu.
- **SVG escrito à mão, sem biblioteca.** São retângulos e uma grade. Recharts
  custaria centenas de KB para isso e exigiria um tema paralelo, já que as
  cores vivem nos tokens do CSS. O bundle ficou em 372 KB (106 KB gzip).
- **Rankings exigem ADMIN em `auditoria`.** "Quem mais revela segredos" expõe
  a atividade dos colegas, que é exatamente o que a tela de auditoria tranca.
  Sem a regra, o painel seria a porta lateral para o que a trilha protege
  pela porta da frente. Sem ADMIN, `restrito: true` e os rankings saem
  vazios — não com um item só, que sugeriria comparação inexistente.
- **A série sai com todos os dias, inclusive os vazios.** Dia sem evento é
  informação; omiti-lo colaria terça em sexta como se fossem consecutivas.
- **`dias_com_dado` separado de `dias`.** Com 3 dias de histórico, desenhar
  30 posições vazias sugeriria uma queda de atividade que não houve. A tela
  diz "340 eventos em 3 dias com movimento · janela de 30 dias".

### A escala do eixo, que errei primeiro

A primeira versão arredondava o teto para 1·10ⁿ/2·10ⁿ/5·10ⁿ com 4 marcas
fixas. Pareceu razoável até eu ver na tela: com máximo 253 o teto ia para
**500** e a barra ocupava metade da altura, achatando todas as outras.

Tentei duas correções que **pioraram** — medi as duas antes de aceitar. Exigir
que o teto fosse múltiplo de 4 levou `86` a um teto de 200 (43% de
aproveitamento). O que funcionou foi deixar o **número de marcas variar entre
3 e 5** e escolher a combinação que menos sobra: aproveitamento médio da
altura subiu de 80% para 87%, sem nunca produzir marca quebrada como 15 ou 45.
Com os dados reais, o eixo foi de 500 para 300.

### Invariantes

- O valor de um segredo nunca aparece: os rankings trazem **caminho** e
  **ator**, jamais conteúdo. Verificado no JSON cru do sistema no ar.
- `total` e `dias_com_dado` são derivados de `serie_cheia`, não do balde da
  agregação. O balde recebe o que a consulta trouxe, e o filtro não tem teto
  — um evento com data futura (relógio de robô adiantado) entraria nele sem
  ser desenhado, e a legenda desmentiria o gráfico.
- Empate no ranking desempata por nome. `ORDER BY contagem DESC` sozinho não
  é estável e a ordem oscilaria entre recarregadas.

### Mutação

8 mutantes, 8 mortos, 0 sobreviventes — depois de duas rodadas. Na primeira,
dois sobreviveram e ambos eram lacuna real:

1. **`.date()` sem converter para UTC.** Aqui descobri que `_aware()` **não**
   resolve o caso do Postgres: ele só *preenche* timezone ausente (o caso do
   SQLite), e um valor que já chega com offset `-03` passa intacto. O
   comentário que eu tinha escrito no código estava errado. Corrigi com
   `astimezone(UTC)` explícito e escrevi um teste que força na saída do banco
   o formato que só o Postgres produz — coisa que um teste contra SQLite
   jamais geraria sozinho.
2. **`dias_com_dado = len(por_dia)`.** Parecia equivalente. Não é: evento com
   data futura entra no balde e não na série.

Um terceiro mutante ("janela perde o dia mais antigo") sobreviveu e **é
genuinamente equivalente**: o laço que monta a série recalcula os dias por
conta própria, então alargar `desde` só busca linhas que ninguém lê. Removi
da bateria em vez de escrever teste para ele — mas o fato de duas linhas
distantes dependerem uma da outra em silêncio foi o que me levou a derivar
`dias_com_dado` da série.

### Gates

788 testes verdes nos **dois dialetos** (SQLite e Postgres), `eslint
--max-warnings 0` limpo, `npm run build` limpo, validação com o sistema no ar
(série de 30 e de 7 dias, limites `dias=0`/`dias=999` recusados com 422, sem
token recusado) e conferência visual das duas telas no navegador.

---

## 2026-10-20 — Lib de gráficos própria, ranking configurável e menu agrupado

Três pedidos do usuário, na mesma leva.

### 1. Lib de gráficos (`shared/charts`)

O argumento foi: *"isso posteriormente pode dar problema, então podemos fazer
a nossa lib de gráficos, sei que dá trabalho mas vai melhorar futuramente"*.
Procede — gráficos soltos num arquivo de 317 linhas é o estado em que o quinto
gráfico reimplementa marcação de eixo do zero.

A decisão de desenho é **separar cálculo de renderização**:

- `escala.ts` — funções puras de números para números, sem React. É onde moram
  as decisões difíceis: quanto o eixo aproveita da altura, como as faixas se
  empilham, quantos rótulos cabem.
- `primitivos.tsx` — eixo, grade, legenda, moldura e alvo de leitura.
- Um arquivo por gráfico, montado sobre os dois acima.

Isso é o que torna a lib testável sem DOM. Instalei **Vitest** (o projeto não
tinha teste de front nenhum) e o núcleo saiu com **18 testes**. O ambiente é
`node`, não `jsdom`: o núcleo é função pura e exigir DOM só deixaria a suíte
lenta à toa.

Vitest 2.1.8 trazia vulnerabilidade **crítica** (`tinypool`, `vitest`); subi
para 5.0.5 e o `npm audit` caiu de 8 problemas com 2 críticos para 2
moderados — os restantes são do `react-router-dom`, que já existia.

O `BarrasEmpilhadas` ficou genérico: recebe as séries que deve empilhar, não
três faixas fixas. O gráfico de atividade do cofre é *um uso* dele.

Bundle: 373 KB (106 KB gzip), praticamente igual ao de antes da lib.

### 2. Quem vê os rankings virou configurável

Pedido: *"admin ou gestor, mas deixe configurável isso tb"*.

A escolha de desenho que importa: configurar por **capacidade exigida**
(`admin` ou `approve`), não por nome de papel. Papel é dado criado em tempo de
execução — uma lista de nomes na configuração apontaria para o vazio no dia em
que alguém renomeasse "gestor", e falharia fechando: o ranking sumiria sem
explicação. Capacidade faz parte do domínio e não desaparece.

Passa no critério que o próprio módulo de configuração estabelece (*"se alguém
escolher o pior valor possível, isso enfraquece a segurança?"*): o valor mais
permissivo amplia a leitura para quem **já aprova pedidos de acesso** — gente
que, pela definição do papel, já decide quem vê o quê. A lista é fechada
justamente para impedir `read` ou `list`, que abririam a atividade dos colegas
a quase todo mundo.

Detalhes que decidem o comportamento:

- **ADMIN passa sempre**, mesmo quando a instalação exige APPROVE. Quem
  administra a auditoria já lê a trilha inteira pela tela de auditoria;
  recusar aqui só produziria a pergunta "por que o painel esconde o que a
  trilha mostra?".
- O padrão é o **restritivo**, inclusive para instalação que já existia —
  `evoluir_schema` acrescenta a coluna com `default='admin'`.
- A resposta das métricas carrega `capacidade_exigida`, e a tela **explica**
  por que não mostra os rankings em vez de apenas omiti-los: um bloco que some
  sem explicação parece falta de dado.
- A mudança entra na trilha com antes e depois (`admin -> approve`), porque é
  o que uma auditoria vai querer revisar.

**Bug reencontrado:** o PUT da configuração monta as mudanças campo a campo, e
eu esqueci de incluir o novo. Resultado: 200 OK e o campo ignorado em
silêncio. É exatamente o mesmo bug do `expira_em` na chave de API, no mesmo
formato. O teste pegou na hora.

### 3. Menu lateral

Pedido: *"eu estou me perdendo com tantos menus, e sem nenhum ícone, mesmas
cores, sem agrupamento"*. Eram 13 itens em lista corrida.

Agrupei por **pergunta que a pessoa tem na cabeça**, não por entidade do
sistema: *Visão geral* · *Segredos* (onde o segredo mora) · *Uso e histórico*
(o que já aconteceu com ele) · *Minha conta* · *Administração*. "Cofres,
dispositivos, credenciais, certificados" em sequência indistinta não ajuda
ninguém a parar a busca visual.

Ícones em SVG próprio (`app/icones.tsx`), pelo mesmo motivo da lib de
gráficos: são vinte formas de poucos traços, e uma biblioteca de ícones
custaria centenas de KB e traria um estilo que não é o do design system. Todos
seguem um contrato só — 24×24, traço 1.6, `currentColor` — para herdarem a cor
do item sem regra extra. São decorativos (`aria-hidden`): o rótulo em texto
sempre acompanha.

O item ativo passou a ter **três sinais** — fundo, peso da fonte e barra na
lateral. Fundo sozinho some em tela clara ou impressa, e cor sozinha não chega
a quem não a distingue. A barra fica em `left:-12px` para alcançar a borda da
sidebar, que tem 12px de padding; com `left:0` apareceria colada ao texto,
parecendo defeito.

**O lint pegou um erro meu que eu teria deixado passar:** ao reagrupar, deixei
"Perfil" de fora do menu. O `IconePerfil` ficou importado sem uso e o
`--max-warnings 0` reprovou. Sem esse gate, o item teria simplesmente sumido
da navegação.

### Mutação

11 mutantes atravessando as três frentes — backend e front na mesma bateria.
10 mortos na primeira rodada; **11 de 11 na segunda**, depois da correção
abaixo.

O sobrevivente foi instrutivo: remover o `Math.max(1, …)` de
`passoDosRotulos` não quebrou nada. Investiguei em vez de escrever teste: a
guarda `if (quantos <= 0) return 1` logo acima já cobre o caso, e com
`quantos > 0` e `maximoVisivel` finito o `Math.ceil` nunca devolve menos que
1. O único jeito de produzir zero seria `maximoVisivel = Infinity`, que
nenhum chamador passa. Era **código morto** fingindo ser defesa.

Apaguei a linha em vez de inventar um teste para defendê-la, e reescrevi o
mutante para atacar a guarda — que é a proteção de verdade.

### 🚨 O gate do Postgres cobria só um terço da suíte

Investigando uma falha intermitente (`test_capacidade_fora_da_lista_e_recusada`
falhou uma vez na suíte completa e não reproduziu depois), descobri algo
bem pior que a falha: **os testes de ponta a ponta nunca rodaram em
Postgres.**

`tests/integration/conftest.py` honra `VAULT_TEST_DATABASE_URL`, mas
`tests/e2e/conftest.py` tinha `database_url` fixo em
`sqlite+pysqlite:///:memory:`. Ou seja, "rodar a suíte no dialeto Postgres"
cobria **7 arquivos de integração e deixava os 18 de ponta a ponta sempre em
SQLite** — justamente os que exercitam a API inteira, onde a divergência de
dialeto aparece.

Isso explica por que o bug da timezone (`_aware` não converte offset já
existente) precisou de um teste que **forjava** a saída do Postgres: contra
SQLite, nenhum teste e2e jamais produziria um datetime com offset.

Corrigi em duas tentativas, e a primeira estava errada.

**Tentativa 1 — compartilhar o banco.** Fiz a e2e honrar a variável com
`drop_all`/`create_all` por teste. Resultado: **39 falhas em
`tests/integration`**, todas `duplicate key ... ana@exemplo.com.br`. A causa
é uma diferença de contrato entre as duas suítes que eu não tinha notado: a
integração isola por **rollback**, enquanto a e2e dá **COMMIT de verdade** (a
fixture `app` confirma a transação, porque os testes conferem o que ficou
gravado). Dividindo o banco, o que a e2e commitava sobrevivia para a
integração encontrar.

**Tentativa 2 — banco separado.** A e2e passou a usar `vault_test_e2e`,
derivado da mesma variável com sufixo. Nenhuma das duas suítes precisa
conhecer a outra, e a diferença de contrato deixa de importar. O banco
precisa existir:

    docker compose exec db psql -U vault -d vault -c "CREATE DATABASE vault_test_e2e;"

O sinal de que passou a valer: `test_api_metricas.py` saiu de 9s para 41s.

**Nota sobre a falha que iniciou tudo.** O `test_capacidade_fora_da_lista`
falhou uma vez e não reproduziu. A causa foi prosaica e minha: eu tinha duas
execuções da suíte disputando o mesmo `vault_test` — uma delas disparada
junto de um `docker compose up --build`. Os 87 erros `already exists` de uma
terceira execução confirmaram. Não era divergência de dialeto nem
contaminação entre testes; era concorrência que eu mesmo criei. A lacuna da
conftest, essa sim, era real — e só apareceu porque fui atrás da falha.

### Validação com o sistema no ar

`evoluir_schema` aplicou sozinho o
`ALTER TABLE configuracao ADD COLUMN capacidade_do_ranking VARCHAR(20)
DEFAULT 'admin' NOT NULL` numa tabela que já existia, que é exatamente o
caso que motivou a ferramenta. Pela tela: troquei para "Administradores e
gestores", confirmei no banco (`approve`) e na trilha
(`quem vê os rankings: admin -> approve`, com o autor), e voltei ao padrão
restritivo.

---

## 2026-10-20 — Paleta e formatos da referência

Três ajustes pedidos depois de ver o resultado no ar: o gráfico de atividade
estava **enorme**, a tela de alertas **não tinha mudado quase nada**, e a
inspiração precisava ser lida também para cor, fundo e formato — não só para
estrutura.

### O que medi, em vez de estimar

Em vez de olhar o print e chutar valores, extraí os tokens do DOM da
referência. Dois achados mudaram o resultado:

1. **A paleta é OKLCH**, com luminosidade alta (.86–.96) e croma baixo
   (.04–.10). São pastéis, não cores saturadas. Adotei OKLCH pelo mesmo
   motivo que eles: a luminosidade é perceptual, então duas cores com o mesmo
   L pesam igual aos olhos por mais distantes que sejam os matizes — é o que
   permite trocar azul por vermelho numa faixa sem que uma pareça "mais
   forte".
2. **O cartão não é branco chapado.** Tem borda branca translúcida, raio de
   16–22px e uma sombra de três camadas: difusa para profundidade, curta para
   assentar, e um realce branco *interno* no topo. É esse realce que dá o
   aspecto de superfície levantada.

O fundo da página lá é quase branco: quem carrega a cor são os cartões e os
gráficos. O meu tinha dois halos coloridos fortes demais, que competiam.

### A tira de atividade

O gráfico alto virou uma tira de 64px — o formato das colunas da aba
"Análise". Colunas largas e encostadas, topo arredondado, base reta, cor
clara para o volume e saturada para o que foi negado. Sem eixo Y e sem
grade: a pergunta aqui é *em que dias houve movimento e quando foi atípico*,
que é comparação de forma. `BarrasEmpilhadas` continua existindo para quando
a pergunta for *quanto*.

**Errei duas vezes na geometria antes de acertar**, e as duas tentativas
ensinam coisas opostas sobre `preserveAspectRatio`:

- Com `none` e altura só no estilo, o SVG esticou cada eixo de forma
  independente: as colunas achataram até quase sumir e a fonte dos rótulos
  saiu deformada.
- Troquei para `meet`, que respeita a proporção — e aí a altura passou a ser
  refém da largura: num container de 1300px, o viewBox forçava ~120px e a
  tira deixava de ser tira.

A resposta foi voltar a `none` **e tirar o texto de dentro do SVG**. As
colunas são retângulos e esticam sem parecer erradas; texto, não. Os rótulos
de data ficaram em HTML, numa grade de colunas iguais sob o gráfico.

### Alertas

A crítica estava certa: eu tinha trocado a estrutura e mantido a aparência.
Agora:

- Os cards ganharam **ponto colorido, rótulo em versalete, barra de proporção
  e "% do total"** — um número solto não diz se é muito; "3" pode ser
  catástrofe ou rotina, e "50% do total" se lê de relance.
- O cartão "Como as pendências se distribuem" **saiu**. A barra de proporção
  que havia nele repetia o que os três cards passaram a mostrar, e dois
  desenhos do mesmo número competem em vez de somar.
- Os chips subiram para **junto da lista que filtram**, sem cartão próprio —
  como na aba "Erros" da referência. Um cartão só para os filtros os afastava
  do efeito que produzem.

---

## 2026-10-21 — Abas por domínio no painel

O painel passou a ter uma aba por página do grupo "Segredos" do menu, mais um
resumo. A ordem das abas repete a do menu de propósito: quem decorou a
navegação lateral encontra o mesmo arranjo aqui.

### Um endpoint, não cinco

`GET /panorama` devolve as contagens dos cinco domínios de uma vez. Abas
trocam rápido, e uma chamada por aba faria cada clique esperar a rede. O
corpo é pequeno — são contagens, nunca listas —, então trazer tudo sai mais
barato que buscar sob demanda.

**Nenhuma aba lista recursos um a um.** Isso é trabalho da página de destino,
que tem filtro, busca e paginação; duplicar a lista criaria duas telas para
manter e duas versões da mesma verdade. A aba mostra o estado e aponta o que
precisa de ação; o botão "abrir" leva à lista.

### O que cada aba responde

- **Cofres** — segredos ativos contra o que está na lixeira. A lixeira não
  entra no acervo ativo: somá-los inflaria o número com o que foi
  deliberadamente descartado.
- **Credenciais** — custódia aberta, custódia vencida e, principalmente,
  *nunca rotacionadas*: essas podem ainda ser a senha de fábrica.
- **Certificados** — vencidos e vencendo contam separado (somá-los esconderia
  o que já quebrou dentro do que ainda dá para resolver), e a aba mostra o
  **próximo a vencer com nome e prazo**, que é a pergunta que se faz antes de
  renovar.
- **Chaves de API** — o ciclo de vida, e as *ativas sem vencimento*: não é
  erro, mas é dívida, porque sem prazo ninguém decide quando elas saem de
  circulação.
- **Dispositivos** — cobertura: quantos ainda não têm credencial no cofre, ou
  seja, cujo acesso mora em planilha ou na memória de alguém.

O **resumo** traz um número por domínio e um bloco "Precisa de atenção" que
soma as pendências de todos, cada linha levando à página que a explica. Sem
ele o resumo seria só contagem de acervo: saber que há 42 credenciais ajuda
menos do que saber que 3 estão com a rotação atrasada.

### Visibilidade

Toda contagem respeita a política do usuário, pelo mesmo motivo da busca: um
número que some recursos inalcançáveis denuncia a existência deles. Quem não
tem acesso a nada vê **zero em tudo, não um erro** — o painel é a primeira
tela depois do login, e falhar nela faria parecer que o sistema quebrou
quando o que falta é permissão.

### Menu

Os títulos de grupo estavam menores que os itens (10px contra 13,5px), mas em
cinza-apagado — então pesavam **menos** que os próprios itens e sumiam na
varredura em vez de organizá-la. Agora são maiores, em negrito forte e na cor
da marca: três sinais em vez de um.

### Erro que o teste pegou

Escrevi o endpoint chamando `secrets.list_for_vault()` e `list_deleted()`, que
**não existem** — inventei os nomes. O real é
`list_in_vault(vault_id, include_deleted=)`, e a lixeira sai da diferença
entre as duas chamadas. Também usei `device_name` onde o campo é `device_id`.
Confirmei cada nome no código antes de rodar, em vez de confiar na memória.

Os primeiros testes falharam por culpa **do teste**, não do endpoint: concedi
política em `certificados` quando os recursos moram em `certificados/<nome>`,
e o padrão do projeto é o curinga `certificados/*`.

### 🚨 Mutação achou o vazamento que eu dizia estar protegendo

Primeira rodada: 4 mortos, **2 sobreviventes** — e o primeiro era grave.
Remover o filtro de política da contagem de cofres **não quebrou nenhum
teste**. Eu havia escrito no docstring que a visibilidade estava protegida, e
tinha escrito um teste de vazamento só para certificados; o domínio onde os
segredos de fato moram ficou sem cobertura.

O segundo sobrevivente ensina sobre a forma do teste, não sobre o código:
trocar `EXPIRED` por `EXPIRING` passava porque meu teste tinha **um
certificado de cada estado**, e com 1-1-1 a soma fecha mesmo se os rótulos
trocarem de lugar. Refiz com dois vencidos e um vencendo — quantidades
diferentes só batem se cada estado for contado pelo que é.

Segunda rodada: **6 de 6 mortos, zero sobreviventes.**

---

## 2026-10-21 — Resumo e detalhe trocados de lugar

O usuário notou a inconsistência: *"a aba de resumo tem mais gráficos que o
restante"*. Medindo: o resumo tinha **3 gráficos** (tira de 30 colunas + dois
rankings top-8) e as abas de detalhe tinham **1 ou nenhum**. Estava invertido.

### O que a pesquisa diz

O cânone é o **Visual Information Seeking Mantra** de Shneiderman (1996):
*overview first, zoom and filter, then details-on-demand*. As três etapas
têm conteúdos distintos — a visão geral carrega valor atual, variação e
status; o detalhe carrega séries, registros, quebras por categoria e filtros.
A justificativa citada para manter a primeira tela enxuta é a **Lei de
Hick**: mais opções simultâneas atrasam a decisão.

Série temporal com seletor de período é *zoom and filter*; ranking top-8 é
*details-on-demand*. Os dois estavam na aba cuja função é dar o panorama.

### De onde veio o erro

Não foi acidente de layout. O resumo **nasceu primeiro**, antes de existirem
abas. Quando acrescentei as abas, movi os dados novos para elas e deixei o
conteúdo antigo onde estava, em vez de redistribuir — o resumo virou "a tela
antiga mais um cabeçalho".

### Como ficou

**Resumo:** 4 KPIs, o bloco de pendências e **uma** tira de atividade em
janela fixa de 7 dias, sem seletor. Um link leva à aba Cofres para quem
quiser mais.

**Aba Cofres** recebeu a série com seletor 7/30/90 e os dois rankings — o
assunto deles é este domínio: quem revela segredos, e quais segredos.

**Abas de detalhe** ganharam o que lhes faltava: distribuição por faixa de
tempo em Certificados (quando vencem), Credenciais (há quanto tempo foram
trocadas) e Chaves de API (quando as ativas vencem).

O componente `Atividade` foi extraído para servir aos dois lugares,
parametrizado pelo que muda — o resumo passa um rodapé que leva ao detalhe, a
aba passa o seletor. Duplicar o bloco faria os dois divergirem no primeiro
ajuste.

**Mitigação do custo:** uma das fontes aponta que *overview + detail* em
telas separadas dificulta relacionar informação entre as visões. Os mesmos
KPIs aparecem no topo de cada aba, então o número visto no resumo reaparece
idêntico no detalhe e serve de âncora.

### Faixas acumulativas contariam o mesmo item duas vezes

As faixas de vencimento são **excludentes**: cada item cai na primeira cujo
teto alcança. Lidas como tetos independentes, "vence em 30 dias" e "vence em
90" descreveriam o mesmo certificado, e o gráfico mostraria mais itens do que
existem. O teste prende isso exigindo que a soma das faixas feche o total.

Os cortes não são redondos por acaso: **7 dias** é o que sobra para uma
renovação de emergência, **30** é o prazo de uma emissão manual tranquila,
**90** é o horizonte de planejamento.

### Primeiro desenho da linha do tempo estava errado

Usei `ColunasCompactas` e, na tela, as cinco faixas saíram **todas da mesma
altura** — com um item em cada, o teto é 1 e a forma não informa nada. Trocei
por barras horizontais com o número escrito ao lado: com poucas categorias de
valor parecido, a altura não distingue e o número resolve. A barra mede
contra a **maior faixa**, não contra o total, senão cinco faixas de 1 item
dariam cinco fios de 20%.

### Mutação

9 mutantes, 9 mortos — depois de duas rodadas. O sobrevivente da primeira
levou a uma lacuna de dado, não de código: nenhum teste criava chave de API
**revogada com vencimento**, então trocar `ativas` por `todas_chaves` no
gráfico não quebrava nada.

Ao escrever esse teste, errei o payload: enviei `expira_em`, e o cadastro
recebe `dias_de_validade` — a data é derivada no servidor, para não depender
do relógio de quem chama. O Pydantic descartou o campo desconhecido em
silêncio e a soma deu zero. Mesma classe do bug do `expira_em` no PUT, agora
do lado do teste.

---

## 2026-10-21 — Lote 1: Sessões SSH e aprovação em massa

Primeiro de três lotes de um pedido grande (14 frentes em 7 páginas).

### Alvo e motivo deixaram de ser texto livre

O pedido foi direto: *"campo de alvo e motivo não pode ser aberto, pq se não
fica impossível mensurar"*. Procede — como texto livre, o mesmo servidor vira
`srv-prod`, `SRV-PROD` e `servidor de producao`, e a pergunta "quantas
sessões de incidente tivemos no mês?" deixa de ter resposta.

- **Alvo** virou seletor das máquinas com acesso SSH cadastrado.
- **Motivo** virou lista fechada (`MotivoDaSessao`), validada no domínio.
- **Detalhe** continua livre, ao lado: a categoria serve ao relatório, o
  detalhe serve à auditoria. Perder o "ticket #4417" seria trocar um problema
  por outro.

### Nenhum cadastro novo de máquina

A parte que **não** construí é a que mais importa aqui. O pedido falava em
"cadastrar a máquina com o código de conexão SSH", e a tentação era criar uma
tabela de máquinas de sessão. Mas a máquina já existe em **Dispositivos**,
com endereço, e `AcessoRemoto` já tem `metodo=ssh`, `identificador`, `porta` e
`usuario_sugerido` — tudo o que uma sessão SSH precisa.

Um segundo cadastro criaria duas listas que divergem, e aí "qual é o IP do
srv-db-01?" passa a ter duas respostas. Em vez disso, `GET /sessoes/maquinas`
projeta os dispositivos que têm acesso SSH, já com o caminho da credencial
quando existe — e a tela preenche o resto sozinha quando a máquina é
escolhida.

A senha segue a mesma lógica: não há "cadastrar senha da sessão". Ou a
credencial está no cofre (e a sessão aponta o caminho, nunca o valor), ou a
tela diz que não está.

### Card da sessão ativa

As três perguntas de quem olha uma sessão em andamento são **quem**, **em qual
máquina** e **há quanto tempo**. Numa tabela de oito colunas elas ficavam
espremidas entre dados que só importam depois. Agora são card, com o tempo
recalculado a cada segundo — "há 3 minutos" congelado numa tela aberta há meia
hora é pior que não mostrar nada.

### Aprovação em massa

`POST /solicitacoes/aprovar-em-lote` processa um a um e **relata cada
resultado**. Três decisões:

- Cada pedido gera **seu próprio evento de auditoria**. Um evento único de
  "lote aprovado" esconderia *o que* foi concedido — justamente o que uma
  auditoria vai revisar.
- Uma falha **não derruba as outras**, mas aparece na resposta com a razão.
  Aprovar 20 e receber "ok" quando 3 falharam seria pior que não ter o botão.
- Ids repetidos processam uma vez só, e cada pedido passa pela **mesma
  checagem de permissão** da aprovação individual: o lote é conveniência, não
  caminho lateral.

Na tela, a caixa "selecionar todas" tem estado **indeterminado** quando a
seleção é parcial — senão ela mostraria "nada selecionado" com 3 de 7
marcados.

### A ideia do usuário: se já puxa tudo, por que pedir para montar?

Depois de ver o seletor funcionando, o usuário levou a decisão adiante:
*"já que ele puxa tudo de lá, vamos puxar tb os dados de acesso e preencher
isso tudo automaticamente, e sem precisar de alguém criar uma nova
conexão"*. Procede, e muda o fluxo de lugar.

A tela deixou de começar por "Abrir sessão" e passa a começar por **"Máquinas
que você alcança"** — porque ninguém vai a Sessões para abrir uma sessão, vai
para **entrar numa máquina**. O registro é consequência, não o pedido.

Cada máquina traz o comando pronto (`ssh deploy@10.0.0.5 -p 2222`), a
credencial do cofre e um botão **Conectar**. O passo seguinte pede só o
motivo — a única coisa que o sistema não tem como saber sozinho. Aberta a
sessão, aparece o painel com o comando, botão de copiar, link `ssh://` e o
atalho para revelar a senha.

Detalhes que decidem a qualidade:

- **O comando é montado no servidor**, não na tela. Deixar o front concatenar
  host, porta e usuário espalharia a regra por cada lugar que precisa dela, e
  cada um erraria a seu modo: a porta some, o usuário vira "root" chumbado.
- **`-p` só aparece quando a porta não é 22.** `-p 22` é ruído num comando
  que a pessoa lê antes de colar. Na URL a porta vai sempre, porque ali não
  custa leitura.
- **Sem usuário sugerido, o comando sai só com o host.** Inventar "root"
  seria pior que deixar a pessoa completar.
- **O comando nunca carrega a senha** — nada de `sshpass`. Senha em comando é
  senha no histórico do shell de quem colou, fora do cofre e fora da
  auditoria. É a mesma regra do arquivo `.rdp`, que já saía sem senha.

### Erros que os testes pegaram

1. A regra nova quebrou **32 testes** de uma vez, todos abrindo sessão com
   motivo livre. Separar foi fácil porque só 2 abriam sessão; os outros 30
   eram `motivo` de *encerramento* e de recuperação de senha, que seguem
   livres — e devem seguir.
2. Escrevi um teste que aprovava um pedido antes do lote e esperava 2 de 3
   aprovados. Deu 3. A causa era o **meu teste**: a aprovação prévia foi
   enviada sem corpo e devolveu 422, então nunca aconteceu. Asserção no
   status da chamada preparatória resolveu.
3. Corrigi os testes e2e e **dei a suíte por fechada cedo demais** — os
   unitários montam `Sessao` direto, sem passar pela API, e também quebraram.
   Foram 25 falhas numa segunda rodada. A correção foi de uma linha (o helper
   `_sessao` tem um dicionário `base` único), mas a lição é que validar por
   recorte (`-k "sessao"`) não substitui a suíte inteira: o recorte pegava os
   e2e e deixava os unitários de fora.

---

## 2026-10-22 — Sessões SSH: acompanhar, não conectar

O usuário apontou duas coisas na tela de Sessões: faltava **ver quem está
acessando**, e o botão **Conectar** não devia estar ali — a função já existe
em Dispositivos, e a tela de sessões é para acompanhar.

### A tela tinha duas profissões

Na véspera eu havia posto "Máquinas que você alcança" no topo, com Conectar
por máquina. Resolvia um problema real (ninguém vai a Sessões para "abrir uma
sessão"), mas pela porta errada: criou um **segundo** lugar de conectar, e
duas telas que fazem a mesma coisa divergem no primeiro ajuste. A função
pertence a Dispositivos, onde o cadastro mora. Sessões responde *quem está
dentro de qual máquina agora*.

Removidos `ConexaoAberta`, `MaquinasDisponiveis` e `Conectar` (~7.100
caracteres). `MaquinaSsh` ficou: o registro manual de acesso usa a lista para
oferecer as máquinas conhecidas em vez de texto livre.

### `usuario_label` responde "qual conta", não "quem"

O campo que existia era o e-mail. Numa lista de sessões alheias,
`a.souza@` e `a.santos@` se confundem onde "Ana Souza" e "Ana Santos" não se
confundiriam. Acrescentei `usuario_nome` — e o e-mail **continua**, porque é
ele que desempata homônimos.

Resolvido por `_nomes_de(db, sessoes)`, **uma consulta** com `id IN (...)`:
buscar usuário por sessão faria uma lista de 20 virar 21 consultas. Quem não
for encontrado não entra no mapa e a tela cai no e-mail — conta removida não
apaga a sessão da trilha.

Propagado às **6** rotas que devolvem sessão. Um campo preenchido em uma
rota e vazio nas outras é pior que não existir: a mesma pessoa apareceria com
nome numa tela e com e-mail na outra.

### Três contagens que não são a mesma

**Sessões agora**, **Pessoas conectadas**, **Máquinas em uso**. Duas sessões
da mesma pessoa na mesma máquina são 3 números diferentes (2, 1, 1) — e é
essa diferença que diz se o acesso está concentrado ou espalhado. Confirmado
na tela: 3 sessões, 2 pessoas, 3 máquinas.

### Vazio que responde em vez de sumir

"Sessões de outras pessoas" só aparecia quando havia alguma. Numa tela de
acompanhamento, a seção sumir deixa a pergunta sem resposta visível: quem
olha não sabe se ninguém está conectado ou se o bloco não existe. Passou a
dizer **"Ninguém mais está conectado agora"**.

O vazio de "Minhas sessões" também mudou: mandava "abra uma ao acessar um
sistema", coisa que ali já não se faz. Agora aponta Dispositivos.

### O que o botão Conectar nunca fez

Vale registrar, porque a mesma limitação vale para Dispositivos: ele **nunca
abriu terminal**. Montava o comando `ssh` e oferecia copiar ou chamar o
cliente do sistema via `ssh://`. Acesso de dentro do navegador exige proxy SSH
— que é justamente o item **BLOQUEADO** no fim deste arquivo. Com ele, a
gravação passaria a ser automática.

### Mutação

6 mutantes, **0 sobreviventes**, com integridade verde antes e restauração
verde depois. O que mais importa é o segundo: trocar o nome de *quem abriu* pelo
de *quem consulta* morre — um teste com uma pessoa só passaria, e era
exatamente o erro que apagaria a distinção numa lista de sessões alheias.

| Mutante | |
|---|---|
| nome sempre vazio (campo decorativo) | morto |
| nome de quem CONSULTA, não de quem abriu | morto |
| mapa de nomes nunca consultado | morto |
| histórico sem nomes resolvidos | morto |
| detalhe sem nomes resolvidos | morto |
| abrir sem nomes resolvidos | morto |

### Erros que apareceram no caminho

1. Concedi a política em `sessoes/*` e a sessão alheia não apareceu: o
   caminho avaliado é `sessoes` **exato**. O teste de duas pessoas pegou.
2. Rodei o gate Postgres com senha adivinhada (`vault:vault`) e colhi **426
   erros**. Eram todos `password authentication failed` — falha de conexão,
   não de código. Ler a causa antes de interpretar o número evitou "a suíte
   quebrou".
3. Contas de teste com domínio `.local` deram 422 no login: `EmailStr` não
   aceita o TLD. E apaguei os usuários deixando política e papel órfãos, o
   que fez a recriação colidir em `politicas_name_key`.
4. Li "48min" nos três cards e **suspeitei do relógio**. Estava certo: as
   sessões tinham mesmo 48 minutos, abertas enquanto o gate Postgres rodava.
   Conferir contra o backend (`duracao_ms=2908589` ≈ 2909s reais) antes de
   "corrigir" evitou um conserto do que não estava quebrado.

### Gate

- SQLite: **832 verdes** (823 + 5 novos + 4 que já existiam no arquivo)
- Postgres: **100 integration + 341 e2e = 441 verdes**, 18min24s — a
  duração é o que confirma que rodou mesmo contra Postgres
- `eslint --max-warnings 0` e `npm run build` limpos
- Conferido na tela com 2 contas descartáveis e 3 sessões, depois removidas

---

## 2026-10-22 — Lote 2: criar credencial, guardar certificado, chamar a API

Três formulários que faltavam, e um deles obrigou a mexer no backend.

### O backend já esperava por isto

`CertificateModel` tinha `secret_id` com um comentário dizendo que a chave
privada, quando guardada, é segredo cifrado no cofre. `SecretKind` já tinha
`CERTIFICATE`. A arquitetura previa o upload antes de ele existir — guardar o
arquivo virou **reusar o cofre**, não construir armazenamento novo.

O mesmo valeu para credenciais: `POST /dispositivos/{nome}/credenciais` já
existia. Faltava só a tela, o que mudou o tamanho do trabalho assim que
conferi em vez de supor.

### Duas permissões para guardar um arquivo, não uma

Guardar exige `UPDATE` no certificado **e** `CREATE` no cofre de destino.
Checar só a primeira deixaria quem administra certificados gravar em qualquer
cofre por esta porta — e ninguém procuraria por ali, porque a tela de
certificados não parece uma tela de cofre.

Baixar exige `REVEAL` no cofre, não `READ` no certificado: acompanhar
vencimento é rotina de quem cuida de prazos; sacar um `.pfx` entrega a chave
privada da empresa. São perguntas diferentes e merecem permissões diferentes.

Reenviar **versiona** em vez de sobrescrever: é o que responde "com qual
arquivo isso foi assinado em março?".

### O parser de X.509 é nosso, de propósito

~200 linhas legíveis em vez de uma dependência. O caminho que processa
arquivo de origem externa é exatamente onde uma dependência comprometida faz
mais estrago, e o que precisamos do X.509 é pouco: serial, emissor, validade,
titular.

`.pfx`/`.p12` **não** é aberto: abrir exigiria a senha na tela, e a senha do
`.pfx` é segredo do cofre, não campo de formulário. A tela guarda o arquivo e
pede os campos.

### O openssl como gabarito achou dois erros meus

Gerei um certificado real e comparei com `openssl x509 -noout -subject
-issuer -serial -dates`. Dois achados:

1. **O serial perdia o zero à esquerda.** Eu tratava `08…` como padding de
   sinal do DER e cortava. O openssl imprime todos os bytes — e um serial
   que não casa com o da autoridade emissora não serve para nada, já que
   conferir contra ela é sua única função.
2. **A ordem do DN.** Aqui o errado era meu *gabarito*: eu havia gerado com
   `-nameopt RFC2253`, que inverte. O padrão é a ordem do DER, que o parser
   já produzia.

A diferença entre os dois importa: no primeiro corrigi o código, no segundo o
teste. Testar contra a própria leitura teria validado os dois erros.

Acrescentei uma verificação que roda o openssl de verdade sobre PEM e DER em
disco e compara campo a campo. **Prova positiva:** ela pula sem a variável de
ambiente, passa com o parser certo e **falha** com o parser sabotado — testei
as três. Ela vive no scratchpad, não na suíte: usa APIs do Node que o
`tsconfig` de browser não conhece, e a suíte não pode depender de uma
ferramenta externa para passar.

### Importação: detectar o formato, não perguntar

Quem acabou de exportar de outra ferramenta sabe que clicou em "exportar",
não o nome do formato. Seletor errado produz importação vazia, e a conclusão é
que o arquivo veio corrompido. A tela tenta formato próprio → Bitwarden →
1Password → lista genérica, **nessa ordem**: a genérica casa com quase tudo e,
posta antes, roubaria os específicos.

**A senha nunca entra**, mesmo quando o arquivo a traz — e arquivos de
gerenciador trazem. A tela conta quantas vinham e diz que foram descartadas,
em vez de ficar calada.

Ignorados também são ditos: "Contrato do datacenter (não é login)". Silêncio
sobre o que ficou de fora esconde perda.

### Chave de API: o exemplo que roda

Saber que a chave vai em `Authorization: Bearer` não diz *contra o quê*.
Acrescentei endereço, método e rota de exemplo — todos opcionais, porque nem
todo serviço tem uma rota única que sirva, e exigir faria alguém inventar um
endereço, que é pior que o vazio.

A requisição é montada **no servidor**, em pares (rótulo, valor), pela mesma
razão do comando SSH: deixar a tela concatenar espalharia a regra. O valor
sai sempre como `<valor>` — exemplo com chave de verdade vira chave em print,
em chamado e em histórico de navegador.

### Mutação: 5 sobreviventes na primeira rodada

A bateria pegou o que eu não tinha coberto — e o pior era conhecido:

| Mutante | 1ª rodada | 2ª |
|---|---|---|
| baixar não exige REVEAL no cofre | morto | morto |
| guardar não exige CREATE no cofre (escalada lateral) | morto | morto |
| guardar não exige UPDATE no certificado | **sobreviveu** | morto |
| reenvio sobrescreve em vez de versionar | morto | morto |
| `tem_arquivo` sempre falso | morto | morto |
| base64 inválido passa em silêncio | morto | morto |
| curl ignora o método (POST vira GET) | **sobreviveu** | morto |
| chave na query também vai no cabeçalho | **sobreviveu** | morto |
| url sem esquema é aceita | **sobreviveu** | morto |
| **PUT da chave ignora a rota** | **sobreviveu** | morto |

O último é a terceira vez que este projeto encontra o mesmo bug: campo novo
aceito pelo PUT, devolvido na resposta e **não gravado** — some no próximo
GET, sem erro nenhum. Desta vez o teste relê do banco em vez de conferir a
resposta do PUT, que é o que distingue os dois casos.

Depois dos testes novos: **10 mutantes, 0 sobreviventes.**

### Um teste que passava pelo motivo errado

`test_sem_permissao_no_cofre_nao_guarda` aceitava 403 **ou** 404. Tentei
endurecer para 403 e descobri que o cofre devolve **404** a quem não o
enxerga — não revelar a existência é deliberado. Exigir 403 seria exigir um
vazamento.

A correção não foi no código de status: o teste passou a verificar o
**efeito** — que `tem_arquivo` continua falso depois da tentativa. O que
importa é que não gravou, não como a recusa foi numerada.

### Gate

- SQLite: **848 verdes** (832 + 16 novos)
- Frontend: **49 testes** (18 + 31 novos), lint `--max-warnings 0` e build limpos
- **17 verificações de ponta a ponta contra a API real**: o certificado de
  1.316 bytes volta **idêntico** depois de cifrado e decifrado, e o reenvio
  gera versão 2
- `evoluir_schema` aplicou as 5 colunas novas sozinho no boot
- Conferido na tela: importação Bitwarden (3 reconhecidas, 1 nota ignorada,
  2 senhas descartadas), terminal openssl e os três blocos do exemplo da API

---

## 2026-10-22 — Lote 3: tours, tutorial de API, gravações em grade

E um bug de produção que só apareceu porque fui conferir na tela.

### O bug: um registro antigo derrubava a listagem inteira

Ao abrir Gravações para validar o novo layout, a tela veio **vazia**. A rota
devolvia **422**:

> Motivo 'Validacao' não é uma opção. Escolha entre: manutencao, incidente…

No Lote 1 fechei a lista de motivos. A validação roda no `__post_init__` da
entidade — e o `__post_init__` roda também **na leitura**, quando o
repositório monta a `Sessao` a partir do banco. Quatro sessões gravadas antes
da mudança (`Validacao`, `Conferencia do fechamento`) passaram a ser
ilegíveis, e como a rota monta a lista inteira de uma vez, **um registro
antigo escondia todos os corretos**.

**A correção separa criação de leitura**, em vez de afrouxar a regra ou
apagar o passado:

- campo `legado: bool` na entidade, ligado **só** pelo repositório ao ler;
- `if not self.legado and self.motivo not in …` — a checagem da lista vale
  para quem entra agora;
- tudo o mais (motivo vazio, alvo ausente) continua recusado nos dois casos.

Reescrever o motivo dos registros antigos seria pior: a trilha passaria a
dizer que aquela sessão foi de "manutenção" quando ninguém escreveu isso.

**Prova positiva:** com a correção revertida, 2 dos 3 testes novos falham;
restaurada, os 3 passam. O terceiro — criar com motivo fora da lista continua
recusado — passa nos dois casos, porque guarda a regra que *não* mudou.

Na tela, depois: 11 gravações listadas, com `srv-validacao-67` ("Validacao") e
`pg-contabil` ("Conferencia do fechamento") convivendo com as novas.

**A lição:** validação de domínio que roda na hidratação do banco transforma
mudança de regra em perda de leitura. O passado não se conforma à regra nova,
e insistir não corrige o cadastro — quebra a auditoria.

### Tours: oferecidos, nunca impostos

Cinco tours, um por tela de Segredos. Abre sozinho **na primeira visita** e
some para sempre depois de concluído ou dispensado; o botão "Como funciona?"
reabre. Tour que reaparece é treinamento para clicar em "fechar" sem ler.

O destaque é um **recorte na cortina** (`box-shadow: 0 0 0 9999px`), não uma
borda colorida: escurecer tudo menos o elemento diz "olhe aqui" sem
acrescentar mais uma cor à interface que está sendo explicada.

Cada passo fala de **conceito e sequência**, não de mecânica de botão. Um
tour que explica o que um campo faz está consertando um rótulo ruim — e o
conserto some quando a pessoa fecha o tour.

Decisões que viraram teste: primeiro passo sem âncora (explica a tela antes
de apontar), texto ≤ 300 caracteres, âncora sempre `[data-tour="…"]` e nunca
classe de estilo (que quebraria em silêncio no primeiro ajuste de CSS), e
`localStorage` que **nunca lança** — em aba anônima o acesso falha, e um tour
capaz de derrubar a tela ao abrir é pior que tour nenhum.

### Tutorial de API: só leitura, e isso é decisão

Botão "Ver pela API" nas cinco telas de Segredos e em Gravações, com os
endpoints de consulta, `curl` pronto e exemplo de resposta.

**Nenhum `POST` documentado.** Criar e alterar continuam passando pela
interface, onde cada ação tem confirmação, justificativa e trilha. Documentar
escrita aqui convidaria a automatizá-la — e escrita automatizada sem revisão é
como inventários ganham dezenas de registros que ninguém reconhece depois.

O token sai como `$VAULT_TOKEN`, com o aviso de guardá-lo numa variável: o
`curl` é feito para ser colado tal como está, e token no comando fica no
histórico do shell.

### Gravações: grade em vez de tabela

Uma gravação é **assistida, não comparada**. A pergunta é "qual delas eu
abro", e a tabela de oito colunas respondia à pergunta errada. A tabela
continua num alternador, porque comparar lado a lado ainda serve para a
revisão periódica.

A miniatura é a **barra de atividade**: doze traços, mais altos onde houve
mais eventos. Derivada de duração e contagem, não da linha do tempo — baixar
o conteúdo de todas as gravações para desenhar barrinhas seria caro e, pior,
despejaria no navegador o que as pessoas digitaram em produção sem ninguém
ter aberto nada.

Por isso ela representa **densidade**, não instantes: o cartão não promete
onde clicar, mostra se a sessão foi intensa ou calma. A semente vem do id
para o desenho ser estável — com `Math.random()` as barras tremeriam a cada
tecla digitada na busca.

Na tela, lado a lado: `srv-db-prod` (140 eventos) com barras cheias e
`srv-ssh-demo` (6) quase rasas.

### Linha clicável e botão voltar

Em Cofres, a linha inteira abre o cofre — alvo do tamanho do texto obriga a
mirar, e a linha toda é o que a pessoa já tenta clicar antes de descobrir que
não funciona. Com `role="link"` e `tabIndex`, porque `<tr>` não é focável e
sem isso o teclado não alcança.

**Correção de um levantamento meu:** eu havia dito que as subtelas não tinham
volta. Elas tinham — um breadcrumb com link para a listagem. Busquei pela
palavra "Voltar" e não vi os crumbs. O que fiz foi acrescentar o botão
explícito **acima** do crumb: o crumb diz onde você está, o botão diz como
sair, e um não substitui o outro.

`<Link>` de verdade, não botão com `history.back()`: quem chega por link
direto não tem histórico, e numa aba nova `back()` sai do sistema.

### Gate

- SQLite: **858 verdes** (848 + 10 do motivo legado)
- Frontend: **76 testes** (49 + 27 novos), lint `--max-warnings 0` e build limpos
- Postgres do **Lote 2**: 457 verdes, 11min51s
- Postgres do **Lote 3**: **461 verdes**, 8min57s — rodado de novo depois
  dos testes da revisão, porque o gate anterior não os continha

### Revisão adversarial depois de pronto

Procurando o que quebra, não confirmando o que funciona — e achou três coisas.

**1. A mutação revelou teste que passava pelo motivo errado.** Dois mutantes
sobreviveram na primeira rodada, o pior sendo *"criação aceita motivo fora da
lista"*. A razão: pela API o **Pydantic recusa o valor antes** de a entidade
ser construída, então o teste e2e nunca exercitava a regra do domínio. Um
afrouxamento ali passaria despercebido.

A correção foram 6 testes **no nível do domínio**, onde a regra vive:
`legado=True` aceita motivo fora da lista, mas continua recusando motivo
vazio e alvo vazio — a tolerância é para a lista, não para tudo. Segunda
rodada: **5 mutantes, 0 sobreviventes**.

**2. Encerrar uma sessão legada não pode reescrever o motivo.** `save_estado`
grava estado e horário, nunca o motivo — mas nada protegia isso. Um refactor
que passasse a gravar o registro inteiro faria a sessão antiga aparecer como
"manutenção": um valor plausível que **ninguém digitou**, e que a auditoria
leria como declaração de quem abriu a sessão. Virou teste, e o mutante morre.

**3. Verificação cruzada das âncoras do tour.** O teste unitário valida o
*formato* da âncora (`[data-tour="…"]`), não se o elemento **existe** — e uma
âncora órfã não dá erro, só perde o alvo em silêncio. Script que cruza
declaração e JSX: **11 de 11**. Prova positiva: com uma âncora quebrada de
propósito, ele acusa e sai com erro.

Durante essa prova eu sabotei `passos.ts` e o backup caiu em `/tmp` em vez do
scratchpad, deixando o arquivo quebrado por um momento. Restaurado e
reconferido (18 testes verdes, `tsc` limpo) — mas vale a nota: **ao sabotar
um arquivo de propósito, conferir que o backup existe onde se espera antes de
rodar a prova.**

**4. `backend/gravacoes/` estava fora do `.gitignore`.** 36 arquivos `.jsonl`
com o conteúdo do que pessoas digitaram em terminais, prontos para entrar num
commit. Versionar uma gravação a espalha por todo clone do repositório — fora
do cofre, fora da auditoria e sem volta, porque o histórico guarda.

Conferido que nunca chegaram a ser rastreadas (`git ls-files`), e que nenhum
`.env`, `.pem`, `.pfx` ou `.key` está no índice. `gravacoes/` e
`exportacoes/` entraram no `.gitignore`.

O achado veio de ler o `git status` inteiro antes de dar por encerrado — e
não da suíte, que não tem como saber o que deveria ou não ser versionado.

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
- [x] **Captura automática por proxy SSH** — **feito e provado contra SSH
      real** (26/10). `ProxySsh` guarda a fila de eventos e
      `ServidorDeSessoes` (asyncssh) aceita a conexão, busca a credencial do
      alvo no cofre e copia os dois sentidos. Para ligar: instalar o extra
      `ssh`, gerar a chave de host em arquivo (`ssh-keygen -t ed25519`) e
      `VAULT_SESSAO_CAPTURA=proxy-ssh`.
- [x] **Armazenamento imutável de gravação** — `ArmazenamentoS3` escrito e
      provado contra S3 com Object Lock (26/10). Falta só o bucket de
      produção: COMPLIANCE, versionado, e credencial **sem** `DeleteObject`.
- [x] **KMS como provedor de chave** — adaptador e fiação já existiam;
      agora provado contra KMS real (26/10). Falta a credencial da AWS e
      `VAULT_KMS_KEY_ID`. **Até lá a KEK está em memória:** quem lê o
      processo decifra o cofre inteiro offline.
- [x] **Gate do Postgres desta rodada** — 934 verdes em 9min33s (26/10).
