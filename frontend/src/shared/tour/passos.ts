/**
 * Tours das telas: Segredos, Uso e histórico, e o perfil.
 *
 * Um tour responde "o que é esta tela e por onde começo", para quem chega
 * pela primeira vez. Não substitui rótulo claro: um tour que precisa
 * explicar o que um campo faz está consertando um campo mal nomeado, e o
 * conserto some assim que a pessoa fecha o tour.
 *
 * **Como escrever um passo.** O título diz o que é, em palavras que a
 * pessoa usaria. O texto diz o que ela faz ali, e só então por quê, se o
 * porquê mudar a decisão dela.
 *
 * O que evitar, porque a primeira versão destes textos tinha tudo isto:
 * título que é tese em vez de rótulo ("Selado é diferente de vazio");
 * travessão emendando uma sentença de efeito no fim; frase de palestra
 * ("é o que transforma uma conta invadida em desastre"); e doutrina de
 * segurança antes de dizer para que serve a tela. Quem abre o tour quer
 * saber o que fazer, não ser convencido.
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
      titulo: 'O que é um cofre',
      texto:
        'É onde ficam guardadas as senhas, chaves e certificados, cifrados. As outras telas de Segredos guardam só os dados de controle (de qual máquina é, quem responde, quando vence) e apontam para cá.',
    },
    {
      titulo: 'Clique na linha para abrir',
      texto:
        'Qualquer ponto da linha abre o cofre e mostra o que tem dentro. Toda vez que alguém revela um valor, fica registrado quem revelou e quando.',
      alvo: '[data-tour="linha-cofre"]',
    },
    {
      titulo: 'Cofre selado continua cheio',
      texto:
        'Selar bloqueia a leitura sem apagar nada: o conteúdo continua lá e volta quando o cofre for reaberto. Serve para cortar o acesso rápido, quando há suspeita de problema.',
      alvo: '[data-tour="estado-cofre"]',
    },
  ],
}

export const TOUR_CREDENCIAIS: Tour = {
  id: 'credenciais',
  titulo: 'Como as credenciais funcionam',
  passos: [
    {
      titulo: 'Esta tela não guarda a senha',
      texto:
        'Aqui ficam os dados de controle: de qual máquina a credencial é, quem usa e de quanto em quanto tempo precisa ser trocada. A senha em si fica no cofre, cifrada.',
    },
    {
      titulo: 'Retirar reserva para você',
      texto:
        'Enquanto você está com a credencial, ninguém mais consegue retirá-la. Isso evita duas pessoas trocarem a mesma senha ao mesmo tempo e uma derrubar o acesso da outra.',
      alvo: '[data-tour="retirar"]',
    },
    {
      titulo: 'Nunca trocada aparece como atrasada',
      texto:
        'Uma credencial que nunca foi rotacionada entra na lista de atrasadas. É normalmente a senha que veio de fábrica e ninguém mexeu, então é a que mais precisa aparecer.',
      alvo: '[data-tour="rotacao"]',
    },
    {
      titulo: 'A importação descarta as senhas',
      texto:
        'Arquivos exportados de gerenciadores costumam vir com as senhas dentro. A importação traz só os dados de controle, descarta o resto e avisa quantas descartou. As senhas você cadastra pelo cofre.',
      alvo: '[data-tour="importar"]',
    },
  ],
}

export const TOUR_CERTIFICADOS: Tour = {
  id: 'certificados',
  titulo: 'Como os certificados funcionam',
  passos: [
    {
      titulo: 'Ordenados por quem vence antes',
      texto:
        'A lista começa pelo certificado mais próximo de vencer, e não por nome. Quando um certificado vence, o site ou serviço para de funcionar na hora, sem aviso.',
    },
    {
      titulo: 'As faixas somam umas às outras',
      texto:
        'O que vence em 7 dias também está contado em "até 30 dias". Se você somar as faixas esperando chegar ao total, vai dar número errado.',
      alvo: '[data-tour="faixas"]',
    },
    {
      titulo: 'Envie o arquivo em vez de digitar',
      texto:
        'Com o .pem, .crt ou .cer, o sistema lê titular, emissor, serial e validade sozinho. Digitar à mão costuma dar erro no serial, que é um número longo e é por ele que a emissora identifica o certificado.',
      alvo: '[data-tour="novo-certificado"]',
    },
    {
      titulo: 'Confira o que está instalado',
      texto:
        'Esta tela mostra o que foi cadastrado aqui. Os comandos openssl leem o arquivo que está rodando na máquina. Se os dois não baterem, vale o que está na máquina: alguém renovou e não avisou.',
      alvo: '[data-tour="ver-certificado"]',
    },
  ],
}

export const TOUR_CHAVES: Tour = {
  id: 'chaves-api',
  titulo: 'Como as chaves de API funcionam',
  passos: [
    {
      titulo: 'Anote onde cada chave é usada',
      texto:
        'Além da chave, cadastre o serviço, o ambiente e em que sistema ela é usada. É essa informação que permite revogar uma chave sabendo o que vai parar de funcionar.',
    },
    {
      titulo: 'Chaves sem uso declarado',
      texto:
        'São chaves ativas que ninguém registrou onde usa. Uma forma de resolver: revogue e espere. Se nada parar de funcionar, a chave não era necessária.',
      alvo: '[data-tour="sem-uso"]',
    },
    {
      titulo: 'Exemplo pronto para copiar',
      texto:
        'Preenchendo o endereço e a rota, a tela monta a requisição e o comando curl. No lugar da chave aparece sempre <valor>, para o exemplo poder ser colado em chamado ou print sem vazar nada.',
      alvo: '[data-tour="ver-exemplo"]',
    },
  ],
}

export const TOUR_DISPOSITIVOS: Tour = {
  id: 'dispositivos',
  titulo: 'Como os dispositivos funcionam',
  passos: [
    {
      titulo: 'Procure pela máquina',
      texto:
        'Cada credencial e cada acesso pertencem a um equipamento. Na prática é assim que se procura: ninguém lembra do nome da senha, lembra que precisa entrar no srv-db-01.',
    },
    {
      titulo: 'Cadastre o acesso uma vez só',
      texto:
        'O endereço, a porta e o usuário informados aqui são reaproveitados pelas outras telas na hora de conectar. Assim ninguém precisa montar o comando de cabeça e errar a porta.',
      alvo: '[data-tour="acessos"]',
    },
  ],
}

// ------------------------------------------------- tours de Uso e histórico

export const TOUR_SOLICITACOES: Tour = {
  id: 'solicitacoes',
  titulo: 'Como o acesso é pedido e concedido',
  passos: [
    {
      titulo: 'O acesso tem prazo',
      texto:
        'Em vez de deixar todo mundo com acesso permanente a tudo, aqui você pede o acesso quando precisa dele, por um tempo determinado. Vencido o prazo, ele cai sozinho, sem ninguém precisar lembrar de remover.',
    },
    {
      titulo: 'Fila de aprovação',
      texto:
        'Se você pode aprovar, vê aqui os pedidos de todo mundo, com o motivo e o prazo de cada um. Dá para aprovar vários de uma vez quando chegam muitos pedidos iguais.',
      alvo: '[data-tour="fila-aprovacao"]',
    },
    {
      titulo: 'Seus pedidos',
      texto:
        'O que você pediu, se já foi respondido e até quando o acesso vale. Os pedidos recusados também ficam na lista, com a decisão registrada.',
      alvo: '[data-tour="meus-pedidos"]',
    },
  ],
}

export const TOUR_SESSOES: Tour = {
  id: 'sessoes',
  titulo: 'Como as sessões funcionam',
  passos: [
    {
      titulo: 'O que é uma sessão',
      texto:
        'Toda vez que alguém entra numa máquina pelo Vault, fica registrado quem entrou, onde, por que motivo e por quanto tempo. É o que responde depois quem estava no servidor em determinado horário.',
    },
    {
      titulo: 'Os três números são diferentes',
      texto:
        'Sessões abertas, pessoas conectadas e máquinas em uso raramente são iguais: uma pessoa pode abrir duas sessões, e duas pessoas podem estar na mesma máquina.',
      alvo: '[data-tour="metricas-sessoes"]',
    },
    {
      titulo: 'Encerrar a sessão de outra pessoa',
      texto:
        'Você pode cortar o acesso de alguém na hora, e fica registrado que foi você quem cortou. O que já tinha sido feito continua gravado: encerrar não apaga a gravação.',
      alvo: '[data-tour="sessoes-outras"]',
    },
  ],
}

export const TOUR_GRAVACOES: Tour = {
  id: 'gravacoes',
  titulo: 'Como as gravações funcionam',
  passos: [
    {
      titulo: 'O que fica gravado',
      texto:
        'Tudo o que foi digitado na sessão e tudo o que a máquina respondeu, com o horário de cada coisa. Dá para assistir depois, seja para revisar uma mudança, ensinar alguém ou entender o que causou um problema.',
    },
    {
      titulo: 'A barra mostra os momentos de uso',
      texto:
        'Uma sessão de 40 minutos pode ter tido 2 minutos de trabalho ou 40. A barra mostra em quais trechos houve digitação, para você pular direto para o que interessa.',
      alvo: '[data-tour="barra-atividade"]',
    },
    {
      titulo: 'Não dá para editar nem apagar',
      texto:
        'O sistema não oferece como alterar uma gravação, de propósito: se desse para reescrever, ela não serviria de comprovação. Quando o armazenamento configurado não garante isso, a tela avisa.',
      alvo: '[data-tour="linha-gravacao"]',
    },
  ],
}

export const TOUR_AUDITORIA: Tour = {
  id: 'auditoria',
  titulo: 'Como a trilha funciona',
  passos: [
    {
      titulo: 'Os registros são encadeados',
      texto:
        'Cada evento guarda uma marca do evento anterior, como elos de uma corrente. Se alguém apagar ou alterar um registro do meio, os elos deixam de encaixar e esta tela mostra onde quebrou.',
    },
    {
      titulo: 'O que "íntegra" quer dizer aqui',
      texto:
        'Quer dizer que os elos encaixam: nada foi alterado. Mas quem tivesse controle total do sistema poderia refazer a corrente inteira. Por isso existe a cópia externa, explicada no passo seguinte.',
      alvo: '[data-tour="integridade"]',
    },
    {
      titulo: 'Exportar guarda uma cópia fora',
      texto:
        'Exportar envia os eventos novos para um destino que o Vault não consegue alterar depois. Assim a comparação deixa de depender só do próprio sistema. Se o destino configurado não for desse tipo, a tela avisa.',
      alvo: '[data-tour="exportar-trilha"]',
    },
  ],
}

export const TOUR_PERFIL: Tour = {
  id: 'perfil',
  titulo: 'Sua conta',
  passos: [
    {
      titulo: 'Seus dados',
      texto:
        'Aqui você altera os seus próprios dados e cuida da segurança da sua conta. Nada do que você mudar nesta tela afeta outras pessoas. Permissões e papéis ficam na tela de Administração.',
    },
    {
      titulo: 'Apelido e nome completo',
      texto:
        'O apelido é como você aparece nas telas do dia a dia. O nome completo é o que fica nos registros de auditoria e nas sessões, onde alguém pode precisar identificar você meses depois.',
      alvo: '[data-tour="editar-perfil"]',
    },
    {
      titulo: 'Para trocar e-mail ou senha, confirme a senha atual',
      texto:
        'É uma proteção para o caso de alguém pegar seu computador desbloqueado ou roubar seu acesso: sem saber a sua senha, a pessoa não consegue trocar o e-mail nem a senha e deixar você de fora da conta.',
    },
    {
      titulo: 'Verificação em duas etapas',
      texto:
        'Com ela ativada, saber a sua senha não basta para entrar: é pedido também um código que só aparece no seu celular. Vale a pena ativar.',
    },
  ],
}

const TOURS: Record<string, Tour> = {
  [TOUR_COFRES.id]: TOUR_COFRES,
  [TOUR_CREDENCIAIS.id]: TOUR_CREDENCIAIS,
  [TOUR_CERTIFICADOS.id]: TOUR_CERTIFICADOS,
  [TOUR_CHAVES.id]: TOUR_CHAVES,
  [TOUR_DISPOSITIVOS.id]: TOUR_DISPOSITIVOS,
  [TOUR_SOLICITACOES.id]: TOUR_SOLICITACOES,
  [TOUR_SESSOES.id]: TOUR_SESSOES,
  [TOUR_GRAVACOES.id]: TOUR_GRAVACOES,
  [TOUR_AUDITORIA.id]: TOUR_AUDITORIA,
  [TOUR_PERFIL.id]: TOUR_PERFIL,
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
