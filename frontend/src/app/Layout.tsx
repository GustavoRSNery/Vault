import type { ComponentType } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
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

type Grupo = {
  titulo: string
  itens: Item[]
  /** Só para quem administra. */
  admin?: boolean
}

/**
 * O menu, agrupado por **pergunta que a pessoa tem na cabeça**, não por
 * entidade do sistema.
 *
 * Treze itens numa lista corrida obrigam a ler todos para achar um: sem
 * agrupamento não há onde parar a busca visual. Os grupos aqui separam
 * *onde o segredo mora* de *o que já aconteceu com ele* e de *quem pediu o
 * quê* — que é como alguém pensa ao procurar, e não "cofres, dispositivos,
 * credenciais, certificados" em sequência indistinta.
 *
 * "Visão geral" fica sozinha em cima de propósito: é o ponto de partida e o
 * retorno, e empurrá-la para dentro de um grupo a esconderia.
 */
const GRUPOS: Grupo[] = [
  {
    titulo: 'Visão geral',
    itens: [
      { para: '/', rotulo: 'Painel', fim: true, Icone: IconePainel },
      { para: '/busca', rotulo: 'Busca', fim: false, Icone: IconeBusca },
      { para: '/alertas', rotulo: 'Alertas', fim: false, Icone: IconeAlerta },
    ],
  },
  {
    titulo: 'Segredos',
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
    titulo: 'Uso e histórico',
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
    // Sozinho num grupo próprio: "Perfil" não é nem segredo nem histórico, e
    // enfiá-lo num dos dois obrigaria a procurá-lo no lugar errado.
    titulo: 'Minha conta',
    itens: [{ para: '/perfil', rotulo: 'Perfil', fim: false, Icone: IconePerfil }],
  },
  {
    // Esconder não é proteger: as rotas da API checam a política por
    // requisição, independentemente do que o menu mostra.
    titulo: 'Administração',
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

export function Layout() {
  const { usuario, sair } = useAuth()
  const iniciais = (usuario?.full_name ?? '?')
    .split(' ')
    .slice(0, 2)
    .map((parte) => parte.charAt(0).toUpperCase())
    .join('')

  const visiveis = GRUPOS.filter((grupo) => !grupo.admin || usuario?.is_admin)

  return (
    <div className="app">
      <nav className="sidebar" aria-label="Navegação principal">
        <div className="logo">
          <span className="mark" aria-hidden="true">
            <strong>V</strong>
          </span>
          <span>
            <b>Vault</b>
            <small>de senhas</small>
          </span>
        </div>

        {visiveis.map((grupo) => (
          // `<section>` com `aria-label` e não `<div>`: assim o leitor de
          // tela anuncia o grupo e permite pular de um para o outro, que é o
          // mesmo atalho que o título dá a quem enxerga.
          <section key={grupo.titulo} aria-label={grupo.titulo} className="nav-grupo">
            <div className="nav-cap">{grupo.titulo}</div>
            {grupo.itens.map((item) => (
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
          </section>
        ))}

        <div className="foot">
          <button type="button" className="nav-item nav-sair" onClick={sair}>
            <IconeSair className="nav-icone" />
            <span>Sair</span>
          </button>
        </div>
      </nav>

      <main className="main">
        <div className="topbar">
          <span className="spacer" />
          <span className="avatar" title={usuario?.email ?? ''} aria-hidden="true">
            {iniciais}
          </span>
        </div>
        <Outlet />
      </main>
    </div>
  )
}
