import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Badge, Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'

type Severidade = 'alta' | 'media' | 'baixa'

type Alerta = {
  severidade: Severidade
  categoria: string
  titulo: string
  detalhe: string
  rota: string
  quando: string | null
}

type Alertas = {
  total: number
  altas: number
  itens: Alerta[]
}

const TOM: Record<Severidade, 'danger' | 'warning' | 'muted'> = {
  alta: 'danger',
  media: 'warning',
  baixa: 'muted',
}

const ROTULO: Record<Severidade, string> = {
  alta: 'Alta',
  media: 'Média',
  baixa: 'Informação',
}

export function AlertasPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['alertas'],
    queryFn: () => request<Alertas>('/alertas'),
  })

  // O filtro é por categoria, não por severidade: os cards de severidade já
  // dão a leitura de gravidade, e "Certificado" ou "Rotação" é o que diz a
  // quem o problema pertence.
  const [categoria, setCategoria] = useState<string | null>(null)

  const itens = useMemo(() => data?.itens ?? [], [data])

  const categorias = useMemo(() => {
    const contagem = new Map<string, number>()
    for (const alerta of itens) {
      contagem.set(alerta.categoria, (contagem.get(alerta.categoria) ?? 0) + 1)
    }
    // Da mais numerosa para a menos; empate pelo nome, senão a ordem dos
    // chips muda a cada recarga sem nada ter mudado.
    return [...contagem.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
  }, [itens])

  if (isLoading) return <Carregando texto="Verificando pendências…" />

  const altas = itens.filter((i) => i.severidade === 'alta').length
  const medias = itens.filter((i) => i.severidade === 'media').length
  const baixas = itens.filter((i) => i.severidade === 'baixa').length

  // Um chip de categoria que sumiu do filtro deixaria a lista vazia sem
  // explicação; por isso o filtro só vale se a categoria ainda existe.
  const filtroAtivo = categoria && categorias.some(([nome]) => nome === categoria)
  const visiveis = filtroAtivo ? itens.filter((i) => i.categoria === categoria) : itens

  return (
    <>
      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <h1 className="display">Alertas</h1>
          <div className="row wrap" style={{ gap: 8 }}>
            <TutorialApi
              titulo="Alertas"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/alertas',
                  descricao:
                    'O que precisa de atenção: vencimentos, credenciais paradas, selos e pendências.',
                },
              ]}
            />
          </div>
        </div>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          Derivados do estado atual, não de uma tabela de alertas — alerta
          gravado precisa ser apagado quando a causa some, e esquecer disso
          produz alarme falso. Só o que você pode ver.
        </p>
      </header>

      <div className="cards-3">
        <CardMetrica rotulo="Alta" valor={altas} tom="danger" de={itens.length} />
        <CardMetrica rotulo="Média" valor={medias} tom="warning" de={itens.length} />
        <CardMetrica
          rotulo="Informação"
          valor={baixas}
          tom="muted"
          de={itens.length}
        />
      </div>

      {/* Os chips ficam COLADOS na lista que filtram, sem cartão próprio.
          Um cartão só para os filtros os afastaria do efeito que produzem, e
          a barra de proporção que havia aqui repetia o que os três cards
          acima já mostram — dois desenhos do mesmo número competem em vez de
          somar. */}
      {itens.length > 0 && (
        <div className="pill-group">
          <button
            type="button"
            className={`chip${filtroAtivo ? '' : ' active'}`}
            onClick={() => setCategoria(null)}
          >
            Todas <span className="qtd">{itens.length}</span>
          </button>
          {categorias.map(([nome, quantas]) => (
            <button
              key={nome}
              type="button"
              className={`chip${categoria === nome ? ' active' : ''}`}
              onClick={() => setCategoria(categoria === nome ? null : nome)}
            >
              {nome} <span className="qtd">{quantas}</span>
            </button>
          ))}
        </div>
      )}

      <Card>
        {visiveis.length === 0 ? (
          <Vazio
            titulo={filtroAtivo ? `Nada em ${categoria}` : 'Nada pendente'}
            descricao={
              filtroAtivo
                ? 'Escolha outra categoria ou volte para "Todas".'
                : 'Nenhum certificado vencendo, nenhuma rotação atrasada, nenhum cofre selado.'
            }
          />
        ) : (
          <div className="col" style={{ gap: 10 }}>
            {visiveis.map((alerta, i) => (
              <Link
                key={`${alerta.categoria}-${i}`}
                to={alerta.rota}
                className="row between wrap"
                style={{
                  gap: 12,
                  padding: '14px 16px',
                  borderRadius: 10,
                  background:
                    alerta.severidade === 'alta'
                      ? 'var(--danger-soft)'
                      : alerta.severidade === 'media'
                        ? 'var(--warning-soft)'
                        : 'var(--surface-200)',
                  textDecoration: 'none',
                  color: 'inherit',
                }}
              >
                <span className="col" style={{ gap: 3 }}>
                  <span className="row" style={{ gap: 8, alignItems: 'center' }}>
                    <Badge tom={TOM[alerta.severidade]}>
                      {ROTULO[alerta.severidade]}
                    </Badge>
                    <b>{alerta.titulo}</b>
                  </span>
                  <span className="help">{alerta.detalhe}</span>
                </span>
                <span className="col" style={{ gap: 3, textAlign: 'right' }}>
                  <span className="help">{alerta.categoria}</span>
                  {alerta.quando && (
                    <span className="help">{formatarDataHora(alerta.quando)}</span>
                  )}
                </span>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </>
  )
}
