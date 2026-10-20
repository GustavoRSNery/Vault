/**
 * Download de um JSON gerado no navegador.
 *
 * O arquivo é montado a partir da resposta que já veio pela API autenticada,
 * em vez de abrir a URL numa aba nova: uma aba nova não carrega o cabeçalho
 * Authorization, e resolver isso com token na query string colocaria
 * credencial no histórico do navegador e no log do servidor.
 *
 * O objectURL é revogado logo depois — deixá-lo vivo mantém o conteúdo na
 * memória do navegador, e aqui o conteúdo é sempre material de auditoria.
 */
export function baixarJson(dados: unknown, nomeDoArquivo: string): void {
  const conteudo = JSON.stringify(dados, null, 2)
  baixarTexto(conteudo, nomeDoArquivo, 'application/json')
}

export function baixarTexto(
  conteudo: string,
  nomeDoArquivo: string,
  tipo = 'text/plain',
): void {
  const url = URL.createObjectURL(new Blob([conteudo], { type: `${tipo};charset=utf-8` }))
  const link = document.createElement('a')
  link.href = url
  link.download = nomeDoArquivo
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
