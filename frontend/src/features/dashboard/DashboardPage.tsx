import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import { useCofres } from '@/features/vaults/CofresPage'
import { request } from '@/shared/api/client'
import { Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { BarrasHorizontais, ColunasCompactas } from '@/shared/charts'

type PontoDaSerie = {
  dia: string
  sucesso: number
  negado: number
  falha_login: number
}

/** `2026-10-20` vira `20/10`: o ano é o mesmo em toda a janela. */
function diaCurto(iso: string): string {
  const [, mes, dia] = iso.split('-')
  return `${dia}/${mes}`
}

type Metricas = {
  dias: number
  dias_com_dado: number
  total: number
  serie: PontoDaSerie[]
  por_ator: { rotulo: string; quantas: number }[]
  por_caminho: { rotulo: string; quantas: number }[]
  restrito: boolean
  capacidade_exigida: string
}

const JANELAS = [
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
  { dias: 90, rotulo: '90 dias' },
]

export function DashboardPage() {
  const { usuario } = useAuth()
  const { data: cofres, isLoading } = useCofres()
  const [dias, setDias] = useState(30)

  const { data: metricas, isLoading: carregandoMetricas } = useQuery({
    queryKey: ['metricas', dias],
    queryFn: () => request<Metricas>(`/metricas/serie?dias=${dias}`),
  })

  const primeiroNome = usuario?.full_name.split(' ')[0] ?? ''
  const ativos = cofres?.filter((c) => c.state === 'ativo').length ?? 0
  const selados = cofres?.filter((c) => c.state === 'selado').length ?? 0

  const negados = metricas?.serie.reduce((soma, p) => soma + p.negado, 0) ?? 0

  return (
    <>
      <header>
        <h1 className="display">Olá, {primeiroNome}</h1>
        <p className="sub">Aqui está o resumo dos seus cofres.</p>
      </header>

      {isLoading ? (
        <Carregando />
      ) : (
        <>
          <div className="cards-3">
            <CardMetrica rotulo="Cofres com acesso" valor={cofres?.length ?? 0} tom="brand" />
            <CardMetrica
              rotulo="Cofres ativos"
              valor={ativos}
              tom="success"
              de={cofres?.length}
            />
            <CardMetrica
              rotulo="Cofres selados"
              valor={selados}
              tom="danger"
              de={cofres?.length}
            />
          </div>

          <Card
            titulo="Atividade do cofre"
            acao={
              <div className="pill-group">
                {JANELAS.map((janela) => (
                  <button
                    key={janela.dias}
                    type="button"
                    className={`pill${dias === janela.dias ? ' active' : ''}`}
                    onClick={() => setDias(janela.dias)}
                  >
                    {janela.rotulo}
                  </button>
                ))}
              </div>
            }
          >
            {carregandoMetricas ? (
              <Carregando texto="Lendo a trilha…" />
            ) : !metricas || metricas.total === 0 ? (
              <Vazio
                titulo="Nenhum movimento no período"
                descricao="Nada foi revelado, negado ou tentado nesta janela."
              />
            ) : (
              <div className="col" style={{ gap: 14 }}>
                <div className="row between wrap" style={{ gap: 12 }}>
                  <div className="g-legenda">
                    <span className="item">
                      <span className="chave k-volume" /> Movimento do dia
                    </span>
                    <span className="item">
                      <span className="chave k-negado" /> Negado ou falho
                    </span>
                  </div>
                  <span className="help">
                    {/* A janela pedida e o histórico real são coisas
                        diferentes: dizer "30 dias" num cofre instalado há 3
                        sugeriria uma queda de atividade que não houve. */}
                    {metricas.total} evento(s) em {metricas.dias_com_dado} dia(s) com
                    movimento
                    {metricas.dias_com_dado < metricas.dias &&
                      ` · janela de ${metricas.dias} dias`}
                  </span>
                </div>

                <ColunasCompactas
                  colunas={metricas.serie.map((p) => {
                    const total = p.sucesso + p.negado + p.falha_login
                    const barrado = p.negado + p.falha_login
                    return {
                      rotulo: diaCurto(p.dia),
                      total,
                      destaque: barrado,
                      descricao:
                        `${diaCurto(p.dia)} · ${total} evento(s): ` +
                        `${p.sucesso} concluído(s), ${p.negado} negado(s), ` +
                        `${p.falha_login} falha(s) de login`,
                    }
                  })}
                  descricao={`Atividade por dia em ${metricas.dias} dias: ${metricas.total} eventos.`}
                />

                {negados > 0 && (
                  <p className="help" style={{ margin: 0 }}>
                    <b style={{ color: 'var(--danger-text)' }}>
                      {negados} acesso(s) negado(s)
                    </b>{' '}
                    no período. Negação em série costuma ser política mal
                    dimensionada — ou alguém pedindo o que não deveria.
                  </p>
                )}
              </div>
            )}
          </Card>

          {metricas?.restrito && metricas.total > 0 && (
            <Card>
              <p className="help" style={{ margin: 0 }}>
                Os rankings de atividade —{' '}
                <i>quem mais revela segredos</i> e <i>o que mais é revelado</i>{' '}
                — exigem a capacidade{' '}
                <b>{metricas.capacidade_exigida}</b> no caminho de auditoria.
                {/* Dizer por que está ausente, em vez de só omitir: um bloco
                    que some sem explicação parece falta de dado. */}
              </p>
            </Card>
          )}

          {metricas && !metricas.restrito && metricas.por_ator.length > 0 && (
            <div className="cards-2">
              <Card titulo="Quem mais revela segredos">
                <BarrasHorizontais
                  itens={metricas.por_ator}
                  descricao="Pessoas e robôs que mais revelaram segredos no período."
                />
              </Card>
              <Card titulo="O que mais é revelado">
                <BarrasHorizontais
                  itens={metricas.por_caminho}
                  descricao="Segredos mais revelados no período."
                />
              </Card>
            </div>
          )}

          <Card titulo="Seus cofres">
            {!cofres || cofres.length === 0 ? (
              <Vazio
                titulo="Nenhum cofre ainda"
                descricao="Peça acesso a um administrador para começar."
              />
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {cofres.slice(0, 5).map((cofre) => (
                  <li key={cofre.id} style={{ padding: '6px 0' }}>
                    <Link
                      to={`/cofres/${cofre.name}`}
                      style={{ color: 'var(--brand-text)', textDecoration: 'none' }}
                    >
                      {cofre.display_name}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {!usuario?.mfa_enabled && (
            <Card>
              <div className="row between wrap">
                <div>
                  <h2 className="title">Ative a verificação em duas etapas</h2>
                  <p className="sub" style={{ margin: '4px 0 0' }}>
                    Um segundo fator protege seus cofres mesmo que a senha vaze.
                  </p>
                </div>
                <span className="badge b-warning">Pendente</span>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  )
}
