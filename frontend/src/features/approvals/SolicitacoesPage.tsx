import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

type ResultadoDoLote = {
  aprovadas: number
  recusadas: number
  resultados: { id: string; aprovada: boolean; erro: string }[]
}

type Solicitacao = {
  id: string
  requester_label: string
  path: string
  capabilities: string[]
  reason: string
  hours: number
  status: string
  decided_by_label: string
  decision_note: string
  decided_at: string | null
  granted_until: string | null
  horas_restantes: number | null
  ativa: boolean
  created_at: string
}

const CAPACIDADES = [
  { valor: 'read', rotulo: 'read — ver metadados' },
  { valor: 'reveal', rotulo: 'reveal — revelar o valor' },
  { valor: 'list', rotulo: 'list — listar' },
  { valor: 'update', rotulo: 'update — alterar' },
  { valor: 'delete', rotulo: 'delete — excluir' },
]

const JANELAS = [
  { valor: 1, rotulo: '1 hora' },
  { valor: 4, rotulo: '4 horas' },
  { valor: 8, rotulo: '8 horas' },
  { valor: 24, rotulo: '1 dia' },
  { valor: 72, rotulo: '3 dias' },
  { valor: 168, rotulo: '7 dias' },
  { valor: 720, rotulo: '30 dias (máximo)' },
]

export function SolicitacoesPage() {
  const queryClient = useQueryClient()
  const [pedindo, setPedindo] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['solicitacoes'] })
    void queryClient.invalidateQueries({ queryKey: ['fila'] })
  }

  const { data: minhas, isLoading } = useQuery({
    queryKey: ['solicitacoes'],
    queryFn: () => request<Solicitacao[]>('/solicitacoes'),
  })

  const [marcadas, setMarcadas] = useState<Set<string>>(new Set())
  const [resumoDoLote, setResumoDoLote] = useState<string | null>(null)

  const { data: fila } = useQuery({
    queryKey: ['fila'],
    queryFn: () => request<Solicitacao[]>('/solicitacoes/fila'),
  })

  const decidir = useMutation({
    mutationFn: ({ id, rota, note }: { id: string; rota: string; note?: string }) =>
      request<Solicitacao>(`/solicitacoes/${id}/${rota}`, {
        method: 'POST',
        body: rota === 'revogar' ? undefined : { note: note ?? '' },
      }),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível concluir.'),
  })

  const aprovarLote = useMutation({
    mutationFn: (ids: string[]) =>
      request<ResultadoDoLote>('/solicitacoes/aprovar-em-lote', {
        method: 'POST',
        body: { ids, note: '' },
      }),
    onSuccess: (r) => {
      setErro(null)
      setMarcadas(new Set())
      // O resumo aparece mesmo quando tudo deu certo: "aprovei 7" confirma
      // que o clique fez o que prometia. Quando algo falha, dizer quantos e
      // por quê é o mínimo — aprovar 20 e receber um "ok" genérico
      // esconderia os 3 que ficaram para trás.
      setResumoDoLote(
        r.recusadas === 0
          ? `${r.aprovadas} solicitação(ões) aprovada(s).`
          : `${r.aprovadas} aprovada(s), ${r.recusadas} não: ` +
            r.resultados
              .filter((x) => !x.aprovada)
              .map((x) => x.erro)
              .join(' · '),
      )
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível aprovar.'),
  })

  if (isLoading) return <Carregando texto="Carregando solicitações…" />

  const ativas = (minhas ?? []).filter((s) => s.ativa)

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Solicitações de acesso</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              Acesso que você não deveria ter <b>para sempre</b>. A concessão
              nasce com prazo e caduca sozinha — ninguém precisa lembrar de
              remover.
            </p>
          </div>
          <Botao pequeno onClick={() => setPedindo(true)}>
            Pedir acesso
          </Botao>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      {ativas.length > 0 && (
        <Alerta tom="warning">
          Você tem {ativas.length === 1 ? 'um acesso temporário ativo' : `${ativas.length} acessos temporários ativos`}.
          Terminou antes do prazo? Devolver é um clique — e devolver cedo nunca
          é risco.
        </Alerta>
      )}

      {pedindo && (
        <NovoPedido
          aoFechar={() => setPedindo(false)}
          aoPedir={() => {
            setPedindo(false)
            invalidar()
          }}
        />
      )}

      {fila && fila.length > 0 && (
        <Card titulo={`Fila de aprovação (${fila.length})`}>
          <p className="sub" style={{ marginTop: 0 }}>
            Só o que cabe a você decidir. Pedidos seus não aparecem aqui: quem
            pede não aprova, nem tendo permissão.
          </p>
          {/* Barra de seleção: fica acima da lista e some quando não há
              nada marcado, para não ocupar espaço anunciando uma ação
              indisponível. */}
          <div className="row between wrap" style={{ gap: 12, marginBottom: 14 }}>
            <label className="row" style={{ gap: 8, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={marcadas.size === fila.length && fila.length > 0}
                // Marcado em parte: nem vazio nem cheio. Sem isto, a caixa
                // mostraria "nada selecionado" com 3 de 7 marcados.
                ref={(el) => {
                  if (el) el.indeterminate = marcadas.size > 0 && marcadas.size < fila.length
                }}
                onChange={(e) =>
                  setMarcadas(
                    e.target.checked ? new Set(fila.map((s) => s.id)) : new Set(),
                  )
                }
              />
              <span className="help">
                {marcadas.size > 0
                  ? `${marcadas.size} de ${fila.length} selecionada(s)`
                  : 'Selecionar todas'}
              </span>
            </label>

            {marcadas.size > 0 && (
              <Botao
                pequeno
                onClick={() => aprovarLote.mutate([...marcadas])}
                disabled={aprovarLote.isPending}
              >
                {aprovarLote.isPending
                  ? 'Aprovando…'
                  : `Aprovar ${marcadas.size} selecionada(s)`}
              </Botao>
            )}
          </div>

          {resumoDoLote && (
            <Alerta tom="warning">{resumoDoLote}</Alerta>
          )}

          <div className="col" style={{ gap: 14 }}>
            {fila.map((s) => (
              <CartaoDecisao
                key={s.id}
                solicitacao={s}
                ocupado={decidir.isPending || aprovarLote.isPending}
                aoDecidir={(rota, note) => decidir.mutate({ id: s.id, rota, note })}
                marcada={marcadas.has(s.id)}
                aoMarcar={(marcar) =>
                  setMarcadas((atual) => {
                    const proximo = new Set(atual)
                    if (marcar) proximo.add(s.id)
                    else proximo.delete(s.id)
                    return proximo
                  })
                }
              />
            ))}
          </div>
        </Card>
      )}

      <Card titulo="Minhas solicitações">
        {!minhas || minhas.length === 0 ? (
          <Vazio
            titulo="Você ainda não pediu acesso"
            descricao="Peça quando precisar de algo pontual, em vez de uma permissão permanente."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Caminho</th>
                  <th>Capacidades</th>
                  <th>Motivo</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {minhas.map((s) => (
                  <tr key={s.id}>
                    <td className="strong">
                      <code className="secret-sm">{s.path}</code>
                      <div className="help">
                        Pedido em {formatarDataHora(s.created_at)} · {s.hours}h
                      </div>
                    </td>
                    <td>
                      <div className="row wrap" style={{ gap: 6 }}>
                        {s.capabilities.map((c) => (
                          <Badge key={c} tom="muted">
                            {c}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="muted">{s.reason}</td>
                    <td>
                      <SituacaoPedido solicitacao={s} />
                    </td>
                    <td>
                      {s.ativa && (
                        <Botao
                          variante="secondary"
                          pequeno
                          onClick={() => decidir.mutate({ id: s.id, rota: 'revogar' })}
                          disabled={decidir.isPending}
                        >
                          Devolver
                        </Botao>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function SituacaoPedido({ solicitacao }: { solicitacao: Solicitacao }) {
  if (solicitacao.ativa) {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="success">Ativo</Badge>
        <span className="help">
          Expira em {solicitacao.horas_restantes}h
          {solicitacao.decided_by_label && ` · por ${solicitacao.decided_by_label}`}
        </span>
      </div>
    )
  }

  const tons: Record<string, 'brand' | 'danger' | 'muted' | 'warning'> = {
    pendente: 'warning',
    aprovada: 'muted',
    negada: 'danger',
    revogada: 'muted',
    expirada: 'muted',
  }
  const rotulos: Record<string, string> = {
    pendente: 'Pendente',
    aprovada: 'Expirado',
    negada: 'Negado',
    revogada: 'Devolvido',
    expirada: 'Expirado',
  }

  return (
    <div className="col" style={{ gap: 4 }}>
      <Badge tom={tons[solicitacao.status] ?? 'muted'}>
        {rotulos[solicitacao.status] ?? solicitacao.status}
      </Badge>
      {solicitacao.decided_by_label && (
        <span className="help">
          {solicitacao.decided_by_label}
          {solicitacao.decision_note && ` — ${solicitacao.decision_note}`}
        </span>
      )}
    </div>
  )
}

function CartaoDecisao({
  solicitacao,
  ocupado,
  aoDecidir,
  marcada,
  aoMarcar,
}: {
  solicitacao: Solicitacao
  ocupado: boolean
  aoDecidir: (rota: string, note: string) => void
  marcada: boolean
  aoMarcar: (marcada: boolean) => void
}) {
  const [nota, setNota] = useState('')

  return (
    <div
      className="col"
      style={{
        gap: 12,
        padding: 16,
        borderRadius: 10,
        background: 'var(--surface-2, rgba(0,0,0,.03))',
      }}
    >
      <div className="row between wrap" style={{ gap: 10 }}>
        <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
          <input
            type="checkbox"
            checked={marcada}
            onChange={(e) => aoMarcar(e.target.checked)}
            aria-label={`Selecionar pedido de ${solicitacao.requester_label}`}
            style={{ marginTop: 4 }}
          />
        <div>
          <b>{solicitacao.requester_label}</b>
          <div className="help">
            pede <code className="secret-sm">{solicitacao.capabilities.join(', ')}</code>{' '}
            em <code className="secret-sm">{solicitacao.path}</code> por{' '}
            {solicitacao.hours}h
          </div>
        </div>
        </div>
        <span className="help">{formatarDataHora(solicitacao.created_at)}</span>
      </div>

      <div
        style={{
          padding: 10,
          borderRadius: 8,
          background: 'var(--surface, #fff)',
          fontSize: 13.5,
        }}
      >
        {solicitacao.reason}
      </div>

      <Campo
        rotulo="Observação da decisão"
        value={nota}
        onChange={(e) => setNota(e.target.value)}
        ajuda="Opcional, fica na trilha junto com a decisão."
      />

      <div className="row" style={{ gap: 10 }}>
        <Botao
          pequeno
          onClick={() => aoDecidir('aprovar', nota)}
          disabled={ocupado}
        >
          Aprovar por {solicitacao.hours}h
        </Botao>
        <Botao
          variante="danger"
          pequeno
          onClick={() => aoDecidir('negar', nota)}
          disabled={ocupado}
        >
          Negar
        </Botao>
      </div>
    </div>
  )
}

function NovoPedido({
  aoFechar,
  aoPedir,
}: {
  aoFechar: () => void
  aoPedir: () => void
}) {
  const [caminho, setCaminho] = useState('')
  const [capacidades, setCapacidades] = useState<string[]>(['reveal'])
  const [motivo, setMotivo] = useState('')
  const [horas, setHoras] = useState(4)
  const [erro, setErro] = useState<string | null>(null)

  const pedir = useMutation({
    mutationFn: () =>
      request<Solicitacao>('/solicitacoes', {
        method: 'POST',
        body: { path: caminho, capabilities: capacidades, reason: motivo, hours: horas },
      }),
    onSuccess: aoPedir,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível pedir.'),
  })

  const alternar = (c: string) =>
    setCapacidades((atual) =>
      atual.includes(c) ? atual.filter((x) => x !== c) : [...atual, c],
    )

  const invalido =
    caminho.trim() === '' || motivo.trim() === '' || capacidades.length === 0

  return (
    <Card titulo="Pedir acesso">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Campo
          rotulo="Caminho"
          value={caminho}
          onChange={(e) => setCaminho(e.target.value)}
          ajuda="Ex.: cofres/contabil/segredos/token-sefaz"
          autoFocus
        />

        <div className="col" style={{ gap: 6 }}>
          <label className="help" style={{ fontWeight: 600 }}>
            Capacidades
          </label>
          <div className="row wrap" style={{ gap: 10 }}>
            {CAPACIDADES.map((c) => (
              <label key={c.valor} className="row" style={{ gap: 5, cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={capacidades.includes(c.valor)}
                  onChange={() => alternar(c.valor)}
                />
                <span className="help">{c.rotulo}</span>
              </label>
            ))}
          </div>
        </div>

        <Campo
          rotulo="Justificativa"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          ajuda="Quem decide vai ler isto. Fica na trilha de auditoria."
        />

        <div className="field">
          <label htmlFor="janela">Por quanto tempo</label>
          <select
            id="janela"
            className="input"
            value={horas}
            onChange={(e) => setHoras(Number(e.target.value))}
          >
            {JANELAS.map((j) => (
              <option key={j.valor} value={j.valor}>
                {j.rotulo}
              </option>
            ))}
          </select>
          <span className="help">
            O prazo conta da aprovação, não do pedido. Acima de 30 dias não é
            temporário: altere a política, que é revisada.
          </span>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => pedir.mutate()} disabled={invalido || pedir.isPending}>
            {pedir.isPending ? 'Enviando…' : 'Enviar pedido'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
