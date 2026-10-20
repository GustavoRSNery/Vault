/**
 * Testes do núcleo da lib de gráficos.
 *
 * O que se protege aqui é o que não dá para ver num print: a escala que
 * desperdiça altura, a marca quebrada, a divisão por zero numa série vazia.
 * São erros que passam despercebidos porque o gráfico *parece* certo.
 */

import { describe, expect, it } from 'vitest'

import { empilhar, escalaDoEixo, passoDosRotulos, posicaoNoEixo } from './escala'

describe('escalaDoEixo', () => {
  it('nunca termina abaixo do maior valor', () => {
    for (const maximo of [1, 3, 7, 17, 48, 86, 120, 253, 338, 499, 1200, 97531]) {
      expect(escalaDoEixo(maximo).teto).toBeGreaterThanOrEqual(maximo)
    }
  })

  it('produz marcas inteiras, em ordem, começando no zero', () => {
    for (const maximo of [3, 17, 48, 86, 253, 338, 1200]) {
      const { teto, marcas } = escalaDoEixo(maximo)
      expect(marcas[0]).toBe(0)
      expect(marcas[marcas.length - 1]).toBe(teto)
      expect(marcas).toEqual([...marcas].sort((a, b) => a - b))
      for (const marca of marcas) expect(Number.isInteger(marca)).toBe(true)
    }
  })

  it('usa passo constante entre as marcas', () => {
    // Passo irregular (0, 10, 25, 40) desenharia grade enganosa: a distância
    // visual deixaria de ser proporcional à diferença de valor.
    for (const maximo of [3, 17, 48, 86, 253, 338, 499, 1200]) {
      const { marcas } = escalaDoEixo(maximo)
      const passos = marcas.slice(1).map((m, i) => m - (marcas[i] ?? 0))
      expect(new Set(passos).size).toBe(1)
    }
  })

  it('aproveita ao menos 60% da altura nas faixas reais', () => {
    // A regressão que isto trava: a versão anterior levava 253 a um teto de
    // 500, ou seja 51% — metade do gráfico vazia.
    for (const maximo of [3, 7, 17, 40, 48, 86, 120, 253, 338, 499, 1200]) {
      const { teto } = escalaDoEixo(maximo)
      expect(maximo / teto).toBeGreaterThanOrEqual(0.6)
    }
  })

  it('escolhe 300 e não 500 para máximo 253', () => {
    // O caso concreto que motivou a mudança, preso por nome.
    expect(escalaDoEixo(253)).toEqual({ teto: 300, marcas: [0, 100, 200, 300] })
  })

  it('devolve eixo 0–1 para série vazia ou zerada', () => {
    // Zero não pode virar divisão por zero lá na frente.
    for (const vazio of [0, -5, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(escalaDoEixo(vazio)).toEqual({ teto: 1, marcas: [0, 1] })
    }
  })

  it('respeita o número de marcas pedido', () => {
    const { marcas } = escalaDoEixo(100, { minMarcas: 4, maxMarcas: 4 })
    expect(marcas).toHaveLength(5) // 4 passos = 5 marcas, contando o zero
  })
})

describe('posicaoNoEixo', () => {
  it('leva zero ao começo e o teto ao fim', () => {
    expect(posicaoNoEixo(0, 100, 200)).toBe(0)
    expect(posicaoNoEixo(100, 100, 200)).toBe(200)
  })

  it('inverte para o eixo Y do SVG, onde o zero fica embaixo', () => {
    expect(posicaoNoEixo(0, 100, 200, { invertido: true })).toBe(200)
    expect(posicaoNoEixo(100, 100, 200, { invertido: true })).toBe(0)
    expect(posicaoNoEixo(50, 100, 200, { invertido: true })).toBe(100)
  })

  it('prende valores fora da faixa dentro da área', () => {
    // Sem isto, um valor acima do teto desenharia barra para fora do quadro.
    expect(posicaoNoEixo(150, 100, 200)).toBe(200)
    expect(posicaoNoEixo(-10, 100, 200)).toBe(0)
  })

  it('não divide por zero quando o teto é zero', () => {
    expect(Number.isFinite(posicaoNoEixo(5, 0, 200))).toBe(true)
  })
})

describe('passoDosRotulos', () => {
  it('escreve todos os rótulos quando cabem', () => {
    expect(passoDosRotulos(7)).toBe(1)
  })

  it('rareia os rótulos quando são muitos', () => {
    expect(passoDosRotulos(30)).toBe(3)
    expect(passoDosRotulos(90)).toBe(9)
  })

  it('nunca devolve passo zero, que travaria o laço', () => {
    for (const quantos of [0, -1]) expect(passoDosRotulos(quantos)).toBe(1)
  })
})

describe('empilhar', () => {
  it('encosta cada faixa na anterior, sem vão nem sobreposição', () => {
    const faixas = empilhar(
      [
        { chave: 'a', valor: 30 },
        { chave: 'b', valor: 20 },
      ],
      100,
      200,
    )
    expect(faixas).toHaveLength(2)
    const [primeira, segunda] = faixas
    if (!primeira || !segunda) throw new Error('faixas faltando')
    // A segunda termina exatamente onde a primeira começa.
    expect(segunda.y + segunda.altura).toBeCloseTo(primeira.y)
  })

  it('soma das alturas corresponde à soma dos valores', () => {
    const faixas = empilhar(
      [
        { chave: 'a', valor: 25 },
        { chave: 'b', valor: 25 },
        { chave: 'c', valor: 50 },
      ],
      100,
      200,
    )
    const alturaTotal = faixas.reduce((soma, f) => soma + f.altura, 0)
    expect(alturaTotal).toBeCloseTo(200)
  })

  it('descarta parcela zerada em vez de criar retângulo invisível', () => {
    // Altura zero não desenha nada, mas entra no DOM e vira item vazio em
    // leitor de tela.
    const faixas = empilhar(
      [
        { chave: 'a', valor: 10 },
        { chave: 'vazia', valor: 0 },
        { chave: 'b', valor: 10 },
      ],
      100,
      200,
    )
    expect(faixas.map((f) => f.chave)).toEqual(['a', 'b'])
  })

  it('desloca tudo pelo topo informado', () => {
    const [semTopo] = empilhar([{ chave: 'a', valor: 50 }], 100, 200)
    const [comTopo] = empilhar([{ chave: 'a', valor: 50 }], 100, 200, 12)
    if (!semTopo || !comTopo) throw new Error('faixas faltando')
    expect(comTopo.y).toBeCloseTo(semTopo.y + 12)
    expect(comTopo.altura).toBeCloseTo(semTopo.altura)
  })
})
