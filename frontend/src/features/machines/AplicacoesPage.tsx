import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'

type Aplicacao = {
  id: string
  name: string
  display_name: string
  description: string
  owner_label: string
  status: string
  lease_minutos: number
  role_id: string
  papel: string | null
  credenciais_ativas: number
  leases_ativos: number
  created_at: string
}

type CredencialEmitida = {
  id: string
  role_id: string
  secret_id: string
  label: string
  expires_at: string | null
  aviso: string
}

type Credencial = {
  id: string
  label: string
  created_by: string
  created_at: string
  expires_at: string | null
  revoked_at: string | null
  last_used_at: string | null
  usos: number
  valida: boolean
}

type Lease = {
  id: string
  caminhos: string[]
  capacidades: string[]
  created_at: string
  expires_at: string
  revoked_at: string | null
  leituras: number
  ativo: boolean
  minutos_restantes: number | null
}

type LinhaConsumo = {
  caminho: string
  leituras: number
  ultima: string
  tipo: string
  cofre: string
}

type Consumo = {
  aplicacao: string
  dias: number
  lidos: LinhaConsumo[]
  negados: LinhaConsumo[]
  caminhos_no_escopo: string[]
  nunca_lidos: string[]
  por_tipo: Record<string, number>
}

/**
 * Rótulos dos tipos de segredo.
 *
 * O tipo responde "que espécie de credencial este robô usa?" — a diferença
 * entre uma lista de caminhos, que ninguém julga, e uma revisão de escopo
 * que alguém consegue conferir em segundos.
 */
const ROTULO_TIPO_SEGREDO: Record<string, string> = {
  senha: 'senha',
  chave_api: 'chave de API',
  chave_ssh: 'chave SSH',
  certificado: 'certificado',
  token: 'token',
  nota: 'nota',
  desconhecido: 'desconhecido',
}

const TOM_DO_TIPO: Record<string, 'brand' | 'warning' | 'muted'> = {
  senha: 'brand',
  chave_api: 'warning',
  chave_ssh: 'warning',
  certificado: 'brand',
  token: 'warning',
  nota: 'muted',
  desconhecido: 'muted',
}

type CredencialVencendo = {
  aplicacao: string
  responsavel: string
  credencial_id: string
  label: string
  dias_para_vencer: number | null
  ultimo_uso: string | null
  nunca_usada: boolean
}

type Vencimentos = {
  dias: number
  vencendo: CredencialVencendo[]
  nunca_usadas: CredencialVencendo[]
}

type Papel = { id: string; name: string; policies: string[] }

export function AplicacoesPage() {
  const queryClient = useQueryClient()
  const [criando, setCriando] = useState(false)
  const [detalhe, setDetalhe] = useState<string | null>(null)
  const [emitida, setEmitida] = useState<CredencialEmitida | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['aplicacoes'] })
    if (detalhe) {
      void queryClient.invalidateQueries({ queryKey: ['credenciais-app', detalhe] })
      void queryClient.invalidateQueries({ queryKey: ['leases', detalhe] })
    }
  }

  const { data: apps, isLoading, error } = useQuery({
    queryKey: ['aplicacoes'],
    queryFn: () => request<Aplicacao[]>('/aplicacoes'),
  })

  const { data: vencimentos } = useQuery({
    queryKey: ['vencimentos'],
    queryFn: () => request<Vencimentos>('/aplicacoes-vencimentos'),
    retry: false,
  })

  if (isLoading) return <Carregando texto="Carregando aplicações…" />
  if (error) {
    return (
      <Vazio
        titulo="Área restrita"
        descricao="Apenas quem administra aplicações acessa esta tela."
      />
    )
  }

  if (emitida) {
    return (
      <CredencialNova
        credencial={emitida}
        aoFechar={() => {
          setEmitida(null)
          invalidar()
        }}
      />
    )
  }

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Aplicações</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              RPAs e serviços que leem segredos sem pessoa envolvida. Em vez de
              senha eterna no código, cada um autentica e recebe um acesso
              temporário que expira sozinho.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <TutorialApi
              titulo="Aplicações"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/aplicacoes',
                  descricao:
                    'As aplicações cadastradas para acesso de máquina.',
                },
                {
                  metodo: 'GET',
                  caminho: '/aplicacoes/{nome}/credenciais',
                  descricao:
                    'As credenciais que a aplicação pode ler.',
                },
                {
                  metodo: 'GET',
                  caminho: '/aplicacoes/{nome}/leases',
                  descricao:
                    'Os leases ativos: o acesso que a aplicação tem agora.',
                },
                {
                  metodo: 'GET',
                  caminho: '/aplicacoes/{nome}/consumo',
                  descricao:
                    'O que a aplicação de fato leu, e quando.',
                },
                {
                  metodo: 'GET',
                  caminho: '/aplicacoes-vencimentos',
                  descricao:
                    'Credenciais vencendo e as que ninguém lê há tempo.',
                },
              ]}
              observacao="Se uma credencial está parada há muito tempo, vale checar: ou a aplicação deixou de usá-la, ou ela tem um acesso que não precisa ter."
            />
            <Botao pequeno onClick={() => setCriando(true)}>
              Nova aplicação
            </Botao>
          </div>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      {vencimentos && vencimentos.vencendo.length > 0 && (
        <Alerta tom="warning">
          {vencimentos.vencendo.length === 1
            ? '1 credencial vence'
            : `${vencimentos.vencendo.length} credenciais vencem`}{' '}
          nos próximos {vencimentos.dias} dias:{' '}
          {vencimentos.vencendo
            .map((c) => `${c.aplicacao} (${c.dias_para_vencer}d)`)
            .join(', ')}
          . O robô pode trocar a própria credencial sem parar — a anterior
          ainda vale por alguns minutos depois da troca.
        </Alerta>
      )}

      {vencimentos && vencimentos.nunca_usadas.length > 0 && (
        <Alerta tom="warning">
          {vencimentos.nunca_usadas.length === 1
            ? '1 credencial foi emitida e nunca usada'
            : `${vencimentos.nunca_usadas.length} credenciais foram emitidas e nunca usadas`}
          :{' '}
          {vencimentos.nunca_usadas
            .map((c) => `${c.aplicacao}/${c.label || 'sem rótulo'}`)
            .join(', ')}
          . Credencial esquecida autentica do mesmo jeito — vale revogar.
        </Alerta>
      )}

      {criando && (
        <NovaAplicacao
          aoFechar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            invalidar()
          }}
          aoErro={setErro}
        />
      )}

      <Card>
        {!apps || apps.length === 0 ? (
          <Vazio
            titulo="Nenhuma aplicação cadastrada"
            descricao="Cadastre os RPAs que precisam ler segredos, para que nenhum deles use credencial de pessoa."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Aplicação</th>
                  <th>Responsável</th>
                  <th>Papel</th>
                  <th>Lease</th>
                  <th>Credenciais</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {apps.map((app) => (
                  <tr key={app.id}>
                    <td className="strong">
                      {app.display_name}
                      <div className="help">
                        <code className="secret-sm">{app.role_id}</code>
                      </div>
                      {app.status !== 'ativa' && (
                        <Badge tom="danger">Suspensa</Badge>
                      )}
                    </td>
                    <td className="muted">{app.owner_label}</td>
                    <td>
                      {app.papel ? (
                        <Badge tom="brand">{app.papel}</Badge>
                      ) : (
                        <Badge tom="danger">sem papel</Badge>
                      )}
                    </td>
                    <td className="muted">{app.lease_minutos} min</td>
                    <td>
                      <div className="col" style={{ gap: 2 }}>
                        <span className="secret-sm">
                          {app.credenciais_ativas} ativa
                          {app.credenciais_ativas === 1 ? '' : 's'}
                        </span>
                        {app.leases_ativos > 0 && (
                          <span className="help">
                            {app.leases_ativos} lease
                            {app.leases_ativos === 1 ? '' : 's'} em uso
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <Botao
                        variante="secondary"
                        pequeno
                        onClick={() =>
                          setDetalhe(detalhe === app.name ? null : app.name)
                        }
                      >
                        {detalhe === app.name ? 'Fechar' : 'Abrir'}
                      </Botao>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {detalhe && (
        <DetalheAplicacao
          nome={detalhe}
          aoEmitir={setEmitida}
          aoErro={setErro}
          aoMudar={invalidar}
        />
      )}
    </>
  )
}

function NovaAplicacao({
  aoFechar,
  aoCriar,
  aoErro,
}: {
  aoFechar: () => void
  aoCriar: () => void
  aoErro: (mensagem: string) => void
}) {
  const [nome, setNome] = useState('')
  const [responsavel, setResponsavel] = useState('')
  const [papel, setPapel] = useState('')
  const [minutos, setMinutos] = useState(60)

  const { data: papeis } = useQuery({
    queryKey: ['admin', 'papeis'],
    queryFn: () => request<Papel[]>('/admin/papeis'),
    retry: false,
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
      request<Aplicacao>('/aplicacoes', {
        method: 'POST',
        body: {
          name: identificador,
          display_name: nome,
          owner_label: responsavel,
          papel: papel || null,
          lease_minutos: minutos,
        },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  return (
    <Card titulo="Nova aplicação">
      <div className="col" style={{ gap: 14 }}>
        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda={identificador ? `Identificador: ${identificador}` : 'Ex.: RPA Fiscal.'}
          autoFocus
        />
        <Campo
          rotulo="Responsável"
          value={responsavel}
          onChange={(e) => setResponsavel(e.target.value)}
          ajuda="Quem responde por este robô. Credencial sem dono é credencial que ninguém revoga."
        />

        <div className="field">
          <label htmlFor="papel">Papel</label>
          <select
            id="papel"
            className="input"
            value={papel}
            onChange={(e) => setPapel(e.target.value)}
          >
            <option value="">— sem papel —</option>
            {(papeis ?? []).map((p) => (
              <option key={p.id} value={p.name}>
                {p.name} ({p.policies.join(', ') || 'sem política'})
              </option>
            ))}
          </select>
          <span className="help">
            O papel carrega as políticas — o mesmo mecanismo das pessoas. Sem
            papel, a aplicação não consegue autenticar: um acesso sem escopo
            não serviria para nada.
          </span>
        </div>

        <div className="field">
          <label htmlFor="minutos">Duração do acesso</label>
          <select
            id="minutos"
            className="input"
            value={minutos}
            onChange={(e) => setMinutos(Number(e.target.value))}
          >
            <option value={15}>15 minutos</option>
            <option value={60}>1 hora</option>
            <option value={240}>4 horas</option>
            <option value={720}>12 horas (máximo)</option>
          </select>
          <span className="help">
            Quanto menor, menos vale um token roubado. O teto é 12h: além
            disso deixa de ser empréstimo.
          </span>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => criar.mutate()}
            disabled={!identificador || !responsavel.trim() || criar.isPending}
          >
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

function CredencialNova({
  credencial,
  aoFechar,
}: {
  credencial: CredencialEmitida
  aoFechar: () => void
}) {
  const [confirmou, setConfirmou] = useState(false)

  return (
    <Card titulo="Credencial emitida">
      <div className="col" style={{ gap: 16 }}>
        <Alerta tom="danger">{credencial.aviso}</Alerta>

        <div className="col" style={{ gap: 12 }}>
          <div className="field">
            <label>role_id (público — pode ir no código)</label>
            <code className="secret-sm" style={{ wordBreak: 'break-all' }}>
              {credencial.role_id}
            </code>
          </div>
          <div className="field">
            <label>secret_id (segredo — guarde agora)</label>
            <code className="secret-sm" style={{ wordBreak: 'break-all' }}>
              {credencial.secret_id}
            </code>
            <Botao
              variante="ghost"
              pequeno
              onClick={() => void navigator.clipboard?.writeText(credencial.secret_id)}
            >
              Copiar secret_id
            </Botao>
          </div>
        </div>

        <p className="sub" style={{ margin: 0 }}>
          O <b>role_id</b> identifica e o <b>secret_id</b> autentica. Separá-los
          é o que permite rotacionar a credencial sem alterar o código do robô —
          e faz um role_id vazado sozinho não valer nada.
        </p>

        <label className="row" style={{ gap: 8, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={confirmou}
            onChange={(e) => setConfirmou(e.target.checked)}
          />
          <span className="help">
            Guardei o secret_id e entendo que ele não poderá ser consultado
            novamente.
          </span>
        </label>

        <Botao onClick={aoFechar} disabled={!confirmou}>
          Concluir
        </Botao>
      </div>
    </Card>
  )
}

function DetalheAplicacao({
  nome,
  aoEmitir,
  aoErro,
  aoMudar,
}: {
  nome: string
  aoEmitir: (c: CredencialEmitida) => void
  aoErro: (mensagem: string) => void
  aoMudar: () => void
}) {
  const [rotulo, setRotulo] = useState('')

  const { data: credenciais } = useQuery({
    queryKey: ['credenciais-app', nome],
    queryFn: () =>
      request<Credencial[]>(`/aplicacoes/${encodeURIComponent(nome)}/credenciais`),
  })

  const { data: leases } = useQuery({
    queryKey: ['leases', nome],
    queryFn: () => request<Lease[]>(`/aplicacoes/${encodeURIComponent(nome)}/leases`),
  })

  const { data: consumo } = useQuery({
    queryKey: ['consumo', nome],
    queryFn: () => request<Consumo>(`/aplicacoes/${encodeURIComponent(nome)}/consumo`),
  })

  const emitir = useMutation({
    mutationFn: () =>
      request<CredencialEmitida>(
        `/aplicacoes/${encodeURIComponent(nome)}/credenciais`,
        { method: 'POST', body: { label: rotulo } },
      ),
    onSuccess: (dados) => {
      setRotulo('')
      aoEmitir(dados)
    },
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível emitir.'),
  })

  const revogar = useMutation({
    mutationFn: (id: string) =>
      request(`/aplicacoes/${encodeURIComponent(nome)}/credenciais/${id}/revogar`, {
        method: 'POST',
      }),
    onSuccess: aoMudar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível revogar.'),
  })

  const revogarLeases = useMutation({
    mutationFn: () =>
      request<{ revogados: number }>(
        `/aplicacoes/${encodeURIComponent(nome)}/leases/revogar-todos`,
        { method: 'POST' },
      ),
    onSuccess: aoMudar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível revogar.'),
  })

  const ativos = (leases ?? []).filter((l) => l.ativo)

  return (
    <>
      <Card titulo={`Credenciais de ${nome}`}>
        <div className="col" style={{ gap: 14 }}>
          <p className="sub" style={{ margin: 0 }}>
            Várias credenciais podem coexistir: é assim que se rotaciona sem
            parar o robô — emita a nova, atualize o robô, revogue a antiga.
          </p>

          <div className="row wrap" style={{ gap: 10, alignItems: 'flex-end' }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <Campo
                rotulo="Rótulo da nova credencial"
                value={rotulo}
                onChange={(e) => setRotulo(e.target.value)}
                ajuda="Opcional. Ex.: produção, rotação out/2026."
              />
            </div>
            <Botao pequeno onClick={() => emitir.mutate()} disabled={emitir.isPending}>
              {emitir.isPending ? 'Emitindo…' : 'Emitir credencial'}
            </Botao>
          </div>

          {!credenciais || credenciais.length === 0 ? (
            <Vazio titulo="Nenhuma credencial emitida" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Rótulo</th>
                    <th>Emitida</th>
                    <th>Último uso</th>
                    <th>Usos</th>
                    <th>Situação</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {credenciais.map((c) => (
                    <tr key={c.id}>
                      <td className="strong">{c.label || '— sem rótulo'}</td>
                      <td className="muted">
                        {formatarDataHora(c.created_at)}
                        <div className="help">por {c.created_by}</div>
                      </td>
                      <td className="muted">
                        {c.last_used_at ? formatarDataHora(c.last_used_at) : 'nunca'}
                      </td>
                      <td className="secret-sm">{c.usos}</td>
                      <td>
                        {c.revoked_at ? (
                          <Badge tom="muted">Revogada</Badge>
                        ) : c.valida ? (
                          <Badge tom="success">Válida</Badge>
                        ) : (
                          <Badge tom="warning">Expirada</Badge>
                        )}
                      </td>
                      <td>
                        {c.valida && (
                          <Botao
                            variante="ghost"
                            pequeno
                            onClick={() => revogar.mutate(c.id)}
                            disabled={revogar.isPending}
                          >
                            Revogar
                          </Botao>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      <Card
        titulo={`Acessos em uso (${ativos.length})`}
        acao={
          ativos.length > 0 ? (
            <Botao
              variante="danger"
              pequeno
              onClick={() => revogarLeases.mutate()}
              disabled={revogarLeases.isPending}
            >
              Encerrar todos agora
            </Botao>
          ) : undefined
        }
      >
        <div className="col" style={{ gap: 12 }}>
          <p className="sub" style={{ margin: 0 }}>
            Cada acesso carrega o escopo congelado no momento da autenticação.
            Alterar a política não amplia um acesso já concedido — o robô
            precisa autenticar de novo.
          </p>

          {!leases || leases.length === 0 ? (
            <Vazio titulo="Nenhum acesso concedido ainda" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Escopo</th>
                    <th>Concedido</th>
                    <th>Expira</th>
                    <th>Leituras</th>
                    <th>Situação</th>
                  </tr>
                </thead>
                <tbody>
                  {leases.map((l) => (
                    <tr key={l.id}>
                      <td>
                        <div className="col" style={{ gap: 3 }}>
                          {l.caminhos.map((c) => (
                            <code key={c} className="secret-sm">
                              {c}
                            </code>
                          ))}
                          <span className="help">{l.capacidades.join(', ')}</span>
                        </div>
                      </td>
                      <td className="muted">{formatarDataHora(l.created_at)}</td>
                      <td className="muted">{formatarDataHora(l.expires_at)}</td>
                      <td className="secret-sm">{l.leituras}</td>
                      <td>
                        {l.ativo ? (
                          <div className="col" style={{ gap: 3 }}>
                            <Badge tom="success">Em uso</Badge>
                            <span className="help">
                              {l.minutos_restantes} min restantes
                            </span>
                          </div>
                        ) : l.revoked_at ? (
                          <Badge tom="danger">Encerrado</Badge>
                        ) : (
                          <Badge tom="muted">Expirado</Badge>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>

      {consumo && <CartaoConsumo consumo={consumo} />}
    </>
  )
}

function CartaoConsumo({ consumo }: { consumo: Consumo }) {
  return (
    <Card titulo={`Consumo nos últimos ${consumo.dias} dias`}>
      <div className="col" style={{ gap: 16 }}>
        <p className="sub" style={{ margin: 0 }}>
          Derivado da trilha de auditoria, não de um contador próprio — duas
          fontes do mesmo número divergem na primeira falha de escrita.
        </p>

        {consumo.nunca_lidos.length > 0 && (
          <Alerta tom="warning">
            Este robô tem acesso a {consumo.nunca_lidos.join(', ')} e nunca leu
            nada ali. Permissão que ninguém usa é só superfície de ataque
            esperando um comprometimento — vale enxugar o escopo.
          </Alerta>
        )}

        {Object.keys(consumo.por_tipo ?? {}).length > 0 && (
          <div className="col" style={{ gap: 8 }}>
            <span className="help" style={{ fontWeight: 600 }}>
              O que este robô usa
            </span>
            <div className="row wrap" style={{ gap: 8 }}>
              {Object.entries(consumo.por_tipo).map(([tipo, quantos]) => (
                <Badge key={tipo} tom={TOM_DO_TIPO[tipo] ?? 'muted'}>
                  {quantos} {ROTULO_TIPO_SEGREDO[tipo] ?? tipo}
                  {quantos === 1 ? '' : 's'}
                </Badge>
              ))}
            </div>
            <span className="help">
              Conta caminhos distintos, não leituras: ler a mesma senha mil
              vezes continua sendo uma senha.
            </span>
          </div>
        )}

        <div className="col" style={{ gap: 8 }}>
          <span className="help" style={{ fontWeight: 600 }}>
            Mais lidos
          </span>
          {consumo.lidos.length === 0 ? (
            <span className="muted">Nenhuma leitura no período.</span>
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Caminho</th>
                    <th>Tipo</th>
                    <th>Leituras</th>
                    <th>Última</th>
                  </tr>
                </thead>
                <tbody>
                  {consumo.lidos.map((l) => (
                    <tr key={l.caminho}>
                      <td>
                        <code className="secret-sm">{l.caminho}</code>
                      </td>
                      <td>
                        <Badge tom={TOM_DO_TIPO[l.tipo] ?? 'muted'}>
                          {ROTULO_TIPO_SEGREDO[l.tipo] ?? l.tipo}
                        </Badge>
                      </td>
                      <td className="secret-sm strong">{l.leituras}</td>
                      <td className="muted">{formatarDataHora(l.ultima)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {consumo.negados.length > 0 && (
          <div className="col" style={{ gap: 8 }}>
            <span className="help" style={{ fontWeight: 600 }}>
              Tentou e não pôde
            </span>
            <span className="help">
              Caminho negado com frequência é escopo mal dimensionado — ou robô
              pedindo o que não deveria.
            </span>
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Caminho</th>
                    <th>Tentativas</th>
                    <th>Última</th>
                  </tr>
                </thead>
                <tbody>
                  {consumo.negados.map((l) => (
                    <tr key={l.caminho}>
                      <td>
                        <code className="secret-sm">{l.caminho}</code>
                      </td>
                      <td className="secret-sm strong">{l.leituras}</td>
                      <td className="muted">{formatarDataHora(l.ultima)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Card>
  )
}
