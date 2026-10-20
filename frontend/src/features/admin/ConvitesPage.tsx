import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

type ConvitePendente = {
  id: string
  email: string
  tipo: string
  nome_sugerido: string
  papeis: string[]
  criado_por: string
  criado_em: string
  expira_em: string
  expirado: boolean
}

type ConviteCriado = {
  id: string
  email: string
  tipo: string
  link: string
  expira_em: string
  aviso: string
}

type Pedido = {
  id: string
  email: string
  motivo: string
  ip_address: string | null
  criado_em: string
}

type Papel = { id: string; name: string; policies: string[] }

export function ConvitesPage() {
  const queryClient = useQueryClient()
  const [criando, setCriando] = useState(false)
  const [emitido, setEmitido] = useState<ConviteCriado | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['convites'] })
    void queryClient.invalidateQueries({ queryKey: ['pedidos-redefinicao'] })
  }

  const { data: convites, isLoading, error } = useQuery({
    queryKey: ['convites'],
    queryFn: () => request<ConvitePendente[]>('/convites'),
  })

  const { data: pedidos } = useQuery({
    queryKey: ['pedidos-redefinicao'],
    queryFn: () => request<Pedido[]>('/recuperar/pedidos'),
    retry: false,
  })

  const cancelar = useMutation({
    mutationFn: (id: string) =>
      request(`/convites/${id}/cancelar`, { method: 'POST' }),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cancelar.'),
  })

  const aprovar = useMutation({
    mutationFn: (id: string) =>
      request<ConviteCriado>(`/recuperar/pedidos/${id}/aprovar`, {
        method: 'POST',
      }),
    onSuccess: (dados) => {
      setErro(null)
      setEmitido(dados)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível aprovar.'),
  })

  if (isLoading) return <Carregando texto="Carregando convites…" />
  if (error) {
    return (
      <Vazio
        titulo="Área restrita"
        descricao="Apenas administradores convidam pessoas."
      />
    )
  }

  if (emitido) {
    return <LinkEmitido convite={emitido} aoFechar={() => setEmitido(null)} />
  }

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Convites</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              O link é gerado e exibido aqui — você entrega pelo canal que
              preferir. Não depende de servidor de e-mail.
            </p>
          </div>
          <Botao pequeno onClick={() => setCriando(true)}>
            Convidar pessoa
          </Botao>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      {criando && (
        <NovoConvite
          aoFechar={() => setCriando(false)}
          aoCriar={(dados) => {
            setCriando(false)
            setEmitido(dados)
            invalidar()
          }}
          aoErro={setErro}
        />
      )}

      {pedidos && pedidos.length > 0 && (
        <Card titulo={`Pedidos de redefinição (${pedidos.length})`}>
          <div className="col" style={{ gap: 12 }}>
            <Alerta tom="warning">
              Estas pessoas não têm segundo fator. <b>Confirme a identidade
              por outro meio</b> — ligação, presencialmente — antes de aprovar.
              O sistema registra que você confirmou, mas não tem como verificar.
            </Alerta>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Quem</th>
                    <th>O que disse</th>
                    <th>Quando</th>
                    <th>De onde</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {pedidos.map((p) => (
                    <tr key={p.id}>
                      <td className="strong">{p.email}</td>
                      <td className="muted">{p.motivo || '—'}</td>
                      <td className="muted">{formatarDataHora(p.criado_em)}</td>
                      <td className="secret-sm muted">{p.ip_address ?? '—'}</td>
                      <td>
                        <Botao
                          pequeno
                          onClick={() => aprovar.mutate(p.id)}
                          disabled={aprovar.isPending}
                        >
                          Aprovar e gerar link
                        </Botao>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </Card>
      )}

      <Card titulo="Convites pendentes">
        {!convites || convites.length === 0 ? (
          <Vazio
            titulo="Nenhum convite em aberto"
            descricao="Convites aceitos, cancelados ou expirados saem desta lista."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Para quem</th>
                  <th>Papéis</th>
                  <th>Convidado por</th>
                  <th>Válido até</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {convites.map((c) => (
                  <tr key={c.id}>
                    <td className="strong">
                      {c.email}
                      {c.nome_sugerido && (
                        <div className="help">{c.nome_sugerido}</div>
                      )}
                    </td>
                    <td>
                      <div className="row wrap" style={{ gap: 6 }}>
                        {c.papeis.length === 0 ? (
                          <span className="muted">— nenhum</span>
                        ) : (
                          c.papeis.map((p) => (
                            <Badge key={p} tom="muted">
                              {p}
                            </Badge>
                          ))
                        )}
                      </div>
                    </td>
                    <td className="muted">{c.criado_por}</td>
                    <td>
                      {c.expirado ? (
                        <Badge tom="danger">Expirado</Badge>
                      ) : (
                        <span className="muted">
                          {formatarDataHora(c.expira_em)}
                        </span>
                      )}
                    </td>
                    <td>
                      <Botao
                        variante="ghost"
                        pequeno
                        onClick={() => cancelar.mutate(c.id)}
                        disabled={cancelar.isPending}
                      >
                        Cancelar
                      </Botao>
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

function LinkEmitido({
  convite,
  aoFechar,
}: {
  convite: ConviteCriado
  aoFechar: () => void
}) {
  const [copiou, setCopiou] = useState(false)
  const url = `${window.location.origin}${convite.link}`

  return (
    <Card titulo="Link gerado">
      <div className="col" style={{ gap: 16 }}>
        <Alerta tom="danger">{convite.aviso}</Alerta>

        <div className="field">
          <label>Link para {convite.email}</label>
          <code
            className="secret-sm"
            style={{ wordBreak: 'break-all', lineHeight: 1.6 }}
          >
            {url}
          </code>
        </div>

        <div className="row wrap" style={{ gap: 10 }}>
          <Botao
            onClick={() => {
              void navigator.clipboard?.writeText(url)
              setCopiou(true)
            }}
          >
            {copiou ? 'Copiado' : 'Copiar link'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar} disabled={!copiou}>
            Concluir
          </Botao>
        </div>

        {!copiou && (
          <span className="help">
            Copie o link antes de fechar — ele não aparece de novo.
          </span>
        )}
      </div>
    </Card>
  )
}

function NovoConvite({
  aoFechar,
  aoCriar,
  aoErro,
}: {
  aoFechar: () => void
  aoCriar: (dados: ConviteCriado) => void
  aoErro: (m: string) => void
}) {
  const [email, setEmail] = useState('')
  const [nome, setNome] = useState('')
  const [papeis, setPapeis] = useState<string[]>([])
  const [dias, setDias] = useState(7)

  const { data: disponiveis } = useQuery({
    queryKey: ['admin', 'papeis'],
    queryFn: () => request<Papel[]>('/admin/papeis'),
    retry: false,
  })

  const convidar = useMutation({
    mutationFn: () =>
      request<ConviteCriado>('/convites', {
        method: 'POST',
        body: { email, nome_sugerido: nome, papeis, dias },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível convidar.'),
  })

  const alternar = (nome: string) =>
    setPapeis((atual) =>
      atual.includes(nome) ? atual.filter((p) => p !== nome) : [...atual, nome],
    )

  return (
    <Card titulo="Convidar pessoa">
      <div className="col" style={{ gap: 14 }}>
        <Campo
          rotulo="E-mail"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          autoFocus
        />
        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda="Sugestão que aparece preenchida para a pessoa. Opcional."
        />

        <div className="col" style={{ gap: 6 }}>
          <label className="help" style={{ fontWeight: 600 }}>
            Papéis que ela terá ao entrar
          </label>
          {!disponiveis || disponiveis.length === 0 ? (
            <span className="muted">Nenhum papel cadastrado.</span>
          ) : (
            <div className="row wrap" style={{ gap: 10 }}>
              {disponiveis.map((p) => (
                <label key={p.id} className="row" style={{ gap: 5, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={papeis.includes(p.name)}
                    onChange={() => alternar(p.name)}
                  />
                  <span className="help">{p.name}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <div className="field">
          <label htmlFor="dias">Validade do link</label>
          <select
            id="dias"
            className="input"
            value={dias}
            onChange={(e) => setDias(Number(e.target.value))}
          >
            <option value={1}>1 dia</option>
            <option value={7}>7 dias</option>
            <option value={15}>15 dias</option>
            <option value={30}>30 dias (máximo)</option>
          </select>
          <span className="help">
            Convite que dura meses é porta aberta que ninguém lembra de fechar.
          </span>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => convidar.mutate()}
            disabled={!email.includes('@') || convidar.isPending}
          >
            {convidar.isPending ? 'Gerando…' : 'Gerar link'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
