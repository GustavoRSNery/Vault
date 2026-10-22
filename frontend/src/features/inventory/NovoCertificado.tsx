import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card } from '@/shared/ui/components'
import { lerCertificado } from './certificado'
import { paraIdentificador } from './importar'

type CofreResumo = { name: string; display_name: string }

/** Só a parte da resposta que este formulário consome. */
type CertificadoCriado = { name: string }

/** O arquivo escolhido, já lido e classificado. */
type ArquivoEscolhido = {
  nome: string
  base64: string
  /** `.pfx`/`.p12` carregam a chave privada; `.pem`/`.cer`, só o público. */
  temChavePrivada: boolean
  /** Erro de leitura, quando o arquivo não é X.509 legível. */
  aviso: string | null
}

function ehContainerComChave(nome: string): boolean {
  return /\.(pfx|p12)$/i.test(nome)
}

/** Converte ArrayBuffer em base64 sem estourar a pilha em arquivos grandes. */
function paraBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer)
  let binario = ''
  const passo = 0x8000
  for (let i = 0; i < bytes.length; i += passo) {
    binario += String.fromCharCode(...bytes.subarray(i, i + passo))
  }
  return btoa(binario)
}

/**
 * Cadastro de certificado, com o arquivo como ponto de partida.
 *
 * **Por que o arquivo primeiro.** Titular e serial digitados à mão entram
 * truncados e com um dígito a menos — e são justamente os dois campos que
 * servem para conferir contra a autoridade emissora. O arquivo tem a
 * resposta; pedir que alguém a copie é criar divergência.
 *
 * **Formato é detalhe, não decisão.** `.pem`, `.crt`, `.cer` e `.der` são o
 * mesmo X.509 em embalagens diferentes, e a tela lê os quatro sem perguntar.
 * `.pfx`/`.p12` é container cifrado por senha: a tela não o abre (abrir
 * exigiria a senha aqui, e ela é segredo do cofre), guarda o arquivo e pede
 * os campos.
 *
 * O preenchimento manual continua disponível para o caso de não haver
 * arquivo em mãos — e esse caso existe: certificado que ainda vai ser
 * emitido, ou que está só num HSM.
 */
export function NovoCertificado({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void
  aoCriar: () => void
}) {
  const [nome, setNome] = useState('')
  const [titular, setTitular] = useState('')
  const [emissor, setEmissor] = useState('')
  const [serial, setSerial] = useState('')
  const [responsavel, setResponsavel] = useState('')
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [arquivo, setArquivo] = useState<ArquivoEscolhido | null>(null)
  const [cofre, setCofre] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [lidoDoArquivo, setLidoDoArquivo] = useState(false)

  const { data: cofres } = useQuery({
    queryKey: ['cofres'],
    queryFn: () => request<CofreResumo[]>('/cofres'),
  })

  const identificador = paraIdentificador(nome)

  const escolher = async (file: File) => {
    setErro(null)
    const buffer = await file.arrayBuffer()
    const base64 = paraBase64(buffer)
    const comChave = ehContainerComChave(file.name)

    if (comChave) {
      setArquivo({
        nome: file.name,
        base64,
        temChavePrivada: true,
        aviso:
          'Arquivo .pfx/.p12 é cifrado por senha e não é lido aqui — a senha ' +
          'dele é um segredo do cofre, não um campo de formulário. Preencha ' +
          'os campos abaixo; o arquivo é guardado do mesmo jeito.',
      })
      return
    }

    try {
      const dados = lerCertificado(new Uint8Array(buffer))
      setTitular(dados.subject)
      setEmissor(dados.issuer)
      setSerial(dados.serial)
      setInicio(dados.notBefore.slice(0, 10))
      setFim(dados.notAfter.slice(0, 10))
      setLidoDoArquivo(true)
      // Um nome útil, sem sobrescrever o que a pessoa já digitou.
      const cn = /CN=([^,]+)/.exec(dados.subject)?.[1]?.trim()
      if (cn && nome === '') setNome(cn)
      setArquivo({ nome: file.name, base64, temChavePrivada: false, aviso: null })
    } catch (e) {
      setArquivo({
        nome: file.name,
        base64,
        temChavePrivada: false,
        aviso:
          (e instanceof Error ? e.message : 'Arquivo ilegível.') +
          ' Preencha os campos à mão; o arquivo é guardado do mesmo jeito.',
      })
    }
  }

  const criar = useMutation({
    mutationFn: async () => {
      const criado = await request<CertificadoCriado>('/certificados', {
        method: 'POST',
        body: {
          name: identificador,
          display_name: nome,
          subject: titular || `CN=${nome}`,
          issuer: emissor,
          serial,
          owner_label: responsavel,
          // O input date devolve só a data; a API espera instante com fuso.
          not_before: new Date(`${inicio}T00:00:00`).toISOString(),
          not_after: new Date(`${fim}T23:59:59`).toISOString(),
        },
      })

      // O arquivo vai numa segunda chamada, de propósito: o cadastro vale
      // por si (certificado em HSM não tem arquivo), e uma falha ao guardar
      // não deve desfazer o registro de que o certificado existe e vence.
      if (arquivo && cofre) {
        await request(`/certificados/${criado.name}/arquivo`, {
          method: 'POST',
          body: {
            cofre,
            arquivo_nome: arquivo.nome,
            conteudo_base64: arquivo.base64,
          },
        })
      }
      return criado
    },
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  const invalido =
    identificador === '' || emissor.trim() === '' || inicio === '' || fim === ''

  return (
    <Card titulo="Novo certificado">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <div className="field">
          <label htmlFor="cert-arquivo">Arquivo do certificado</label>
          <input
            id="cert-arquivo"
            className="input"
            type="file"
            accept=".pem,.crt,.cer,.der,.pfx,.p12,application/x-pem-file,application/x-pkcs12"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void escolher(file)
            }}
          />
          <span className="help">
            Aceita .pem, .crt, .cer, .der, .pfx e .p12. Os campos são lidos do
            arquivo quando ele é um X.509 aberto — digitar titular e serial à
            mão é onde eles entram truncados.
          </span>
        </div>

        {arquivo?.aviso && <Alerta tom="warning">{arquivo.aviso}</Alerta>}

        {lidoDoArquivo && (
          <div className="row wrap" style={{ gap: 8, alignItems: 'center' }}>
            <Badge tom="success">Lido do arquivo</Badge>
            <span className="help">
              Titular, emissor, serial e validade vieram de {arquivo?.nome}.
              Confira antes de salvar.
            </span>
          </div>
        )}

        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda={
            identificador ? `Identificador: ${identificador}` : 'Ex.: api.exemplo.com.br.'
          }
          autoFocus
        />
        <Campo
          rotulo="Titular (subject)"
          value={titular}
          onChange={(e) => setTitular(e.target.value)}
          ajuda={`Opcional. Em branco, usa CN=${nome || '…'}.`}
        />
        <Campo
          rotulo="Emissor"
          value={emissor}
          onChange={(e) => setEmissor(e.target.value)}
          ajuda="Quem assinou. Ex.: uma AC pública ou a autoridade interna."
        />
        <Campo
          rotulo="Serial"
          value={serial}
          onChange={(e) => setSerial(e.target.value)}
          ajuda="Opcional. É por ele que a autoridade emissora identifica este certificado."
        />
        <Campo
          rotulo="Responsável"
          value={responsavel}
          onChange={(e) => setResponsavel(e.target.value)}
          ajuda="Quem renova. Opcional, mas é quem será procurado no vencimento."
        />
        <Campo
          rotulo="Válido de"
          type="date"
          value={inicio}
          onChange={(e) => setInicio(e.target.value)}
        />
        <Campo
          rotulo="Válido até"
          type="date"
          value={fim}
          onChange={(e) => setFim(e.target.value)}
        />

        {arquivo && (
          <>
            <div className="field">
              <label htmlFor="cert-cofre">Guardar o arquivo em qual cofre</label>
              <select
                id="cert-cofre"
                className="input"
                value={cofre}
                onChange={(e) => setCofre(e.target.value)}
              >
                <option value="">Não guardar o arquivo</option>
                {(cofres ?? []).map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.display_name} ({c.name})
                  </option>
                ))}
              </select>
              <span className="help">
                O arquivo é cifrado como qualquer segredo, e cada download
                vira evento. Sem cofre escolhido, só os campos são guardados.
              </span>
            </div>

            {arquivo.temChavePrivada && cofre && (
              <Alerta tom="warning">
                Este arquivo carrega a <b>chave privada</b> — é a assinatura da
                empresa, não um anexo. Quem baixar precisará de permissão de
                revelar no cofre escolhido, e o download fica na trilha.
              </Alerta>
            )}

            {(cofres ?? []).length === 0 && (
              <Alerta tom="warning">
                Nenhum cofre disponível para você.{' '}
                <Link to="/cofres">Crie um cofre</Link> para poder guardar o
                arquivo; o certificado pode ser cadastrado sem ele.
              </Alerta>
            )}
          </>
        )}

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => criar.mutate()} disabled={invalido || criar.isPending}>
            {criar.isPending ? 'Cadastrando…' : 'Cadastrar'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
