// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { esquecerVisto, jaViu, marcarVisto } from './passos'

/**
 * Memória do "já vi", que é a única parte do tour que toca o navegador.
 *
 * Arquivo separado para declarar `jsdom` sem arrastar o DOM para os testes
 * de função pura, como o `vite.config.ts` deste projeto pede.
 */

describe('memória do "já vi"', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('começa como não visto e grava depois de concluir', () => {
    expect(jaViu('cofres')).toBe(false)
    marcarVisto('cofres')
    expect(jaViu('cofres')).toBe(true)
  })

  it('esquecer devolve ao estado inicial, para reabrir o tour', () => {
    marcarVisto('cofres')
    esquecerVisto('cofres')
    expect(jaViu('cofres')).toBe(false)
  })

  it('não mistura tours diferentes', () => {
    marcarVisto('cofres')
    expect(jaViu('credenciais')).toBe(false)
  })

  it('responde false quando o armazenamento lança (aba anônima)', () => {
    const espiao = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(() => {
        throw new DOMException('bloqueado')
      })
    // Lançar aqui derrubaria a tela inteira no carregamento — um tour não
    // pode ser capaz disso.
    expect(() => jaViu('cofres')).not.toThrow()
    expect(jaViu('cofres')).toBe(false)
    espiao.mockRestore()
  })

  it('não lança ao gravar com armazenamento bloqueado', () => {
    const espiao = vi
      .spyOn(Storage.prototype, 'setItem')
      .mockImplementation(() => {
        throw new DOMException('bloqueado')
      })
    expect(() => marcarVisto('cofres')).not.toThrow()
    espiao.mockRestore()
  })
})
