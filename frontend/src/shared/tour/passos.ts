/**
 * Tours das telas de Segredos.
 *
 * **O que um tour resolve e o que não resolve.** Ele responde "o que é esta
 * tela e por onde começo" — a pergunta de quem chega pela primeira vez. Não
 * substitui rótulo claro nem texto de ajuda: um tour que precisa explicar o
 * que um campo faz está consertando um campo mal nomeado, e o conserto some
 * assim que a pessoa fecha o tour.
 *
 * Por isso cada passo aqui fala de **conceito e sequência**, não de mecânica
 * de botão. "O cofre guarda o valor; o inventário guarda o governo" é algo
 * que nenhum rótulo cabe em três palavras.
 */

export type Passo = {
  /** Título curto: a pessoa lê isto antes de decidir se continua. */
  titulo: string
  /** Dois a quatro períodos. Mais que isso ninguém lê num balão. */
  texto: string
  /**
   * Seletor CSS do elemento a destacar. Ausente = passo de abertura,
   * centralizado, sem âncora.
   */
  alvo?: string
}

export type Tour = {
  /** Identificador estável: é a chave do "já vi" no armazenamento local. */
  id: string
  titulo: string
  passos: Passo[]
}

export const TOUR_COFRES: Tour = {
  id: 'cofres',
  titulo: 'Como os cofres funcionam',
  passos: [
    {
      titulo: 'O cofre guarda o valor',
      texto:
        'Senha, chave e certificado vivem aqui dentro, cifrados. As outras telas de Segredos guardam o governo — de qual equipamento é, quem responde, quando vence — e apontam para cá.',
    },
    {
      titulo: 'A linha inteira abre o cofre',
      texto:
        'Clique em qualquer ponto da linha para ver os segredos lá dentro. Cada revelação de valor vira evento na trilha, com quem revelou e quando.',
      alvo: '[data-tour="linha-cofre"]',
    },
    {
      titulo: 'Selado é diferente de vazio',
      texto:
        'Um cofre selado existe e tem conteúdo, mas ninguém lê até ser reaberto. É a reação a um incidente: interrompe o acesso sem apagar nada.',
      alvo: '[data-tour="estado-cofre"]',
    },
  ],
}

export const TOUR_CREDENCIAIS: Tour = {
  id: 'credenciais',
  titulo: 'Como as credenciais funcionam',
  passos: [
    {
      titulo: 'Aqui fica o governo, não a senha',
      texto:
        'Esta tela registra de qual equipamento a credencial é, quem usa e de quanto em quanto tempo troca. O valor fica no cofre, cifrado.',
    },
    {
      titulo: 'Retirar é exclusivo',
      texto:
        'Quem retira fica com a credencial até devolver — ninguém mais a leva no meio. É o que evita duas pessoas trocando a mesma senha em paralelo e derrubando o acesso uma da outra.',
      alvo: '[data-tour="retirar"]',
    },
    {
      titulo: 'Nunca rotacionada conta como atrasada',
      texto:
        'É o pior caso, não o caso neutro: deixá-la fora do relatório esconderia justamente a senha de fábrica que ninguém trocou.',
      alvo: '[data-tour="rotacao"]',
    },
    {
      titulo: 'Importar traz o governo, nunca o valor',
      texto:
        'Arquivos de gerenciador trazem senha; a importação descarta e avisa quantas descartou. O valor entra pelo cofre, que cifra e audita.',
      alvo: '[data-tour="importar"]',
    },
  ],
}

export const TOUR_CERTIFICADOS: Tour = {
  id: 'certificados',
  titulo: 'Como os certificados funcionam',
  passos: [
    {
      titulo: 'O que vence derruba conexão',
      texto:
        'Certificado vencido não degrada: corta o TLS de uma vez. Por isso a tela ordena pelo que vence primeiro, e não por nome.',
    },
    {
      titulo: 'As faixas são acumuladas',
      texto:
        '"Em até 30 dias" inclui o que vence em 7. Lidas como fatias separadas, parecem não fechar a conta — e alguém conclui que falta certificado em algum lugar.',
      alvo: '[data-tour="faixas"]',
    },
    {
      titulo: 'O arquivo preenche os campos',
      texto:
        'Envie o .pem, .crt ou .cer e titular, emissor, serial e validade são lidos dele. Digitar à mão é onde o serial entra com um dígito a menos — e é por ele que a autoridade emissora identifica o certificado.',
      alvo: '[data-tour="novo-certificado"]',
    },
    {
      titulo: 'A tela mostra o cadastro; o terminal mostra o arquivo',
      texto:
        'Os comandos openssl leem o arquivo instalado de verdade, na máquina onde ele está. Quando os dois divergem — e divergem, porque alguém renovou sem avisar — é o arquivo que vale.',
      alvo: '[data-tour="ver-certificado"]',
    },
  ],
}

export const TOUR_CHAVES: Tour = {
  id: 'chaves-api',
  titulo: 'Como as chaves de API funcionam',
  passos: [
    {
      titulo: 'Chave de API não é senha comum',
      texto:
        'Ela tem serviço, ambiente, escopo e lugar de uso. Sem isso, ninguém sabe o que quebra ao revogá-la — e é por isso que chaves vazadas ficam ativas por anos.',
    },
    {
      titulo: '"Sem uso declarado" é candidata a revogação',
      texto:
        'São chaves ativas que ninguém disse onde usa. Revogue e espere: se nada quebrar, não precisavam existir.',
      alvo: '[data-tour="sem-uso"]',
    },
    {
      titulo: 'O exemplo sai pronto para colar',
      texto:
        'Com endereço e rota preenchidos, a tela monta a requisição e o curl. O valor sai sempre como <valor> — exemplo com chave de verdade vira chave em print de tela e em anexo de chamado.',
      alvo: '[data-tour="ver-exemplo"]',
    },
  ],
}

export const TOUR_DISPOSITIVOS: Tour = {
  id: 'dispositivos',
  titulo: 'Como os dispositivos funcionam',
  passos: [
    {
      titulo: 'O equipamento é a âncora',
      texto:
        'Credenciais e acessos pendem de um dispositivo. É assim que se procura: ninguém pergunta "onde está a senha-root?", pergunta "qual a senha do srv-db-01?".',
    },
    {
      titulo: 'Acesso cadastrado vira conexão pronta',
      texto:
        'Host, porta e usuário informados aqui alimentam a conexão nas outras telas. Cadastrar uma vez evita que cada pessoa monte o comando à sua maneira — e erre a porta.',
      alvo: '[data-tour="acessos"]',
    },
  ],
}

const TOURS: Record<string, Tour> = {
  [TOUR_COFRES.id]: TOUR_COFRES,
  [TOUR_CREDENCIAIS.id]: TOUR_CREDENCIAIS,
  [TOUR_CERTIFICADOS.id]: TOUR_CERTIFICADOS,
  [TOUR_CHAVES.id]: TOUR_CHAVES,
  [TOUR_DISPOSITIVOS.id]: TOUR_DISPOSITIVOS,
}

export function tourDe(id: string): Tour | undefined {
  return TOURS[id]
}

const PREFIXO = 'vault:tour-visto:'

/**
 * Se este tour já foi concluído neste navegador.
 *
 * Em aba anônima ou com armazenamento bloqueado o acesso **lança**, e um
 * tour que derruba a tela ao abrir seria pior que tour nenhum. No erro,
 * responde `false`: a pessoa vê a oferta de novo, que é o lado inofensivo.
 */
export function jaViu(id: string): boolean {
  try {
    return window.localStorage.getItem(PREFIXO + id) === 'sim'
  } catch {
    return false
  }
}

export function marcarVisto(id: string): void {
  try {
    window.localStorage.setItem(PREFIXO + id, 'sim')
  } catch {
    // Sem armazenamento, o tour reaparece na próxima visita. É o degrau
    // suave: incomoda um pouco e não quebra nada.
  }
}

export function esquecerVisto(id: string): void {
  try {
    window.localStorage.removeItem(PREFIXO + id)
  } catch {
    // Idem: nada a recuperar.
  }
}

/**
 * O passo seguinte, limitado ao fim.
 *
 * Função pura para o avanço não depender do componente: é a regra que
 * decide se o botão diz "Próximo" ou "Concluir", e ela precisa de teste.
 */
export function proximoPasso(atual: number, total: number): number {
  return Math.min(atual + 1, Math.max(total - 1, 0))
}

export function passoAnterior(atual: number): number {
  return Math.max(atual - 1, 0)
}

export function ehUltimo(atual: number, total: number): boolean {
  return atual >= total - 1
}
