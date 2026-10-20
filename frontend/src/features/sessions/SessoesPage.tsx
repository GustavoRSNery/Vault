import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

export type Sessao = {
  id: string
  usuario_label: string
  tipo: string
  alvo: string
  motivo: string
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

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Sessões ativas</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              A trilha diz quem revelou qual segredo. A gravação diz o que a
              pessoa fez com ele depois — e é essa a diferença numa
              investigação.
            </p>
          </div>
          <Botao pequeno onClick={() => setAbrindo(true)}>
            Abrir sessão
          </Botao>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

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
            titulo="Nenhuma sessão sua em andamento"
            descricao="Abra uma ao acessar um sistema com credencial do cofre."
          />
        ) : (
          <TabelaSessoes
            sessoes={minhas}
            acao={(s) => (
              <Botao
                variante="secondary"
                pequeno
                onClick={() => encerrar.mutate(s.id)}
                disabled={encerrar.isPending}
              >
                Encerrar
              </Botao>
            )}
          />
        )}
      </Card>

      {alheias.length > 0 && (
        <Card titulo={`Sessões de outras pessoas (${alheias.length})`}>
          <p className="sub" style={{ marginTop: 0 }}>
            Derrubar interrompe o trabalho de alguém — por isso exige
            justificativa, e ela fica na trilha.
          </p>
          <TabelaSessoes
            sessoes={alheias}
            acao={(s) => (
              <Botao
                variante="danger"
                pequeno
                onClick={() => setDerrubando(s.id)}
              >
                Derrubar
              </Botao>
            )}
          />
        </Card>
      )}

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
                {s.usuario_label}
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

        <Campo
          rotulo="Alvo"
          value={alvo}
          onChange={(e) => setAlvo(e.target.value)}
          ajuda="O sistema que você vai acessar. Ex.: srv-producao, pg-financeiro."
          autoFocus
        />
        <Campo
          rotulo="Motivo"
          value={motivo}
          onChange={(e) => setMotivo(e.target.value)}
          ajuda="Fica na trilha. Opcional, mas é o que responde 'por que esse acesso?' depois."
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
