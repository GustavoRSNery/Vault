import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { request, setTokens, setUnauthenticatedHandler } from '@/shared/api/client'

export type Usuario = {
  id: string
  email: string
  full_name: string
  mfa_enabled: boolean
}

type LoginResponse = {
  mfa_required: boolean
  tokens: {
    access_token: string
    refresh_token: string
    token_type: string
    expires_in: number
  } | null
}

/** O login pode terminar em sessão aberta ou em desafio de MFA. */
export type ResultadoLogin = { tipo: 'autenticado' } | { tipo: 'mfa_necessario' }

type AuthContextValue = {
  usuario: Usuario | null
  carregando: boolean
  entrar: (email: string, senha: string, codigo?: string) => Promise<ResultadoLogin>
  sair: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(false)

  const sair = useCallback(() => {
    setTokens(null)
    setUsuario(null)
  }, [])

  useEffect(() => {
    // Quando o cliente HTTP esgota o refresh, a aplicação volta ao login.
    setUnauthenticatedHandler(() => setUsuario(null))
  }, [])

  const entrar = useCallback(
    async (email: string, senha: string, codigo?: string): Promise<ResultadoLogin> => {
      setCarregando(true)
      try {
        const resposta = await request<LoginResponse>('/auth/login', {
          method: 'POST',
          body: { email, password: senha, totp_code: codigo ?? null },
        })

        if (resposta.mfa_required || !resposta.tokens) {
          return { tipo: 'mfa_necessario' }
        }

        setTokens(resposta.tokens)
        setUsuario(await request<Usuario>('/auth/me'))
        return { tipo: 'autenticado' }
      } finally {
        setCarregando(false)
      }
    },
    [],
  )

  const valor = useMemo(
    () => ({ usuario, carregando, entrar, sair }),
    [usuario, carregando, entrar, sair],
  )

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const contexto = useContext(AuthContext)
  if (!contexto) throw new Error('useAuth precisa estar dentro de AuthProvider.')
  return contexto
}
