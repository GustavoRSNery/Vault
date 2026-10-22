import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao } from '@/shared/ui/components'
import { comandosOpenssl } from './certificado'

type ArquivoBaixado = {
  arquivo_nome: string
  conteudo_base64: string
  versao: number
}

/**
 * Os comandos que conferem o certificado na máquina de quem o instala.
 *
 * **Por que comandos e não uma saída simulada.** O que esta tela mostra é o
 * que *nós* guardamos no cadastro; o `openssl` lê o arquivo que está de fato
 * no servidor. Quando os dois divergem — e divergem, porque alguém renovou
 * sem avisar — é o arquivo que vale. Uma saída simulada a partir dos nossos
 * campos pareceria confirmação e seria eco.
 */
export function TerminalCertificado({
  nomeDoCertificado,
  arquivoNome,
  temArquivo,
}: {
  nomeDoCertificado: string
  arquivoNome: string
  temArquivo: boolean
}) {
  const [copiado, setCopiado] = useState<string | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const comandos = comandosOpenssl(
    arquivoNome,
    /\.(pfx|p12)$/i.test(arquivoNome),
  )

  const copiar = async (comando: string) => {
    try {
      await navigator.clipboard.writeText(comando)
      setCopiado(comando)
      window.setTimeout(() => setCopiado(null), 2000)
    } catch {
      // Área de transferência bloqueada: o comando continua selecionável na
      // tela, então não há o que recuperar — só não avisamos que copiou.
      setCopiado(null)
    }
  }

  const baixar = useMutation({
    mutationFn: () =>
      request<ArquivoBaixado>(`/certificados/${nomeDoCertificado}/arquivo`),
    onSuccess: (dados) => {
      // Reconstrói o arquivo no navegador: o conteúdo chega em base64 e o
      // download sai com o nome original, para que os comandos abaixo
      // funcionem sem renomear nada.
      const binario = atob(dados.conteudo_base64)
      const bytes = new Uint8Array(binario.length)
      for (let i = 0; i < binario.length; i += 1) bytes[i] = binario.charCodeAt(i)
      const url = URL.createObjectURL(new Blob([bytes]))
      const link = document.createElement('a')
      link.href = url
      link.download = dados.arquivo_nome
      link.click()
      URL.revokeObjectURL(url)
    },
    onError: (e) =>
      setErro(
        e instanceof ApiError
          ? e.message
          : 'Não foi possível baixar o arquivo.',
      ),
  })

  return (
    <div className="col" style={{ gap: 10 }}>
      {erro && <Alerta tom="danger">{erro}</Alerta>}

      <div className="row between wrap" style={{ gap: 10, alignItems: 'center' }}>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <b>Conferir no terminal</b>
          {temArquivo ? (
            <Badge tom="success">arquivo guardado: {arquivoNome}</Badge>
          ) : (
            <Badge tom="muted">sem arquivo guardado</Badge>
          )}
        </div>
        {temArquivo && (
          <Botao
            pequeno
            variante="secondary"
            disabled={baixar.isPending}
            onClick={() => baixar.mutate()}
          >
            {baixar.isPending ? 'Baixando…' : 'Baixar arquivo'}
          </Botao>
        )}
      </div>

      <p className="help" style={{ margin: 0 }}>
        A tela mostra o que está no cadastro. Estes comandos leem o arquivo de
        verdade, na máquina onde ele está instalado — e quando os dois
        divergem, é o arquivo que vale.
      </p>

      <div className="terminal">
        {comandos.map((c) => (
          <div key={c.titulo} className="terminal-bloco">
            <div className="terminal-titulo">
              <span>{c.titulo}</span>
              <button
                type="button"
                className="terminal-copiar"
                onClick={() => void copiar(c.comando)}
              >
                {copiado === c.comando ? 'copiado' : 'copiar'}
              </button>
            </div>
            {c.comando.split('\n').map((linha) => (
              <div key={linha} className="terminal-linha">
                <span className="terminal-prompt">$</span>
                <code>{linha}</code>
              </div>
            ))}
            <div className="terminal-explica">{c.explica}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
