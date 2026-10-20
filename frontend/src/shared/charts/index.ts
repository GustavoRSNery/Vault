/**
 * Lib de gráficos do Vault.
 *
 * Por que não usar Recharts, Chart.js ou similar: as formas que este sistema
 * precisa são retângulos sobre uma grade. Uma lib de uso geral custaria
 * centenas de KB no bundle e exigiria um tema paralelo, já que as cores aqui
 * vivem nos tokens de `design-system.css` e não em objetos JavaScript. O
 * custo de manter isto é baixo porque o núcleo é função pura e testada.
 *
 * Como a lib é organizada:
 *
 * - `escala.ts` — o cálculo. Funções puras de números para números, sem
 *   React. É onde moram as decisões difíceis (quanto o eixo aproveita da
 *   altura, como as faixas se empilham) e é o que os testes cobrem.
 * - `primitivos.tsx` — eixo, grade, legenda, moldura e alvo de leitura. As
 *   peças que todo gráfico reaproveita.
 * - Um arquivo por gráfico, montado sobre os dois acima.
 *
 * Para acrescentar um gráfico: componha os primitivos e, se precisar de
 * geometria nova, ela vai em `escala.ts` **com teste**, não dentro do
 * componente. Regra que mantém a lib viva: nenhuma cor literal nos
 * componentes — classe do design system, sempre.
 */

export { BarraDeProporcao, type ParteDaProporcao } from './BarraDeProporcao'
export { BarrasEmpilhadas, type Serie } from './BarrasEmpilhadas'
export { BarrasHorizontais, type ItemDoRanking } from './BarrasHorizontais'
export { ColunasCompactas, type ColunaDoDia } from './ColunasCompactas'
export {
  AlvoDeLeitura,
  EixoHorizontal,
  EixoVertical,
  Legenda,
  MARGEM_PADRAO,
  Quadro,
  type ItemDeLegenda,
  type Margem,
} from './primitivos'
export {
  empilhar,
  escalaDoEixo,
  passoDosRotulos,
  posicaoNoEixo,
  type Escala,
  type FaixaPosicionada,
} from './escala'
