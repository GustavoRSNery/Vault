import { useQuery } from '@tanstack/react-query'
import { request } from '@/shared/api/client'

export type Configuracao = {
  segundos_segredo_visivel: number
  custodia_horas_padrao: number
  alerta_certificado_dias: number
  rotacao_dias_padrao: number
  trilha_limite_padrao: number
  atualizado_por: string
  atualizado_em: string
  limites: Record<string, [number, number]>
}

/**
 * Configuração operacional da instalação.
 *
 * `staleTime` alto de propósito: estes valores mudam raramente e são lidos
 * por várias telas. Reconsultar a cada montagem só geraria tráfego — e, num
 * cofre, cada chamada ao servidor é uma linha de auditoria.
 */
export function useConfiguracao() {
  return useQuery({
    queryKey: ['configuracao'],
    queryFn: () => request<Configuracao>('/configuracao'),
    staleTime: 5 * 60_000,
    retry: false,
  })
}
