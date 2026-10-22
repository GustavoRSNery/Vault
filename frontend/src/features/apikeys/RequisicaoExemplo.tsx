import { useState } from 'react'
import { Badge } from '@/shared/ui/components'

/**
 * A requisição de exemplo, no formato de um cliente de API.
 *
 * **Por que isto existe.** Saber que a chave vai em `Authorization: Bearer`
 * não diz *contra o quê*. Quem recebe uma chave ainda precisa descobrir o
 * endereço, o verbo e a rota — e vai procurar isso num chamado antigo ou
 * perguntar para alguém. O exemplo montado aqui responde de uma vez, e sai
 * copiável.
 *
 * **O valor nunca aparece**, nem quando está no cofre: sai como `<valor>`.
 * Exemplo com chave de verdade vira chave em print de tela, em anexo de
 * chamado e em histórico de navegador — três lugares fora da auditoria.
 *
 * O servidor monta as partes; esta tela só desenha. A regra de como a chave
 * entra na requisição vive num lugar só, pela mesma razão do comando SSH.
 */
export function RequisicaoExemplo({
  linhas,
  curl,
  documentacaoUrl,
}: {
  linhas: [string, string][]
  curl: string
  documentacaoUrl: string
}) {
  const [copiado, setCopiado] = useState<string | null>(null)

  const copiar = async (texto: string, marca: string) => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(marca)
      window.setTimeout(() => setCopiado(null), 2000)
    } catch {
      // Área de transferência bloqueada: o texto segue selecionável na tela.
      setCopiado(null)
    }
  }

  const metodo = linhas.find(([rotulo]) => rotulo === 'metodo')?.[1] ?? ''
  const cabecalho = linhas.find(([rotulo]) => rotulo === 'cabecalho')?.[1] ?? ''

  if (metodo === '' && cabecalho === '') return null

  return (
    <div className="col" style={{ gap: 8 }}>
      <div className="terminal">
        {metodo && (
          <div className="terminal-bloco">
            <div className="terminal-titulo">
              <span>Requisição</span>
              <button
                type="button"
                className="terminal-copiar"
                onClick={() => void copiar(metodo, 'metodo')}
              >
                {copiado === 'metodo' ? 'copiado' : 'copiar'}
              </button>
            </div>
            <div className="terminal-linha">
              <code>{metodo}</code>
            </div>
          </div>
        )}

        {cabecalho && (
          <div className="terminal-bloco">
            <div className="terminal-titulo">
              <span>Autenticação</span>
              <button
                type="button"
                className="terminal-copiar"
                onClick={() => void copiar(cabecalho, 'cabecalho')}
              >
                {copiado === 'cabecalho' ? 'copiado' : 'copiar'}
              </button>
            </div>
            <div className="terminal-linha">
              <code>{cabecalho}</code>
            </div>
          </div>
        )}

        {curl && (
          <div className="terminal-bloco">
            <div className="terminal-titulo">
              <span>curl</span>
              <button
                type="button"
                className="terminal-copiar"
                onClick={() => void copiar(curl, 'curl')}
              >
                {copiado === 'curl' ? 'copiado' : 'copiar'}
              </button>
            </div>
            <div className="terminal-linha">
              <span className="terminal-prompt">$</span>
              <code>{curl}</code>
            </div>
            <div className="terminal-explica">
              Troque <code>&lt;valor&gt;</code> pela chave revelada no cofre — a
              revelação fica na trilha.
            </div>
          </div>
        )}
      </div>

      <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
        <Badge tom="muted">o valor nunca aparece aqui</Badge>
        {documentacaoUrl && (
          <a
            className="help"
            href={documentacaoUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            Documentação do serviço →
          </a>
        )}
      </div>
    </div>
  )
}
