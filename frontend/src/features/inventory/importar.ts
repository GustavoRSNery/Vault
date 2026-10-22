/**
 * Leitura de credenciais exportadas de outras ferramentas.
 *
 * **Por que detectar o formato em vez de pedir para a pessoa escolher.** Quem
 * acabou de exportar de outra ferramenta nem sempre sabe o nome do formato —
 * sabe que clicou em "exportar" no Bitwarden. Um seletor errado produz
 * importação silenciosamente vazia, e a pessoa conclui que o arquivo veio
 * corrompido.
 *
 * **O que NÃO entra aqui:** a senha. Este módulo lê *governo* (qual
 * credencial, de qual equipamento, qual usuário) e descarta o valor, mesmo
 * quando o arquivo o traz — e arquivos de gerenciador trazem. O valor entra
 * no cofre pelo caminho do cofre, que cifra e audita; passá-lo por aqui o
 * faria atravessar a tela e o corpo de uma requisição que não foi feita para
 * ele.
 */

/** Uma credencial pronta para cadastrar, já normalizada. */
export type CredencialImportada = {
  name: string
  username: string
  description: string
  /** Só informativo: diz de onde a linha veio, para a tela explicar. */
  origem: string
}

export type ResultadoDaLeitura = {
  credenciais: CredencialImportada[]
  formato: string
  /** O que foi deixado de fora, e por quê. Silêncio aqui esconde perda. */
  ignorados: string[]
  /** Quantas linhas traziam senha — contada para avisar, nunca guardada. */
  comSenha: number
}

/** Transforma um texto livre em identificador aceito pela API. */
export function paraIdentificador(texto: string): string {
  return texto
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64)
}

/** Primeiro valor não vazio entre as chaves dadas. */
function primeiro(objeto: Record<string, unknown>, chaves: string[]): string {
  for (const chave of chaves) {
    const valor = objeto[chave]
    if (typeof valor === 'string' && valor.trim() !== '') return valor.trim()
  }
  return ''
}

function temSenha(objeto: Record<string, unknown>): boolean {
  const campos = ['password', 'senha', 'value', 'valor', 'secret']
  return campos.some((c) => {
    const v = objeto[c]
    return typeof v === 'string' && v !== ''
  })
}

/** O formato que a própria tela exporta — e o caso mais comum de volta. */
function lerFormatoProprio(dados: unknown): ResultadoDaLeitura | null {
  const lista = Array.isArray(dados) ? dados : [dados]
  const credenciais: CredencialImportada[] = []
  const ignorados: string[] = []
  let comSenha = 0

  for (const item of lista) {
    if (typeof item !== 'object' || item === null) continue
    const obj = item as Record<string, unknown>
    // A exportação desta tela usa chaves em português. Exigir as duas
    // distingue o formato próprio de um JSON qualquer com campo "nome".
    const nome = primeiro(obj, ['nome', 'name'])
    const temMarcaPropria = 'usuario' in obj || 'dispositivo' in obj || 'rotacao_dias' in obj
    if (!nome || !temMarcaPropria) return null

    if (temSenha(obj)) comSenha += 1
    credenciais.push({
      name: paraIdentificador(nome),
      username: primeiro(obj, ['usuario', 'username']),
      description: primeiro(obj, ['descricao', 'description', 'observacao']),
      origem: 'exportação do Vault',
    })
  }

  if (credenciais.length === 0) return null
  return { credenciais, formato: 'Vault', ignorados, comSenha }
}

/** Export do Bitwarden: `{ items: [{ name, login: { username } }] }`. */
function lerBitwarden(dados: unknown): ResultadoDaLeitura | null {
  if (typeof dados !== 'object' || dados === null) return null
  const raiz = dados as Record<string, unknown>
  if (!Array.isArray(raiz.items)) return null

  const credenciais: CredencialImportada[] = []
  const ignorados: string[] = []
  let comSenha = 0

  for (const item of raiz.items) {
    if (typeof item !== 'object' || item === null) continue
    const obj = item as Record<string, unknown>
    const nome = primeiro(obj, ['name'])
    if (!nome) continue

    // type 1 é login; 2 nota segura, 3 cartão, 4 identidade. Só o primeiro
    // vira credencial — os outros não têm equipamento nem rotação.
    if (typeof obj.type === 'number' && obj.type !== 1) {
      ignorados.push(`${nome} (não é login)`)
      continue
    }

    const login = (obj.login ?? {}) as Record<string, unknown>
    if (temSenha(login)) comSenha += 1
    credenciais.push({
      name: paraIdentificador(nome),
      username: primeiro(login, ['username']),
      description: primeiro(obj, ['notes']),
      origem: 'Bitwarden',
    })
  }

  if (credenciais.length === 0 && ignorados.length === 0) return null
  return { credenciais, formato: 'Bitwarden', ignorados, comSenha }
}

/** Export do 1Password (`{ accounts: [{ vaults: [{ items: [...] }] }] }`). */
function lerUmPassword(dados: unknown): ResultadoDaLeitura | null {
  if (typeof dados !== 'object' || dados === null) return null
  const raiz = dados as Record<string, unknown>
  if (!Array.isArray(raiz.accounts)) return null

  const credenciais: CredencialImportada[] = []
  let comSenha = 0

  for (const conta of raiz.accounts) {
    const vaults = (conta as Record<string, unknown>)?.vaults
    if (!Array.isArray(vaults)) continue
    for (const cofre of vaults) {
      const itens = (cofre as Record<string, unknown>)?.items
      if (!Array.isArray(itens)) continue
      for (const item of itens) {
        const overview = ((item as Record<string, unknown>)?.overview ??
          {}) as Record<string, unknown>
        const nome = primeiro(overview, ['title'])
        if (!nome) continue
        const detalhes = ((item as Record<string, unknown>)?.details ??
          {}) as Record<string, unknown>
        if (temSenha(detalhes)) comSenha += 1
        credenciais.push({
          name: paraIdentificador(nome),
          username: primeiro(detalhes, ['username', 'loginFields']),
          description: primeiro(overview, ['url']),
          origem: '1Password',
        })
      }
    }
  }

  if (credenciais.length === 0) return null
  return { credenciais, formato: '1Password', ignorados: [], comSenha }
}

/** Lista simples de objetos: o denominador comum de muitas exportações. */
function lerListaGenerica(dados: unknown): ResultadoDaLeitura | null {
  if (!Array.isArray(dados)) return null
  const credenciais: CredencialImportada[] = []
  let comSenha = 0

  for (const item of dados) {
    if (typeof item !== 'object' || item === null) continue
    const obj = item as Record<string, unknown>
    const nome = primeiro(obj, ['name', 'nome', 'title', 'titulo'])
    if (!nome) continue
    if (temSenha(obj)) comSenha += 1
    credenciais.push({
      name: paraIdentificador(nome),
      username: primeiro(obj, ['username', 'usuario', 'user', 'login']),
      description: primeiro(obj, ['description', 'descricao', 'notes', 'url']),
      origem: 'lista JSON',
    })
  }

  if (credenciais.length === 0) return null
  return { credenciais, formato: 'lista JSON', ignorados: [], comSenha }
}

/**
 * Lê o arquivo e devolve as credenciais, qualquer que seja o formato.
 *
 * A ordem das tentativas importa: o formato próprio primeiro, porque é o
 * caso que precisa voltar exatamente como saiu. A lista genérica fica por
 * último — ela casa com quase tudo, e posta antes roubaria os formatos
 * específicos, perdendo os campos que só eles sabem ler.
 */
export function lerCredenciais(texto: string): ResultadoDaLeitura {
  let dados: unknown
  try {
    dados = JSON.parse(texto)
  } catch {
    throw new Error('O arquivo não é um JSON válido.')
  }

  for (const leitor of [
    lerFormatoProprio,
    lerBitwarden,
    lerUmPassword,
    lerListaGenerica,
  ]) {
    const resultado = leitor(dados)
    if (resultado) return resultado
  }

  throw new Error(
    'Não reconheci credenciais neste arquivo. Esperado: a exportação desta ' +
      'tela, um export de Bitwarden ou 1Password, ou uma lista de objetos ' +
      'com "name".',
  )
}
