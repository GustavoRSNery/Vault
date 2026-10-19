import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'

type Regra = {
  path: string
  capabilities: string[]
  effect: string
}

type Politica = {
  id: string
  name: string
  description: string
  rules: Regra[]
  roles: string[]
}

type Simulacao = {
  permitido: boolean
  motivo: string
}

const CAPACIDADES = [
  { valor: 'read', rotulo: 'read', ajuda: 'ver metadados' },
  { valor: 'reveal', rotulo: 'reveal', ajuda: 'revelar o valor' },
  { valor: 'list', rotulo: 'list', ajuda: 'listar' },
  { valor: 'create', rotulo: 'create', ajuda: 'criar' },
  { valor: 'update', rotulo: 'update', ajuda: 'alterar' },
  { valor: 'delete', rotulo: 'delete', ajuda: 'excluir' },
  { valor: 'approve', rotulo: 'approve', ajuda: 'aprovar pedidos' },
  { valor: 'admin', rotulo: 'admin', ajuda: 'administrar' },
]

export function PoliticasPage() {
  const [editando, setEditando] = useState<string | null>(null)

  const { data: politicas, isLoading, error } = useQuery({
    queryKey: ['admin', 'politicas'],
    queryFn: () => request<Politica[]>('/admin/politicas'),
  })

  if (isLoading) return <Carregando texto="Carregando políticas…" />
  if (error) {
    return (
      <Vazio
        titulo="Área restrita"
        descricao="Apenas administradores acessam as políticas de acesso."
      />
    )
  }

  const emEdicao = politicas?.find((p) => p.name === editando)

  return (
    <>
      <header>
        <h1 className="display">Políticas de acesso</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          {politicas?.length ?? 0} polític{(politicas?.length ?? 0) === 1 ? 'a' : 'as'}.
          Uma regra <b>deny</b> derruba qualquer <b>allow</b>, por mais específico
          que seja — é o que torna a revogação confiável.
        </p>
      </header>

      {emEdicao ? (
        <EditorDePolitica
          politica={emEdicao}
          aoFechar={() => setEditando(null)}
        />
      ) : (
        <Card>
          {!politicas || politicas.length === 0 ? (
            <Vazio titulo="Nenhuma política cadastrada" />
          ) : (
            <div className="tbl-wrap">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Política</th>
                    <th>Regras</th>
                    <th>Papéis</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {politicas.map((p) => (
                    <tr key={p.id}>
                      <td className="strong">
                        {p.name}
                        {p.description && <div className="help">{p.description}</div>}
                      </td>
                      <td>
                        <div className="col" style={{ gap: 4 }}>
                          {p.rules.map((r, i) => (
                            <LinhaRegra key={`${r.path}-${i}`} regra={r} />
                          ))}
                        </div>
                      </td>
                      <td>
                        {p.roles.length === 0 ? (
                          <span className="muted">— nenhum</span>
                        ) : (
                          <div className="row wrap" style={{ gap: 6 }}>
                            {p.roles.map((papel) => (
                              <Badge key={papel} tom="muted">
                                {papel}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>
                        <Botao
                          variante="secondary"
                          pequeno
                          onClick={() => setEditando(p.name)}
                        >
                          Editar
                        </Botao>
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
  )
}

function LinhaRegra({ regra }: { regra: Regra }) {
  const negacao = regra.effect === 'deny'
  return (
    <div className="row" style={{ gap: 8, alignItems: 'center' }}>
      <Badge tom={negacao ? 'danger' : 'success'}>{negacao ? 'deny' : 'allow'}</Badge>
      <code className="secret-sm">{regra.path}</code>
      <span className="help">{regra.capabilities.join(', ')}</span>
    </div>
  )
}

function EditorDePolitica({
  politica,
  aoFechar,
}: {
  politica: Politica
  aoFechar: () => void
}) {
  const queryClient = useQueryClient()
  const [regras, setRegras] = useState<Regra[]>(politica.rules)
  const [erro, setErro] = useState<string | null>(null)

  const salvar = useMutation({
    mutationFn: () =>
      request<Politica>(`/admin/politicas/${encodeURIComponent(politica.name)}/regras`, {
        method: 'PUT',
        body: {
          rules: regras.map((r) => ({
            path: r.path,
            capabilities: r.capabilities,
            effect: r.effect,
          })),
        },
      }),
    onSuccess: () => {
      setErro(null)
      void queryClient.invalidateQueries({ queryKey: ['admin', 'politicas'] })
      // Mudar política muda o que o próprio usuário vê: o cache de cofres e
      // segredos ficou obsoleto no mesmo instante.
      void queryClient.invalidateQueries({ queryKey: ['cofres'] })
      aoFechar()
    },
    onError: (e) =>
      setErro(
        e instanceof ApiError ? e.message : 'Não foi possível salvar a política.',
      ),
  })

  const alterarRegra = (indice: number, mudanca: Partial<Regra>) =>
    setRegras((atual) =>
      atual.map((r, i) => (i === indice ? { ...r, ...mudanca } : r)),
    )

  const alternarCapacidade = (indice: number, capacidade: string) =>
    setRegras((atual) =>
      atual.map((r, i) => {
        if (i !== indice) return r
        const tem = r.capabilities.includes(capacidade)
        return {
          ...r,
          capabilities: tem
            ? r.capabilities.filter((c) => c !== capacidade)
            : [...r.capabilities, capacidade],
        }
      }),
    )

  const adicionar = () =>
    setRegras((atual) => [
      ...atual,
      { path: '', capabilities: ['read'], effect: 'allow' },
    ])

  const remover = (indice: number) =>
    setRegras((atual) => atual.filter((_, i) => i !== indice))

  const invalida =
    regras.length === 0 ||
    regras.some((r) => r.path.trim() === '' || r.capabilities.length === 0)

  return (
    <>
      <Card
        titulo={`Editando ${politica.name}`}
        acao={
          <Botao variante="ghost" pequeno onClick={aoFechar}>
            Voltar
          </Botao>
        }
      >
        <div className="col" style={{ gap: 18 }}>
          {erro && <Alerta tom="danger">{erro}</Alerta>}

          {politica.roles.length > 0 && (
            <Alerta tom="warning">
              Esta política está em {politica.roles.join(', ')}. Qualquer mudança
              aqui vale imediatamente para quem tem esse papel.
            </Alerta>
          )}

          {regras.map((regra, indice) => (
            <div
              key={indice}
              className="col"
              style={{
                gap: 10,
                padding: 14,
                borderRadius: 10,
                background: 'var(--surface-2, rgba(0,0,0,.03))',
              }}
            >
              <div className="row between wrap" style={{ gap: 10 }}>
                <div className="row" style={{ gap: 8 }}>
                  <Botao
                    variante={regra.effect === 'allow' ? 'primary' : 'secondary'}
                    pequeno
                    onClick={() => alterarRegra(indice, { effect: 'allow' })}
                  >
                    allow
                  </Botao>
                  <Botao
                    variante={regra.effect === 'deny' ? 'danger' : 'secondary'}
                    pequeno
                    onClick={() => alterarRegra(indice, { effect: 'deny' })}
                  >
                    deny
                  </Botao>
                </div>
                <Botao variante="ghost" pequeno onClick={() => remover(indice)}>
                  Remover regra
                </Botao>
              </div>

              <Campo
                rotulo="Caminho"
                value={regra.path}
                onChange={(e) => alterarRegra(indice, { path: e.target.value })}
                ajuda="Casa por segmento. cofres/* cobre cofres/contabil, mas cofres/conta não cobre cofres/contabil."
              />

              <div className="col" style={{ gap: 6 }}>
                <label className="help" style={{ fontWeight: 600 }}>
                  Capacidades
                </label>
                <div className="row wrap" style={{ gap: 8 }}>
                  {CAPACIDADES.map((c) => (
                    <label
                      key={c.valor}
                      className="row"
                      style={{ gap: 5, cursor: 'pointer' }}
                      title={c.ajuda}
                    >
                      <input
                        type="checkbox"
                        checked={regra.capabilities.includes(c.valor)}
                        onChange={() => alternarCapacidade(indice, c.valor)}
                      />
                      <code className="secret-sm">{c.rotulo}</code>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          ))}

          <div className="row" style={{ gap: 10 }}>
            <Botao variante="secondary" pequeno onClick={adicionar}>
              Adicionar regra
            </Botao>
          </div>

          {invalida && (
            <Alerta tom="warning">
              Toda regra precisa de um caminho e de ao menos uma capacidade. Uma
              política sem regra não é "sem acesso" — é política inválida.
            </Alerta>
          )}

          <div className="row" style={{ gap: 10 }}>
            <Botao
              onClick={() => salvar.mutate()}
              disabled={invalida || salvar.isPending}
            >
              {salvar.isPending ? 'Salvando…' : 'Salvar política'}
            </Botao>
            <Botao variante="secondary" onClick={aoFechar}>
              Cancelar
            </Botao>
          </div>
        </div>
      </Card>

      <Simulador regras={regras} />
    </>
  )
}

function Simulador({ regras }: { regras: Regra[] }) {
  const [caminho, setCaminho] = useState('cofres/contabil/segredos/token-sefaz')
  const [capacidade, setCapacidade] = useState('reveal')
  const [resultado, setResultado] = useState<Simulacao | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const simular = useMutation({
    mutationFn: () =>
      request<Simulacao>('/admin/politicas/simular', {
        method: 'POST',
        body: {
          path: caminho,
          capability: capacidade,
          rules: regras.map((r) => ({
            path: r.path,
            capabilities: r.capabilities,
            effect: r.effect,
          })),
        },
      }),
    onSuccess: (dados) => {
      setErro(null)
      setResultado(dados)
    },
    onError: (e) => {
      setResultado(null)
      setErro(e instanceof ApiError ? e.message : 'Não foi possível simular.')
    },
  })

  const podeSimular =
    caminho.trim() !== '' &&
    regras.length > 0 &&
    regras.every((r) => r.path.trim() !== '' && r.capabilities.length > 0)

  return (
    <Card titulo="Simular o efeito">
      <div className="col" style={{ gap: 14 }}>
        <p className="sub" style={{ margin: 0 }}>
          Responde, sem gravar nada, a única pergunta que importa antes de salvar:
          este caminho fica permitido ou negado — e por causa de qual regra? Roda
          no mesmo motor que decide em produção.
        </p>

        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Campo
          rotulo="Caminho a testar"
          value={caminho}
          onChange={(e) => setCaminho(e.target.value)}
        />

        <div className="field">
          <label htmlFor="sim-cap">Capacidade</label>
          <select
            id="sim-cap"
            className="input"
            value={capacidade}
            onChange={(e) => setCapacidade(e.target.value)}
          >
            {CAPACIDADES.map((c) => (
              <option key={c.valor} value={c.valor}>
                {c.rotulo} — {c.ajuda}
              </option>
            ))}
          </select>
        </div>

        <div className="row" style={{ gap: 10 }}>
          <Botao
            variante="secondary"
            onClick={() => simular.mutate()}
            disabled={!podeSimular || simular.isPending}
          >
            {simular.isPending ? 'Simulando…' : 'Simular'}
          </Botao>
        </div>

        {resultado && (
          <div
            className="row"
            style={{
              gap: 12,
              alignItems: 'center',
              padding: 14,
              borderRadius: 10,
              background: resultado.permitido
                ? 'var(--success-soft)'
                : 'var(--danger-soft)',
            }}
          >
            <Badge tom={resultado.permitido ? 'success' : 'danger'}>
              {resultado.permitido ? 'Permitido' : 'Negado'}
            </Badge>
            <span style={{ fontSize: 13.5, fontWeight: 500 }}>{resultado.motivo}</span>
          </div>
        )}
      </div>
    </Card>
  )
}
