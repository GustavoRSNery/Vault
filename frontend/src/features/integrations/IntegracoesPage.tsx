import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

/**
 * Integrações por webhook, no padrão Standard Webhooks.
 *
 * Duas decisões moldam esta tela:
 *
 * 1. **O segredo aparece uma vez.** No cadastro e na rotação. Quem o perdeu
 *    rotaciona; mostrá-lo de novo numa listagem o espalharia por log de
 *    proxy, histórico de navegador e captura de tela de quem só queria
 *    conferir uma URL.
 *
 * 2. **A fila é visível.** Tentativas, último status e próxima tentativa
 *    ficam à mostra, porque "o webhook não chegou" é a pergunta que essa
 *    tela existe para responder — e sem a fila a resposta seria um palpite.
 */

type Destino = {
  id: string
  name: string
  display_name: string
  url: string
  eventos: string[]
  estado: string
  descricao: string
  falhas_seguidas: number
  ultima_entrega_em: string | null
  ultimo_erro: string
  created_at: string
}

type DestinoCriado = Destino & { segredo: string; aviso: string }

type Entrega = {
  id: string
  id_evento: string
  tipo: string
  estado: string
  tentativas: number
  proxima_em: string
  ultimo_status: number | null
  ultimo_erro: string
  entregue_em: string | null
  created_at: string
}

type Despacho = {
  tentadas: number
  entregues: number
  falhadas: number
  desistidas: number
  destinos_desligados: number
  entregador: string
}

export function IntegracoesPage() {
  const [criando, setCriando] = useState(false)
  const [segredoNovo, setSegredoNovo] = useState<DestinoCriado | null>(null)
  const [abertoId, setAbertoId] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const { data: destinos, isLoading, error } = useQuery({
    queryKey: ['integracoes'],
    queryFn: () => request<Destino[]>('/integracoes'),
  })

  const recarregar = () =>
    void queryClient.invalidateQueries({ queryKey: ['integracoes'] })

  const despachar = useMutation({
    mutationFn: () => request<Despacho>('/integracoes/despachar', { method: 'POST' }),
    onSuccess: recarregar,
  })

  if (isLoading) return <Carregando texto="Carregando integrações…" />
  if (error) {
    return (
      <Vazio
        titulo="Nenhuma integração acessível"
        descricao="Você pode não ter permissão no caminho de integrações."
      />
    )
  }

  const lista = destinos ?? []
  const comProblema = lista.filter(
    (d) => d.estado === 'desligado' || d.falhas_seguidas > 0,
  )

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Integrações</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              O Vault avisa outros sistemas por webhook, no padrão{' '}
              <strong>Standard Webhooks</strong>: cada evento vai assinado, com
              reentrega automática e identificador estável para o destino
              descartar duplicata.
            </p>
          </div>
          <div className="row" style={{ gap: 8 }}>
            <Botao
              pequeno
              variante="secondary"
              disabled={despachar.isPending}
              onClick={() => despachar.mutate()}
              title="Entrega agora o que está pendente na fila."
            >
              {despachar.isPending ? 'Despachando…' : 'Despachar fila'}
            </Botao>
            <Botao pequeno onClick={() => setCriando(true)}>
              Novo destino
            </Botao>
          </div>
        </div>
      </header>

      {despachar.data && (
        <Alerta tom={despachar.data.falhadas > 0 ? 'warning' : 'warning'}>
          Despacho por <strong>{despachar.data.entregador}</strong>:{' '}
          {despachar.data.tentadas} tentada(s), {despachar.data.entregues}{' '}
          entregue(s), {despachar.data.falhadas} falha(s).
          {despachar.data.desistidas > 0 &&
            ` ${despachar.data.desistidas} desistiu depois de esgotar as tentativas.`}
        </Alerta>
      )}

      {comProblema.length > 0 && (
        <Alerta tom="danger">
          {comProblema.length === 1
            ? '1 destino com falha.'
            : `${comProblema.length} destinos com falha.`}{' '}
          Um destino que falha seguidamente é desligado sozinho — tentar para
          sempre em silêncio seria pior do que avisar.
        </Alerta>
      )}

      {segredoNovo && (
        <SegredoRevelado destino={segredoNovo} aoFechar={() => setSegredoNovo(null)} />
      )}

      {criando && (
        <NovoDestino
          aoFechar={() => setCriando(false)}
          aoCriar={(criado) => {
            setCriando(false)
            setSegredoNovo(criado)
            recarregar()
          }}
        />
      )}

      <Card>
        {lista.length === 0 ? (
          <Vazio
            titulo="Nenhum destino cadastrado"
            descricao="Cadastre um endpoint para receber os eventos do cofre: revelação de segredo, certificado vencendo, acesso negado."
          />
        ) : (
          <div className="col" style={{ gap: 4 }}>
            {lista.map((d) => (
              <LinhaDestino
                key={d.id}
                destino={d}
                aberto={abertoId === d.id}
                aoAlternar={() => setAbertoId(abertoId === d.id ? null : d.id)}
                aoMudar={recarregar}
                aoRotacionar={setSegredoNovo}
              />
            ))}
          </div>
        )}
      </Card>
    </>
  )
}

function SegredoRevelado({
  destino,
  aoFechar,
}: {
  destino: DestinoCriado
  aoFechar: () => void
}) {
  const [copiado, setCopiado] = useState(false)

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(destino.segredo)
      setCopiado(true)
    } catch {
      setCopiado(false)
    }
  }

  return (
    <Card titulo={`Segredo de assinatura — ${destino.display_name}`}>
      <div className="col" style={{ gap: 14 }}>
        <Alerta tom="warning">{destino.aviso}</Alerta>

        <div className="field">
          <label htmlFor="segredo-novo">Segredo</label>
          <input id="segredo-novo" className="input" value={destino.segredo} readOnly />
          <span className="help">
            Configure este valor no destino. É com ele que o outro lado
            confere que o evento veio mesmo daqui.
          </span>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => void copiar()}>
            {copiado ? 'Copiado' : 'Copiar segredo'}
          </Botao>
          <Botao variante="secondary" disabled={!copiado} onClick={aoFechar}>
            {copiado ? 'Já guardei' : 'Copie antes de fechar'}
          </Botao>
        </div>
      </div>
    </Card>
  )
}

function LinhaDestino({
  destino,
  aberto,
  aoAlternar,
  aoMudar,
  aoRotacionar,
}: {
  destino: Destino
  aberto: boolean
  aoAlternar: () => void
  aoMudar: () => void
  aoRotacionar: (d: DestinoCriado) => void
}) {
  const [erro, setErro] = useState<string | null>(null)
  const [confirmandoExclusao, setConfirmandoExclusao] = useState(false)

  const acao = useMutation({
    mutationFn: (rota: string) =>
      request<Destino>(`/integracoes/${destino.name}/${rota}`, { method: 'POST' }),
    onSuccess: aoMudar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível concluir.'),
  })

  const testar = useMutation({
    mutationFn: () =>
      request<Despacho>(`/integracoes/${destino.name}/testar`, { method: 'POST' }),
    onSuccess: aoMudar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível testar.'),
  })

  const rotacionar = useMutation({
    mutationFn: () =>
      request<DestinoCriado>(`/integracoes/${destino.name}/rotacionar-segredo`, {
        method: 'POST',
      }),
    onSuccess: (novo) => {
      aoRotacionar(novo)
      aoMudar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível rotacionar.'),
  })

  const excluir = useMutation({
    mutationFn: () =>
      request<void>(`/integracoes/${destino.name}`, { method: 'DELETE' }),
    onSuccess: () => {
      setConfirmandoExclusao(false)
      aoMudar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível excluir.'),
  })

  return (
    <div
      className="col"
      style={{ gap: 10, padding: '12px 0', borderTop: '1px solid var(--line)' }}
    >
      {erro && <Alerta tom="danger">{erro}</Alerta>}

      <div className="row between wrap" style={{ gap: 10 }}>
        <div className="col" style={{ gap: 4 }}>
          <div className="row" style={{ gap: 8, alignItems: 'center' }}>
            <span className="strong">{destino.display_name}</span>
            <EstadoDoDestino destino={destino} />
          </div>
          <code className="help">{destino.url}</code>
          <div className="row wrap" style={{ gap: 6 }}>
            {destino.eventos.length === 0 ? (
              <Badge tom="muted">todos os eventos</Badge>
            ) : (
              destino.eventos.map((e) => (
                <Badge key={e} tom="muted">
                  {e}
                </Badge>
              ))
            )}
          </div>
          {destino.ultimo_erro && (
            <span className="help" style={{ color: 'var(--danger-text)' }}>
              {destino.ultimo_erro}
            </span>
          )}
        </div>

        <div className="row wrap" style={{ gap: 6 }}>
          <Botao
            pequeno
            variante="secondary"
            disabled={testar.isPending}
            onClick={() => testar.mutate()}
            title="Envia um evento de teste agora. Não leva dado de cofre."
          >
            {testar.isPending ? 'Testando…' : 'Testar'}
          </Botao>
          <Botao pequeno variante="ghost" onClick={aoAlternar}>
            {aberto ? 'Fechar fila' : 'Ver fila'}
          </Botao>
          {destino.estado === 'ativo' ? (
            <Botao
              pequeno
              variante="ghost"
              onClick={() => acao.mutate('pausar')}
              disabled={acao.isPending}
            >
              Pausar
            </Botao>
          ) : (
            <Botao
              pequeno
              variante="ghost"
              onClick={() => acao.mutate('reativar')}
              disabled={acao.isPending}
            >
              Reativar
            </Botao>
          )}
          <Botao
            pequeno
            variante="ghost"
            disabled={rotacionar.isPending}
            onClick={() => rotacionar.mutate()}
            title="Gera um segredo novo. As entregas falham até o destino ser atualizado."
          >
            Rotacionar segredo
          </Botao>
          <Botao
            pequeno
            variante="ghost"
            onClick={() => setConfirmandoExclusao(true)}
          >
            Excluir
          </Botao>
        </div>
      </div>

      {testar.data && (
        <Alerta tom="warning">
          Teste por <strong>{testar.data.entregador}</strong>:{' '}
          {testar.data.entregues > 0
            ? 'entregue.'
            : `falhou (${testar.data.falhadas}).`}{' '}
          {testar.data.entregador === 'ensaio' &&
            'O entregador de ensaio não sai para a rede — troque por HTTP para entregar de verdade.'}
        </Alerta>
      )}

      {confirmandoExclusao && (
        <>
          <Alerta tom="warning">
            Excluir remove <strong>{destino.display_name}</strong> e sua fila de
            entregas. Para só parar de enviar, use Pausar.
          </Alerta>
          <div className="row" style={{ gap: 10 }}>
            <Botao
              variante="danger"
              disabled={excluir.isPending}
              onClick={() => excluir.mutate()}
            >
              Excluir destino
            </Botao>
            <Botao variante="secondary" onClick={() => setConfirmandoExclusao(false)}>
              Cancelar
            </Botao>
          </div>
        </>
      )}

      {aberto && <FilaDoDestino nome={destino.name} />}
    </div>
  )
}

function EstadoDoDestino({ destino }: { destino: Destino }) {
  if (destino.estado === 'desligado') {
    return (
      <div className="row" style={{ gap: 6, alignItems: 'center' }}>
        <Badge tom="danger">Desligado</Badge>
        <span className="help">
          {destino.falhas_seguidas} falha
          {destino.falhas_seguidas === 1 ? '' : 's'} seguida
          {destino.falhas_seguidas === 1 ? '' : 's'}
        </span>
      </div>
    )
  }
  if (destino.estado === 'pausado') return <Badge tom="muted">Pausado</Badge>
  if (destino.falhas_seguidas > 0) {
    return (
      <div className="row" style={{ gap: 6, alignItems: 'center' }}>
        <Badge tom="warning">Falhando</Badge>
        <span className="help">{destino.falhas_seguidas} seguida(s)</span>
      </div>
    )
  }
  return <Badge tom="success">Ativo</Badge>
}

function FilaDoDestino({ nome }: { nome: string }) {
  const { data: entregas, isLoading } = useQuery({
    queryKey: ['integracoes', nome, 'entregas'],
    queryFn: () => request<Entrega[]>(`/integracoes/${nome}/entregas`),
  })

  if (isLoading) return <Carregando texto="Carregando fila…" />

  const lista = entregas ?? []
  if (lista.length === 0) {
    return <span className="help">Nenhuma entrega ainda.</span>
  }

  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Evento</th>
            <th>Situação</th>
            <th>Tentativas</th>
            <th>Quando</th>
          </tr>
        </thead>
        <tbody>
          {lista.map((e) => (
            <tr key={e.id}>
              <td>
                <div className="strong">{e.tipo}</div>
                <code className="help" title="É por este id que o destino descarta duplicata.">
                  {e.id_evento}
                </code>
              </td>
              <td>
                <EstadoDaEntrega entrega={e} />
              </td>
              <td className="secret-sm">{e.tentativas}</td>
              <td className="muted">
                {e.entregue_em
                  ? formatarDataHora(e.entregue_em)
                  : `próxima: ${formatarDataHora(e.proxima_em)}`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EstadoDaEntrega({ entrega }: { entrega: Entrega }) {
  if (entrega.estado === 'entregue') {
    return <Badge tom="success">Entregue</Badge>
  }
  if (entrega.estado === 'desistiu') {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="danger">Desistiu</Badge>
        <span className="help">{entrega.ultimo_erro}</span>
      </div>
    )
  }
  if (entrega.estado === 'falhou') {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="warning">Vai tentar de novo</Badge>
        <span className="help">
          {entrega.ultimo_status ? `HTTP ${entrega.ultimo_status}` : entrega.ultimo_erro}
        </span>
      </div>
    )
  }
  return <Badge tom="muted">Pendente</Badge>
}

function NovoDestino({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void
  aoCriar: (criado: DestinoCriado) => void
}) {
  const [nome, setNome] = useState('')
  const [url, setUrl] = useState('')
  const [descricao, setDescricao] = useState('')
  const [selecionados, setSelecionados] = useState<string[]>([])
  const [erro, setErro] = useState<string | null>(null)

  const { data: eventos } = useQuery({
    queryKey: ['integracoes', 'eventos'],
    queryFn: () => request<string[]>('/integracoes/eventos'),
  })

  const identificador = nome
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64)

  const criar = useMutation({
    mutationFn: () =>
      request<DestinoCriado>('/integracoes', {
        method: 'POST',
        body: {
          name: identificador,
          display_name: nome,
          url: url.trim(),
          eventos: selecionados,
          descricao,
        },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  const alternar = (evento: string) =>
    setSelecionados(
      selecionados.includes(evento)
        ? selecionados.filter((e) => e !== evento)
        : [...selecionados, evento],
    )

  // As famílias, derivadas do que a API publica: deixa assinar `segredo.*`
  // sem ter que marcar cada evento futuro dessa família um a um.
  const familias = Array.from(
    new Set((eventos ?? []).map((e) => `${e.split('.')[0]}.*`)),
  )

  const invalido = identificador === '' || !url.trim().startsWith('https://')

  return (
    <Card titulo="Novo destino">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda={identificador ? `Identificador: ${identificador}` : 'Ex.: SIEM corporativo.'}
          autoFocus
        />
        <Campo
          rotulo="URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          ajuda="Precisa ser https: a assinatura prova a origem, não esconde o conteúdo — e nele vão caminhos de segredos."
          placeholder="https://siem.exemplo.com.br/hooks/vault"
          erro={
            url.trim() !== '' && !url.trim().startsWith('https://')
              ? 'Somente https.'
              : undefined
          }
        />
        <Campo
          rotulo="Descrição"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          ajuda="Opcional. Para que serve esta integração."
        />

        <div className="col" style={{ gap: 8 }}>
          <span className="help" style={{ fontWeight: 600 }}>
            Eventos
          </span>
          <span className="help">
            Nenhum marcado = recebe tudo. As opções com <code>.*</code> cobrem
            a família inteira, inclusive eventos que ainda não existem.
          </span>
          <div className="row wrap" style={{ gap: 6 }}>
            {familias.map((f) => (
              <Botao
                key={f}
                pequeno
                variante={selecionados.includes(f) ? 'primary' : 'secondary'}
                onClick={() => alternar(f)}
              >
                {f}
              </Botao>
            ))}
          </div>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => criar.mutate()} disabled={invalido || criar.isPending}>
            {criar.isPending ? 'Cadastrando…' : 'Cadastrar'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
