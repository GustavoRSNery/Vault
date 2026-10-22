import { useMutation, useQuery } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Vazio } from '@/shared/ui/components'
import { lerCredenciais, paraIdentificador, type CredencialImportada } from './importar'

type DispositivoResumo = { name: string; display_name: string }

/** O corpo que a API espera em `POST /dispositivos/{nome}/credenciais`. */
type CorpoDaCredencial = {
  name: string
  username: string
  description: string
  rotation_days: number
}

function useDispositivos() {
  return useQuery({
    queryKey: ['dispositivos'],
    queryFn: () => request<DispositivoResumo[]>('/dispositivos'),
  })
}

/**
 * Cadastro de uma credencial.
 *
 * A credencial nasce **dentro de um dispositivo** porque é assim que ela é
 * procurada depois: ninguém pergunta "onde está a senha-root?", pergunta
 * "qual a senha do srv-db-01?". Uma credencial solta seria achável só por
 * busca textual, e a primeira grafia divergente a perderia.
 *
 * **O valor da senha não passa por aqui.** Esta tela cria o *governo* — de
 * qual equipamento é, quem usa, de quantos em quantos dias troca. O valor é
 * segredo do cofre, cifrado, com revelação auditada. Aceitá-lo neste
 * formulário o faria trafegar por um caminho que não foi construído para
 * ele, e apareceria no corpo de uma requisição comum.
 */
export function NovaCredencial({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void
  aoCriar: () => void
}) {
  const { data: dispositivos } = useDispositivos()
  const [dispositivo, setDispositivo] = useState('')
  const [nome, setNome] = useState('')
  const [usuario, setUsuario] = useState('')
  const [descricao, setDescricao] = useState('')
  const [rotacao, setRotacao] = useState('90')
  const [erro, setErro] = useState<string | null>(null)

  const identificador = paraIdentificador(nome)
  const dias = Number(rotacao)

  const criar = useMutation({
    mutationFn: () =>
      request(`/dispositivos/${dispositivo}/credenciais`, {
        method: 'POST',
        body: {
          name: identificador,
          username: usuario.trim(),
          description: descricao.trim(),
          rotation_days: dias,
        } satisfies CorpoDaCredencial,
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  const semDispositivo = dispositivos !== undefined && dispositivos.length === 0

  return (
    <Card titulo="Nova credencial">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Alerta tom="warning">
          Esta tela não recebe a senha. Aqui fica o <b>governo</b>: de qual
          equipamento é, quem usa e de quanto em quanto tempo troca. O valor
          vai para um cofre, cifrado — e cada revelação vira evento.
        </Alerta>

        {semDispositivo ? (
          <Vazio
            titulo="Nenhum dispositivo cadastrado"
            descricao="A credencial pertence a um equipamento: é assim que alguém a procura depois."
            acao={
              <Link to="/dispositivos" className="btn btn-secondary btn-sm">
                Cadastrar em Dispositivos →
              </Link>
            }
          />
        ) : (
          <>
            <div className="field">
              <label htmlFor="cred-dispositivo">Dispositivo</label>
              <select
                id="cred-dispositivo"
                className="input"
                value={dispositivo}
                onChange={(e) => setDispositivo(e.target.value)}
                autoFocus
              >
                <option value="">Escolha o equipamento…</option>
                {(dispositivos ?? []).map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.display_name} ({d.name})
                  </option>
                ))}
              </select>
              <span className="help">
                Ninguém pergunta "onde está a senha-root?" — pergunta "qual a
                senha do srv-db-01?".
              </span>
            </div>

            <Campo
              rotulo="Nome da credencial"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
              placeholder="Senha root"
              ajuda={
                identificador
                  ? `Identificador: ${identificador}`
                  : 'Ex.: Senha root, Usuário de backup.'
              }
            />

            <Campo
              rotulo="Usuário (opcional)"
              value={usuario}
              onChange={(e) => setUsuario(e.target.value)}
              placeholder="root"
              ajuda="O login a que esta senha pertence."
            />

            <Campo
              rotulo="Descrição (opcional)"
              value={descricao}
              onChange={(e) => setDescricao(e.target.value)}
              ajuda="Para que serve. Quem lê daqui a um ano agradece."
            />

            <div className="field">
              <label htmlFor="cred-rotacao">Trocar a cada</label>
              <select
                id="cred-rotacao"
                className="input"
                value={rotacao}
                onChange={(e) => setRotacao(e.target.value)}
              >
                <option value="30">30 dias</option>
                <option value="60">60 dias</option>
                <option value="90">90 dias</option>
                <option value="180">180 dias</option>
                <option value="365">1 ano</option>
                <option value="0">Não rotaciona</option>
              </select>
              <span className="help">
                {dias === 0
                  ? 'Decisão explícita: esta credencial não entra no relatório de rotação atrasada.'
                  : 'Credencial nunca rotacionada conta como atrasada — é o pior caso, e esconder isso esconderia a senha de fábrica.'}
              </span>
            </div>

            <div className="row" style={{ gap: 10 }}>
              <Botao
                onClick={() => criar.mutate()}
                disabled={!dispositivo || !identificador || criar.isPending}
              >
                {criar.isPending ? 'Cadastrando…' : 'Cadastrar'}
              </Botao>
              <Botao variante="secondary" onClick={aoFechar}>
                Cancelar
              </Botao>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

type Resultado = { nome: string; ok: boolean; mensagem: string }

/**
 * Importação de credenciais a partir de um arquivo JSON.
 *
 * **Por que detectar o formato em vez de pedir para escolher.** Quem acabou
 * de exportar de outra ferramenta sabe que clicou em "exportar", não o nome
 * do formato. Um seletor errado produz importação vazia, e a conclusão é que
 * o arquivo veio corrompido.
 *
 * **Prévia antes de gravar, sempre.** Importação é a operação que cria dezenas
 * de registros de uma vez; vê-los antes é a diferença entre corrigir um
 * arquivo e limpar um inventário.
 */
export function ImportarCredenciais({
  aoFechar,
  aoImportar,
}: {
  aoFechar: () => void
  aoImportar: () => void
}) {
  const { data: dispositivos } = useDispositivos()
  const [dispositivo, setDispositivo] = useState('')
  const [lidas, setLidas] = useState<CredencialImportada[] | null>(null)
  const [formato, setFormato] = useState('')
  const [ignorados, setIgnorados] = useState<string[]>([])
  const [comSenha, setComSenha] = useState(0)
  const [erro, setErro] = useState<string | null>(null)
  const [resultados, setResultados] = useState<Resultado[] | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const escolher = async (arquivo: File) => {
    setErro(null)
    setResultados(null)
    try {
      const leitura = lerCredenciais(await arquivo.text())
      setLidas(leitura.credenciais)
      setFormato(leitura.formato)
      setIgnorados(leitura.ignorados)
      setComSenha(leitura.comSenha)
    } catch (e) {
      setLidas(null)
      setErro(e instanceof Error ? e.message : 'Não foi possível ler o arquivo.')
    }
  }

  const importar = useMutation({
    mutationFn: async () => {
      // Uma a uma, e **não** em paralelo: o servidor processa cada uma com
      // sua própria checagem de permissão e seu próprio evento de auditoria,
      // e um lote paralelo embaralharia a ordem dos eventos sem ganhar nada
      // perceptível para dezenas de linhas.
      const saida: Resultado[] = []
      for (const c of lidas ?? []) {
        try {
          await request(`/dispositivos/${dispositivo}/credenciais`, {
            method: 'POST',
            body: {
              name: c.name,
              username: c.username,
              description: c.description,
              rotation_days: 90,
            } satisfies CorpoDaCredencial,
          })
          saida.push({ nome: c.name, ok: true, mensagem: 'cadastrada' })
        } catch (e) {
          // Uma falha não interrompe as outras: num arquivo de 40 linhas,
          // parar na terceira deixaria 37 por fazer e nenhuma pista de
          // quais já entraram.
          saida.push({
            nome: c.name,
            ok: false,
            mensagem: e instanceof ApiError ? e.message : 'falhou',
          })
        }
      }
      return saida
    },
    onSuccess: (saida) => {
      setResultados(saida)
      aoImportar()
    },
  })

  const criadas = resultados?.filter((r) => r.ok).length ?? 0
  const falhas = resultados?.filter((r) => !r.ok) ?? []

  return (
    <Card titulo="Importar credenciais de um arquivo">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <p className="sub" style={{ margin: 0 }}>
          Aceita a exportação desta tela, export de Bitwarden ou 1Password, e
          listas JSON com <code>name</code>. O formato é detectado pelo
          conteúdo.
        </p>

        <Alerta tom="warning">
          <b>As senhas não são importadas</b>, mesmo quando o arquivo as
          traz. Entra o governo — nome, usuário, descrição. O valor vai para um
          cofre pelo caminho do cofre, que cifra e audita.
        </Alerta>

        <div className="field">
          <label htmlFor="imp-arquivo">Arquivo JSON</label>
          <input
            id="imp-arquivo"
            ref={inputRef}
            className="input"
            type="file"
            accept=".json,application/json"
            onChange={(e) => {
              const arquivo = e.target.files?.[0]
              if (arquivo) void escolher(arquivo)
            }}
          />
          <span className="help">O arquivo é lido no navegador; nada sobe ainda.</span>
        </div>

        {lidas && (
          <>
            <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
              <Badge tom="success">{formato}</Badge>
              <span>
                <b>{lidas.length}</b> credencia{lidas.length === 1 ? 'l' : 'is'}{' '}
                reconhecida{lidas.length === 1 ? '' : 's'}
              </span>
              {comSenha > 0 && (
                <Badge tom="warning">
                  {comSenha} traziam senha — descartada{comSenha === 1 ? '' : 's'}
                </Badge>
              )}
            </div>

            {ignorados.length > 0 && (
              <Alerta tom="warning">
                Ficaram de fora: {ignorados.join('; ')}. Só itens de login
                viram credencial — nota e cartão não têm equipamento nem
                rotação.
              </Alerta>
            )}

            <div className="field">
              <label htmlFor="imp-dispositivo">Cadastrar em qual dispositivo</label>
              <select
                id="imp-dispositivo"
                className="input"
                value={dispositivo}
                onChange={(e) => setDispositivo(e.target.value)}
              >
                <option value="">Escolha o equipamento…</option>
                {(dispositivos ?? []).map((d) => (
                  <option key={d.name} value={d.name}>
                    {d.display_name} ({d.name})
                  </option>
                ))}
              </select>
              <span className="help">
                Todas vão para o mesmo equipamento. Arquivos de gerenciador não
                dizem de qual máquina cada senha é — e adivinhar criaria um
                inventário que mente.
              </span>
            </div>

            <div className="tbl-wrap" style={{ maxHeight: 260, overflow: 'auto' }}>
              <table className="tbl">
                <thead>
                  <tr>
                    <th>Identificador</th>
                    <th>Usuário</th>
                    <th>Descrição</th>
                  </tr>
                </thead>
                <tbody>
                  {lidas.map((c) => (
                    <tr key={c.name}>
                      <td className="strong">{c.name}</td>
                      <td className="muted">{c.username || '—'}</td>
                      <td className="muted">{c.description || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {/* Sucesso não é alerta: `Alerta` tem só os tons de aviso e erro, e
            pintar "deu certo" de amarelo treina a pessoa a ignorar amarelo.
            A falha parcial, essa sim, precisa chamar atenção. */}
        {resultados && (
          <>
            <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
              <Badge tom="success">
                {criadas} cadastrada{criadas === 1 ? '' : 's'}
              </Badge>
              {falhas.length > 0 && (
                <Badge tom="danger">
                  {falhas.length} não entrou{falhas.length === 1 ? '' : 'ram'}
                </Badge>
              )}
            </div>
            {falhas.length > 0 && (
              <Alerta tom="warning">
                {falhas.map((f) => `${f.nome}: ${f.mensagem}`).join('; ')}. As
                demais entraram — uma falha no meio do arquivo não desfaz o que
                já passou.
              </Alerta>
            )}
          </>
        )}

        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => importar.mutate()}
            disabled={!lidas || !dispositivo || importar.isPending}
          >
            {importar.isPending
              ? 'Importando…'
              : `Importar ${lidas?.length ?? 0}`}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            {resultados ? 'Fechar' : 'Cancelar'}
          </Botao>
        </div>
      </div>
    </Card>
  )
}
