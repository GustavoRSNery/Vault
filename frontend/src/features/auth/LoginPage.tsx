import { useState, type FormEvent } from 'react'
import { ApiError } from '@/shared/api/client'
import { Alerta, Botao, Campo } from '@/shared/ui/components'
import { useAuth } from './AuthContext'

export function LoginPage() {
  const { entrar, carregando } = useAuth()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [codigo, setCodigo] = useState('')
  const [pedindoMfa, setPedindoMfa] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  async function aoEnviar(evento: FormEvent) {
    evento.preventDefault()
    setErro(null)
    try {
      const resultado = await entrar(email, senha, pedindoMfa ? codigo : undefined)
      if (resultado.tipo === 'mfa_necessario') {
        setPedindoMfa(true)
      }
      // Autenticado: o roteador troca a tela sozinho ao ver o usuário.
    } catch (e) {
      setErro(e instanceof ApiError ? e.message : 'Não foi possível entrar.')
    }
  }

  return (
    <div className="auth-wrap">
      <form className="auth-card" onSubmit={aoEnviar}>
        <div>
          <h1 className="display" style={{ fontSize: 22 }}>
            Vault de Senhas
          </h1>
          <p className="sub" style={{ margin: '6px 0 0' }}>
            {pedindoMfa
              ? 'Informe o código do seu aplicativo autenticador.'
              : 'Entre para acessar seus cofres.'}
          </p>
        </div>

        {erro && <Alerta tom="danger">{erro}</Alerta>}

        {!pedindoMfa ? (
          <>
            <Campo
              rotulo="E-mail"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              autoFocus
            />
            <Campo
              rotulo="Senha"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              autoComplete="current-password"
              required
            />
          </>
        ) : (
          <Campo
            rotulo="Código de verificação"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
            inputMode="numeric"
            autoComplete="one-time-code"
            ajuda="6 dígitos, trocados a cada 30 segundos."
            required
            autoFocus
          />
        )}

        <Botao type="submit" disabled={carregando}>
          {carregando ? 'Entrando…' : pedindoMfa ? 'Confirmar' : 'Entrar'}
        </Botao>

        {pedindoMfa && (
          <Botao
            type="button"
            variante="ghost"
            onClick={() => {
              setPedindoMfa(false)
              setCodigo('')
              setErro(null)
            }}
          >
            Voltar
          </Botao>
        )}
      </form>
    </div>
  )
}
