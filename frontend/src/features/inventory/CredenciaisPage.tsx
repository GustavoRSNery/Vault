import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'
import { baixarJson } from '@/shared/lib/baixar'
import { useAuth } from '@/features/auth/AuthContext'
import { ImportarCredenciais, NovaCredencial } from './NovaCredencial'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'

type Custodia = {
  id: string
  user_label: string
  reason: string
  taken_at: string
  due_at: string
  returned_at: string | null
  em_atraso: boolean
}

type Credencial = {
  id: string
  name: string
  device_id: string
  device_name: string
  username: string
  description: string
  status: string
  rotation_days: number
  last_rotated_at: string | null
  due_at: string | null
  dias_para_vencer: number | null
  atrasada: boolean
  custodia_aberta: Custodia | null
  historico: Custodia[]
}

export function CredenciaisPage() {
  const queryClient = useQueryClient()
  const { usuario } = useAuth()
  const [erro, setErro] = useState<string | null>(null)
  const [retirando, setRetirando] = useState<string | null>(null)
  const [verHistorico, setVerHistorico] = useState<string | null>(null)
  const [criando, setCriando] = useState(false)
  const [importando, setImportando] = useState(false)
  const tour = useTour('credenciais')

  const exportar = useMutation({
    mutationFn: (credencial: Credencial) =>
      request<Record<string, unknown>>(`/credenciais/${credencial.id}/exportar`).then(
        (dados) => ({ dados, nome: credencial.name }),
      ),
    onSuccess: ({ dados, nome }) => baixarJson(dados, `credencial-${nome}.json`),
  })

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['credenciais'] })
    void queryClient.invalidateQueries({ queryKey: ['dispositivos'] })
  }

  const { data: credenciais, isLoading, error } = useQuery({
    queryKey: ['credenciais'],
    queryFn: () => request<Credencial[]>('/credenciais'),
  })

  const acao = useMutation({
    mutationFn: ({ id, rota, body }: { id: string; rota: string; body?: unknown }) =>
      request<Credencial>(`/credenciais/${id}/${rota}`, { method: 'POST', body }),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível concluir.'),
  })

  if (isLoading) return <Carregando texto="Carregando credenciais…" />
  if (error) {
    return (
      <Vazio
        titulo="Nenhuma credencial acessível"
        descricao="Você pode não ter permissão no caminho de credenciais."
      />
    )
  }

  const atrasadas = credenciais?.filter((c) => c.atrasada).length ?? 0
  const emCustodia = credenciais?.filter((c) => c.custodia_aberta).length ?? 0

  return (
    <>
      <Tour id="credenciais" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <h1 className="display">Credenciais</h1>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Credenciais"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/credenciais',
                  descricao:
                    'Governo de cada credencial: equipamento, usuário, prazo de rotação e quem está com ela. Nunca a senha.',
                  exemplo:
                    '[{"name":"senha-root","device_name":"srv-db-01","atrasada":true}]',
                },
                {
                  metodo: 'GET',
                  caminho: '/dispositivos',
                  descricao:
                    'Os equipamentos a que as credenciais pertencem — útil para cruzar com a listagem acima.',
                },
              ]}
              observacao="Retirar e devolver são escrita: passam pela tela, porque exigem justificativa que vai para a trilha."
            />
            <Botao
              variante="secondary"
              pequeno
              data-tour="importar"
              onClick={() => {
                setImportando(true)
                setCriando(false)
              }}
            >
              Importar JSON
            </Botao>
            <Botao
              pequeno
              onClick={() => {
                setCriando(true)
                setImportando(false)
              }}
            >
              Nova credencial
            </Botao>
          </div>
        </div>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          {credenciais?.length ?? 0} credencia{(credenciais?.length ?? 0) === 1 ? 'l' : 'is'}
          {atrasadas > 0 && <> · <b>{atrasadas}</b> com rotação atrasada</>}
          {emCustodia > 0 && <> · {emCustodia} em custódia</>}. Retirar uma
          credencial reserva ela para você até a devolução.
        </p>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      {criando && (
        <NovaCredencial
          aoFechar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            invalidar()
          }}
        />
      )}

      {importando && (
        <ImportarCredenciais
          aoFechar={() => setImportando(false)}
          aoImportar={invalidar}
        />
      )}

      {atrasadas > 0 && (
        <Alerta tom="warning">
          {atrasadas === 1
            ? 'Uma credencial está com a rotação atrasada.'
            : `${atrasadas} credenciais estão com a rotação atrasada.`}{' '}
          Credencial nunca rotacionada conta como atrasada — é o pior caso, e
          deixá-la fora do relatório seria esconder justamente a senha de
          fábrica.
        </Alerta>
      )}

      <Card>
        {!credenciais || credenciais.length === 0 ? (
          <Vazio
            titulo="Nenhuma credencial cadastrada"
            descricao="A credencial pertence a um equipamento: cadastre o dispositivo primeiro, depois as senhas que ele guarda."
            acao={
              <Botao pequeno onClick={() => setCriando(true)}>
                Nova credencial
              </Botao>
            }
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Credencial</th>
                  <th>Dispositivo</th>
                  <th>Rotação</th>
                  <th>Custódia</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {credenciais.map((c) => {
                  const minha = c.custodia_aberta?.user_label === usuario?.email
                  return (
                    <tr key={c.id}>
                      <td className="strong">
                        {c.name}
                        {c.username && <div className="help">{c.username}</div>}
                      </td>
                      <td className="muted">{c.device_name}</td>
                      <td data-tour="rotacao">
                        <EstadoRotacao credencial={c} />
                      </td>
                      <td>
                        {c.custodia_aberta ? (
                          <div className="col" style={{ gap: 4 }}>
                            <Badge tom={c.custodia_aberta.em_atraso ? 'danger' : 'warning'}>
                              {minha ? 'Com você' : `Com ${c.custodia_aberta.user_label}`}
                            </Badge>
                            <span className="help">
                              Até {formatarDataHora(c.custodia_aberta.due_at)}
                              {c.custodia_aberta.em_atraso && ' — em atraso'}
                            </span>
                          </div>
                        ) : (
                          <Badge tom="success">Disponível</Badge>
                        )}
                      </td>
                      <td>
                        <div className="row wrap" style={{ gap: 6 }}>
                          {c.custodia_aberta ? (
                            <>
                              <Botao
                                variante="secondary"
                                pequeno
                                onClick={() =>
                                  acao.mutate({ id: c.id, rota: 'devolver', body: {} })
                                }
                                disabled={acao.isPending || !minha}
                                title={
                                  minha
                                    ? undefined
                                    : 'Só quem retirou devolve, ou um administrador força.'
                                }
                              >
                                Devolver
                              </Botao>
                              {!minha && usuario?.is_admin && (
                                <Botao
                                  variante="ghost"
                                  pequeno
                                  onClick={() =>
                                    acao.mutate({
                                      id: c.id,
                                      rota: 'devolver',
                                      body: { force: true },
                                    })
                                  }
                                  disabled={acao.isPending}
                                >
                                  Forçar devolução
                                </Botao>
                              )}
                            </>
                          ) : (
                            <Botao
                              pequeno
                              data-tour="retirar"
                              onClick={() =>
                                setRetirando(retirando === c.id ? null : c.id)
                              }
                            >
                              Retirar
                            </Botao>
                          )}
                          <Botao
                            variante="ghost"
                            pequeno
                            onClick={() =>
                              acao.mutate({ id: c.id, rota: 'rotacionar' })
                            }
                            disabled={acao.isPending}
                            title="Registra que a senha foi trocada agora."
                          >
                            Rotacionei
                          </Botao>
                          {c.historico.length > 0 && (
                            <Botao
                              variante="ghost"
                              pequeno
                              onClick={() =>
                                setVerHistorico(verHistorico === c.id ? null : c.id)
                              }
                            >
                              Histórico
                            </Botao>
                          )}
                          <Botao
                            variante="ghost"
                            pequeno
                            disabled={exportar.isPending}
                            onClick={() => exportar.mutate(c)}
                            title="Governo da credencial em JSON. A senha não vai junto."
                          >
                            Exportar JSON
                          </Botao>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {retirando && credenciais && (
        <FormularioRetirada
          credencial={credenciais.find((c) => c.id === retirando)!}
          aoFechar={() => setRetirando(null)}
          aoRetirar={() => {
            setRetirando(null)
            invalidar()
          }}
        />
      )}

      {verHistorico && credenciais && (
        <HistoricoCustodia
          credencial={credenciais.find((c) => c.id === verHistorico)!}
        />
      )}
    </>
  )
}

function EstadoRotacao({ credencial }: { credencial: Credencial }) {
  if (credencial.rotation_days === 0) {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="muted">Não rotaciona</Badge>
        <span className="help">Prazo zero, por decisão explícita.</span>
      </div>
    )
  }

  if (credencial.last_rotated_at === null) {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="danger">Nunca rotacionada</Badge>
        <span className="help">Cada {credencial.rotation_days} dias.</span>
      </div>
    )
  }

  const dias = credencial.dias_para_vencer
  return (
    <div className="col" style={{ gap: 4 }}>
      <Badge tom={credencial.atrasada ? 'danger' : 'success'}>
        {credencial.atrasada ? 'Atrasada' : `Vence em ${dias} dia${dias === 1 ? '' : 's'}`}
      </Badge>
      <span className="help">
        Trocada em {formatarDataHora(credencial.last_rotated_at)}
      </span>
    </div>
  )
}

function FormularioRetirada({
  credencial,
  aoFechar,
  aoRetirar,
}: {
  credencial: Credencial
  aoFechar: () => void
  aoRetirar: () => void
}) {
  const [motivo, setMotivo] = useState('')
  const [horas, setHoras] = useState(4)
  const [erro, setErro] = useState<string | null>(null)

  const retirar = useMutation({
    mutationFn: () =>
      request<Credencial>(`/credenciais/${credencial.id}/retirar`, {
        method: 'POST',
        body: { reason: motivo, hours: horas },
      }),
    onSuccess: aoRetirar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível retirar.'),
  })

  return (
    <Card titulo={`Retirar ${credencial.name}`}>
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <p className="sub" style={{ margin: 0 }}>
          Enquanto estiver com você, mais ninguém retira esta credencial. É o
          que evita duas pessoas trocando a mesma senha em paralelo — a segunda
          invalidaria a primeira sem ninguém notar.
        </p>

        <Campo
          rotulo="Justificativa"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          ajuda="Fica na trilha de auditoria. Ex.: troca de senha trimestral."
          autoFocus
        />

        <div className="field">
          <label htmlFor="horas">Prazo de devolução</label>
          <select
            id="horas"
            className="input"
            value={horas}
            onChange={(e) => setHoras(Number(e.target.value))}
          >
            <option value={1}>1 hora</option>
            <option value={4}>4 horas</option>
            <option value={8}>8 horas</option>
            <option value={24}>1 dia</option>
            <option value={72}>3 dias</option>
            <option value={168}>7 dias</option>
          </select>
          <span className="help">
            Passado o prazo, a retirada aparece como em atraso — não é
            devolvida sozinha, porque a credencial pode ainda estar em uso.
          </span>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => retirar.mutate()}
            disabled={motivo.trim() === '' || retirar.isPending}
          >
            {retirar.isPending ? 'Retirando…' : 'Retirar credencial'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}

function HistoricoCustodia({ credencial }: { credencial: Credencial }) {
  return (
    <Card titulo={`Custódias de ${credencial.name}`}>
      <p className="sub" style={{ marginTop: 0 }}>
        Devolver fecha a retirada, nunca apaga o fato de ter acontecido.
      </p>
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th>Quem</th>
              <th>Motivo</th>
              <th>Retirada</th>
              <th>Prazo</th>
              <th>Devolução</th>
            </tr>
          </thead>
          <tbody>
            {credencial.historico.map((c) => (
              <tr key={c.id}>
                <td className="strong">{c.user_label}</td>
                <td className="muted">{c.reason}</td>
                <td className="muted">{formatarDataHora(c.taken_at)}</td>
                <td className="muted">{formatarDataHora(c.due_at)}</td>
                <td>
                  {c.returned_at ? (
                    <span className="muted">{formatarDataHora(c.returned_at)}</span>
                  ) : (
                    <Badge tom={c.em_atraso ? 'danger' : 'warning'}>
                      {c.em_atraso ? 'Em atraso' : 'Em aberto'}
                    </Badge>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
