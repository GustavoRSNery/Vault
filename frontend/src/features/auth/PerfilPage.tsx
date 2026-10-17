import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card } from '@/shared/ui/components'
import { useAuth } from './AuthContext'

type StatusMfa = { mfa_enabled: boolean }
type IniciarMfa = { provisioning_uri: string }

/** Extrai o segredo da URI otpauth, para quem digita à mão no autenticador. */
function segredoDaUri(uri: string): string | null {
  try {
    return new URL(uri).searchParams.get('secret')
  } catch {
    return null
  }
}

export function PerfilPage() {
  const { usuario } = useAuth()
  const queryClient = useQueryClient()
  const [uri, setUri] = useState<string | null>(null)
  const [codigo, setCodigo] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const { data: status } = useQuery({
    queryKey: ['mfa', 'status'],
    queryFn: () => request<StatusMfa>('/mfa/status'),
  })

  const iniciar = useMutation({
    mutationFn: () => request<IniciarMfa>('/mfa/iniciar', { method: 'POST' }),
    onSuccess: (dados) => {
      setUri(dados.provisioning_uri)
      setErro(null)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível gerar o segredo.'),
  })

  const confirmar = useMutation({
    mutationFn: () =>
      request<StatusMfa>('/mfa/confirmar', { method: 'POST', body: { code: codigo } }),
    onSuccess: () => {
      setUri(null)
      setCodigo('')
      setErro(null)
      void queryClient.invalidateQueries({ queryKey: ['mfa', 'status'] })
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível confirmar o código.'),
  })

  const segredo = uri ? segredoDaUri(uri) : null

  return (
    <>
      <header>
        <h1 className="display">Perfil</h1>
        <p className="sub">Seus dados e a segurança da sua conta.</p>
      </header>

      <Card titulo="Dados da conta">
        <dl className="kv">
          <dt>Nome</dt>
          <dd>{usuario?.full_name}</dd>
          <dt>E-mail</dt>
          <dd>{usuario?.email}</dd>
        </dl>
      </Card>

      <Card
        titulo="Verificação em duas etapas"
        acao={
          status?.mfa_enabled ? (
            <Badge tom="success">Ativa</Badge>
          ) : (
            <Badge tom="warning">Pendente</Badge>
          )
        }
      >
        <div className="col" style={{ gap: 16 }}>
          {erro && <Alerta tom="danger">{erro}</Alerta>}

          {status?.mfa_enabled ? (
            <p className="sub" style={{ margin: 0 }}>
              Sua conta pede um código do aplicativo autenticador a cada acesso.
            </p>
          ) : !uri ? (
            <>
              <p className="sub" style={{ margin: 0 }}>
                Um segundo fator protege seus cofres mesmo que a senha vaze.
              </p>
              <div>
                <Botao onClick={() => iniciar.mutate()} disabled={iniciar.isPending}>
                  {iniciar.isPending ? 'Gerando…' : 'Ativar segundo fator'}
                </Botao>
              </div>
            </>
          ) : (
            <>
              <p className="sub" style={{ margin: 0 }}>
                Cadastre a chave abaixo no seu aplicativo autenticador e informe o
                código de 6 dígitos para concluir.
              </p>

              {/* A chave aparece uma única vez e não é persistida em lugar
                  nenhum do navegador: some ao sair desta tela. */}
              {segredo && (
                <div className="secret-box">
                  <span className="secret" style={{ wordBreak: 'break-all' }}>
                    {segredo}
                  </span>
                </div>
              )}

              <Campo
                rotulo="Código do aplicativo"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
                inputMode="numeric"
                autoComplete="one-time-code"
                ajuda="6 dígitos, trocados a cada 30 segundos."
              />

              <div className="row" style={{ gap: 10 }}>
                <Botao
                  onClick={() => confirmar.mutate()}
                  disabled={codigo.length !== 6 || confirmar.isPending}
                >
                  {confirmar.isPending ? 'Confirmando…' : 'Confirmar e ativar'}
                </Botao>
                <Botao
                  variante="secondary"
                  onClick={() => {
                    setUri(null)
                    setCodigo('')
                    setErro(null)
                  }}
                >
                  Cancelar
                </Botao>
              </div>
            </>
          )}
        </div>
      </Card>
    </>
  )
}
