// @vitest-environment jsdom
import { afterEach, describe, expect, it } from 'vitest'
import { posicionar, type Retangulo } from './Tour'

/**
 * Posicionamento do balão do tour.
 *
 * O erro aqui não levanta exceção nem deixa teste vermelho: aparece como
 * balão cortado na tela de alguém, com o título fora da janela. Foi assim
 * que o defeito corrigido aqui apareceu — vendo o tour rodar, não na
 * suíte.
 */

const ALTURA_JANELA = 800
const LARGURA_JANELA = 1400
const LARGURA_BALAO = 340

function janela(altura = ALTURA_JANELA, largura = LARGURA_JANELA) {
  Object.defineProperty(window, 'innerHeight', { value: altura, writable: true })
  Object.defineProperty(window, 'innerWidth', { value: largura, writable: true })
}

function alvo(parcial: Partial<Retangulo> = {}): Retangulo {
  return { topo: 300, esquerda: 500, largura: 200, altura: 60, ...parcial }
}

/** Topo do balão, já resolvido em número pela própria `posicionar`. */
function topoEfetivo(estilo: React.CSSProperties) {
  if (typeof estilo.top !== 'number') {
    throw new Error('balão sem posição vertical numérica')
  }
  return estilo.top
}

afterEach(() => janela())

describe('posicionar', () => {
  it('centraliza quando o passo não tem âncora', () => {
    const { estilo, seta } = posicionar(null)
    expect(estilo.top).toBe('50%')
    expect(seta).toBeNull()
  })

  it('fica abaixo do alvo quando há espaço', () => {
    janela()
    const a = alvo({ topo: 100 })
    const { estilo, seta } = posicionar(a)
    expect(estilo.top).toBe(a.topo + a.altura + 14)
    // A seta aponta para o alvo, que está ACIMA do balão.
    expect(seta).toBe('cima')
  })

  it('sobe quando o alvo está no fim da página', () => {
    janela()
    const a = alvo({ topo: 700 })
    const { estilo, seta } = posicionar(a)
    // Acima do alvo: o balão termina antes de onde o alvo começa.
    expect(Number(estilo.top) + Number(estilo.maxHeight)).toBeLessThanOrEqual(
      a.topo,
    )
    expect(seta).toBe('baixo')
  })

  it('não estoura a janela quando nenhum lado comporta o balão', () => {
    // O defeito corrigido: alvo alto numa janela baixa. Ancorado por
    // `bottom` logo acima dele, o balão crescia para cima e saía da tela,
    // levando o título junto — e o que fica fora da janela não dá nem para
    // rolar até.
    janela(400)
    const { estilo } = posicionar(alvo({ topo: 150, altura: 40 }))
    expect(topoEfetivo(estilo)).toBeGreaterThanOrEqual(0)
    expect(
      topoEfetivo(estilo) + Number(estilo.maxHeight),
    ).toBeLessThanOrEqual(400)
  })

  it('escolhe o lado com mais espaço quando nenhum tem o ideal', () => {
    // Janela de 400: acima do alvo sobram ~136px, abaixo ~204px. Tem de ir
    // para baixo, que é o maior, em vez de insistir em cima.
    janela(400)
    const { estilo, seta } = posicionar(alvo({ topo: 150, altura: 40 }))
    expect(estilo.top).toBeDefined()
    expect(seta).toBe('cima')
  })

  it('limita a altura ao espaço do lado escolhido', () => {
    janela(400)
    const { estilo } = posicionar(alvo({ topo: 150, altura: 40 }))
    // 400 - (150+40) - 14 - 12 = 184
    expect(Number(estilo.maxHeight)).toBeLessThanOrEqual(184)
    // E rola por dentro em vez de cortar o conteúdo.
    expect(estilo.overflowY).toBe('auto')
  })

  it('garante uma altura mínima utilizável quando a janela comporta', () => {
    // O balão precisa de altura para título e botões, nem que role por
    // dentro. Numa janela que comporta os 140px, eles valem.
    janela(400)
    const { estilo } = posicionar(alvo({ topo: 150, altura: 40 }))
    expect(Number(estilo.maxHeight)).toBeGreaterThanOrEqual(140)
  })

  it('o piso de altura não empurra o balão para fora da tela', () => {
    // Varredura, não um caso escolhido a dedo: foi exatamente assim que
    // sobrou um buraco na primeira correção. O teto por lado resolvia as
    // janelas médias, mas o piso de 140px ainda estourava as baixas — e o
    // caso que eu havia escolhido para testar não era um deles.
    for (const altura of [160, 180, 200, 240, 300, 360, 420, 600, 900]) {
      for (const topo of [0, 40, 90, 150, altura - 80, altura - 20]) {
        janela(altura)
        const { estilo } = posicionar(alvo({ topo, altura: 40 }))
        const alturaBalao = Number(estilo.maxHeight)
        const topoBalao = topoEfetivo(estilo)

        expect(
          topoBalao,
          `janela ${altura}px, alvo em ${topo}px: topo do balão em ${topoBalao}`,
        ).toBeGreaterThanOrEqual(0)
        expect(
          topoBalao + alturaBalao,
          `janela ${altura}px, alvo em ${topo}px: balão passa do fim`,
        ).toBeLessThanOrEqual(altura)
      }
    }
  })

  it('não deixa o balão sair pela esquerda', () => {
    janela()
    const { estilo } = posicionar(alvo({ esquerda: 0, largura: 40 }))
    expect(Number(estilo.left)).toBeGreaterThanOrEqual(12)
  })

  it('não deixa o balão sair pela direita', () => {
    janela()
    const { estilo } = posicionar(alvo({ esquerda: LARGURA_JANELA - 40, largura: 40 }))
    expect(Number(estilo.left)).toBeLessThanOrEqual(
      LARGURA_JANELA - LARGURA_BALAO - 12,
    )
  })

  it('centra o balão no alvo quando há folga dos dois lados', () => {
    janela()
    const a = alvo({ esquerda: 600, largura: 200 })
    const { estilo } = posicionar(a)
    expect(Number(estilo.left)).toBe(a.esquerda + a.largura / 2 - LARGURA_BALAO / 2)
  })
})
