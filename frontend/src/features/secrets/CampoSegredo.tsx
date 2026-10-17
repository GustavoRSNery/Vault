/**
 * Campo de segredo: nasce mascarado, revela por tempo limitado.
 *
 * Regras que o design system fixa e que este componente implementa:
 * - nenhum valor aparece por padrão; revelar é ação explícita do usuário;
 * - a revelação some sozinha depois de alguns segundos, para não ficar
 *   exposta numa tela esquecida aberta;
 * - copiar não revela: o valor vai para a área de transferência sem passar
 *   pela tela;
 * - mascarado e revelado ocupam a mesma largura, para o layout não saltar.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Botao } from '@/shared/ui/components'

const SEGUNDOS_VISIVEL = 30

type RevealResponse = {
  secret_id: string
  secret_name: string
  version: number
  value: string
}

export function CampoSegredo({
  cofre,
  segredo,
}: {
  cofre: string
  segredo: string
}) {
  const [valor, setValor] = useState<string | null>(null)
  const [restante, setRestante] = useState(0)
  const [ocupado, setOcupado] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [aviso, setAviso] = useState<string | null>(null)

  // Guarda o timer para limpá-lo ao desmontar: sem isso, um setState
  // dispararia depois de o componente sair da tela.
  const timerRef = useRef<number | null>(null)

  const esconder = useCallback(() => {
    setValor(null)
    setRestante(0)
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  useEffect(() => esconder, [esconder])

  // Ao trocar de segredo, o valor anterior não pode permanecer na tela.
  useEffect(() => {
    esconder()
    setErro(null)
    setAviso(null)
  }, [cofre, segredo, esconder])

  const buscarValor = useCallback(async (): Promise<string | null> => {
    setErro(null)
    setOcupado(true)
    try {
      const resposta = await request<RevealResponse>(
        `/cofres/${encodeURIComponent(cofre)}/segredos/${encodeURIComponent(segredo)}/revelar`,
        { method: 'POST' },
      )
      return resposta.value
    } catch (e) {
      setErro(
        e instanceof ApiError ? e.message : 'Não foi possível revelar o segredo.',
      )
      return null
    } finally {
      setOcupado(false)
    }
  }, [cofre, segredo])

  const revelar = useCallback(async () => {
    const recebido = await buscarValor()
    if (recebido === null) return

    setValor(recebido)
    setRestante(SEGUNDOS_VISIVEL)
    timerRef.current = window.setInterval(() => {
      setRestante((anterior) => {
        if (anterior <= 1) {
          esconder()
          return 0
        }
        return anterior - 1
      })
    }, 1000)
  }, [buscarValor, esconder])

  const copiar = useCallback(async () => {
    // Busca o valor de novo em vez de reaproveitar o revelado: copiar deve
    // funcionar sem nunca ter exibido o segredo na tela.
    const recebido = valor ?? (await buscarValor())
    if (recebido === null) return
    try {
      await navigator.clipboard.writeText(recebido)
      setAviso('Copiado para a área de transferência.')
      window.setTimeout(() => setAviso(null), 4000)
    } catch {
      setErro('O navegador bloqueou o acesso à área de transferência.')
    }
  }, [valor, buscarValor])

  return (
    <div className="col" style={{ gap: 8 }}>
      <div className="secret-box">
        <span className="secret" style={{ flex: 1, wordBreak: 'break-all' }}>
          {valor ?? '••••••••••••'}
        </span>

        <Botao
          variante="secondary"
          pequeno
          onClick={valor ? esconder : revelar}
          disabled={ocupado}
          aria-label={valor ? 'Ocultar segredo' : 'Revelar segredo'}
        >
          {ocupado && !valor ? 'Revelando…' : valor ? 'Ocultar' : 'Revelar'}
        </Botao>

        <Botao
          variante="secondary"
          pequeno
          onClick={copiar}
          disabled={ocupado}
          aria-label="Copiar segredo"
        >
          Copiar
        </Botao>
      </div>

      {valor && (
        <span className="help" role="status" aria-live="polite">
          Oculta automaticamente em {restante}s.
        </span>
      )}
      {aviso && (
        <span className="help" role="status" aria-live="polite">
          {aviso}
        </span>
      )}
      {erro && (
        <span className="help" role="alert" style={{ color: 'var(--danger-text)' }}>
          {erro}
        </span>
      )}
    </div>
  )
}
