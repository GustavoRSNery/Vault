import { describe, expect, it } from 'vitest'
import {
  TOUR_AUDITORIA,
  TOUR_CERTIFICADOS,
  TOUR_CHAVES,
  TOUR_COFRES,
  TOUR_CREDENCIAIS,
  TOUR_DISPOSITIVOS,
  TOUR_GRAVACOES,
  TOUR_PERFIL,
  TOUR_SESSOES,
  TOUR_SOLICITACOES,
  ehUltimo,
  passoAnterior,
  proximoPasso,
  tourDe,
} from './passos'

const TODOS = [
  TOUR_COFRES,
  TOUR_CREDENCIAIS,
  TOUR_CERTIFICADOS,
  TOUR_CHAVES,
  TOUR_DISPOSITIVOS,
  TOUR_SOLICITACOES,
  TOUR_SESSOES,
  TOUR_GRAVACOES,
  TOUR_AUDITORIA,
  TOUR_PERFIL,
]

describe('navegação entre passos', () => {
  it('avança até o último e para', () => {
    expect(proximoPasso(0, 3)).toBe(1)
    expect(proximoPasso(1, 3)).toBe(2)
    // No último, continuar não pode estourar o índice e sumir com o balão.
    expect(proximoPasso(2, 3)).toBe(2)
  })

  it('volta até o primeiro e para', () => {
    expect(passoAnterior(2)).toBe(1)
    expect(passoAnterior(0)).toBe(0)
  })

  it('reconhece o último passo, que é quando o botão vira "Concluir"', () => {
    expect(ehUltimo(1, 3)).toBe(false)
    expect(ehUltimo(2, 3)).toBe(true)
  })

  it('não quebra com tour de um passo só', () => {
    expect(proximoPasso(0, 1)).toBe(0)
    expect(ehUltimo(0, 1)).toBe(true)
  })

  it('não quebra com tour vazio', () => {
    expect(proximoPasso(0, 0)).toBe(0)
    expect(ehUltimo(0, 0)).toBe(true)
  })
})

describe('catálogo de tours', () => {
  it('acha cada tour pelo id', () => {
    for (const tour of TODOS) {
      expect(tourDe(tour.id)).toBe(tour)
    }
  })

  it('devolve undefined para id desconhecido, em vez de um tour vazio', () => {
    expect(tourDe('inexistente')).toBeUndefined()
  })

  it('cobre Segredos, Uso e histórico, e o perfil', () => {
    expect(TODOS.map((t) => t.id).sort()).toEqual([
      'auditoria',
      'certificados',
      'chaves-api',
      'cofres',
      'credenciais',
      'dispositivos',
      'gravacoes',
      'perfil',
      'sessoes',
      'solicitacoes',
    ])
  })

  it('o catálogo não tem tour fora desta lista', () => {
    // Pega o esquecimento inverso: registrar o tour em TOURS e esquecer de
    // exportá-lo faria o `tourDe` achar algo que nenhum teste conhece.
    for (const id of TODOS.map((t) => t.id)) {
      expect(tourDe(id)).toBeDefined()
    }
  })
})

describe('qualidade dos passos', () => {
  it('todo tour tem ao menos dois passos', () => {
    // Um passo só não é um tour: é um aviso, e aviso tem outro lugar.
    for (const tour of TODOS) {
      expect(tour.passos.length).toBeGreaterThanOrEqual(2)
    }
  })

  it('o primeiro passo não tem âncora: explica a tela antes de apontar', () => {
    for (const tour of TODOS) {
      expect(tour.passos[0]?.alvo).toBeUndefined()
    }
  })

  it('nenhum texto passa de 300 caracteres', () => {
    // Acima disso ninguém lê num balão — e um passo não lido é pior que
    // nenhum, porque custa um clique e não entrega nada.
    for (const tour of TODOS) {
      for (const passo of tour.passos) {
        expect(passo.texto.length).toBeLessThanOrEqual(300)
      }
    }
  })

  it('todo título é curto o bastante para ser lido de relance', () => {
    for (const tour of TODOS) {
      for (const passo of tour.passos) {
        expect(passo.titulo.length).toBeLessThanOrEqual(60)
      }
    }
  })

  it('âncoras usam data-tour, não classe de estilo', () => {
    // Seletor de classe quebra em silêncio no primeiro ajuste de CSS: o
    // destaque some e ninguém percebe. `data-tour` existe só para isto.
    for (const tour of TODOS) {
      for (const passo of tour.passos) {
        if (passo.alvo !== undefined) {
          expect(passo.alvo).toMatch(/^\[data-tour="[a-z-]+"\]$/)
        }
      }
    }
  })
})
