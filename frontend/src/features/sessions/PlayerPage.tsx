import { useQuery } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'
import { formatarDuracao, type Sessao } from './SessoesPage'

type Evento = {
  deslocamento_ms: number
  tipo: string
  conteudo: string
}

type Detalhe = Sessao & {
  linha_do_tempo: Evento[]
  aviso: string | null
}

const VELOCIDADES = [1, 2, 4, 8]

/** Marca o instante no formato que a timeline usa: 1:23. */
function marcar(ms: number): string {
  const total = Math.floor(ms / 1000)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

export function PlayerPage() {
  const { id = '' } = useParams<{ id: string }>()
  const [posicao, setPosicao] = useState(0)
  const [tocando, setTocando] = useState(false)
  const [velocidade, setVelocidade] = useState(1)
  const [busca, setBusca] = useState('')
  const timerRef = useRef<number | null>(null)

  const { data: sessao, isLoading, error } = useQuery({
    queryKey: ['sessao', id],
    queryFn: () => request<Detalhe>(`/sessoes/${encodeURIComponent(id)}`),
    retry: false,
  })

  const total = sessao?.linha_do_tempo.at(-1)?.deslocamento_ms ?? 0

  // Avança a posição enquanto estiver tocando. O intervalo é fixo e a
  // velocidade multiplica o passo: mexer no intervalo daria reprodução
  // irregular em velocidades altas.
  useEffect(() => {
    if (!tocando) return
    timerRef.current = window.setInterval(() => {
      setPosicao((atual) => {
        const proximo = atual + 100 * velocidade
        if (proximo >= total) {
          setTocando(false)
          return total
        }
        return proximo
      })
    }, 100)
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current)
    }
  }, [tocando, velocidade, total])

  const visiveis = useMemo(
    () =>
      (sessao?.linha_do_tempo ?? []).filter(
        (e) => e.deslocamento_ms <= posicao,
      ),
    [sessao, posicao],
  )

  const achados = useMemo(() => {
    const alvo = busca.trim().toLowerCase()
    if (alvo.length < 2) return []
    return (sessao?.linha_do_tempo ?? []).filter((e) =>
      e.conteudo.toLowerCase().includes(alvo),
    )
  }, [sessao, busca])

  if (isLoading) return <Carregando texto="Carregando gravação…" />
  if (error || !sessao) {
    return (
      <Vazio
        titulo="Gravação indisponível"
        descricao="Ela pode ser de outra pessoa, ou não existir."
      />
    )
  }

  return (
    <>
      <header>
        <nav className="crumbs" style={{ marginBottom: 6 }}>
          <Link to="/sessoes/gravacoes">Gravações</Link>{' '}
          <span aria-hidden="true">›</span> {sessao.alvo}
        </nav>
        <div className="row between wrap">
          <div>
            <h1 className="display">{sessao.alvo}</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {sessao.usuario_label} · {formatarDataHora(sessao.iniciada_em)} ·{' '}
              {formatarDuracao(sessao.duracao_ms)} ·{' '}
              {sessao.linha_do_tempo.length} eventos
            </p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <Badge tom={sessao.estado === 'derrubada' ? 'danger' : 'muted'}>
              {sessao.estado}
            </Badge>
            {sessao.captura_automatica ? (
              <Badge tom="success">capturada</Badge>
            ) : (
              <Badge tom="warning">anotada</Badge>
            )}
          </div>
        </div>
      </header>

      {/* A origem da gravação muda o peso dela numa investigação. */}
      {sessao.aviso && <Alerta tom="warning">{sessao.aviso}</Alerta>}

      {sessao.estado === 'derrubada' && sessao.motivo_encerramento && (
        <Alerta tom="danger">
          Interrompida por {sessao.encerrada_por}: {sessao.motivo_encerramento}
        </Alerta>
      )}

      <Card titulo="Reprodução">
        <div className="col" style={{ gap: 14 }}>
          <div className="row wrap" style={{ gap: 10, alignItems: 'center' }}>
            <Botao
              pequeno
              onClick={() => {
                if (posicao >= total) setPosicao(0)
                setTocando(!tocando)
              }}
              disabled={total === 0}
            >
              {tocando ? 'Pausar' : 'Reproduzir'}
            </Botao>
            <Botao
              variante="secondary"
              pequeno
              onClick={() => {
                setTocando(false)
                setPosicao(0)
              }}
            >
              Início
            </Botao>
            <Botao
              variante="ghost"
              pequeno
              onClick={() => {
                setTocando(false)
                setPosicao(total)
              }}
            >
              Fim
            </Botao>
            <span className="row" style={{ gap: 6, alignItems: 'center' }}>
              {VELOCIDADES.map((v) => (
                <Botao
                  key={v}
                  variante={velocidade === v ? 'primary' : 'secondary'}
                  pequeno
                  onClick={() => setVelocidade(v)}
                >
                  {v}×
                </Botao>
              ))}
            </span>
            <span className="secret-sm muted">
              {marcar(posicao)} / {marcar(total)}
            </span>
          </div>

          <input
            type="range"
            min={0}
            max={Math.max(total, 1)}
            value={posicao}
            onChange={(e) => {
              setTocando(false)
              setPosicao(Number(e.target.value))
            }}
            style={{ width: '100%' }}
            aria-label="Posição na gravação"
          />

          <div
            className="secret-sm"
            style={{
              background: '#1a1a1a',
              color: '#e8e8e8',
              borderRadius: 10,
              padding: 16,
              minHeight: 280,
              maxHeight: 420,
              overflowY: 'auto',
              lineHeight: 1.6,
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-all',
            }}
          >
            {visiveis.length === 0 ? (
              <span style={{ opacity: 0.6 }}>
                Reproduza para ver a sessão a partir do início.
              </span>
            ) : (
              visiveis.map((e, i) => (
                <div
                  key={`${e.deslocamento_ms}-${i}`}
                  style={{
                    color: e.tipo === 'entrada' ? '#7dd3fc' : '#e8e8e8',
                    opacity: e.tipo === 'marco' ? 0.6 : 1,
                  }}
                >
                  {e.tipo === 'entrada' && <span style={{ opacity: 0.5 }}>$ </span>}
                  {e.conteudo}
                </div>
              ))
            )}
          </div>
        </div>
      </Card>

      <Card titulo="Buscar na gravação">
        <div className="col" style={{ gap: 12 }}>
          <p className="sub" style={{ margin: 0 }}>
            Ninguém assiste três horas de sessão para achar um comando. Clique
            num resultado para pular até ele.
          </p>
          <Campo
            rotulo="Termo"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            ajuda="Ao menos 2 letras."
            placeholder="systemctl, sudo, DROP…"
          />
          {busca.trim().length >= 2 && (
            achados.length === 0 ? (
              <span className="muted">Nada encontrado nesta gravação.</span>
            ) : (
              <div className="col" style={{ gap: 6 }}>
                <span className="help">
                  {achados.length} ocorrência{achados.length === 1 ? '' : 's'}
                </span>
                {achados.map((e, i) => (
                  <button
                    key={`${e.deslocamento_ms}-${i}`}
                    className="row"
                    style={{
                      gap: 10,
                      padding: '8px 12px',
                      borderRadius: 8,
                      background: 'var(--surface-2, rgba(0,0,0,.03))',
                      border: 0,
                      cursor: 'pointer',
                      textAlign: 'left',
                      width: '100%',
                    }}
                    onClick={() => {
                      setTocando(false)
                      setPosicao(e.deslocamento_ms)
                    }}
                  >
                    <code className="secret-sm muted">
                      {marcar(e.deslocamento_ms)}
                    </code>
                    <code className="secret-sm">{e.conteudo}</code>
                  </button>
                ))}
              </div>
            )
          )}
        </div>
      </Card>
    </>
  )
}
