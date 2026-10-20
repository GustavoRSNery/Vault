import { useMutation, useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Botao, Campo, Carregando } from '@/shared/ui/components'

type ConviteInfo = {
  email: string
  tipo: string
  nome_sugerido: string
  valido: boolean
}

/**
 * Aceite de convite e redefinição por link.
 *
 * A mesma tela serve aos dois porque o fluxo é o mesmo: o token é a prova,
 * e o que muda é só o que se pede (nome + senha, ou só a senha).
 *
 * Link inválido e link expirado mostram a mesma mensagem — distinguir
 * ajudaria quem está testando tokens.
 */
export function ConvitePage({ modo }: { modo: 'convite' | 'redefinir' }) {
  const { token = '' } = useParams<{ token: string }>()
  const [nome, setNome] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [pronto, setPronto] = useState(false)

  const { data: info, isLoading } = useQuery({
    queryKey: ['convite', token],
    queryFn: () => request<ConviteInfo>(`/convites/${encodeURIComponent(token)}/info`),
    enabled: modo === 'convite',
    retry: false,
  })

  useEffect(() => {
    if (info?.nome_sugerido) setNome(info.nome_sugerido)
  }, [info])

  const aceitar = useMutation({
    mutationFn: () =>
      modo === 'convite'
        ? request('/convites/aceitar', {
            method: 'POST',
            body: { token, nome, senha },
          })
        : request('/recuperar/link', {
            method: 'POST',
            body: { token, nova_senha: senha },
          }),
    onSuccess: () => {
      setErro(null)
      setPronto(true)
    },
    onError: (e) =>
      setErro(
        e instanceof ApiError
          ? e.message
          : 'Não foi possível concluir. O link pode ter expirado.',
      ),
  })

  const senhasConferem = senha.length >= 12 && senha === confirmacao
  const faltaNome = modo === 'convite' && !nome.trim()

  if (modo === 'convite' && isLoading) {
    return (
      <div className="auth-wrap">
        <div className="auth-card">
          <Carregando texto="Verificando o convite…" />
        </div>
      </div>
    )
  }

  const linkInvalido = modo === 'convite' && info && !info.valido

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="logo" style={{ marginBottom: 20 }}>
          <span className="mark" aria-hidden="true">
            <strong>V</strong>
          </span>
          <span>
            <b>Vault</b>
            <small>de senhas</small>
          </span>
        </div>

        {pronto ? (
          <div className="col" style={{ gap: 14 }}>
            <h1 className="title">
              {modo === 'convite' ? 'Conta criada' : 'Senha redefinida'}
            </h1>
            <Alerta tom="warning">
              {modo === 'convite'
                ? 'Entre com seu e-mail e a senha que você acabou de definir. Ative o segundo fator no Perfil — com ele, você recupera a senha sozinho se precisar.'
                : 'Entre com a nova senha.'}
            </Alerta>
            <Link to="/">
              <Botao>Ir para o login</Botao>
            </Link>
          </div>
        ) : linkInvalido ? (
          <div className="col" style={{ gap: 14 }}>
            <h1 className="title">Link indisponível</h1>
            <Alerta tom="danger">
              Este link não é válido, já foi usado ou expirou. Peça um novo a
              quem convidou você.
            </Alerta>
            <Link to="/">
              <Botao variante="secondary">Voltar ao login</Botao>
            </Link>
          </div>
        ) : (
          <div className="col" style={{ gap: 14 }}>
            <h1 className="title">
              {modo === 'convite' ? 'Criar sua conta' : 'Definir nova senha'}
            </h1>

            {modo === 'convite' && info?.email && (
              <p className="sub" style={{ margin: 0 }}>
                Convite para <b>{info.email}</b>.
              </p>
            )}

            {erro && <Alerta tom="danger">{erro}</Alerta>}

            {modo === 'convite' && (
              <Campo
                rotulo="Seu nome"
                value={nome}
                onChange={(e) => setNome(e.target.value)}
                autoFocus
              />
            )}

            <Campo
              rotulo={modo === 'convite' ? 'Senha' : 'Nova senha'}
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              ajuda="Ao menos 12 caracteres. Use uma frase que só você saiba."
              autoFocus={modo === 'redefinir'}
            />
            <Campo
              rotulo="Repita a senha"
              type="password"
              value={confirmacao}
              onChange={(e) => setConfirmacao(e.target.value)}
              erro={
                confirmacao && !senhasConferem
                  ? 'As senhas não conferem ou são curtas demais.'
                  : undefined
              }
            />

            <Botao
              onClick={() => aceitar.mutate()}
              disabled={!senhasConferem || faltaNome || aceitar.isPending}
            >
              {aceitar.isPending
                ? 'Concluindo…'
                : modo === 'convite'
                  ? 'Criar conta'
                  : 'Redefinir senha'}
            </Botao>
          </div>
        )}
      </div>
    </div>
  )
}
