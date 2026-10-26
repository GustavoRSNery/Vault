import type { ComponentType } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import {
  IconeAlerta,
  IconeAplicacao,
  IconeBusca,
  IconeCertificado,
  IconeChave,
  IconeCofre,
  IconeConfiguracao,
  IconeConvite,
  IconeCredencial,
  IconeDispositivo,
  IconeGravacao,
  IconeIntegracao,
  IconePainel,
  IconePerfil,
  IconePessoas,
  IconePolitica,
  IconeSair,
  IconeSessao,
  IconeSolicitacao,
  IconeTrilha,
} from './icones'

type Item = {
  para: string
  rotulo: string
  fim: boolean
  Icone: ComponentType<{ className?: string }>
}

export type Area = {
  /** Identificador estável; não aparece na tela. */
  id: string
  titulo: string
  /** Frase de uma linha sob o título, na abertura da área. */
  resumo: string
  Icone: ComponentType<{ className?: string }>
  /**
   * Pelo menos um item, declarado no tipo e não só por convenção: o primeiro
   * é o destino da pílula lá em cima. Uma área sem itens levaria a pílula a
   * lugar nenhum, e com `noUncheckedIndexedAccess` o erro apareceria como um
   * `undefined` solto longe daqui, na hora de montar o link.
   */
  itens: [Item, ...Item[]]
  /** Só para quem administra. */
  admin?: boolean
}

/** Lista que o tipo garante não-vazia — ver o fallback de `areaDoCaminho`. */
type Areas = [Area, ...Area[]]

/**
 * As **áreas** do sistema: a barra superior escolhe uma, a lateral navega
 * dentro dela.
 *
 * Estes eram os grupos da lateral, empilhados. A divisão continua sendo por
 * *pergunta que a pessoa tem na cabeça* — onde o segredo mora, o que já
 * aconteceu com ele, quem pediu o quê — e não por entidade do sistema; o que
 * mudou é onde ela aparece. Empilhados, os vinte itens das cinco áreas
 * tomavam a lateral inteira; a barra superior mostra as cinco de uma vez e a
 * lateral passa a mostrar no máximo seis itens.
 *
 * "Visão geral" é a primeira de propósito: é o ponto de partida e o retorno.
 */
export const AREAS: Areas = [
  {
    id: 'visao-geral',
    titulo: 'Visão geral',
    resumo: 'O estado do cofre agora: painel, busca e o que pede atenção.',
    Icone: IconePainel,
    itens: [
      { para: '/', rotulo: 'Painel', fim: true, Icone: IconePainel },
      { para: '/busca', rotulo: 'Busca', fim: false, Icone: IconeBusca },
      { para: '/alertas', rotulo: 'Alertas', fim: false, Icone: IconeAlerta },
    ],
  },
  {
    id: 'segredos',
    titulo: 'Segredos',
    resumo: 'Onde o segredo mora: cofres, credenciais, certificados e chaves.',
    Icone: IconeCofre,
    itens: [
      { para: '/cofres', rotulo: 'Cofres', fim: false, Icone: IconeCofre },
      {
        para: '/credenciais',
        rotulo: 'Credenciais',
        fim: false,
        Icone: IconeCredencial,
      },
      {
        para: '/certificados',
        rotulo: 'Certificados',
        fim: false,
        Icone: IconeCertificado,
      },
      { para: '/chaves-api', rotulo: 'Chaves de API', fim: false, Icone: IconeChave },
      {
        para: '/dispositivos',
        rotulo: 'Dispositivos',
        fim: false,
        Icone: IconeDispositivo,
      },
    ],
  },
  {
    id: 'uso',
    titulo: 'Uso e histórico',
    resumo: 'O que já aconteceu: quem pediu, quem acessou e o que ficou gravado.',
    Icone: IconeTrilha,
    itens: [
      {
        para: '/solicitacoes',
        rotulo: 'Solicitações',
        fim: false,
        Icone: IconeSolicitacao,
      },
      { para: '/sessoes', rotulo: 'Sessões SSH', fim: true, Icone: IconeSessao },
      {
        para: '/sessoes/gravacoes',
        rotulo: 'Gravações',
        fim: false,
        Icone: IconeGravacao,
      },
      { para: '/auditoria', rotulo: 'Auditoria', fim: false, Icone: IconeTrilha },
    ],
  },
  {
    id: 'conta',
    titulo: 'Minha conta',
    resumo: 'Seus dados de acesso: nome, foto, e-mail, senha e segundo fator.',
    Icone: IconePerfil,
    itens: [{ para: '/perfil', rotulo: 'Perfil', fim: false, Icone: IconePerfil }],
  },
  {
    // Esconder não é proteger: as rotas da API checam a política por
    // requisição, independentemente do que o menu mostra.
    id: 'admin',
    titulo: 'Administração',
    resumo: 'Quem pode o quê, e como o cofre conversa com o resto.',
    Icone: IconeConfiguracao,
    admin: true,
    itens: [
      { para: '/admin/usuarios', rotulo: 'Pessoas', fim: false, Icone: IconePessoas },
      {
        para: '/admin/politicas',
        rotulo: 'Políticas',
        fim: false,
        Icone: IconePolitica,
      },
      { para: '/admin/convites', rotulo: 'Convites', fim: false, Icone: IconeConvite },
      {
        para: '/admin/aplicacoes',
        rotulo: 'Aplicações',
        fim: false,
        Icone: IconeAplicacao,
      },
      {
        para: '/admin/integracoes',
        rotulo: 'Integrações',
        fim: false,
        Icone: IconeIntegracao,
      },
      {
        para: '/admin/configuracao',
        rotulo: 'Configurações',
        fim: false,
        Icone: IconeConfiguracao,
      },
    ],
  },
]

/**
 * Qual área cobre este caminho.
 *
 * Casa por prefixo e fica com o **mais longo** que casar. Ordem de
 * declaração não serve: `/sessoes/gravacoes` casa tanto com `/sessoes`
 * quanto consigo mesmo, e varrer na ordem entregaria o primeiro — a área
 * certa só por sorte. O mais longo é sempre o item mais específico.
 *
 * `/` casa com tudo por prefixo, então fica fora da comparação: sem essa
 * ressalva toda rota cairia em "Visão geral" e a barra nunca mudaria.
 *
 * O prefixo tem de terminar em `/`: sem isso, `/cofres-antigos` casaria com
 * `/cofres` e abriria a área errada — e um caminho que não é filho daquele
 * item apareceria como se fosse.
 */
export function areaDoCaminho(caminho: string, areas: Area[] = AREAS): Area {
  let melhor: Area | null = null
  let tamanho = 0
  for (const area of areas) {
    for (const item of area.itens) {
      if (item.para === '/') continue
      const casa = caminho === item.para || caminho.startsWith(`${item.para}/`)
      if (casa && item.para.length > tamanho) {
        melhor = area
        tamanho = item.para.length
      }
    }
  }
  // Rota desconhecida (a 404, por exemplo) cai no fallback: a barra mostra a
  // primeira área em vez de ficar sem nenhuma marcada.
  //
  // `AREAS[0]` como último recurso e não `areas[0]`: `areas` é a lista já
  // filtrada por permissão e pode chegar vazia — se todas as áreas fossem
  // de admin, `areas[0]` seria `undefined` e a tela quebraria ao ler o
  // título. A primeira área da lista completa é visível para todos.
  return melhor ?? areas[0] ?? AREAS[0]
}

export function Layout() {
  const { usuario, sair } = useAuth()
  const { pathname } = useLocation()

  const iniciais = (usuario?.full_name ?? '?')
    .split(' ')
    .slice(0, 2)
    .map((parte) => parte.charAt(0).toUpperCase())
    .join('')

  const visiveis = AREAS.filter((area) => !area.admin || usuario?.is_admin)
  const atual = areaDoCaminho(pathname, visiveis)

  return (
    <div className="app">
      {/* A barra atravessa a largura inteira: é o nível de cima da
          navegação, e recuá-la para começar depois da lateral a faria
          parecer subordinada ao que está embaixo dela. */}
      <header className="topnav">
        <div className="logo">
          <span className="mark" aria-hidden="true">
            <strong>V</strong>
          </span>
          <span>
            <b>Vault</b>
            <small>de senhas</small>
          </span>
        </div>

        <nav className="areas" aria-label="Áreas do sistema">
          <span className="areas-cap" aria-hidden="true">
            Áreas
          </span>
          <div className="areas-pilulas">
            {visiveis.map((area) => {
              const ativa = area.id === atual.id
              return (
                <NavLink
                  key={area.id}
                  to={area.itens[0].para}
                  className={`area-btn${ativa ? ' active' : ''}`}
                  // `aria-current="page"` seria mentira: o link leva ao
                  // primeiro item da área, não necessariamente à página
                  // aberta. "true" diz só "é este o contexto atual".
                  aria-current={ativa ? 'true' : undefined}
                  title={area.titulo}
                >
                  <area.Icone className="area-icone" />
                  {/* O rótulo some em tela estreita (ver CSS), mas continua
                      no HTML: é ele que o leitor de tela anuncia, e um
                      botão só com ícone não diz nada a quem não enxerga. */}
                  <span className="area-rotulo">{area.titulo}</span>
                </NavLink>
              )
            })}
          </div>
        </nav>

        <div className="topnav-conta">
          {/* A foto, quando existe, no lugar das iniciais. `title` com o
              e-mail nos dois casos: é como se confere de qual conta é a
              sessão sem abrir o perfil. */}
          {usuario?.foto ? (
            <img
              className="avatar avatar-img"
              src={usuario.foto}
              title={usuario.email}
              alt={`Foto de ${usuario.apelido || usuario.full_name}`}
            />
          ) : (
            <span className="avatar" title={usuario?.email ?? ''} aria-hidden="true">
              {iniciais}
            </span>
          )}
        </div>
      </header>

      <div className="corpo">
        <nav className="sidebar" aria-label={`Navegação de ${atual.titulo}`}>
          {/* O título da área se repete aqui de propósito: a pílula lá em
              cima é pequena e fica longe do olhar de quem já desceu para a
              lateral — sem esta âncora, a lateral trocaria de conteúdo sem
              dizer por quê. */}
          <div className="sidebar-area">
            <div className="sidebar-area-topo">
              <atual.Icone className="sidebar-area-icone" />
              <b>{atual.titulo}</b>
            </div>
            <p className="sidebar-area-resumo">{atual.resumo}</p>
          </div>

          <div className="nav-grupo">
            {atual.itens.map((item) => (
              <NavLink
                key={item.para}
                to={item.para}
                end={item.fim}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                <item.Icone className="nav-icone" />
                <span>{item.rotulo}</span>
              </NavLink>
            ))}
          </div>

          <div className="foot">
            <button type="button" className="nav-item nav-sair" onClick={sair}>
              <IconeSair className="nav-icone" />
              <span>Sair</span>
            </button>
          </div>
        </nav>

        <main className="main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
