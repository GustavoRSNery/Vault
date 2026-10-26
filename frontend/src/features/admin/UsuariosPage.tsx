import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Card, Carregando, Vazio } from '@/shared/ui/components'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'
import { useAuth } from '@/features/auth/AuthContext'

type Usuario = {
  id: string
  email: string
  full_name: string
  is_active: boolean
  mfa_enabled: boolean
  roles: string[]
  created_at: string
}

type Papel = {
  id: string
  name: string
  description: string
  policies: string[]
  users: number
}

export function UsuariosPage() {
  const queryClient = useQueryClient()
  const { usuario: eu } = useAuth()
  const [erro, setErro] = useState<string | null>(null)
  const [editandoPapeis, setEditandoPapeis] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['admin', 'usuarios'] })
    void queryClient.invalidateQueries({ queryKey: ['admin', 'papeis'] })
  }

  const { data: usuarios, isLoading, error } = useQuery({
    queryKey: ['admin', 'usuarios'],
    queryFn: () => request<Usuario[]>('/admin/usuarios'),
  })

  const { data: papeis } = useQuery({
    queryKey: ['admin', 'papeis'],
    queryFn: () => request<Papel[]>('/admin/papeis'),
  })

  const acao = useMutation({
    mutationFn: ({ id, rota }: { id: string; rota: string }) =>
      request<Usuario>(`/admin/usuarios/${id}/${rota}`, { method: 'POST' }),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível concluir.'),
  })

  if (isLoading) return <Carregando texto="Carregando usuários…" />
  if (error) {
    return (
      <Vazio
        titulo="Área restrita"
        descricao="Apenas administradores acessam a gestão de pessoas."
      />
    )
  }

  return (
    <>
      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <h1 className="display">Pessoas</h1>
          <div className="row wrap" style={{ gap: 8 }}>
            <TutorialApi
              titulo="Pessoas"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/admin/usuarios',
                  descricao:
                    'As contas, com papéis e se estão ativas.',
                },
                {
                  metodo: 'GET',
                  caminho: '/admin/papeis',
                  descricao:
                    'Os papéis existentes e as políticas de cada um.',
                },
              ]}
              observacao="Rotas de administração: cada uma confere a permissão de novo no servidor."
            />
          </div>
        </div>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          {usuarios?.length ?? 0} conta{(usuarios?.length ?? 0) === 1 ? '' : 's'}.
          Desativar uma conta derruba o acesso na chamada seguinte, mesmo com
          token ainda válido.
        </p>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}

      <Card>
        {!usuarios || usuarios.length === 0 ? (
          <Vazio titulo="Nenhuma conta cadastrada" />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Pessoa</th>
                  <th>Papéis</th>
                  <th>MFA</th>
                  <th>Situação</th>
                  <th>Desde</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {usuarios.map((u) => {
                  const souEu = u.email === eu?.email
                  return (
                    <tr key={u.id}>
                      <td className="strong">
                        {u.full_name}
                        <div className="help">{u.email}</div>
                      </td>
                      <td>
                        {u.roles.length === 0 ? (
                          <span className="muted">— nenhum</span>
                        ) : (
                          <div className="row wrap" style={{ gap: 6 }}>
                            {u.roles.map((papel) => (
                              <Badge key={papel} tom="muted">
                                {papel}
                              </Badge>
                            ))}
                          </div>
                        )}
                      </td>
                      <td>
                        {u.mfa_enabled ? (
                          <Badge tom="success">Ativo</Badge>
                        ) : (
                          <Badge tom="warning">Sem MFA</Badge>
                        )}
                      </td>
                      <td>
                        {u.is_active ? (
                          <Badge tom="success">Ativa</Badge>
                        ) : (
                          <Badge tom="danger">Desativada</Badge>
                        )}
                      </td>
                      <td className="muted">{formatarDataHora(u.created_at)}</td>
                      <td>
                        <div className="row wrap" style={{ gap: 6 }}>
                          <Botao
                            variante="ghost"
                            pequeno
                            onClick={() =>
                              setEditandoPapeis(
                                editandoPapeis === u.id ? null : u.id,
                              )
                            }
                          >
                            Papéis
                          </Botao>
                          {u.mfa_enabled && (
                            <Botao
                              variante="ghost"
                              pequeno
                              onClick={() =>
                                acao.mutate({ id: u.id, rota: 'reiniciar-mfa' })
                              }
                              disabled={acao.isPending}
                            >
                              Reiniciar MFA
                            </Botao>
                          )}
                          {u.is_active ? (
                            <Botao
                              variante="ghost"
                              pequeno
                              onClick={() =>
                                acao.mutate({ id: u.id, rota: 'desativar' })
                              }
                              disabled={acao.isPending || souEu}
                              title={
                                souEu
                                  ? 'Você não pode desativar a própria conta.'
                                  : undefined
                              }
                            >
                              Desativar
                            </Botao>
                          ) : (
                            <Botao
                              variante="secondary"
                              pequeno
                              onClick={() => acao.mutate({ id: u.id, rota: 'ativar' })}
                              disabled={acao.isPending}
                            >
                              Ativar
                            </Botao>
                          )}
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

      {editandoPapeis && usuarios && papeis && (
        <EditorDePapeis
          usuario={usuarios.find((u) => u.id === editandoPapeis)!}
          papeis={papeis}
          aoFechar={() => setEditandoPapeis(null)}
          aoSalvar={() => {
            setEditandoPapeis(null)
            invalidar()
          }}
        />
      )}

      <Card titulo="Papéis">
        <p className="sub" style={{ marginTop: 0 }}>
          Papel agrupa políticas. Pessoas recebem papéis — nunca regras soltas —
          para que revogar um acesso seja uma operação só.
        </p>
        {!papeis || papeis.length === 0 ? (
          <Vazio titulo="Nenhum papel cadastrado" />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Papel</th>
                  <th>Políticas</th>
                  <th>Pessoas</th>
                </tr>
              </thead>
              <tbody>
                {papeis.map((p) => (
                  <tr key={p.id}>
                    <td className="strong">{p.name}</td>
                    <td>
                      <div className="row wrap" style={{ gap: 6 }}>
                        {p.policies.map((pol) => (
                          <Badge key={pol} tom="brand">
                            {pol}
                          </Badge>
                        ))}
                      </div>
                    </td>
                    <td className="secret-sm">{p.users}</td>
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

function EditorDePapeis({
  usuario,
  papeis,
  aoFechar,
  aoSalvar,
}: {
  usuario: Usuario
  papeis: Papel[]
  aoFechar: () => void
  aoSalvar: () => void
}) {
  const [selecionados, setSelecionados] = useState<string[]>(usuario.roles)
  const [erro, setErro] = useState<string | null>(null)

  const salvar = useMutation({
    mutationFn: () =>
      request<Usuario>(`/admin/usuarios/${usuario.id}/papeis`, {
        method: 'PUT',
        body: { roles: selecionados },
      }),
    onSuccess: aoSalvar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.'),
  })

  const alternar = (nome: string) =>
    setSelecionados((atual) =>
      atual.includes(nome) ? atual.filter((n) => n !== nome) : [...atual, nome],
    )

  const removidos = usuario.roles.filter((r) => !selecionados.includes(r))

  return (
    <Card titulo={`Papéis de ${usuario.full_name}`}>
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <div className="col" style={{ gap: 8 }}>
          {papeis.map((papel) => (
            <label
              key={papel.id}
              className="row"
              style={{ gap: 10, cursor: 'pointer', alignItems: 'flex-start' }}
            >
              <input
                type="checkbox"
                checked={selecionados.includes(papel.name)}
                onChange={() => alternar(papel.name)}
              />
              <span>
                <b>{papel.name}</b>
                <div className="help">
                  {papel.policies.length > 0
                    ? `Políticas: ${papel.policies.join(', ')}`
                    : 'Sem política vinculada.'}
                </div>
              </span>
            </label>
          ))}
        </div>

        {removidos.length > 0 && (
          <Alerta tom="warning">
            Ao salvar, {usuario.full_name} perde {removidos.join(', ')}. O acesso
            que vinha desse papel fecha imediatamente.
          </Alerta>
        )}

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => salvar.mutate()} disabled={salvar.isPending}>
            {salvar.isPending ? 'Salvando…' : 'Salvar papéis'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
