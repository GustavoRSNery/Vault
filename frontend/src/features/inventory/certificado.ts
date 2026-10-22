/**
 * Leitura de um certificado X.509 para preencher o formulário.
 *
 * **Por que ler no navegador em vez de mandar para o servidor decifrar.** O
 * certificado é público — é o que o servidor apresenta a qualquer cliente —
 * então lê-lo aqui não expõe nada. E preencher subject, emissor, validade e
 * serial sozinho elimina a digitação, que é justamente onde `CN=` entra
 * truncado e o serial entra com um dígito a menos.
 *
 * **O que isto NÃO faz:** validar cadeia, conferir assinatura ou abrir
 * `.pfx`. Um `.pfx` é um container cifrado com senha — abri-lo exigiria a
 * senha na tela, e a senha do `.pfx` é um segredo do cofre. Para `.pfx` a
 * tela pede os campos e guarda o arquivo; para `.pem`/`.cer` ela lê.
 *
 * O parser cobre a estrutura X.509 que interessa (TBSCertificate: serial,
 * emissor, validade, titular). Escrevê-lo aqui, em ~200 linhas legíveis,
 * evita uma dependência de terceiro no caminho que processa arquivo de
 * origem externa — que é exatamente onde uma dependência comprometida faria
 * mais estrago.
 */

export type DadosDoCertificado = {
  subject: string
  issuer: string
  serial: string
  notBefore: string
  notAfter: string
}

/** Um nó DER: etiqueta, conteúdo e onde o próximo começa. */
type No = { tag: number; inicio: number; fim: number; proximo: number }

/**
 * Um byte, ou erro se a posição passou do fim.
 *
 * Este parser lê arquivo escolhido pela pessoa, e passar do fim é o modo
 * normal de falha de um arquivo truncado. Ler `undefined` e seguir produziria
 * `NaN` silencioso — uma data inválida em vez de uma mensagem.
 */
function byte(bytes: Uint8Array, posicao: number): number {
  const valor = bytes[posicao]
  if (valor === undefined) {
    throw new Error('O arquivo termina antes do esperado para um certificado.')
  }
  return valor
}

function lerNo(bytes: Uint8Array, posicao: number): No {
  const tag = byte(bytes, posicao)
  let p = posicao + 1
  let tamanho = byte(bytes, p)
  p += 1

  if (tamanho & 0x80) {
    const octetos = tamanho & 0x7f
    if (octetos === 0 || octetos > 4) {
      throw new Error('Comprimento DER fora do esperado para um certificado.')
    }
    tamanho = 0
    for (let i = 0; i < octetos; i += 1) {
      tamanho = tamanho * 256 + byte(bytes, p)
      p += 1
    }
  }

  const fim = p + tamanho
  if (fim > bytes.length) throw new Error('O arquivo termina antes do esperado.')
  return { tag, inicio: p, fim, proximo: fim }
}

/** Filhos diretos de um nó construído (SEQUENCE, SET). */
function filhos(bytes: Uint8Array, no: No): No[] {
  const lista: No[] = []
  let p = no.inicio
  while (p < no.fim) {
    const filho = lerNo(bytes, p)
    lista.push(filho)
    p = filho.proximo
  }
  return lista
}

/** Nomes curtos dos atributos de Distinguished Name, por OID. */
const OIDS: Record<string, string> = {
  '2.5.4.3': 'CN',
  '2.5.4.6': 'C',
  '2.5.4.7': 'L',
  '2.5.4.8': 'ST',
  '2.5.4.10': 'O',
  '2.5.4.11': 'OU',
  '1.2.840.113549.1.9.1': 'E',
}

function lerOid(bytes: Uint8Array, no: No): string {
  const partes: number[] = []
  const primeiro = byte(bytes, no.inicio)
  partes.push(Math.floor(primeiro / 40), primeiro % 40)

  let valor = 0
  for (let p = no.inicio + 1; p < no.fim; p += 1) {
    const atual = byte(bytes, p)
    valor = valor * 128 + (atual & 0x7f)
    if (!(atual & 0x80)) {
      partes.push(valor)
      valor = 0
    }
  }
  return partes.join('.')
}

function lerTexto(bytes: Uint8Array, no: No): string {
  const fatia = bytes.subarray(no.inicio, no.fim)
  // BMPString (tag 30) é UTF-16BE; o resto, na prática, é UTF-8 ou ASCII.
  if (no.tag === 0x1e) {
    let saida = ''
    for (let i = 0; i + 1 < fatia.length; i += 2) {
      saida += String.fromCharCode((byte(fatia, i) << 8) | byte(fatia, i + 1))
    }
    return saida
  }
  return new TextDecoder('utf-8').decode(fatia)
}

/** Um DN vira "CN=exemplo.com.br, O=Empresa" — a forma que todos leem. */
function lerNome(bytes: Uint8Array, no: No): string {
  const partes: string[] = []
  for (const conjunto of filhos(bytes, no)) {
    for (const par of filhos(bytes, conjunto)) {
      const [chave, valor] = filhos(bytes, par)
      if (chave === undefined || valor === undefined) continue
      const oid = lerOid(bytes, chave)
      const rotulo = OIDS[oid] ?? oid
      partes.push(`${rotulo}=${lerTexto(bytes, valor)}`)
    }
  }
  return partes.join(', ')
}

/** UTCTime (AAMMDD) e GeneralizedTime (AAAAMMDD) viram ISO. */
function lerData(bytes: Uint8Array, no: No): string {
  const texto = lerTexto(bytes, no)
  const m =
    no.tag === 0x17
      ? texto.match(/^(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?Z?$/)
      : texto.match(/^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?Z?$/)
  if (!m) throw new Error(`Data do certificado em formato inesperado: ${texto}`)

  let ano = Number(m[1])
  // RFC 5280: em UTCTime, 50-99 é 19xx e 00-49 é 20xx.
  if (no.tag === 0x17) ano += ano >= 50 ? 1900 : 2000
  const iso =
    `${String(ano).padStart(4, '0')}-${m[2] ?? '01'}-${m[3] ?? '01'}` +
    `T${m[4] ?? '00'}:${m[5] ?? '00'}:${m[6] ?? '00'}Z`
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) {
    throw new Error(`Data do certificado inválida: ${texto}`)
  }
  return data.toISOString()
}

/**
 * O serial em hexadecimal, byte a byte.
 *
 * **Sem cortar zeros à esquerda.** Pareceria razoável tratá-los como padding
 * de sinal do DER, mas o `openssl x509 -noout -serial` imprime todos os
 * bytes — um serial que começa com `08` é impresso `08…`. Cortar produziria
 * um valor que não casa com o que a autoridade emissora informa, e o serial
 * só serve justamente para conferir contra ela.
 */
function lerSerial(bytes: Uint8Array, no: No): string {
  let hex = ''
  for (let p = no.inicio; p < no.fim; p += 1) {
    hex += byte(bytes, p).toString(16).padStart(2, '0')
  }
  return hex.toUpperCase() || '0'
}

/** Converte PEM em DER; bytes já binários passam direto. */
export function paraDer(conteudo: Uint8Array): Uint8Array {
  const texto = new TextDecoder('utf-8').decode(conteudo.subarray(0, 64))
  if (!texto.includes('-----BEGIN')) return conteudo

  const completo = new TextDecoder('utf-8').decode(conteudo)
  const corpo = completo
    .replace(/-----BEGIN [^-]+-----/g, '')
    .replace(/-----END [^-]+-----/g, '')
    .replace(/\s+/g, '')
  const binario = atob(corpo)
  const saida = new Uint8Array(binario.length)
  for (let i = 0; i < binario.length; i += 1) saida[i] = binario.charCodeAt(i)
  return saida
}

/**
 * Extrai os campos do certificado.
 *
 * Lança com mensagem legível quando o arquivo não é X.509 — e a tela então
 * oferece o preenchimento manual, em vez de deixar a pessoa sem saída.
 */
export function lerCertificado(conteudo: Uint8Array): DadosDoCertificado {
  const der = paraDer(conteudo)
  if (der.length === 0 || der[0] !== 0x30) {
    throw new Error('Não parece um certificado X.509 (.pem, .crt ou .cer).')
  }

  const raiz = lerNo(der, 0)
  const [tbs] = filhos(der, raiz)
  if (!tbs) throw new Error('Certificado sem conteúdo legível.')

  const campos = filhos(der, tbs)
  // O campo `version` é opcional e vem marcado com [0] (tag 0xa0). Quando
  // existe, tudo depois dele anda uma casa — e ignorar isso é o erro que faz
  // o emissor aparecer como titular.
  const base = campos[0]?.tag === 0xa0 ? 1 : 0

  const serial = campos[base]
  const emissor = campos[base + 2]
  const validade = campos[base + 3]
  const titular = campos[base + 4]
  if (!serial || !emissor || !validade || !titular) {
    throw new Error('Certificado sem os campos esperados de um X.509.')
  }

  const [inicio, fim] = filhos(der, validade)
  if (inicio === undefined || fim === undefined) {
    throw new Error('Certificado sem as datas de validade.')
  }
  return {
    serial: lerSerial(der, serial),
    issuer: lerNome(der, emissor),
    subject: lerNome(der, titular),
    notBefore: lerData(der, inicio),
    notAfter: lerData(der, fim),
  }
}

/**
 * Os comandos que conferem o certificado na máquina de quem o usa.
 *
 * A tela mostra o que *nós* guardamos; estes comandos leem o arquivo de
 * verdade, do lado de quem vai instalá-lo. É a diferença entre o inventário
 * e o fato — e quando os dois divergem, é o fato que vale.
 */
export function comandosOpenssl(arquivo: string, temChavePrivada: boolean): {
  titulo: string
  comando: string
  explica: string
}[] {
  const nome = arquivo || 'certificado.pem'
  const comandos = [
    {
      titulo: 'Ver tudo',
      comando: `openssl x509 -in ${nome} -text -noout`,
      explica: 'Titular, emissor, validade, extensões e uso da chave.',
    },
    {
      titulo: 'Só a validade',
      comando: `openssl x509 -in ${nome} -noout -dates`,
      explica: 'Responde "venceu?" sem rolar a saída inteira.',
    },
    {
      titulo: 'Impressão digital',
      comando: `openssl x509 -in ${nome} -noout -fingerprint -sha256`,
      explica:
        'Confere se o arquivo em mãos é o mesmo que foi emitido — compare com quem emitiu.',
    },
    {
      titulo: 'Domínios cobertos',
      comando: `openssl x509 -in ${nome} -noout -ext subjectAltName`,
      explica: 'O CN sozinho engana: navegador moderno valida pelo SAN.',
    },
  ]

  if (temChavePrivada) {
    comandos.push({
      titulo: 'Abrir o .pfx',
      comando: `openssl pkcs12 -in ${nome} -info -nodes`,
      explica:
        'Pede a senha do arquivo. Rode só em máquina de confiança: -nodes escreve a chave privada em claro na saída.',
    })
    comandos.push({
      titulo: 'A chave bate com o certificado?',
      comando: `openssl x509 -noout -modulus -in cert.pem | openssl md5\nopenssl rsa -noout -modulus -in chave.pem | openssl md5`,
      explica:
        'Os dois md5 têm de ser iguais. Diferentes, o serviço sobe e recusa toda conexão.',
    })
  }

  return comandos
}
