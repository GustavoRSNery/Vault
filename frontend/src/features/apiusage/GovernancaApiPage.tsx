import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { request } from '@/shared/api/client'
import {
  Alerta,
  Badge,
  Card,
  CardMetrica,
  Carregando,
  Vazio,
} from '@/shared/ui/components'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'

type Consumidor = {
  chave: string
  rotulo: string
  origem: string
  chamadas: number
  recusadas: number
  erros: number
  ultima_em: string | null
  duracao_media_ms: number
}

type Rota = {
  metodo: string
  caminho: string
  chamadas: number
  recusadas: number
  erros: number
  duracao_media_ms: number
  duracao_maxima_ms: number
}

type Chamada = {
  id: string
  recebida_em: string
  metodo: string
  caminho: string
  status: number
  resultado: string
  origem: string
  quem: string
  anonima: boolean
  ip: string
  agente: string
  duracao_ms: number
  bytes_recebidos: number
}

type Panorama = {
  resumo: {
    chamadas: number
    recusadas: number
    erros: number
    consumidores: number
    anonimas: number
    dias: number
  }
  consumidores: Consumidor[]
  rotas: Rota[]
}

const PERIODOS = [
  { dias: 1, rotulo: '24 horas' },
  { dias: 7, rotulo: '7 dias' },
  { dias: 30, rotulo: '30 dias' },
  { dias: 90, rotulo: '90 dias' },
]

/** Tom do selo de resultado. Recusado e erro não são a mesma coisa. */
function tomDoResultado(resultado: string) {
  if (resultado === 'ok') return 'success' as const
  if (resultado === 'recusado') return 'warning' as const
  if (resultado === 'erro') return 'danger' as const
  return 'muted' as const
}

function RotuloOrigem({ origem }: { origem: string }) {
  if (origem === 'aplicacao') return <Badge tom="brand">Aplicação</Badge>
  return <Badge tom="muted">Externa</Badge>
}

/**
 * Governança da API: quem consome o Vault de fora, em quais rotas.
 *
 * **O que esta tela não mostra, de propósito.** As chamadas que a própria
 * interface do Vault faz ficam fora. Cada tela aberta dispara dezenas de
 * requisições por minuto, e incluí-las afogaria o consumo externo — que é a
 * única coisa que alguém vem aqui investigar.
 *
 * **Por que três vistas da mesma coisa.** "Quem" responde se uma integração
 * passou a consumir mais que o normal. "Rotas" responde qual dado está
 * saindo. "Chamadas" é a leitura linha a linha, para quando as duas
 * primeiras apontam algo e falta ver o caso concreto.
 */
export function GovernancaApiPage() {
  const [dias, setDias] = useState(7)
  const [vista, setVista] = useState<'quem' | 'rotas' | 'chamadas'>('quem')
  const [origem, setOrigem] = useState('')
  const [resultado, setResultado] = useState('')
  const tour = useTour('api-governanca')

  const { data: panorama, isFetching } = useQuery({
    queryKey: ['api-uso', 'panorama', dias, origem],
    queryFn: () =>
      request<Panorama>(
        `/api-uso/panorama?dias=${dias}${origem ? `&origem=${origem}` : ''}`,
      ),
  })

  const { data: chamadas, isFetching: carregandoChamadas } = useQuery({
    queryKey: ['api-uso', 'chamadas', dias, origem, resultado],
    queryFn: () =>
      request<Chamada[]>(
        `/api-uso/chamadas?dias=${dias}` +
          `${origem ? `&origem=${origem}` : ''}` +
          `${resultado ? `&resultado=${resultado}` : ''}`,
      ),
    // Só busca a listagem quando ela está na tela: é a consulta mais cara
    // das três, e abrir "Quem" não deveria pagar por ela.
    enabled: vista === 'chamadas',
  })

  const resumo = panorama?.resumo
  const consumidores = panorama?.consumidores ?? []
  const rotas = panorama?.rotas ?? []

  return (
    <>
      <Tour id="api-governanca" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <h1 className="display">Consumo da API</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              Quem chama a API do Vault de fora (aplicações, robôs e scripts),
              em quais rotas e com que resultado. As chamadas da própria tela do
              Vault não entram aqui.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Consumo da API"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/api-uso/panorama',
                  descricao:
                    'Os números do período e os rankings de consumidor e de rota. Aceita ?dias= e ?origem=.',
                },
                {
                  metodo: 'GET',
                  caminho: '/api-uso/chamadas',
                  descricao:
                    'As chamadas uma a uma, mais recentes primeiro. Aceita ?dias=, ?origem=, ?resultado= e ?aplicacao=.',
                },
              ]}
              observacao="O conteúdo enviado nas requisições não é guardado — só o tamanho em bytes. Uma chamada que cria segredo traz a senha no corpo."
            />
          </div>
        </div>
      </header>

      <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
        {PERIODOS.map((p) => (
          <button
            key={p.dias}
            type="button"
            className={`chip${dias === p.dias ? ' active' : ''}`}
            onClick={() => setDias(p.dias)}
          >
            {p.rotulo}
          </button>
        ))}
        <span style={{ flex: 1 }} />
        <select
          className="input"
          value={origem}
          onChange={(e) => setOrigem(e.target.value)}
          aria-label="Filtrar por origem"
        >
          <option value="">Toda origem</option>
          <option value="aplicacao">Aplicações (AppRole)</option>
          <option value="externa">Externas</option>
        </select>
      </div>

      {isFetching && !panorama ? (
        <Carregando />
      ) : (
        <>
          <div className="cards-3" data-tour="metricas-api">
            <CardMetrica rotulo="Chamadas" valor={resumo?.chamadas ?? 0} />
            <CardMetrica
              rotulo="Recusadas"
              valor={resumo?.recusadas ?? 0}
              tom="warning"
              de={resumo?.chamadas}
            />
            <CardMetrica
              rotulo="Com erro"
              valor={resumo?.erros ?? 0}
              tom="danger"
              de={resumo?.chamadas}
            />
          </div>

          {(resumo?.recusadas ?? 0) > 0 && (
            <Alerta tom="warning">
              <b>
                {resumo?.recusadas} chamada(s) recusada(s) no período.
              </b>{' '}
              Recusa é 401 ou 403: credencial errada ou acesso fora do escopo.
              Em pequeno número costuma ser integração mal configurada; muitas
              seguidas do mesmo lugar merecem olhar.
            </Alerta>
          )}

          <div className="row wrap" style={{ gap: 8 }}>
            <button
              type="button"
              className={`chip${vista === 'quem' ? ' active' : ''}`}
              onClick={() => setVista('quem')}
            >
              Quem chama
            </button>
            <button
              type="button"
              className={`chip${vista === 'rotas' ? ' active' : ''}`}
              onClick={() => setVista('rotas')}
            >
              O que é chamado
            </button>
            <button
              type="button"
              className={`chip${vista === 'chamadas' ? ' active' : ''}`}
              onClick={() => setVista('chamadas')}
            >
              Chamada a chamada
            </button>
          </div>

          {vista === 'quem' && (
            <Card titulo="Quem chama a API" data-tour="consumidores">
              {consumidores.length === 0 ? (
                <Vazio
                  titulo="Nenhuma chamada externa no período"
                  descricao="Quando uma aplicação ou script consumir a API, aparece aqui."
                />
              ) : (
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Consumidor</th>
                        <th>Origem</th>
                        <th>Chamadas</th>
                        <th>Recusadas</th>
                        <th>Erros</th>
                        <th>Média</th>
                        <th>Última</th>
                      </tr>
                    </thead>
                    <tbody>
                      {consumidores.map((c) => (
                        <tr key={c.chave}>
                          <td>
                            <b>{c.rotulo}</b>
                          </td>
                          <td>
                            <RotuloOrigem origem={c.origem} />
                          </td>
                          <td>{c.chamadas}</td>
                          <td>
                            {c.recusadas > 0 ? (
                              <Badge tom="warning">{c.recusadas}</Badge>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            {c.erros > 0 ? (
                              <Badge tom="danger">{c.erros}</Badge>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>{c.duracao_media_ms} ms</td>
                          <td>
                            {c.ultima_em ? formatarDataHora(c.ultima_em) : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {vista === 'rotas' && (
            <Card titulo="O que está sendo consumido" data-tour="rotas">
              {rotas.length === 0 ? (
                <Vazio
                  titulo="Nenhuma rota chamada no período"
                  descricao="Amplie o período ou tire o filtro de origem."
                />
              ) : (
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Rota</th>
                        <th>Chamadas</th>
                        <th>Recusadas</th>
                        <th>Erros</th>
                        <th>Média</th>
                        <th>Pior</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rotas.map((r) => (
                        <tr key={`${r.metodo} ${r.caminho}`}>
                          <td>
                            <code className="secret-sm">
                              {r.metodo} {r.caminho}
                            </code>
                          </td>
                          <td>{r.chamadas}</td>
                          <td>
                            {r.recusadas > 0 ? (
                              <Badge tom="warning">{r.recusadas}</Badge>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            {r.erros > 0 ? (
                              <Badge tom="danger">{r.erros}</Badge>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>{r.duracao_media_ms} ms</td>
                          {/* A pior ao lado da média: uma média boa esconde
                              a chamada de 9 segundos que derruba o robô por
                              timeout. */}
                          <td>{r.duracao_maxima_ms} ms</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}

          {vista === 'chamadas' && (
            <Card titulo="Chamada a chamada" data-tour="chamadas">
              <div className="row wrap" style={{ gap: 8, marginBottom: 10 }}>
                <select
                  className="input"
                  value={resultado}
                  onChange={(e) => setResultado(e.target.value)}
                  aria-label="Filtrar por resultado"
                >
                  <option value="">Todo resultado</option>
                  <option value="ok">Bem sucedidas</option>
                  <option value="recusado">Recusadas (401/403)</option>
                  <option value="invalido">Inválidas (4xx)</option>
                  <option value="erro">Com erro (5xx)</option>
                </select>
              </div>

              {carregandoChamadas && !chamadas ? (
                <Carregando />
              ) : (chamadas ?? []).length === 0 ? (
                <Vazio
                  titulo="Nenhuma chamada no período"
                  descricao="Amplie o período ou tire os filtros."
                />
              ) : (
                <div className="tbl-wrap">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th>Quando</th>
                        <th>Quem</th>
                        <th>Rota</th>
                        <th>Status</th>
                        <th>Tempo</th>
                        <th>De onde</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(chamadas ?? []).map((c) => (
                        <tr key={c.id}>
                          <td>{formatarDataHora(c.recebida_em)}</td>
                          <td>
                            {c.anonima ? (
                              <span className="sub">não identificado</span>
                            ) : (
                              c.quem
                            )}
                          </td>
                          <td>
                            <code className="secret-sm">
                              {c.metodo} {c.caminho}
                            </code>
                          </td>
                          <td>
                            <Badge tom={tomDoResultado(c.resultado)}>
                              {c.status}
                            </Badge>
                          </td>
                          <td>{c.duracao_ms} ms</td>
                          <td>
                            <span className="secret-sm">{c.ip || '—'}</span>
                            {c.agente && (
                              <div className="sub" title={c.agente}>
                                {c.agente.slice(0, 40)}
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Card>
          )}
        </>
      )}
    </>
  )
}
