/** Quantas fatias a miniatura tem. Doze cabem na largura do cartão. */
export const FATIAS = 12

/**
 * O perfil de atividade de uma gravação: doze alturas entre 0 e 1.
 *
 * **O que isto é e o que não é.** A listagem não traz a linha do tempo — e
 * trazê-la faria a tela baixar o conteúdo de todas as gravações só para
 * desenhar barrinhas, que é caro e, pior, despeja no navegador o que a
 * pessoa digitou em produção sem ela ter aberto nada. Então o perfil é
 * derivado de **duração e número de eventos**: representa a *densidade* da
 * sessão, não os instantes exatos.
 *
 * Por isso o cartão não promete onde clicar; mostra se a sessão foi intensa
 * ou esparsa, que é o que ajuda a escolher qual abrir.
 *
 * A semente vem do id para o desenho ser **estável**: o mesmo cartão sai
 * igual a cada renderização. Com `Math.random()` as barras tremeriam a cada
 * digitação na busca.
 */
export function perfilDeAtividade(
  id: string,
  eventos: number,
  duracaoMs: number,
): number[] {
  if (eventos <= 0) return Array.from({ length: FATIAS }, () => 0)

  const minutos = Math.max(duracaoMs / 60_000, 1)
  // 20 eventos por minuto satura a barra: acima disso a diferença deixa de
  // ser legível, e esticar a escala só achataria todo o resto.
  const densidade = Math.min(eventos / minutos / 20, 1)

  let semente = 0
  for (const c of id) semente = (semente * 31 + c.charCodeAt(0)) % 9973

  return Array.from({ length: FATIAS }, (_, i) => {
    semente = (semente * 1103515245 + 12345) % 2147483648
    const ruido = (semente / 2147483648) * 0.55 + 0.45
    // Arco suave: sessões costumam começar e terminar mais calmas que o meio.
    const arco = Math.sin((Math.PI * (i + 0.5)) / FATIAS) * 0.5 + 0.5
    return Math.min(densidade * ruido * arco * 1.6, 1)
  })
}
