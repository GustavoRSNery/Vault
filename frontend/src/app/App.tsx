import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/features/auth/AuthContext'
import { LoginPage } from '@/features/auth/LoginPage'
import { PerfilPage } from '@/features/auth/PerfilPage'
import { AuditoriaPage } from '@/features/audit/AuditoriaPage'
import { PoliticasPage } from '@/features/admin/PoliticasPage'
import { UsuariosPage } from '@/features/admin/UsuariosPage'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { CofreDetalhePage } from '@/features/vaults/CofreDetalhePage'
import { CofresPage } from '@/features/vaults/CofresPage'
import { Layout } from './Layout'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Nada de reconsultar sozinho ao focar a janela: num cofre, cada
      // chamada ao servidor é uma linha de auditoria.
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30_000,
    },
  },
})

function Rotas() {
  const { usuario } = useAuth()

  if (!usuario) {
    return (
      <Routes>
        <Route path="*" element={<LoginPage />} />
      </Routes>
    )
  }

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<DashboardPage />} />
        <Route path="cofres" element={<CofresPage />} />
        <Route path="cofres/:nome" element={<CofreDetalhePage />} />
        <Route path="auditoria" element={<AuditoriaPage />} />
        <Route path="perfil" element={<PerfilPage />} />
        <Route path="admin/usuarios" element={<UsuariosPage />} />
        <Route path="admin/politicas" element={<PoliticasPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Rotas />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
