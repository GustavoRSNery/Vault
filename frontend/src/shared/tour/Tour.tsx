import { useEffect, useLayoutEffect, useState } from 'react'
import {
  ehUltimo,
  jaViu,
  marcarVisto,
  passoAnterior,
  proximoPasso,
  tourDe,
  type Tour as TipoTour,
} from './passos'

type Retangulo = { topo: number; esquerda: number; largura: number; altura: number }

/** Onde o balão cabe em relação ao elemento destacado. */
function posicionar(alvo: Retangulo | null): {
  estilo: React.CSSProperties
  seta: 'cima' | 'baixo' | null
} {
  if (!alvo) {
    return {
      estilo: { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' },
      seta: null,
    }
  }

  const LARGURA = 340
  const ESPACO = 14
  const espacoAbaixo = window.innerHeight - (alvo.topo + alvo.altura)
  // Abaixo por padrão; acima só quando não cabe. Um balão que cobre o
  // próprio elemento que está explicando não explica nada.
  const abaixo = espacoAbaixo > 220

  const esquerda = Math.min(
    Math.max(alvo.esquerda + alvo.largura / 2 - LARGURA / 2, 12),
    window.innerWidth - LARGURA - 12,
  )

  return {
    estilo: {
      width: LARGURA,
      left: esquerda,
      top: abaixo ? alvo.topo + alvo.altura + ESPACO : undefined,
      bottom: abaixo
        ? undefined
        : window.innerHeight - alvo.topo + ESPACO,
    },
    seta: abaixo ? 'cima' : 'baixo',
  }
}

/**
 * Tour guiado de uma tela.
 *
 * **Oferecido, nunca imposto.** Abre sozinho só na primeira visita e some
 * para sempre depois de concluído ou dispensado. Um tour que reaparece é
 * treinamento para clicar em "fechar" sem ler — e aí não serve nem na
 * primeira vez.
 *
 * O destaque é um recorte na cortina, não uma borda colorida: escurecer tudo
 * menos o elemento diz "olhe aqui" sem competir com a interface que está
 * sendo explicada.
 */
export function Tour({
  id,
  aberto,
  aoFechar,
}: {
  id: string
  aberto: boolean
  aoFechar: () => void
}) {
  const tour = tourDe(id)
  const [passo, setPasso] = useState(0)
  const [alvo, setAlvo] = useState<Retangulo | null>(null)

  const atual = tour?.passos[passo]

  // `useLayoutEffect` e não `useEffect`: medir depois da pintura faria o
  // balão aparecer no lugar errado por um quadro, e o salto é visível.
  useLayoutEffect(() => {
    if (!aberto || !atual) return

    const medir = () => {
      if (!atual.alvo) {
        setAlvo(null)
        return
      }
      const elemento = document.querySelector(atual.alvo)
      if (!elemento) {
        // Passo ancorado em algo que não está nesta tela (lista vazia, por
        // exemplo): vira passo centralizado em vez de sumir. Some, a
        // explicação se perde sem ninguém saber que existia.
        setAlvo(null)
        return
      }
      const r = elemento.getBoundingClientRect()
      setAlvo({ topo: r.top, esquerda: r.left, largura: r.width, altura: r.height })
    }

    medir()
    window.addEventListener('resize', medir)
    window.addEventListener('scroll', medir, true)
    return () => {
      window.removeEventListener('resize', medir)
      window.removeEventListener('scroll', medir, true)
    }
  }, [aberto, atual])

  // Rolar o elemento para a vista: destacar algo fora da tela é destacar nada.
  useEffect(() => {
    if (!aberto || !atual?.alvo) return
    document.querySelector(atual.alvo)?.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
    })
  }, [aberto, atual])

  useEffect(() => {
    if (!aberto) return
    const tecla = (e: KeyboardEvent) => {
      if (e.key === 'Escape') aoFechar()
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [aberto, aoFechar])

  useEffect(() => {
    if (aberto) setPasso(0)
  }, [aberto])

  if (!aberto || !tour || !atual) return null

  const total = tour.passos.length
  const ultimo = ehUltimo(passo, total)
  const { estilo, seta } = posicionar(alvo)

  const concluir = () => {
    marcarVisto(tour.id)
    aoFechar()
  }

  return (
    <div className="tour-cortina" role="dialog" aria-label={tour.titulo}>
      {alvo && (
        <div
          className="tour-recorte"
          style={{
            top: alvo.topo - 6,
            left: alvo.esquerda - 6,
            width: alvo.largura + 12,
            height: alvo.altura + 12,
          }}
          aria-hidden="true"
        />
      )}

      <div className={`tour-balao${seta ? ` seta-${seta}` : ''}`} style={estilo}>
        <div className="tour-cap">
          {tour.titulo} · {passo + 1} de {total}
        </div>
        <h3 className="tour-titulo">{atual.titulo}</h3>
        <p className="tour-texto">{atual.texto}</p>

        <div className="tour-pontos" aria-hidden="true">
          {tour.passos.map((p, i) => (
            <span key={p.titulo} className={i === passo ? 'ativo' : ''} />
          ))}
        </div>

        <div className="tour-acoes">
          <button type="button" className="tour-pular" onClick={concluir}>
            {ultimo ? '' : 'Pular'}
          </button>
          <div className="row" style={{ gap: 8 }}>
            {passo > 0 && (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setPasso(passoAnterior(passo))}
              >
                Voltar
              </button>
            )}
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() =>
                ultimo ? concluir() : setPasso(proximoPasso(passo, total))
              }
            >
              {ultimo ? 'Entendi' : 'Próximo'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Liga o tour a uma tela: abre sozinho na primeira visita e devolve o
 * controle para o botão de ajuda.
 */
export function useTour(id: string): {
  aberto: boolean
  abrir: () => void
  fechar: () => void
} {
  const [aberto, setAberto] = useState(false)

  useEffect(() => {
    if (!jaViu(id)) setAberto(true)
  }, [id])

  return {
    aberto,
    abrir: () => setAberto(true),
    fechar: () => setAberto(false),
  }
}

/** O botão que reabre o tour depois de concluído. */
export function BotaoTour({ aoAbrir }: { aoAbrir: () => void }) {
  return (
    <button
      type="button"
      className="btn btn-ghost btn-sm"
      onClick={aoAbrir}
      title="Rever a explicação desta tela"
    >
      Como funciona?
    </button>
  )
}

export type { TipoTour }
