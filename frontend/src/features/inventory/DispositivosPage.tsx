import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'
import { PainelAcessoRemoto, type Acesso } from './AcessoRemoto'

type Dispositivo = {
  id: string
  name: string
  display_name: string
  kind: string
  address: string
  tags: string[]
  description: string
  acessos: Acesso[]
  is_active: boolean
  credenciais: number
  created_at: string
}

const TIPOS = [
  { valor: 'servidor', rotulo: 'Servidor' },
  { valor: 'roteador', rotulo: 'Roteador' },
  { valor: 'switch', rotulo: 'Switch' },
  { valor: 'firewall', rotulo: 'Firewall' },
  { valor: 'banco_de_dados', rotulo: 'Banco de dados' },
  { valor: 'aplicacao', rotulo: 'Aplicação' },
  { valor: 'outro', rotulo: 'Outro' },
]

const ROTULO_TIPO: Record<string, string> = Object.fromEntries(
  TIPOS.map((t) => [t.valor, t.rotulo]),
)

export function DispositivosPage() {
  const [criando, setCriando] = useState(false)
  const [filtro, setFiltro] = useState('')
  const queryClient = useQueryClient()

  const { data: dispositivos, isLoading, error } = useQuery({
    queryKey: ['dispositivos'],
    queryFn: () => request<Dispositivo[]>('/dispositivos'),
  })

  if (isLoading) return <Carregando texto="Carregando dispositivos…" />
  if (error) {
    return (
      <Vazio
        titulo="Nenhum dispositivo acessível"
        descricao="Você pode não ter permissão no caminho de dispositivos."
      />
    )
  }

  const termo = filtro.trim().toLowerCase()
  const visiveis = (dispositivos ?? []).filter(
    (d) =>
      termo === '' ||
      d.display_name.toLowerCase().includes(termo) ||
      d.address.toLowerCase().includes(termo) ||
      d.tags.some((t) => t.includes(termo)),
  )

  return (
    <>
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Dispositivos</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {dispositivos?.length ?? 0} equipamento
              {(dispositivos?.length ?? 0) === 1 ? '' : 's'}. O inventário diz de
              quem é cada credencial — sem isso, senha guardada é senha órfã.
            </p>
          </div>
          <Botao pequeno onClick={() => setCriando(true)}>
            Novo dispositivo
          </Botao>
        </div>
      </header>

      {criando && (
        <NovoDispositivo
          aoFechar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            void queryClient.invalidateQueries({ queryKey: ['dispositivos'] })
          }}
        />
      )}

      <Card>
        <div className="col" style={{ gap: 14 }}>
          <Campo
            rotulo="Buscar"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            ajuda="Por nome, endereço ou etiqueta."
            placeholder="firewall, 10.0.0.1, produção…"
          />

          {visiveis.length === 0 ? (
            <Vazio
              titulo={
                termo === ''
                  ? 'Nenhum dispositivo cadastrado'
                  : 'Nada encontrado para esta busca'
              }
            />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Dispositivo</th>
                    <th>Tipo</th>
                    <th>Endereço</th>
                    <th>Etiquetas</th>
                    <th>Credenciais</th>
                    <th>Acesso</th>
                    <th>Desde</th>
                  </tr>
                </thead>
                <tbody>
                  {visiveis.map((d) => (
                    <LinhaDispositivo key={d.id} dispositivo={d} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </Card>
    </>
  )
}

function LinhaDispositivo({ dispositivo: d }: { dispositivo: Dispositivo }) {
  const [verAcessos, setVerAcessos] = useState(false)
  const acessos = d.acessos ?? []

  return (
    <>
                    <tr>
                      <td className="strong">
                        {d.display_name}
                        {d.description && <div className="help">{d.description}</div>}
                        {!d.is_active && (
                          <div>
                            <Badge tom="muted">Inativo</Badge>
                          </div>
                        )}
                      </td>
                      <td className="muted">{ROTULO_TIPO[d.kind] ?? d.kind}</td>
                      <td className="secret-sm muted">{d.address || '—'}</td>
                      <td>
                        <div className="row wrap" style={{ gap: 6 }}>
                          {d.tags.length === 0 ? (
                            <span className="muted">—</span>
                          ) : (
                            d.tags.map((t) => (
                              <Badge key={t} tom="muted">
                                {t}
                              </Badge>
                            ))
                          )}
                        </div>
                      </td>
                      <td className="secret-sm">{d.credenciais}</td>
                      <td>
                        <Botao
                          pequeno
                          variante={acessos.length > 0 ? 'secondary' : 'ghost'}
                          onClick={() => setVerAcessos(!verAcessos)}
                        >
                          {verAcessos
                            ? 'Fechar'
                            : acessos.length === 0
                              ? 'Cadastrar'
                              : `Acessar (${acessos.length})`}
                        </Botao>
                      </td>
                      <td className="muted">{formatarDataHora(d.created_at)}</td>
                    </tr>

      {verAcessos && (
        <tr>
          <td colSpan={7}>
            <PainelAcessoRemoto dispositivo={d.name} acessos={acessos} />
          </td>
        </tr>
      )}
    </>
  )
}

function NovoDispositivo({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void
  aoCriar: () => void
}) {
  const [nome, setNome] = useState('')
  const [tipo, setTipo] = useState('servidor')
  const [endereco, setEndereco] = useState('')
  const [etiquetas, setEtiquetas] = useState('')
  const [descricao, setDescricao] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  /** Deriva o identificador do nome visível: "Firewall Matriz" → firewall-matriz. */
  const identificador = nome
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64)

  const criar = useMutation({
    mutationFn: () =>
      request<Dispositivo>('/dispositivos', {
        method: 'POST',
        body: {
          name: identificador,
          display_name: nome,
          kind: tipo,
          address: endereco,
          tags: etiquetas
            .split(',')
            .map((t) => t.trim())
            .filter(Boolean),
          description: descricao,
        },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  return (
    <Card titulo="Novo dispositivo">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda={
            identificador
              ? `Identificador: ${identificador}`
              : 'Ex.: Firewall Matriz.'
          }
          autoFocus
        />

        <div className="field">
          <label htmlFor="tipo">Tipo</label>
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
          rotulo="Endereço"
          value={endereco}
          onChange={(e) => setEndereco(e.target.value)}
          ajuda="IP ou host. Opcional."
        />
        <Campo
          rotulo="Etiquetas"
          value={etiquetas}
          onChange={(e) => setEtiquetas(e.target.value)}
          ajuda="Separadas por vírgula. Ex.: produção, crítico."
        />
        <Campo
          rotulo="Descrição"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          ajuda="Opcional."
        />

        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => criar.mutate()}
            disabled={identificador === '' || criar.isPending}
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
