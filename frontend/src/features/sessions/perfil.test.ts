import { describe, expect, it } from 'vitest'
import { FATIAS, perfilDeAtividade } from './perfil'

describe('perfilDeAtividade', () => {
  it('devolve sempre o mesmo número de fatias', () => {
    expect(perfilDeAtividade('abc', 50, 600_000)).toHaveLength(FATIAS)
    expect(perfilDeAtividade('abc', 0, 0)).toHaveLength(FATIAS)
  })

  it('é estável: o mesmo id desenha igual', () => {
    // Sem isto as barras tremeriam a cada digitação na busca, porque a
    // lista re-renderiza a cada tecla.
    const a = perfilDeAtividade('sessao-1', 40, 300_000)
    const b = perfilDeAtividade('sessao-1', 40, 300_000)
    expect(a).toEqual(b)
  })

  it('ids diferentes desenham diferente', () => {
    const a = perfilDeAtividade('sessao-1', 40, 300_000)
    const b = perfilDeAtividade('sessao-2', 40, 300_000)
    expect(a).not.toEqual(b)
  })

  it('sessão sem evento fica zerada, não inventa atividade', () => {
    expect(perfilDeAtividade('x', 0, 600_000)).toEqual(
      Array.from({ length: FATIAS }, () => 0),
    )
  })

  it('nunca passa de 1 nem fica negativo', () => {
    for (const eventos of [1, 50, 5_000, 1_000_000]) {
      for (const altura of perfilDeAtividade('x', eventos, 60_000)) {
        expect(altura).toBeGreaterThanOrEqual(0)
        expect(altura).toBeLessThanOrEqual(1)
      }
    }
  })

  it('sessão densa fica mais alta que sessão esparsa', () => {
    // É a única coisa que a miniatura promete: distinguir intensa de calma.
    const soma = (v: number[]) => v.reduce((a, b) => a + b, 0)
    const densa = soma(perfilDeAtividade('mesmo-id', 400, 300_000))
    const esparsa = soma(perfilDeAtividade('mesmo-id', 4, 300_000))
    expect(densa).toBeGreaterThan(esparsa)
  })

  it('duração zero não estoura a divisão', () => {
    const r = perfilDeAtividade('x', 10, 0)
    expect(r.every((n) => Number.isFinite(n))).toBe(true)
  })

  it('id vazio não quebra', () => {
    expect(() => perfilDeAtividade('', 10, 1000)).not.toThrow()
    expect(perfilDeAtividade('', 10, 1000)).toHaveLength(FATIAS)
  })

  it('a mesma densidade em durações diferentes dá alturas próximas', () => {
    // 10 eventos/min nos dois casos: a barra fala de densidade, não de
    // volume total — senão toda sessão longa pareceria intensa.
    const soma = (v: number[]) => v.reduce((a, b) => a + b, 0)
    const curta = soma(perfilDeAtividade('id', 20, 120_000))
    const longa = soma(perfilDeAtividade('id', 100, 600_000))
    expect(Math.abs(curta - longa)).toBeLessThan(0.01)
  })
})
