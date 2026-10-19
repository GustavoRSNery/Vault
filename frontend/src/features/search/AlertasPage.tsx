import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Badge, Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
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

  if (isLoading) return <Carregando texto="Verificando pendências…" />

  const itens = data?.itens ?? []
  const medias = itens.filter((i) => i.severidade === 'media').length
  const baixas = itens.filter((i) => i.severidade === 'baixa').length

  return (
    <>
      <header>
        <h1 className="display">Alertas</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          Derivados do estado atual, não de uma tabela de alertas — alerta
          gravado precisa ser apagado quando a causa some, e esquecer disso
          produz alarme falso. Só o que você pode ver.
        </p>
      </header>

      <div className="cards-3">
        <CardMetrica rotulo="Alta" valor={data?.altas ?? 0} tom="danger" />
        <CardMetrica rotulo="Média" valor={medias} tom="warning" />
        <CardMetrica rotulo="Informação" valor={baixas} tom="muted" />
      </div>

      <Card>
        {itens.length === 0 ? (
          <Vazio
            titulo="Nada pendente"
            descricao="Nenhum certificado vencendo, nenhuma rotação atrasada, nenhum cofre selado."
          />
        ) : (
          <div className="col" style={{ gap: 10 }}>
            {itens.map((alerta, i) => (
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
                        : 'var(--surface-2, rgba(0,0,0,.03))',
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
