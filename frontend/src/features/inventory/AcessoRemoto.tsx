import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request, requestText } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Vazio } from '@/shared/ui/components'
import { baixarTexto } from '@/shared/lib/baixar'

/**
 * Acesso remoto do dispositivo.
 *
 * Duas decisões moldam esta tela:
 *
 * 1. **Os identificadores ficam visíveis.** O código do AnyDesk e o host do
 *    RDP dizem *onde* a máquina está, não *como* entrar nela — quem tem o
 *    número e não tem a senha não entra. Mascará-los atrapalharia o uso
 *    diário (alguém precisa ditar o número no telefone) sem proteger nada.
 *
 * 2. **O .rdp sai sem senha.** É o padrão que as ferramentas do ramo usam, e
 *    a razão é direta: senha dentro de arquivo é senha no disco de quem
 *    baixou, fora do cofre e fora da auditoria. A pessoa revela a senha no
 *    cofre — o que vira evento — e cola na janela do RDP.
 *
 * O que o sistema não intermedia (AnyDesk, Google Remote Desktop) tem botão
 * de "registrar acesso": sem isso a trilha teria um buraco justamente nos
 * acessos informais, que são os que mais pesam numa revisão.
 */

export type Acesso = {
  metodo: string
  identificador: string
  porta: number | null
  usuario_sugerido: string
  observacao: string
  suporta_arquivo_rdp: boolean
  link: string | null
}

const METODOS = [
  {
    valor: 'rdp',
    rotulo: 'RDP',
    ajuda: 'Endereço ou nome da máquina. Ex.: 10.0.1.20.',
    pedePorta: true,
  },
  {
    valor: 'anydesk',
    rotulo: 'AnyDesk',
    ajuda: 'O código de 9 dígitos que aparece no AnyDesk da máquina.',
    pedePorta: false,
  },
  {
    valor: 'google_remote',
    rotulo: 'Google Remote Desktop',
    ajuda: 'O nome com que a máquina aparece na lista do Google.',
    pedePorta: false,
  },
  {
    valor: 'ssh',
    rotulo: 'SSH',
    ajuda: 'Endereço do host. A porta padrão é 22.',
    pedePorta: true,
  },
  { valor: 'vnc', rotulo: 'VNC', ajuda: 'Endereço do host.', pedePorta: true },
  {
    valor: 'teamviewer',
    rotulo: 'TeamViewer',
    ajuda: 'O ID da máquina no TeamViewer.',
    pedePorta: false,
  },
  { valor: 'outro', rotulo: 'Outro', ajuda: 'Descreva na observação.', pedePorta: false },
]

const ROTULO_METODO: Record<string, string> = Object.fromEntries(
  METODOS.map((m) => [m.valor, m.rotulo]),
)

export function PainelAcessoRemoto({
  dispositivo,
  acessos,
}: {
  dispositivo: string
  acessos: Acesso[]
}) {
  const [editando, setEditando] = useState(false)

  if (editando) {
    return (
      <EditorDeAcessos
        dispositivo={dispositivo}
        acessos={acessos}
        aoFechar={() => setEditando(false)}
      />
    )
  }

  return (
    <div className="col" style={{ gap: 12 }}>
      {acessos.length === 0 ? (
        <Vazio
          titulo="Nenhuma forma de acesso cadastrada"
          descricao="Cadastre como se alcança esta máquina: sem isso, quem precisa dela depende de perguntar a alguém."
          acao={<Botao pequeno onClick={() => setEditando(true)}>Cadastrar acesso</Botao>}
        />
      ) : (
        <>
          <div className="col" style={{ gap: 10 }}>
            {acessos.map((a) => (
              <CartaoDeAcesso key={a.metodo} dispositivo={dispositivo} acesso={a} />
            ))}
          </div>
          <div className="row" style={{ gap: 10 }}>
            <Botao pequeno variante="secondary" onClick={() => setEditando(true)}>
              Editar acessos
            </Botao>
          </div>
          <span className="help">
            Os identificadores acima são públicos por natureza: dizem onde a
            máquina está, não como entrar nela. A senha continua no cofre e sai
            pela revelação, que fica registrada.
          </span>
        </>
      )}
    </div>
  )
}

function CartaoDeAcesso({
  dispositivo,
  acesso,
}: {
  dispositivo: string
  acesso: Acesso
}) {
  const [copiado, setCopiado] = useState(false)
  const [erro, setErro] = useState<string | null>(null)
  const [registrado, setRegistrado] = useState(false)

  const baixarRdp = useMutation({
    mutationFn: () => requestText(`/dispositivos/${dispositivo}/rdp`),
    onSuccess: (conteudo) => baixarTexto(conteudo, `${dispositivo}.rdp`),
    onError: (e) =>
      setErro(
        e instanceof ApiError
          ? e.message
          : 'Não foi possível gerar o arquivo. Verifique sua permissão.',
      ),
  })

  const registrar = useMutation({
    mutationFn: () =>
      request<void>(
        `/dispositivos/${dispositivo}/acesso-registrado?metodo=${acesso.metodo}`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      setRegistrado(true)
      window.setTimeout(() => setRegistrado(false), 4000)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível registrar.'),
  })

  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(acesso.identificador)
      setCopiado(true)
      window.setTimeout(() => setCopiado(false), 2000)
    } catch {
      setErro('O navegador bloqueou a cópia. Selecione o código e copie à mão.')
    }
  }

  return (
    <div className="col" style={{ gap: 8, padding: '10px 0', borderTop: '1px solid var(--line)' }}>
      {erro && <Alerta tom="danger">{erro}</Alerta>}

      <div className="row between wrap" style={{ gap: 10 }}>
        <div className="col" style={{ gap: 4 }}>
          <div className="row" style={{ gap: 8, alignItems: 'center' }}>
            <Badge tom="muted">{ROTULO_METODO[acesso.metodo] ?? acesso.metodo}</Badge>
            <code>{acesso.identificador}</code>
            {acesso.porta !== null && <span className="help">porta {acesso.porta}</span>}
          </div>
          {acesso.usuario_sugerido && (
            <span className="help">Usuário sugerido: {acesso.usuario_sugerido}</span>
          )}
          {acesso.observacao && <span className="help">{acesso.observacao}</span>}
        </div>

        <div className="row wrap" style={{ gap: 6 }}>
          <Botao pequeno variante="ghost" onClick={() => void copiar()}>
            {copiado ? 'Copiado' : 'Copiar código'}
          </Botao>

          {acesso.suporta_arquivo_rdp && (
            <Botao
              pequeno
              disabled={baixarRdp.isPending}
              onClick={() => baixarRdp.mutate()}
              title="Baixa a conexão já apontada para o host. A senha não vai no arquivo."
            >
              {baixarRdp.isPending ? 'Gerando…' : 'Conectar por RDP'}
            </Botao>
          )}

          {acesso.link && (
            <Botao
              pequeno
              onClick={() => {
                registrar.mutate()
                window.open(acesso.link!, '_blank', 'noopener,noreferrer')
              }}
            >
              Abrir
            </Botao>
          )}

          {!acesso.suporta_arquivo_rdp && !acesso.link && (
            <Botao
              pequeno
              variante="secondary"
              disabled={registrar.isPending}
              onClick={() => registrar.mutate()}
              title="O acesso acontece fora do sistema; este botão deixa o registro na trilha."
            >
              {registrado ? 'Registrado' : 'Registrar acesso'}
            </Botao>
          )}
        </div>
      </div>

      {acesso.suporta_arquivo_rdp && (
        <span className="help">
          O arquivo vem sem senha — é de propósito. Revele a senha no cofre e
          cole na janela do RDP; assim a senha não fica num arquivo no disco.
        </span>
      )}
      {registrado && !acesso.link && (
        <span className="help">Acesso registrado na auditoria.</span>
      )}
    </div>
  )
}

function EditorDeAcessos({
  dispositivo,
  acessos,
  aoFechar,
}: {
  dispositivo: string
  acessos: Acesso[]
  aoFechar: () => void
}) {
  const [linhas, setLinhas] = useState<Acesso[]>(
    acessos.length > 0 ? acessos : [novaLinha('rdp')],
  )
  const [erro, setErro] = useState<string | null>(null)
  const queryClient = useQueryClient()

  const salvar = useMutation({
    mutationFn: () =>
      request(`/dispositivos/${dispositivo}/acessos`, {
        method: 'PUT',
        body: {
          acessos: linhas
            .filter((l) => l.identificador.trim() !== '')
            .map((l) => ({
              metodo: l.metodo,
              identificador: l.identificador.trim(),
              porta: l.porta,
              usuario_sugerido: l.usuario_sugerido,
              observacao: l.observacao,
            })),
        },
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['dispositivos'] })
      aoFechar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.'),
  })

  const atualizar = (indice: number, mudanca: Partial<Acesso>) =>
    setLinhas(linhas.map((l, i) => (i === indice ? { ...l, ...mudanca } : l)))

  const metodosUsados = new Set(linhas.map((l) => l.metodo))
  // Cada método aparece uma vez só: dois RDPs confundem quem vai conectar.
  const proximoMetodo = METODOS.find((m) => !metodosUsados.has(m.valor))?.valor

  return (
    <div className="col" style={{ gap: 14 }}>
      {erro && <Alerta tom="danger">{erro}</Alerta>}

      <Alerta tom="warning">
        Salvar <strong>substitui</strong> a lista inteira. Um acesso removido
        aqui some do cadastro — e manter um acesso que já não funciona é pior
        do que não ter nenhum, porque alguém vai tentar por ele na urgência.
      </Alerta>

      {linhas.map((linha, indice) => {
        const definicao = METODOS.find((m) => m.valor === linha.metodo)
        return (
          <div
            key={indice}
            className="col"
            style={{ gap: 10, padding: '10px 0', borderTop: '1px solid var(--line)' }}
          >
            <div className="field">
              <label htmlFor={`metodo-${indice}`}>Método</label>
              <select
                id={`metodo-${indice}`}
                className="input"
                value={linha.metodo}
                onChange={(e) => atualizar(indice, { metodo: e.target.value })}
              >
                {METODOS.filter(
                  (m) => m.valor === linha.metodo || !metodosUsados.has(m.valor),
                ).map((m) => (
                  <option key={m.valor} value={m.valor}>
                    {m.rotulo}
                  </option>
                ))}
              </select>
            </div>

            <Campo
              rotulo="Identificador"
              value={linha.identificador}
              onChange={(e) => atualizar(indice, { identificador: e.target.value })}
              ajuda={definicao?.ajuda}
            />

            {definicao?.pedePorta && (
              <Campo
                rotulo="Porta"
                type="number"
                value={linha.porta === null ? '' : String(linha.porta)}
                onChange={(e) =>
                  atualizar(indice, {
                    porta: e.target.value === '' ? null : Number(e.target.value),
                  })
                }
                ajuda="Em branco usa a porta padrão do método."
              />
            )}

            <Campo
              rotulo="Usuário sugerido"
              value={linha.usuario_sugerido}
              onChange={(e) => atualizar(indice, { usuario_sugerido: e.target.value })}
              ajuda="Opcional. Só o nome do usuário — a senha fica no cofre."
            />
            <Campo
              rotulo="Observação"
              value={linha.observacao}
              onChange={(e) => atualizar(indice, { observacao: e.target.value })}
              ajuda="Opcional. Ex.: só funciona na VPN."
            />

            <div>
              <Botao
                pequeno
                variante="ghost"
                onClick={() => setLinhas(linhas.filter((_, i) => i !== indice))}
              >
                Remover este acesso
              </Botao>
            </div>
          </div>
        )
      })}

      <div className="row wrap" style={{ gap: 10 }}>
        {proximoMetodo !== undefined && (
          <Botao
            pequeno
            variante="secondary"
            onClick={() => setLinhas([...linhas, novaLinha(proximoMetodo)])}
          >
            Adicionar acesso
          </Botao>
        )}
        <Botao disabled={salvar.isPending} onClick={() => salvar.mutate()}>
          {salvar.isPending ? 'Salvando…' : 'Salvar acessos'}
        </Botao>
        <Botao variante="secondary" onClick={aoFechar}>
          Cancelar
        </Botao>
      </div>
    </div>
  )
}

function novaLinha(metodo: string): Acesso {
  return {
    metodo,
    identificador: '',
    porta: null,
    usuario_sugerido: '',
    observacao: '',
    suporta_arquivo_rdp: false,
    link: null,
  }
}
