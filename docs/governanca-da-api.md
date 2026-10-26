# Governança da API

Quem consome a API do Vault de fora, em quais rotas e com que resultado.
A tela fica em **Administração → Consumo da API** e exige `ADMIN` no
caminho `auditoria`.

---

## O recorte: consumo externo, não a própria interface

O relatório cobre **aplicações, robôs e scripts**. As chamadas que a tela
do Vault faz no navegador ficam de fora.

A razão é prática: cada tela aberta dispara dezenas de requisições por
minuto. Incluí-las afogaria o consumo externo — a única coisa que alguém
vem aqui investigar — numa massa de chamadas do próprio sistema.

### Como a classificação funciona

Está em `Origem.classificar` (`app/domain/apiusage/entities.py`), nesta
ordem:

1. **Tem lease de aplicação?** → `aplicacao`. Um RPA autenticado por
   AppRole é consumo de máquina, mesmo que os cabeçalhos imitem a
   interface.
2. **`Sec-Fetch-Site: same-origin`?** → `tela`, e sai do relatório. Quando
   o cabeçalho `Origin` também vem, ele precisa bater com
   `VAULT_CORS_ORIGINS`.
3. **Qualquer outra coisa** → `externa`.

Quem decide é o `Sec-Fetch-Site`, não o `Origin`: aquele é preenchido pelo
**navegador** e JavaScript não consegue alterá-lo, enquanto `curl` e
scripts escolhem o `Origin` que quiserem. Um script que forje `Origin`
continua aparecendo no relatório.

> **`Origin` ausente é normal, não anomalia.** Em produção a página e a API
> ficam no mesmo host atrás do nginx, e o navegador **omite** `Origin` em
> GET same-origin. Exigi-lo foi um bug: toda a navegação da interface
> entrava como externa. Corrigido em 26/10/2026, com teste (`test_sem_origin_mas_same_origin_e_tela`).

A regra erra para o lado de **registrar**: na dúvida, a chamada entra. Uma
linha a mais é barulho; uma a menos é um consumidor invisível.

---

## O corpo das requisições não é guardado

Nenhuma coluna da tabela `api_chamadas` recebe o conteúdo enviado. Só o
**tamanho** em bytes, lido do cabeçalho `Content-Length`.

Isso vale em três camadas, de propósito:

| Camada | Garantia |
|---|---|
| Domínio | `ChamadaDeApi` não tem campo para corpo — um adaptador novo não grava sem alterar a entidade |
| Banco | `api_chamadas` não tem coluna de corpo |
| Middleware | Nunca chama `await request.body()`; não toca no fluxo de entrada |

A razão é direta: uma chamada que cria segredo carrega a **senha** no
corpo. Guardá-la numa tabela de log a deixaria em claro, fora do cofre,
sem cifragem de envelope e sem política de acesso.

O middleware também não bufferiza a requisição. Ler o corpo ali o consome
do stream e obrigaria a reinjetá-lo, fazendo o conteúdo de toda escrita
existir numa variável do processo — com chance de cair em log de exceção
ou dump de memória. O caminho escolhido é não ter o dado.

Há teste para as três camadas em `tests/e2e/test_api_governanca.py::TestCorpoNaoVazaParaOBanco`,
inclusive um que faz um login real com senha marcada e varre **todas** as
colunas de texto do que foi registrado.

---

## Retenção: 90 dias

```bash
VAULT_API_USO_RETENCAO_DIAS=90   # padrão; 0 desliga o expurgo
```

Diferente da trilha de auditoria, que **não expira** — aquilo é prova,
isto é operacional. Uma tabela de chamadas sem teto cresce até as
consultas da tela doerem.

O expurgo não é automático. Rode por agendador, uma vez ao dia:

```bash
docker compose exec api python -m app.tools.expurgar_uso_api
docker compose exec api python -m app.tools.expurgar_uso_api 30   # força 30 dias
```

Apagar dado em segundo plano, sem ninguém pedir, faz registros sumirem sem
explicação. Aqui a remoção tem um comando, um responsável e uma saída que
diz quanto saiu.

---

## O que a tela responde

| Aba | Pergunta |
|---|---|
| **Quem chama** | Alguma integração passou a consumir mais que o normal? Apareceu consumidor que ninguém reconhece? |
| **O que é chamado** | Qual dado está saindo? Qual rota está lenta? |
| **Chamada a chamada** | O caso concreto, quando as duas primeiras apontam algo |

Na aba de rotas, a coluna **pior** fica ao lado da **média** de propósito:
uma média boa esconde a chamada de vários segundos que estoura o tempo
limite do robô e derruba a integração de vez em quando.

Consumidores sem identidade são agrupados **por IP**, não num "anônimo"
único: separa uma varredura vinda de um endereço de várias tentativas
espalhadas, que são problemas diferentes.

---

## Rotas

```
GET /api/v1/api-uso/panorama   ?dias=7&origem=aplicacao
GET /api/v1/api-uso/chamadas   ?dias=7&origem=&resultado=recusado&aplicacao=&limite=200
```

`resultado` aceita `ok`, `redirecionado`, `recusado` (401/403),
`invalido` (demais 4xx) e `erro` (5xx).

Recusado é separado dos demais 4xx porque conta "quem tentou sem poder",
enquanto 404/422 contam "quem errou a chamada" — juntá-los faria um
cliente mal configurado parecer tentativa de acesso indevido.

---

## O que **não** entra no registro

- Chamadas da interface do Vault (ver recorte acima)
- `POST /auth/refresh` — o navegador o chama sozinho a cada expiração de
  token e encheria o relatório de ruído do próprio sistema
- Tudo fora de `/api/v1` (`/saude`, `/docs`, estáticos do front)
- A query string das URLs: pode carregar termo de busca, que é dado de
  quem usa, e nenhuma pergunta deste relatório precisa dela

## Falha no registro nunca derruba a API

O middleware engole o próprio erro. Quando o registro roda, quem chamou
**já recebeu a resposta** — um banco de log cheio não pode transformar uma
leitura de segredo bem sucedida em 500 para o robô que depende dela.
