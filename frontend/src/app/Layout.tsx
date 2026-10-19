import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'

const ITENS = [
  { para: '/', rotulo: 'Dashboard', fim: true },
  { para: '/cofres', rotulo: 'Cofres', fim: false },
  { para: '/dispositivos', rotulo: 'Dispositivos', fim: false },
  { para: '/credenciais', rotulo: 'Credenciais', fim: false },
  { para: '/certificados', rotulo: 'Certificados', fim: false },
  { para: '/auditoria', rotulo: 'Auditoria', fim: false },
  { para: '/perfil', rotulo: 'Perfil', fim: false },
]

// Itens que só aparecem para quem administra. Esconder não é proteger: as
// rotas da API checam a política por requisição, independentemente do menu.
const ITENS_ADMIN = [
  { para: '/admin/usuarios', rotulo: 'Pessoas', fim: false },
  { para: '/admin/politicas', rotulo: 'Políticas', fim: false },
]

export function Layout() {
  const { usuario, sair } = useAuth()
  const iniciais = (usuario?.full_name ?? '?')
    .split(' ')
    .slice(0, 2)
    .map((parte) => parte.charAt(0).toUpperCase())
    .join('')

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

        <div className="nav-cap">Navegação</div>
        {ITENS.map((item) => (
          <NavLink
            key={item.para}
            to={item.para}
            end={item.fim}
            className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          >
            {item.rotulo}
          </NavLink>
        ))}

        {usuario?.is_admin && (
          <>
            <div className="nav-cap">Administração</div>
            {ITENS_ADMIN.map((item) => (
              <NavLink
                key={item.para}
                to={item.para}
                end={item.fim}
                className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              >
                {item.rotulo}
              </NavLink>
            ))}
          </>
        )}

        <div className="foot">
          <button className="nav-item" onClick={sair} style={{ width: '100%', textAlign: 'left', border: 0, background: 'none', cursor: 'pointer' }}>
            Sair
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
