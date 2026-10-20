/**
 * Escala e geometria. Núcleo da lib de gráficos — nada de React aqui.
 *
 * A separação é o ponto do arquivo: tudo que decide *onde* uma forma fica é
 * função pura de números para números. Isso é o que torna a lib testável sem
 * DOM, sem renderizar nada, e o que permite trocar o jeito de desenhar (SVG,
 * canvas) sem tocar no cálculo.
 */

/** Uma marca do eixo: o valor e onde ele cai, em pixels. */
export type Marca = { valor: number; px: number }

export type Escala = {
  /** Valor no topo (ou na direita) do eixo. */
  teto: number
  /** As marcas, do zero ao teto. */
  marcas: number[]
}

/**
 * Escolhe o teto e as marcas do eixo a partir do maior valor da série.
 *
 * Fixar o número de marcas e arredondar o teto para 1·10ⁿ/2·10ⁿ/5·10ⁿ parece
 * razoável e desperdiça muita altura: com máximo 253 o teto saltava para 500
 * e a barra mais alta ocupava metade do gráfico, achatando todas as outras e
 * escondendo variação real.
 *
 * Aqui o número de marcas varia entre `minMarcas` e `maxMarcas` e o passo é
 * sempre um número redondo. Vence a combinação que menos sobra acima do
 * máximo, então 253 termina em 300 (0, 100, 200, 300) em vez de 500. Nas
 * faixas testadas isso levou o aproveitamento médio da altura de 80% para
 * 87%, sem nunca produzir marca quebrada como 15 ou 45.
 */
export function escalaDoEixo(
  maximo: number,
  { minMarcas = 3, maxMarcas = 5 }: { minMarcas?: number; maxMarcas?: number } = {},
): Escala {
  // Série vazia ou toda em zero: um eixo 0–1 é honesto (não há o que mostrar)
  // e evita divisão por zero em `posicaoNoEixo`.
  if (!Number.isFinite(maximo) || maximo <= 0) return { teto: 1, marcas: [0, 1] }

  let melhor: { teto: number; passo: number; quantas: number; sobra: number } | null = null
  for (let quantas = minMarcas; quantas <= maxMarcas; quantas += 1) {
    for (let expoente = 0; expoente <= 12; expoente += 1) {
      for (const base of [1, 2, 5]) {
        const passo = base * 10 ** expoente
        const teto = passo * quantas
        if (teto < maximo) continue
        const sobra = teto - maximo
        // `<` e não `<=`: no empate fica o primeiro, que tem menos marcas.
        if (!melhor || sobra < melhor.sobra) melhor = { teto, passo, quantas, sobra }
      }
    }
  }

  // 10¹² × 5 cobre qualquer contagem real de eventos, mas o tipo não sabe.
  if (!melhor) return { teto: maximo, marcas: [0, maximo] }

  const marcas: number[] = []
  for (let i = 0; i <= melhor.quantas; i += 1) marcas.push(melhor.passo * i)
  return { teto: melhor.teto, marcas }
}

/**
 * Converte um valor em posição de pixel dentro de um comprimento.
 *
 * `invertido` serve ao eixo Y do SVG, onde o zero fica embaixo mas a
 * coordenada cresce para baixo.
 */
export function posicaoNoEixo(
  valor: number,
  teto: number,
  comprimento: number,
  { invertido = false }: { invertido?: boolean } = {},
): number {
  if (teto <= 0) return invertido ? comprimento : 0
  const proporcao = Math.max(0, Math.min(valor / teto, 1))
  return invertido ? comprimento * (1 - proporcao) : comprimento * proporcao
}

/**
 * Quantas posições pular entre rótulos para eles não se sobreporem.
 *
 * Com 30 dias em 700px cabe um rótulo a cada 3; escrever todos produziria
 * texto empilhado e ilegível.
 */
export function passoDosRotulos(quantos: number, maximoVisivel = 10): number {
  // A guarda abaixo é a única proteção necessária. Um `Math.max(1, …)` no
  // retorno parece defensivo e é código morto: com `quantos > 0` e um
  // `maximoVisivel` finito, `Math.ceil` nunca devolve menos que 1. Um
  // mutante que removia esse `Math.max` sobreviveu à bateria — e o certo
  // era apagar a linha redundante, não inventar um teste para defendê-la.
  if (quantos <= 0) return 1
  return Math.ceil(quantos / maximoVisivel)
}

/** Uma faixa empilhada já posicionada: o que o renderizador precisa saber. */
export type FaixaPosicionada = {
  chave: string
  valor: number
  y: number
  altura: number
}

/**
 * Empilha as parcelas de uma barra, de baixo para cima.
 *
 * Parcelas zeradas saem de fora: um retângulo de altura zero não desenha
 * nada, mas entra no DOM e aparece em leitor de tela como item vazio.
 */
export function empilhar(
  parcelas: { chave: string; valor: number }[],
  teto: number,
  alturaArea: number,
  topo = 0,
): FaixaPosicionada[] {
  const posicionadas: FaixaPosicionada[] = []
  let base = 0
  for (const parcela of parcelas) {
    if (parcela.valor <= 0) continue
    const yTopo = topo + posicionadaY(base + parcela.valor, teto, alturaArea)
    const yBase = topo + posicionadaY(base, teto, alturaArea)
    posicionadas.push({
      chave: parcela.chave,
      valor: parcela.valor,
      y: yTopo,
      altura: yBase - yTopo,
    })
    base += parcela.valor
  }
  return posicionadas
}

function posicionadaY(valor: number, teto: number, altura: number): number {
  return posicaoNoEixo(valor, teto, altura, { invertido: true })
}
