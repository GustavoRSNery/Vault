import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import {
  Alerta,
  Badge,
  Botao,
  Campo,
  Card,
  CardMetrica,
  Carregando,
  Vazio,
} from '@/shared/ui/components'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'

/** Uma máquina alcançável por SSH, vinda de Dispositivos. */
export type MaquinaSsh = {
  name: string
  display_name: string
  host: string
  porta: number
  usuario_sugerido: string
  segredo_path: string
  tem_credencial: boolean
  /** A conexão já montada pelo servidor — a tela não concatena nada. */
  comando: string
  url: string
}

export type MotivoDeSessao = { valor: string; rotulo: string }

export type Sessao = {
  id: string
  usuario_label: string
  usuario_nome: string
  tipo: string
  alvo: string
  motivo: string
  motivo_detalhe: string
  estado: string
  ip_address: string | null
  iniciada_em: string
  ultima_atividade_em: string
  encerrada_em: string | null
  encerrada_por: string
  motivo_encerramento: string
  duracao_ms: number
  eventos: number
  minha: boolean
  capturado_por: string
  captura_automatica: boolean
  origem: {
    ip_address: string | null
    hostname: string
    user_agent: string
    dispositivo_name: string
    descricao: string
    identificada: boolean
  }
  consumo: {
    tipo: string
    nome: string
    caminho: string
    pertence_a: string
    descricao: string
    saiu_do_cofre: boolean
  }
}

const TIPOS = [
  { valor: 'ssh', rotulo: 'SSH' },
  { valor: 'rdp', rotulo: 'RDP' },
  { valor: 'banco_de_dados', rotulo: 'Banco de dados' },
  { valor: 'web', rotulo: 'Web' },
  { valor: 'outro', rotulo: 'Outro' },
]

export function formatarDuracao(ms: number): string {
  const segundos = Math.floor(ms / 1000)
  if (segundos < 60) return `${segundos}s`
  const minutos = Math.floor(segundos / 60)
  if (minutos < 60) return `${minutos}min`
  const horas = Math.floor(minutos / 60)
  return `${horas}h ${minutos % 60}min`
}

export function SessoesPage() {
  const queryClient = useQueryClient()
  const [abrindo, setAbrindo] = useState(false)
  const tour = useTour('sessoes')
  const [erro, setErro] = useState<string | null>(null)
  const [derrubando, setDerrubando] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['sessoes'] })
    void queryClient.invalidateQueries({ queryKey: ['gravacoes'] })
  }

  const { data: ativas, isLoading } = useQuery({
    queryKey: ['sessoes'],
    queryFn: () => request<Sessao[]>('/sessoes'),
    // Sessão ativa muda sozinha: a lista precisa acompanhar sem recarregar.
    refetchInterval: 15_000,
  })

  const encerrar = useMutation({
    mutationFn: (id: string) =>
      request<Sessao>(`/sessoes/${id}/encerrar`, {
        method: 'POST',
        body: { motivo: '' },
      }),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível encerrar.'),
  })

  if (isLoading) return <Carregando texto="Carregando sessões…" />

  const lista = ativas ?? []
  const minhas = lista.filter((s) => s.minha)
  const alheias = lista.filter((s) => !s.minha)
  const pessoas = new Set(lista.map((s) => s.usuario_label)).size
  const maquinas = new Set(lista.map((s) => s.alvo)).size

  return (
    <>
      <Tour id="sessoes" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Sessões SSH</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              Quem está dentro de qual máquina, agora. Conectar é em{' '}
              <Link to="/dispositivos">Dispositivos</Link>; aqui se acompanha
              e se encerra o que está em andamento.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Sessões"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/sessoes',
                  descricao: 'As sessões abertas agora, com quem acessa e desde quando.',
                },
                {
                  metodo: 'GET',
                  caminho: '/sessoes/maquinas',
                  descricao: 'As máquinas alcançáveis por SSH, vindas do inventário.',
                },
                {
                  metodo: 'GET',
                  caminho: '/sessoes/motivos',
                  descricao: 'Os motivos aceitos ao abrir uma sessão. Lista fechada.',
                },
              ]}
            />
            <Botao variante="secondary" pequeno onClick={() => setAbrindo(true)}>
              Registrar outro acesso
            </Botao>
          </div>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      {/* Três contagens diferentes, de propósito: duas sessões da mesma
          pessoa na mesma máquina são 2 sessões, 1 pessoa e 1 máquina — e é
          essa diferença que diz se o acesso está concentrado ou espalhado. */}
      <div className="cards-3" data-tour="metricas-sessoes">
        <CardMetrica rotulo="Sessões agora" valor={lista.length} tom="brand" />
        <CardMetrica rotulo="Pessoas conectadas" valor={pessoas} tom="success" />
        <CardMetrica rotulo="Máquinas em uso" valor={maquinas} tom="warning" />
      </div>

      {abrindo && (
        <NovaSessao
          aoFechar={() => setAbrindo(false)}
          aoAbrir={() => {
            setAbrindo(false)
            invalidar()
          }}
          aoErro={setErro}
        />
      )}

      <Card titulo={`Minhas sessões (${minhas.length})`}>
        {minhas.length === 0 ? (
          <Vazio
            titulo="Você não está em nenhuma máquina"
            descricao="As sessões aparecem aqui quando você acessa uma máquina a partir de Dispositivos."
            acao={
              <Link to="/dispositivos" className="btn btn-secondary btn-sm">
                Ir para Dispositivos →
              </Link>
            }
          />
        ) : (
          <div className="col" style={{ gap: 10 }}>
            {minhas.map((s) => (
              <CardDeSessao
                key={s.id}
                sessao={s}
                acao={
                  <Botao
                    variante="secondary"
                    pequeno
                    onClick={() => encerrar.mutate(s.id)}
                    disabled={encerrar.isPending}
                  >
                    Encerrar
                  </Botao>
                }
              />
            ))}
          </div>
        )}
      </Card>

      <Card titulo={`Sessões de outras pessoas (${alheias.length})`} data-tour="sessoes-outras">
        {alheias.length === 0 ? (
          <Vazio
            titulo="Ninguém mais está conectado agora"
            descricao="Aparecem aqui as sessões em andamento de outras pessoas, se você tiver permissão para vê-las."
          />
        ) : (
          <>
            <p className="sub" style={{ marginTop: 0 }}>
              Derrubar interrompe o trabalho de alguém — por isso exige
              justificativa, e ela fica na trilha.
            </p>
            <div className="col" style={{ gap: 10 }}>
              {alheias.map((s) => (
                <CardDeSessao
                  key={s.id}
                  sessao={s}
                  acao={
                    <Botao
                      variante="danger"
                      pequeno
                      onClick={() => setDerrubando(s.id)}
                    >
                      Derrubar
                    </Botao>
                  }
                />
              ))}
            </div>
          </>
        )}
      </Card>

      {derrubando && (
        <FormularioDerrubar
          sessao={lista.find((s) => s.id === derrubando)!}
          aoFechar={() => setDerrubando(null)}
          aoDerrubar={() => {
            setDerrubando(null)
            invalidar()
          }}
          aoErro={setErro}
        />
      )}
    </>
  )
}

/**
 * Uma sessão ativa, em card.
 *
 * As três perguntas de quem olha uma sessão em andamento são **quem**, **em
 * qual máquina** e **há quanto tempo** — e numa tabela de oito colunas elas
 * ficam espremidas entre dados que só importam depois. O card põe as três em
 * primeiro plano e empurra o resto para a segunda linha.
 *
 * O tempo é recalculado a cada segundo: "há 3 minutos" congelado numa tela
 * aberta há meia hora é pior que não mostrar nada.
 */
function CardDeSessao({
  sessao,
  acao,
}: {
  sessao: Sessao
  acao?: React.ReactNode
}) {
  const [agora, setAgora] = useState(() => Date.now())

  useEffect(() => {
    const t = window.setInterval(() => setAgora(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [])

  const desde = new Date(sessao.iniciada_em).getTime()
  const decorrido = Number.isFinite(desde) ? Math.max(agora - desde, 0) : sessao.duracao_ms

  return (
    <div className="card sessao-card">
      <div className="row between wrap" style={{ gap: 12 }}>
        <div className="row" style={{ gap: 12, alignItems: 'flex-start' }}>
          <span className="avatar" aria-hidden="true">
            {iniciaisDe(sessao.usuario_nome || sessao.usuario_label)}
          </span>
          <div className="col" style={{ gap: 2 }}>
            <b>{sessao.usuario_nome || sessao.usuario_label}</b>
            {/* O e-mail só aparece quando há nome: repetido sozinho, viraria
                a mesma linha duas vezes. */}
            {sessao.usuario_nome && (
              <span className="help">{sessao.usuario_label}</span>
            )}
            <span className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <Badge tom="muted">{sessao.tipo}</Badge>
              <Link to={`/sessoes/${sessao.id}`}>{sessao.alvo}</Link>
            </span>
            <span className="help">
              {sessao.origem?.identificada
                ? `de ${sessao.origem.descricao}`
                : 'origem não identificada'}
              {sessao.motivo && ` · ${sessao.motivo}`}
              {sessao.motivo_detalhe && ` — ${sessao.motivo_detalhe}`}
            </span>
          </div>
        </div>

        <div className="col" style={{ gap: 2, alignItems: 'flex-end' }}>
          <span className="sessao-tempo" title={formatarDataHora(sessao.iniciada_em)}>
            {formatarDuracao(decorrido)}
          </span>
          <span className="help">na máquina</span>
          {acao}
        </div>
      </div>
    </div>
  )
}

/** Duas iniciais do nome ou do e-mail, para o avatar. */
function iniciaisDe(rotulo: string): string {
  const base = rotulo.includes('@') ? rotulo.split('@')[0] ?? rotulo : rotulo
  return base
    .split(/[\s._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p.charAt(0).toUpperCase())
    .join('')
}

export function TabelaSessoes({
  sessoes,
  acao,
}: {
  sessoes: Sessao[]
  acao?: (s: Sessao) => React.ReactNode
}) {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>
            <th>Alvo</th>
            <th>Quem</th>
            <th>Início</th>
            <th>Duração</th>
            <th>Eventos</th>
            <th>De onde</th>
            <th>Usou</th>
            <th>Captura</th>
            {acao && <th />}
          </tr>
        </thead>
        <tbody>
          {sessoes.map((s) => (
            <tr key={s.id}>
              <td className="strong">
                <Link to={`/sessoes/${s.id}`}>{s.alvo}</Link>
                {s.motivo && <div className="help">{s.motivo}</div>}
                <div>
                  <Badge tom="muted">{s.tipo}</Badge>
                </div>
              </td>
              <td className="muted">
                {s.usuario_nome || s.usuario_label}
                {s.usuario_nome && <div className="help">{s.usuario_label}</div>}
                {s.ip_address && <div className="help">{s.ip_address}</div>}
              </td>
              <td className="muted">{formatarDataHora(s.iniciada_em)}</td>
              <td className="secret-sm">{formatarDuracao(s.duracao_ms)}</td>
              <td className="secret-sm">{s.eventos}</td>
              <td className="muted">
                {s.origem?.identificada ? (
                  <>
                    {s.origem.descricao}
                    {s.origem.user_agent && (
                      <div className="help">{s.origem.user_agent}</div>
                    )}
                  </>
                ) : (
                  <span className="help">não identificada</span>
                )}
              </td>
              <td className="muted">
                <ConsumoDaSessao consumo={s.consumo} />
              </td>
              <td>
                {s.captura_automatica ? (
                  <Badge tom="success">capturada</Badge>
                ) : (
                  <Badge tom="warning">anotada</Badge>
                )}
              </td>
              {acao && <td>{acao(s)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/**
 * O que a sessão usou para entrar.
 *
 * Mostra o NOME e o CAMINHO, nunca o valor: saber que a sessão usou
 * `cofres/infra/segredos/senha-root` responde à auditoria sem revelar nada.
 * Quem precisa do valor vai ao cofre, e essa ida fica registrada.
 */
function ConsumoDaSessao({ consumo }: { consumo: Sessao['consumo'] }) {
  if (!consumo || consumo.tipo === 'nao_identificado') {
    return <span className="help">não identificado</span>
  }
  if (consumo.tipo === 'propria') {
    return <span className="help">credencial da própria pessoa</span>
  }

  const rotulo =
    consumo.tipo === 'chave_api'
      ? 'Chave de API'
      : consumo.tipo === 'certificado'
        ? 'Certificado'
        : 'Credencial'

  return (
    <div className="col" style={{ gap: 4 }}>
      <div className="row" style={{ gap: 6, alignItems: 'center' }}>
        <Badge tom={consumo.saiu_do_cofre ? 'warning' : 'muted'}>{rotulo}</Badge>
        <span>{consumo.nome}</span>
      </div>
      {consumo.pertence_a && <span className="help">{consumo.pertence_a}</span>}
      {consumo.caminho && (
        <span className="help" title="Caminho do segredo. O valor não sai daqui.">
          <code>{consumo.caminho}</code>
        </span>
      )}
    </div>
  )
}

function NovaSessao({
  aoFechar,
  aoAbrir,
  aoErro,
}: {
  aoFechar: () => void
  aoAbrir: () => void
  aoErro: (m: string) => void
}) {
  const [tipo, setTipo] = useState('ssh')
  const [alvo, setAlvo] = useState('')
  const [motivo, setMotivo] = useState('')
  const [motivoDetalhe, setMotivoDetalhe] = useState('')

  // As duas listas vêm do servidor: duplicá-las aqui as faria divergir do
  // domínio no primeiro valor novo, e a tela ofereceria uma opção que a API
  // recusa.
  const { data: maquinas } = useQuery({
    queryKey: ['sessoes', 'maquinas'],
    queryFn: () => request<MaquinaSsh[]>('/sessoes/maquinas'),
  })
  const { data: motivos } = useQuery({
    queryKey: ['sessoes', 'motivos'],
    queryFn: () => request<MotivoDeSessao[]>('/sessoes/motivos'),
    staleTime: 10 * 60_000,
  })
  const [maquina, setMaquina] = useState('')
  const [consumoTipo, setConsumoTipo] = useState('nao_identificado')
  const [consumoNome, setConsumoNome] = useState('')
  const [consumoDono, setConsumoDono] = useState('')
  const [caminho, setCaminho] = useState('')

  const precisaNome =
    consumoTipo !== 'nao_identificado' && consumoTipo !== 'propria'

  const abrir = useMutation({
    mutationFn: () =>
      request<Sessao>('/sessoes', {
        method: 'POST',
        body: {
          tipo,
          alvo,
          motivo,
          motivo_detalhe: motivoDetalhe.trim(),
          origem_hostname: maquina.trim(),
          consumo_tipo: consumoTipo,
          consumo_nome: consumoNome.trim(),
          consumo_pertence_a: consumoDono.trim(),
          segredo_path: caminho.trim() || null,
        },
      }),
    onSuccess: aoAbrir,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível abrir.'),
  })

  return (
    <Card titulo="Abrir sessão">
      <div className="col" style={{ gap: 14 }}>
        <div className="field">
          <label htmlFor="tipo">Tipo de acesso</label>
          <select
            id="tipo"
            className="input"
            value={tipo}
            onChange={(e) => setTipo(e.target.value)}
          >
            {TIPOS.map((t) => (
              <option key={t.valor} value={t.valor}>
                {t.rotulo}
              </option>
            ))}
          </select>
        </div>

        {/* Alvo e motivo saem de listas, não de texto livre. Livres, viram
            "srv-prod", "SRV-PROD" e "servidor de producao" para a mesma
            máquina — e aí nenhuma pergunta sobre acesso tem resposta. */}
        <div className="field">
          <label htmlFor="alvo">Máquina</label>
          <select
            id="alvo"
            className="input"
            value={alvo}
            onChange={(e) => {
              setAlvo(e.target.value)
              const m = maquinas?.find((x) => x.name === e.target.value)
              // Preenche o caminho da credencial sozinho: quem escolheu a
              // máquina já disse qual segredo usa, e pedir de novo só
              // convidaria a digitar errado.
              if (m?.segredo_path) {
                setCaminho(m.segredo_path)
                setConsumoTipo('credencial')
                setConsumoNome(m.segredo_path.split('/').pop() ?? '')
              }
            }}
            autoFocus
          >
            <option value="">Escolha a máquina…</option>
            {(maquinas ?? []).map((m) => (
              <option key={m.name} value={m.name}>
                {m.display_name} — {m.host}:{m.porta}
                {m.usuario_sugerido ? ` (${m.usuario_sugerido})` : ''}
              </option>
            ))}
          </select>
          <span className="help">
            {maquinas && maquinas.length === 0 ? (
              <>
                Nenhuma máquina com acesso SSH cadastrado. Cadastre em{' '}
                <Link to="/dispositivos">Dispositivos</Link>, na coluna
                Acesso.
              </>
            ) : (
              'Só aparecem as máquinas com acesso SSH cadastrado em Dispositivos.'
            )}
          </span>
        </div>

        <div className="field">
          <label htmlFor="motivo">Motivo</label>
          <select
            id="motivo"
            className="input"
            value={motivo}
            onChange={(e) => setMotivo(e.target.value)}
          >
            <option value="">Escolha o motivo…</option>
            {(motivos ?? []).map((m) => (
              <option key={m.valor} value={m.valor}>
                {m.rotulo}
              </option>
            ))}
          </select>
          <span className="help">
            A categoria é o que permite medir por que as pessoas entram nas
            máquinas.
          </span>
        </div>

        <Campo
          rotulo="Detalhe (opcional)"
          value={motivoDetalhe}
          onChange={(e) => setMotivoDetalhe(e.target.value)}
          ajuda="Ticket, chamado ou o que esta sessão teve de particular. Fica na trilha."
          placeholder="ticket #4417 — lentidão no banco"
        />

        <Campo
          rotulo="Sua máquina"
          value={maquina}
          onChange={(e) => setMaquina(e.target.value)}
          ajuda="Nome do computador de onde você está acessando. O IP sozinho não distingue duas pessoas na mesma rede."
          placeholder="NOTE-CONTABIL-07"
        />

        <div className="field">
          <label htmlFor="consumo">O que você vai usar para entrar</label>
          <select
            id="consumo"
            className="input"
            value={consumoTipo}
            onChange={(e) => setConsumoTipo(e.target.value)}
          >
            <option value="nao_identificado">Não informar</option>
            <option value="credencial">Credencial do cofre</option>
            <option value="chave_api">Chave de API</option>
            <option value="certificado">Certificado</option>
            <option value="propria">Minha própria credencial</option>
          </select>
          <span className="help">
            Identifica o que foi usado, nunca o valor. Quem precisa do valor
            vai ao cofre, e essa ida fica registrada.
          </span>
        </div>

        {precisaNome && (
          <>
            <Campo
              rotulo="Qual"
              value={consumoNome}
              onChange={(e) => setConsumoNome(e.target.value)}
              ajuda="O nome do que você vai usar. Ex.: senha-root, SEFAZ NF-e."
            />
            <Campo
              rotulo="De quem"
              value={consumoDono}
              onChange={(e) => setConsumoDono(e.target.value)}
              ajuda="Opcional. O dispositivo ou serviço dono do segredo."
            />
            <Campo
              rotulo="Caminho no cofre"
              value={caminho}
              onChange={(e) => setCaminho(e.target.value)}
              ajuda="Opcional. Ex.: cofres/infra/segredos/senha-root. Só o caminho — o valor nunca é gravado aqui."
            />
          </>
        )}

        <Alerta tom="warning">
          Nesta instalação a gravação é <b>manual</b>: você registra o que fez.
          Com um proxy conectado, a captura passa a ser automática — e a tela
          avisa qual das duas foi usada em cada gravação.
        </Alerta>

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => abrir.mutate()} disabled={
              !alvo.trim() ||
              // O motivo é obrigatório no domínio; travar aqui evita o 422
              // e diz antes o que falta, em vez de depois.
              !motivo ||
              (precisaNome && !consumoNome.trim()) ||
              abrir.isPending
            }>
            {abrir.isPending ? 'Abrindo…' : 'Abrir'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}

function FormularioDerrubar({
  sessao,
  aoFechar,
  aoDerrubar,
  aoErro,
}: {
  sessao: Sessao
  aoFechar: () => void
  aoDerrubar: () => void
  aoErro: (m: string) => void
}) {
  const [motivo, setMotivo] = useState('')

  const derrubar = useMutation({
    mutationFn: () =>
      request<Sessao>(`/sessoes/${sessao.id}/derrubar`, {
        method: 'POST',
        body: { motivo },
      }),
    onSuccess: aoDerrubar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível derrubar.'),
  })

  return (
    <Card titulo={`Derrubar a sessão de ${sessao.usuario_label}`}>
      <div className="col" style={{ gap: 14 }}>
        <Alerta tom="warning">
          Isto interrompe o trabalho de alguém em <b>{sessao.alvo}</b>. A
          gravação é preservada e a justificativa fica na trilha.
        </Alerta>
        <Campo
          rotulo="Justificativa"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          ajuda="Obrigatória."
          autoFocus
        />
        <div className="row" style={{ gap: 10 }}>
          <Botao
            variante="danger"
            onClick={() => derrubar.mutate()}
            disabled={!motivo.trim() || derrubar.isPending}
          >
            {derrubar.isPending ? 'Derrubando…' : 'Derrubar'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
