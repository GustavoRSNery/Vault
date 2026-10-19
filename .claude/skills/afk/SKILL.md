---
name: afk
description: Modo autônomo do Vault de Senhas. Use quando o usuário disser "afk", "pode seguir sem parar", "siga sozinho", "vou sair", "continue sem perguntar" — ou quando mandar continuar o projeto sem especificar o quê. Decide o próximo passo pelas prioridades registradas, executa de ponta a ponta e anota tudo em DIARIO.md para retomada.
---

# Modo AFK — Vault de Senhas

O usuário saiu. Decida por ele, execute e **registre**. Ele conferirá depois
pelo `DIARIO.md`, não acompanhando a conversa.

## A regra que vale mais que as outras

**Não pergunte. Decida, anote a decisão e o porquê, siga.**

Se uma escolha for ambígua, escolha a opção mais conservadora do ponto de
vista de segurança, registre a alternativa descartada em `DIARIO.md` e siga.
Ele reverte depois se discordar — o repositório é local e tem histórico.

Exceção única, em que você **para e espera**: algo fora do alcance do
terminal, como elevação de UAC, credencial que só ele tem, ou uma conta em
serviço externo. Nesse caso anote o bloqueio no diário, **faça todo o resto
que não depende disso** e só então pare.

## Preferências já estabelecidas (não re-pergunte)

Decisões que ele já tomou neste projeto, em conversas anteriores:

- **Tudo local.** Docker, nada de nuvem. Pode criar repositório git, mas roda
  na máquina dele.
- **Commits sem pedir.** Ele autorizou. Mensagem em português, explicando o
  *porquê* da decisão técnica, não o *o quê* do diff.
- **Nunca citar IA, Claude ou Co-Authored-By** em commit, PR ou comentário.
  Esta regra não tem exceção.
- **Teste de mutação é obrigatório.** Reverta o comportamento, confirme que o
  teste falha, restaure. Mutante sobrevivente = investigue a causa (teste
  fraco, código redundante ou regra morta), não reforce o teste às cegas.
- **Suíte em Postgres, sempre que mexer em SQL, data ou tipo de coluna.** A
  divergência SQLite/Postgres já causou dois bugs neste projeto. Rodar só em
  SQLite não conta como validado.
- **Validar no navegador, não só no teste.** O que vale é o que ele vê. Dois
  bugs reais (cache entre sessões, timezone) só apareceram com o sistema no ar.
- **Honestidade na interface acima de tela bonita.** Se a garantia é parcial,
  a tela diz que é parcial. Selo verde enganoso é pior que aviso amarelo.
- **Comentário explica a decisão, não a sintaxe.** Sobretudo quando a escolha
  tem custo e alguém poderia "simplificar" sem saber o que quebraria.
- **Ele prefere celeridade a polimento**, mas não à custa de correção: entregar
  rápido o que funciona, não entregar rápido o que parece funcionar.

## Como escolher o próximo passo

Leia `DIARIO.md` (a seção **Em aberto**) e pegue o primeiro item não bloqueado.
Se estiver vazio ou desatualizado, use esta ordem:

1. **Fechar o que está pela metade** — nada meio-pronto fica para trás.
2. **Risco de segurança real** no que já existe.
3. **Próximo item estrutural** da fase atual.
4. **Telas do inventário** (`python docs/mapa_telas.py` mostra o que falta).

Não comece frente nova com outra inacabada.

## O ciclo de cada entrega

Entregue **de ponta a ponta**. Backend sem tela é metade; tela sem teste não
está pronta.

1. Domínio (Python puro) → testes unitários
2. Persistência → testes de integração
3. Rota → testes e2e
4. Tela → `npx tsc --noEmit` **e** `npm run build`
5. **Mutação** nas invariantes que importam
6. Suíte completa em SQLite **e** Postgres
7. `docker compose build && up`, validar no navegador
8. Commit
9. **Anotar no `DIARIO.md`**

Pular o passo 9 é o pior erro possível neste modo: o trabalho fica, mas ele
não tem como saber o que foi decidido nem por quê.

## O DIARIO.md

Na raiz do projeto. Crie se não existir, no formato abaixo. Acrescente no
topo, para o mais recente ficar primeiro.

```markdown
# Diário do Vault

Registro do que foi feito em modo autônomo, para retomada.

## <data> — <o que foi entregue>

**Decidi:** <a escolha, em uma linha>
**Porque:** <o motivo — é isto que ele vai querer conferir>
**Descartei:** <alternativa e por que não>

**Feito:** <o que mudou, em 2-4 linhas>
**Validado:** <testes, dialetos, o que foi visto no navegador>
**Commit:** <hash curto + título>

**Surpresa:** <bug ou comportamento inesperado encontrado, se houve>

---
```

Seja específico onde importa: "corrigi o cálculo" não ajuda ninguém;
"o SQLite devolve datetime sem timezone e o Postgres com, então a leitura
estourava num dialeto só" ajuda.

Mantenha no fim do arquivo uma seção **Em aberto**, substituída a cada vez:

```markdown
## Em aberto

- [ ] <próximo item> — <por que importa>
- [ ] <item> — **BLOQUEADO:** <o que precisa dele>
```

## Quando ele voltar

Resuma o que **ele vê**, não o que você fez: o que mudou na tela, o que agora
é possível, o que você decidiu no lugar dele e o que ficou bloqueado. Aponte
o `DIARIO.md` para o detalhe.

Se tomou uma decisão que ele pode querer reverter, diga isso explicitamente —
é mais barato reverter cedo.
