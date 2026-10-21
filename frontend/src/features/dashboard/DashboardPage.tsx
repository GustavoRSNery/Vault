import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import { request } from '@/shared/api/client'
import { Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { BarrasHorizontais, ColunasCompactas } from '@/shared/charts'
import {
  AbaCertificados,
  AbaChaves,
  AbaCofres,
  AbaCredenciais,
  AbaDispositivos,
  type Panorama,
} from './abas'

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

/**
 * As abas do painel.
 *
 * Uma por página do grupo "Segredos" do menu, na mesma ordem — assim quem
 * decorou a navegação lateral encontra o mesmo arranjo aqui. "Resumo" vem
 * primeiro porque é o estado padrão: a pergunta "como estão as coisas?"
 * antecede "como está este domínio?".
 */
const ABAS = [
  { chave: 'resumo', rotulo: 'Resumo' },
  { chave: 'cofres', rotulo: 'Cofres' },
  { chave: 'credenciais', rotulo: 'Credenciais' },
  { chave: 'certificados', rotulo: 'Certificados' },
  { chave: 'chaves', rotulo: 'Chaves de API' },
  { chave: 'dispositivos', rotulo: 'Dispositivos' },
] as const

type ChaveDaAba = (typeof ABAS)[number]['chave']

export function DashboardPage() {
  const { usuario } = useAuth()
  const [aba, setAba] = useState<ChaveDaAba>('resumo')
  const [dias, setDias] = useState(30)

  const { data: panorama, isLoading } = useQuery({
    queryKey: ['panorama'],
    queryFn: () => request<Panorama>('/panorama'),
  })

  const { data: metricas, isLoading: carregandoMetricas } = useQuery({
    queryKey: ['metricas', dias],
    queryFn: () => request<Metricas>(`/metricas/serie?dias=${dias}`),
    // Só o resumo desenha a série; as outras abas não precisam dela.
    enabled: aba === 'resumo',
  })

  const primeiroNome = usuario?.full_name.split(' ')[0] ?? ''
  const negados = metricas?.serie.reduce((soma, p) => soma + p.negado, 0) ?? 0

  /** A contagem que aparece na pílula da aba. */
  const totalDaAba = (chave: ChaveDaAba): number | null => {
    if (!panorama) return null
    switch (chave) {
      case 'resumo':
        return null
      case 'cofres':
        return panorama.cofres.total
      case 'credenciais':
        return panorama.credenciais.total
      case 'certificados':
        return panorama.certificados.total
      case 'chaves':
        return panorama.chaves.total
      case 'dispositivos':
        return panorama.dispositivos.total
    }
  }

  return (
    <>
      <header>
        <h1 className="display">Olá, {primeiroNome}</h1>
        <p className="sub">
          {aba === 'resumo'
            ? 'O estado geral dos seus cofres e o que precisa de atenção.'
            : 'Detalhe deste domínio. Clique em "abrir" para agir sobre os itens.'}
        </p>
      </header>

      <div className="trilho" role="tablist" aria-label="Seções do painel">
        {ABAS.map((item) => {
          const n = totalDaAba(item.chave)
          return (
            <button
              key={item.chave}
              type="button"
              role="tab"
              aria-selected={aba === item.chave}
              className={`aba${aba === item.chave ? ' active' : ''}`}
              onClick={() => setAba(item.chave)}
            >
              {item.rotulo}
              {n !== null && <span className="n">{n}</span>}
            </button>
          )
        })}
      </div>

      {isLoading ? (
        <Carregando />
      ) : !panorama ? (
        <Vazio
          titulo="Não foi possível ler o panorama"
          descricao="Tente recarregar a página."
        />
      ) : (
        <>
          {aba === 'cofres' && <AbaCofres dados={panorama.cofres} />}
          {aba === 'credenciais' && <AbaCredenciais dados={panorama.credenciais} />}
          {aba === 'certificados' && (
            <AbaCertificados dados={panorama.certificados} />
          )}
          {aba === 'chaves' && <AbaChaves dados={panorama.chaves} />}
          {aba === 'dispositivos' && (
            <AbaDispositivos dados={panorama.dispositivos} />
          )}

          {aba === 'resumo' && (
            <>
              {/* O resumo responde "como estão as coisas" com um número por
                  domínio: é o mesmo arranjo das abas, condensado, para que a
                  pessoa veja onde há volume antes de escolher onde entrar. */}
              <div className="cards">
                <CardMetrica
                  rotulo="Segredos"
                  valor={panorama.cofres.segredos}
                  tom="brand"
                />
                <CardMetrica
                  rotulo="Credenciais"
                  valor={panorama.credenciais.total}
                  tom="brand"
                />
                <CardMetrica
                  rotulo="Certificados"
                  valor={panorama.certificados.total}
                  tom="brand"
                />
                <CardMetrica
                  rotulo="Chaves de API"
                  valor={panorama.chaves.total}
                  tom="brand"
                />
              </div>

              <PendenciasDoResumo panorama={panorama} />

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
                            diferentes: dizer "30 dias" num cofre instalado há
                            3 sugeriria uma queda de atividade que não houve. */}
                        {metricas.total} evento(s) em {metricas.dias_com_dado} dia(s)
                        com movimento
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
                    Os rankings de atividade — <i>quem mais revela segredos</i> e{' '}
                    <i>o que mais é revelado</i> — exigem a capacidade{' '}
                    <b>{metricas.capacidade_exigida}</b> no caminho de auditoria.
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

              {!usuario?.mfa_enabled && (
                <Card>
                  <div className="row between wrap">
                    <div>
                      <h2 className="title">Ative a verificação em duas etapas</h2>
                      <p className="sub" style={{ margin: '4px 0 0' }}>
                        Um segundo fator protege seus cofres mesmo que a senha
                        vaze.
                      </p>
                    </div>
                    <Link to="/perfil" className="btn btn-secondary btn-sm">
                      Ativar →
                    </Link>
                  </div>
                </Card>
              )}
            </>
          )}
        </>
      )}
    </>
  )
}

/**
 * O que precisa de ação, somado de todos os domínios.
 *
 * Existe para que o resumo não seja só uma contagem de acervo: saber que há
 * 42 credenciais não ajuda tanto quanto saber que 3 estão com a rotação
 * atrasada. Cada linha leva direto à aba que a explica.
 */
function PendenciasDoResumo({ panorama }: { panorama: Panorama }) {
  const pendencias = [
    {
      rotulo: 'Certificados vencidos',
      quantas: panorama.certificados.vencidos,
      tom: 'danger',
      para: '/certificados',
    },
    {
      rotulo: 'Custódia vencida',
      quantas: panorama.credenciais.custodia_vencida,
      tom: 'danger',
      para: '/credenciais',
    },
    {
      rotulo: 'Rotação atrasada',
      quantas: panorama.credenciais.rotacao_atrasada,
      tom: 'warning',
      para: '/credenciais',
    },
    {
      rotulo: 'Certificados vencendo',
      quantas: panorama.certificados.vencendo,
      tom: 'warning',
      para: '/certificados',
    },
    {
      rotulo: 'Chaves sem vencimento',
      quantas: panorama.chaves.sem_vencimento,
      tom: 'warning',
      para: '/chaves-api',
    },
    {
      rotulo: 'Cofres selados',
      quantas: panorama.cofres.selados,
      tom: 'danger',
      para: '/cofres',
    },
  ].filter((p) => p.quantas > 0)

  if (pendencias.length === 0) {
    return (
      <Card titulo="Pendências">
        <p className="help" style={{ margin: 0 }}>
          Nada vencido, nada atrasado, nenhum cofre selado.
        </p>
      </Card>
    )
  }

  return (
    <Card titulo="Precisa de atenção">
      <div className="col" style={{ gap: 8 }}>
        {pendencias.map((p) => (
          <Link
            key={p.rotulo}
            to={p.para}
            className="row between"
            style={{
              gap: 12,
              padding: '10px 14px',
              borderRadius: 10,
              background: `var(--${p.tom}-soft)`,
              textDecoration: 'none',
              color: 'inherit',
            }}
          >
            <span className="row" style={{ gap: 8 }}>
              <span className={`ponto d-${p.tom}`} aria-hidden="true" />
              {p.rotulo}
            </span>
            <b style={{ color: `var(--${p.tom}-text)`, fontVariantNumeric: 'tabular-nums' }}>
              {p.quantas}
            </b>
          </Link>
        ))}
      </div>
    </Card>
  )
}
