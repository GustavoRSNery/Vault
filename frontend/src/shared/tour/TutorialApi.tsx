import { useState } from 'react'
import { Alerta, Badge } from '@/shared/ui/components'

/** Um endpoint de leitura desta tela. */
export type Endpoint = {
  metodo: 'GET'
  caminho: string
  descricao: string
  /** Trecho da resposta, com os campos que importam. Nunca valores reais. */
  exemplo?: string
}

/**
 * Como consultar esta tela pela API.
 *
 * **Só leitura, e isso é uma decisão, não uma limitação.** Criar e alterar
 * continuam passando pela interface, onde cada ação tem confirmação,
 * justificativa e trilha. Um `POST` documentado aqui convidaria a automatizar
 * escrita — e escrita automatizada sem revisão é como inventários ganham
 * dezenas de registros que ninguém reconhece depois.
 *
 * **O token não aparece.** Sai como `$VAULT_TOKEN`, lido do ambiente. Um
 * exemplo com token de verdade vira token em histórico de shell, em print e
 * em chamado — e o `curl` é feito para ser colado tal como está.
 */
export function TutorialApi({
  titulo,
  endpoints,
  observacao,
}: {
  titulo: string
  endpoints: Endpoint[]
  observacao?: string
}) {
  const [aberto, setAberto] = useState(false)
  const [copiado, setCopiado] = useState<string | null>(null)

  const base = `${window.location.origin}/api/v1`

  const copiar = async (texto: string, marca: string) => {
    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(marca)
      window.setTimeout(() => setCopiado(null), 2000)
    } catch {
      // Área de transferência bloqueada: o texto segue selecionável.
      setCopiado(null)
    }
  }

  if (!aberto) {
    return (
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        onClick={() => setAberto(true)}
        title="Como consultar esta tela pela API"
      >
        Ver pela API
      </button>
    )
  }

  return (
    <div className="card" style={{ marginTop: 14 }}>
      <div className="row between wrap" style={{ gap: 10, alignItems: 'center' }}>
        <div className="row" style={{ gap: 8, alignItems: 'center' }}>
          <b>{titulo} pela API</b>
          <Badge tom="muted">somente leitura</Badge>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setAberto(false)}
        >
          Fechar
        </button>
      </div>

      <p className="help" style={{ margin: '8px 0 0' }}>
        Primeiro faça login em <code>POST /api/v1/auth/login</code>. Ele
        devolve um <code>access_token</code>, que vai no cabeçalho das outras
        chamadas. Esse token dura pouco; quando expirar, use o{' '}
        <code>refresh_token</code> para pegar um novo.
      </p>

      <div className="terminal" style={{ marginTop: 12 }}>
        <div className="terminal-bloco">
          <div className="terminal-titulo">
            <span>Autenticação</span>
            <button
              type="button"
              className="terminal-copiar"
              onClick={() =>
                void copiar(
                  `curl -s -X POST '${base}/auth/login' \\\n  -H 'Content-Type: application/json' \\\n  -d '{"email":"voce@empresa.com.br","password":"..."}'`,
                  'login',
                )
              }
            >
              {copiado === 'login' ? 'copiado' : 'copiar'}
            </button>
          </div>
          <div className="terminal-linha">
            <span className="terminal-prompt">$</span>
            <code>
              curl -s -X POST &apos;{base}/auth/login&apos; -H
              &apos;Content-Type: application/json&apos; -d
              &apos;&#123;&quot;email&quot;:&quot;…&quot;,&quot;password&quot;:&quot;…&quot;&#125;&apos;
            </code>
          </div>
          <div className="terminal-explica">
            Guarde o <code>access_token</code> numa variável:{' '}
            <code>export VAULT_TOKEN=&quot;…&quot;</code>. Evite colar o token
            direto no comando, porque ele fica salvo no histórico do terminal.
          </div>
        </div>

        {endpoints.map((e) => {
          const comando = `curl -s '${base}${e.caminho}' -H "Authorization: Bearer $VAULT_TOKEN"`
          return (
            <div key={e.caminho} className="terminal-bloco">
              <div className="terminal-titulo">
                <span>
                  {e.metodo} {e.caminho}
                </span>
                <button
                  type="button"
                  className="terminal-copiar"
                  onClick={() => void copiar(comando, e.caminho)}
                >
                  {copiado === e.caminho ? 'copiado' : 'copiar'}
                </button>
              </div>
              <div className="terminal-linha">
                <span className="terminal-prompt">$</span>
                <code>{comando}</code>
              </div>
              <div className="terminal-explica">{e.descricao}</div>
              {e.exemplo && (
                <div className="terminal-linha" style={{ marginTop: 6 }}>
                  <code style={{ opacity: 0.72 }}>{e.exemplo}</code>
                </div>
              )}
            </div>
          )
        })}
      </div>

      <Alerta tom="warning">
        <b>Estas rotas só leem dados.</b> Cadastrar, editar e excluir continua
        sendo pela tela, onde cada ação pede confirmação e fica registrada.
        Nenhuma delas devolve a <b>senha</b> guardada: para isso existe uma
        rota separada, que exige permissão específica e registra quem revelou.
        {observacao && <> {observacao}</>}
      </Alerta>
    </div>
  )
}
