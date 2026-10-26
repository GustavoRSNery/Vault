import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { RequisicaoExemplo } from './RequisicaoExemplo'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { Alerta, Badge, Botao, Campo, Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

/**
 * Chaves de API: governo, não armazenamento.
 *
 * Esta tela guarda o que a planilha costuma esquecer — para que serve a
 * chave, quem responde por ela, onde está sendo usada e quando vence. O
 * valor em si vive cifrado no cofre e sai só pela rota de revelar, uma vez,
 * com auditoria.
 *
 * Por isso a tela nunca mostra o valor: quem precisa dele vai ao cofre, e
 * essa ida fica registrada. Mostrar aqui transformaria a listagem num
 * despejo de segredos que ninguém consegue auditar depois.
 */

type ChaveDeApi = {
  id: string
  name: string
  display_name: string
  servico: string
  ambiente: string
  formato: string
  nome_do_campo: string
  escopo: string
  usada_em: string[]
  responsavel: string
  documentacao_url: string
  url_base: string
  metodo: string
  rota_exemplo: string
  vault_name: string
  secret_name: string
  expira_em: string | null
  situacao: string
  dias_para_vencer: number | null
  como_usar: string
  requisicao_exemplo: [string, string][]
  curl_exemplo: string
  created_at: string
}

const METODOS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']

const AMBIENTES = [
  { valor: 'producao', rotulo: 'Produção' },
  { valor: 'homologacao', rotulo: 'Homologação' },
  { valor: 'desenvolvimento', rotulo: 'Desenvolvimento' },
]

const FORMATOS = [
  {
    valor: 'bearer',
    rotulo: 'Bearer token',
    ajuda: 'Vai no cabeçalho Authorization como "Bearer <valor>".',
    pedeCampo: false,
  },
  {
    valor: 'basico',
    rotulo: 'Basic auth',
    ajuda: 'Usuário e senha em Base64 no cabeçalho Authorization.',
    pedeCampo: false,
  },
  {
    valor: 'cabecalho',
    rotulo: 'Cabeçalho próprio',
    ajuda: 'Ex.: X-API-Key. Sem o nome do campo ninguém sabe como enviar.',
    pedeCampo: true,
  },
  {
    valor: 'query',
    rotulo: 'Parâmetro na URL',
    ajuda: 'Desaconselhado: a chave fica no log do servidor e no histórico.',
    pedeCampo: true,
  },
  { valor: 'outro', rotulo: 'Outro', ajuda: 'Descreva no escopo como usar.', pedeCampo: false },
]

const ROTULO_AMBIENTE: Record<string, string> = Object.fromEntries(
  AMBIENTES.map((a) => [a.valor, a.rotulo]),
)
const ROTULO_FORMATO: Record<string, string> = Object.fromEntries(
  FORMATOS.map((f) => [f.valor, f.rotulo]),
)

export function ChavesApiPage() {
  const [criando, setCriando] = useState(false)
  const tour = useTour('chaves-api')
  const [editando, setEditando] = useState<ChaveDeApi | null>(null)
  const [filtro, setFiltro] = useState('')
  const queryClient = useQueryClient()

  const { data: chaves, isLoading, error } = useQuery({
    queryKey: ['chaves-api'],
    queryFn: () => request<ChaveDeApi[]>('/chaves-api'),
  })

  const recarregar = () =>
    void queryClient.invalidateQueries({ queryKey: ['chaves-api'] })

  if (isLoading) return <Carregando texto="Carregando chaves…" />
  if (error) {
    return (
      <Vazio
        titulo="Nenhuma chave acessível"
        descricao="Você pode não ter permissão no caminho de chaves de API."
      />
    )
  }

  const lista = chaves ?? []
  const termo = filtro.trim().toLowerCase()
  const visiveis = lista.filter(
    (c) =>
      termo === '' ||
      c.display_name.toLowerCase().includes(termo) ||
      c.servico.toLowerCase().includes(termo) ||
      c.responsavel.toLowerCase().includes(termo) ||
      c.usada_em.some((u) => u.toLowerCase().includes(termo)),
  )

  const ativas = lista.filter((c) => c.situacao === 'ativa')
  const vencendo = ativas.filter(
    (c) => c.dias_para_vencer !== null && c.dias_para_vencer <= 30,
  )
  const expiradas = lista.filter((c) => c.situacao === 'expirada')
  const semResponsavelClaro = ativas.filter((c) => c.usada_em.length === 0)

  return (
    <>
      <Tour id="chaves-api" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Chaves de API</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {lista.length} chave{lista.length === 1 ? '' : 's'} sob governo.
              A chave em si fica cifrada no cofre. Aqui ficam o dono, o escopo e
              o vencimento, que é o que costuma se perder quando a chave mora
              numa planilha.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Chaves de API"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/chaves-api',
                  descricao:
                    'Governo de cada chave: serviço, ambiente, escopo, onde é usada, responsável e vencimento. O valor fica no cofre.',
                  exemplo:
                    '[{"name":"sefaz-nfe","servico":"SEFAZ","situacao":"ativa","dias_para_vencer":14}]',
                },
                {
                  metodo: 'GET',
                  caminho: '/chaves-api/{nome}',
                  descricao:
                    'Uma chave, com a requisição de exemplo montada e o curl pronto. O valor sai como <valor>, nunca o real.',
                },
              ]}
            />
            <Botao pequeno onClick={() => setCriando(true)}>
              Nova chave
            </Botao>
          </div>
        </div>
      </header>

      {expiradas.length > 0 && (
        <Alerta tom="danger">
          {expiradas.length === 1
            ? '1 chave já expirou'
            : `${expiradas.length} chaves já expiraram`}{' '}
          e continua cadastrada. Se a integração ainda funciona, a chave foi
          trocada fora do cofre — e o que está aqui não vale mais.
        </Alerta>
      )}
      {expiradas.length === 0 && vencendo.length > 0 && (
        <Alerta tom="warning">
          {vencendo.length === 1
            ? '1 chave vence nos próximos 30 dias.'
            : `${vencendo.length} chaves vencem nos próximos 30 dias.`}{' '}
          Rotacionar antes do vencimento evita a parada que a troca às pressas
          costuma causar.
        </Alerta>
      )}

      <div className="cards">
        <CardMetrica rotulo="Ativas" valor={ativas.length} tom="brand" />
        <CardMetrica rotulo="Vencem em 30 dias" valor={vencendo.length} tom="warning" />
        <CardMetrica rotulo="Expiradas" valor={expiradas.length} tom="danger" />
        <div data-tour="sem-uso">
          <CardMetrica
            rotulo="Sem uso declarado"
            valor={semResponsavelClaro.length}
            tom={semResponsavelClaro.length > 0 ? 'warning' : 'brand'}
          />
        </div>
      </div>

      {semResponsavelClaro.length > 0 && (
        <p className="sub" style={{ margin: '0 0 -8px' }}>
          "Sem uso declarado" são chaves ativas que ninguém disse onde usa.
          São as primeiras candidatas a revogação: se nada quebrar, não
          precisavam existir.
        </p>
      )}

      {criando && (
        <FormularioChave
          aoFechar={() => setCriando(false)}
          aoSalvar={() => {
            setCriando(false)
            recarregar()
          }}
        />
      )}

      {editando && (
        <FormularioChave
          chave={editando}
          aoFechar={() => setEditando(null)}
          aoSalvar={() => {
            setEditando(null)
            recarregar()
          }}
        />
      )}

      <Card>
        <div style={{ marginBottom: 14 }}>
          <Campo
            rotulo="Buscar"
            value={filtro}
            onChange={(e) => setFiltro(e.target.value)}
            ajuda="Por nome, serviço, responsável ou aplicação que consome."
            placeholder="sefaz, rpa-fiscal, fulano@…"
          />
        </div>

        {visiveis.length === 0 ? (
          <Vazio
            titulo={
              lista.length === 0
                ? 'Nenhuma chave cadastrada'
                : 'Nenhuma chave para esse filtro'
            }
            descricao={
              lista.length === 0
                ? 'Cadastre as chaves que as integrações já usam: o primeiro ganho é saber quantas são.'
                : 'Ajuste o termo buscado.'
            }
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Chave</th>
                  <th>Ambiente</th>
                  <th>Como enviar</th>
                  <th>Usada em</th>
                  <th>Responsável</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {visiveis.map((c) => (
                  <LinhaChave
                    key={c.id}
                    chave={c}
                    aoEditar={() => setEditando(c)}
                    aoMudar={recarregar}
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function LinhaChave({
  chave,
  aoEditar,
  aoMudar,
}: {
  chave: ChaveDeApi
  aoEditar: () => void
  aoMudar: () => void
}) {
  const [confirmando, setConfirmando] = useState<'revogar' | 'excluir' | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const [vendoExemplo, setVendoExemplo] = useState(false)

  const revogar = useMutation({
    mutationFn: () =>
      request<ChaveDeApi>(`/chaves-api/${chave.name}/revogar`, { method: 'POST' }),
    onSuccess: () => {
      setConfirmando(null)
      aoMudar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível revogar.'),
  })

  const excluir = useMutation({
    mutationFn: () =>
      request<void>(`/chaves-api/${chave.name}`, { method: 'DELETE' }),
    onSuccess: () => {
      setConfirmando(null)
      aoMudar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível excluir.'),
  })

  return (
    <>
      <tr>
        <td className="strong">
          {chave.display_name}
          <div className="help">
            {chave.servico}
            {chave.escopo && ` · ${chave.escopo}`}
          </div>
        </td>
        <td>
          <Badge tom={chave.ambiente === 'producao' ? 'danger' : 'muted'}>
            {ROTULO_AMBIENTE[chave.ambiente] ?? chave.ambiente}
          </Badge>
        </td>
        <td className="muted">
          <code>{chave.como_usar}</code>
          <div className="help">{ROTULO_FORMATO[chave.formato] ?? chave.formato}</div>
          {chave.url_base && (
            <button
              type="button"
              className="link-sutil"
              data-tour="ver-exemplo"
              onClick={() => setVendoExemplo(!vendoExemplo)}
            >
              {vendoExemplo ? 'ocultar exemplo' : 'ver exemplo'}
            </button>
          )}
        </td>
        <td className="muted">
          {chave.usada_em.length === 0 ? (
            <span className="help">não declarado</span>
          ) : (
            chave.usada_em.join(', ')
          )}
        </td>
        <td className="muted">{chave.responsavel}</td>
        <td>
          <SituacaoChave chave={chave} />
        </td>
        <td>
          <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
            <Botao pequeno variante="secondary" onClick={aoEditar}>
              Editar
            </Botao>
            {chave.situacao !== 'revogada' && (
              <Botao
                pequeno
                variante="secondary"
                onClick={() => setConfirmando('revogar')}
              >
                Revogar
              </Botao>
            )}
            <Botao
              pequeno
              variante="secondary"
              onClick={() => setConfirmando('excluir')}
            >
              Excluir
            </Botao>
          </div>
        </td>
      </tr>

      {vendoExemplo && (
        <tr>
          <td colSpan={7}>
            <div style={{ padding: '4px 0 12px' }}>
              <RequisicaoExemplo
                linhas={chave.requisicao_exemplo}
                curl={chave.curl_exemplo}
                documentacaoUrl={chave.documentacao_url}
              />
            </div>
          </td>
        </tr>
      )}

      {confirmando && (
        <tr>
          <td colSpan={7}>
            <div className="col" style={{ gap: 10, padding: '4px 0 10px' }}>
              {erro && <Alerta tom="danger">{erro}</Alerta>}
              <Alerta tom="warning">
                {confirmando === 'revogar' ? (
                  <>
                    Revogar marca <strong>{chave.display_name}</strong> como fora
                    de uso, mas mantém o registro: a auditoria quer saber que a
                    chave existiu. Revogue <em>depois</em> de desligar a chave no{' '}
                    {chave.servico} — o estado aqui não derruba o acesso lá.
                  </>
                ) : (
                  <>
                    Excluir remove o governo de <strong>{chave.display_name}</strong>{' '}
                    desta tela.{' '}
                    {chave.secret_name
                      ? 'O valor continua no cofre — um clique não apaga segredo e rastro ao mesmo tempo.'
                      : 'Não há valor associado no cofre.'}{' '}
                    Para só tirar de circulação, use Revogar.
                  </>
                )}
              </Alerta>
              <div className="row" style={{ gap: 10 }}>
                <Botao
                  variante={confirmando === 'excluir' ? 'danger' : 'primary'}
                  disabled={revogar.isPending || excluir.isPending}
                  onClick={() =>
                    confirmando === 'revogar' ? revogar.mutate() : excluir.mutate()
                  }
                >
                  {confirmando === 'revogar' ? 'Revogar chave' : 'Excluir cadastro'}
                </Botao>
                <Botao
                  variante="secondary"
                  onClick={() => {
                    setConfirmando(null)
                    setErro(null)
                  }}
                >
                  Cancelar
                </Botao>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function SituacaoChave({ chave }: { chave: ChaveDeApi }) {
  if (chave.situacao === 'revogada') {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="muted">Revogada</Badge>
        <span className="help">mantida para histórico</span>
      </div>
    )
  }
  if (chave.situacao === 'expirada') {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="danger">Expirada</Badge>
        <span className="help">{formatarDataHora(chave.expira_em ?? '')}</span>
      </div>
    )
  }
  if (chave.dias_para_vencer !== null && chave.dias_para_vencer <= 30) {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="warning">Vencendo</Badge>
        <span className="help">
          em {chave.dias_para_vencer} dia{chave.dias_para_vencer === 1 ? '' : 's'}
        </span>
      </div>
    )
  }
  return (
    <div className="col" style={{ gap: 4 }}>
      <Badge tom="success">Ativa</Badge>
      <span className="help">
        {chave.dias_para_vencer === null
          ? 'sem vencimento'
          : `${chave.dias_para_vencer} dias restantes`}
      </span>
    </div>
  )
}

function FormularioChave({
  chave,
  aoFechar,
  aoSalvar,
}: {
  chave?: ChaveDeApi
  aoFechar: () => void
  aoSalvar: () => void
}) {
  const editando = chave !== undefined

  const [nome, setNome] = useState(chave?.display_name ?? '')
  const [servico, setServico] = useState(chave?.servico ?? '')
  const [ambiente, setAmbiente] = useState(chave?.ambiente ?? 'producao')
  const [formato, setFormato] = useState(chave?.formato ?? 'bearer')
  const [nomeDoCampo, setNomeDoCampo] = useState(chave?.nome_do_campo ?? '')
  const [escopo, setEscopo] = useState(chave?.escopo ?? '')
  const [usadaEm, setUsadaEm] = useState((chave?.usada_em ?? []).join(', '))
  const [responsavel, setResponsavel] = useState(chave?.responsavel ?? '')
  const [urlBase, setUrlBase] = useState(chave?.url_base ?? '')
  const [metodo, setMetodo] = useState(chave?.metodo ?? 'GET')
  const [rota, setRota] = useState(chave?.rota_exemplo ?? '')
  const [cofre, setCofre] = useState(chave?.vault_name ?? '')
  const [segredo, setSegredo] = useState(chave?.secret_name ?? '')
  const [validade, setValidade] = useState(
    chave?.expira_em ? chave.expira_em.slice(0, 10) : '',
  )
  const [erro, setErro] = useState<string | null>(null)

  const identificador =
    chave?.name ??
    nome
      .normalize('NFKD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '')
      .slice(0, 64)

  const formatoEscolhido = FORMATOS.find((f) => f.valor === formato)

  const corpo = () => ({
    name: identificador,
    display_name: nome,
    servico,
    ambiente,
    formato,
    nome_do_campo: nomeDoCampo,
    escopo,
    usada_em: usadaEm
      .split(',')
      .map((u) => u.trim())
      .filter(Boolean),
    responsavel,
    url_base: urlBase.trim(),
    metodo,
    rota_exemplo: rota.trim(),
    vault_name: cofre,
    secret_name: segredo,
    // O input date devolve só a data; a API espera instante com fuso.
    expira_em: validade ? new Date(`${validade}T23:59:59`).toISOString() : null,
  })

  const salvar = useMutation({
    mutationFn: () =>
      editando
        ? request<ChaveDeApi>(`/chaves-api/${chave.name}`, {
            method: 'PUT',
            body: corpo(),
          })
        : request<ChaveDeApi>('/chaves-api', { method: 'POST', body: corpo() }),
    onSuccess: aoSalvar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.'),
  })

  const faltaCampo = (formatoEscolhido?.pedeCampo ?? false) && nomeDoCampo.trim() === ''
  const invalido =
    identificador === '' ||
    servico.trim() === '' ||
    responsavel.trim() === '' ||
    faltaCampo

  return (
    <Card titulo={editando ? `Editar ${chave.display_name}` : 'Nova chave de API'}>
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Alerta tom="warning">
          Esta tela não recebe o valor da chave. Guarde o valor como segredo em
          um cofre e aponte-o abaixo: assim ele sai cifrado, uma vez por
          revelação, e cada leitura vira evento.
        </Alerta>

        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          disabled={editando}
          ajuda={
            editando
              ? `Identificador: ${identificador} (não muda)`
              : identificador
                ? `Identificador: ${identificador}`
                : 'Ex.: SEFAZ NF-e produção.'
          }
          autoFocus={!editando}
        />
        <Campo
          rotulo="Serviço"
          value={servico}
          onChange={(e) => setServico(e.target.value)}
          ajuda="Quem emite a chave. Ex.: SEFAZ, Stripe, Google Cloud."
        />

        <div className="field">
          <label htmlFor="ambiente">Ambiente</label>
          <select
            id="ambiente"
            className="input"
            value={ambiente}
            onChange={(e) => setAmbiente(e.target.value)}
          >
            {AMBIENTES.map((a) => (
              <option key={a.valor} value={a.valor}>
                {a.rotulo}
              </option>
            ))}
          </select>
          <span className="help">
            Marcar produção não muda o comportamento, mas muda a leitura de
            quem revisa: é o que separa "testei errado" de incidente.
          </span>
        </div>

        <div className="field">
          <label htmlFor="formato">Como a chave é enviada</label>
          <select
            id="formato"
            className="input"
            value={formato}
            onChange={(e) => setFormato(e.target.value)}
          >
            {FORMATOS.map((f) => (
              <option key={f.valor} value={f.valor}>
                {f.rotulo}
              </option>
            ))}
          </select>
          <span className="help">{formatoEscolhido?.ajuda}</span>
        </div>

        {formatoEscolhido?.pedeCampo && (
          <Campo
            rotulo="Nome do campo"
            value={nomeDoCampo}
            onChange={(e) => setNomeDoCampo(e.target.value)}
            ajuda="Ex.: X-API-Key, api_key. Sem ele, quem pegar a chave não sabe onde colocá-la."
            erro={faltaCampo ? 'Obrigatório para este formato.' : undefined}
          />
        )}

        <Campo
          rotulo="Escopo"
          value={escopo}
          onChange={(e) => setEscopo(e.target.value)}
          ajuda="O que a chave permite. Ex.: somente leitura de NF-e."
        />

        {/* Endereço e rota: opcionais, e é deliberado. Nem todo serviço tem
            uma rota única que sirva de exemplo, e exigir faria alguém
            inventar um endereço — pior que o campo vazio, porque parece
            informação. */}
        <Campo
          rotulo="Endereço base (opcional)"
          value={urlBase}
          onChange={(e) => setUrlBase(e.target.value)}
          placeholder="https://api.servico.com.br"
          ajuda="Com http:// ou https://. É o que transforma 'Bearer <valor>' numa chamada que alguém consegue rodar."
        />

        <div className="row wrap" style={{ gap: 12, alignItems: 'flex-end' }}>
          <div className="field" style={{ flex: '0 0 140px' }}>
            <label htmlFor="chave-metodo">Método</label>
            <select
              id="chave-metodo"
              className="input"
              value={metodo}
              onChange={(e) => setMetodo(e.target.value)}
            >
              {METODOS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div style={{ flex: '1 1 240px' }}>
            <Campo
              rotulo="Rota de exemplo (opcional)"
              value={rota}
              onChange={(e) => setRota(e.target.value)}
              placeholder="/v1/notas"
              ajuda="Uma rota qualquer que sirva para testar se a chave responde."
            />
          </div>
        </div>
        <Campo
          rotulo="Usada em"
          value={usadaEm}
          onChange={(e) => setUsadaEm(e.target.value)}
          ajuda="Aplicações separadas por vírgula. É o que diz o que quebra se a chave for revogada."
          placeholder="rpa-fiscal, etl-notas"
        />
        <Campo
          rotulo="Responsável"
          value={responsavel}
          onChange={(e) => setResponsavel(e.target.value)}
          ajuda="Quem renova e responde pela chave. Chave sem dono é chave que ninguém revoga."
        />
        <Campo
          rotulo="Cofre do valor"
          value={cofre}
          onChange={(e) => setCofre(e.target.value)}
          ajuda="Opcional. Identificador do cofre onde o valor está guardado."
        />
        <Campo
          rotulo="Segredo do valor"
          value={segredo}
          onChange={(e) => setSegredo(e.target.value)}
          ajuda="Opcional. Nome do segredo dentro do cofre."
        />
        <Campo
          rotulo="Vence em"
          type="date"
          value={validade}
          onChange={(e) => setValidade(e.target.value)}
          ajuda="Em branco, a chave não vence — e some do radar até falhar."
        />

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => salvar.mutate()} disabled={invalido || salvar.isPending}>
            {salvar.isPending ? 'Salvando…' : editando ? 'Salvar' : 'Cadastrar'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
