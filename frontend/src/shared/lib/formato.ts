/** Formatação compartilhada pelas telas. */

/**
 * Data e hora no formato que o design system fixa: 16/10/2026 14:32.
 * Um ISO inválido vira travessão em vez de "Invalid Date" na tela.
 */
export function formatarDataHora(iso: string): string {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return '—'
  return data.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
