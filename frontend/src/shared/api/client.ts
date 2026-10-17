/**
 * Cliente HTTP da API.
 *
 * Decisão de armazenamento: os tokens ficam em memória, não em localStorage.
 * localStorage é legível por qualquer script na página, então um único XSS
 * entregaria a sessão inteira — num cofre de senhas o custo disso é alto
 * demais. O preço é que recarregar a aba exige novo login; o refresh em
 * memória cobre a troca de rota, que é o caso comum.
 */

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }

  /** O servidor negou por permissão (403) ou selo (423). */
  get isDenied(): boolean {
    return this.status === 403 || this.status === 423
  }
}

type TokenPair = {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

let accessToken: string | null = null
let refreshToken: string | null = null
let onUnauthenticated: (() => void) | null = null

export function setTokens(tokens: TokenPair | null): void {
  accessToken = tokens?.access_token ?? null
  refreshToken = tokens?.refresh_token ?? null
}

export function hasSession(): boolean {
  return accessToken !== null
}

/** Chamado quando a sessão morre de vez: a aplicação volta para o login. */
export function setUnauthenticatedHandler(handler: () => void): void {
  onUnauthenticated = handler
}

type RequestOptions = {
  method?: string
  body?: unknown
  /** Interno: evita laço infinito de refresh. */
  retrying?: boolean
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, retrying = false } = options

  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  const response = await fetch(`/api/v1${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  // 401 com refresh disponível: renova uma vez e repete a chamada original.
  if (response.status === 401 && !retrying && refreshToken) {
    const renovou = await tryRefresh()
    if (renovou) return request<T>(path, { ...options, retrying: true })
  }

  if (response.status === 401) {
    setTokens(null)
    onUnauthenticated?.()
  }

  if (!response.ok) throw await toApiError(response)

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

async function tryRefresh(): Promise<boolean> {
  try {
    const response = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
    if (!response.ok) return false
    setTokens((await response.json()) as TokenPair)
    return true
  } catch {
    return false
  }
}

async function toApiError(response: Response): Promise<ApiError> {
  let code = 'erro_desconhecido'
  let message = 'Não foi possível concluir a operação.'
  try {
    const corpo = (await response.json()) as {
      erro?: { codigo?: string; mensagem?: string }
      detail?: unknown
    }
    if (corpo.erro) {
      code = corpo.erro.codigo ?? code
      message = corpo.erro.mensagem ?? message
    } else if (Array.isArray(corpo.detail)) {
      // Erro de validação do FastAPI.
      code = 'validacao'
      message = 'Verifique os campos preenchidos.'
    }
  } catch {
    // Resposta sem JSON: fica a mensagem genérica.
  }
  return new ApiError(response.status, code, message)
}
