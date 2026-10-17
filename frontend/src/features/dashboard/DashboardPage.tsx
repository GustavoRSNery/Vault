import { Link } from 'react-router-dom'
import { useAuth } from '@/features/auth/AuthContext'
import { useCofres } from '@/features/vaults/CofresPage'
import { Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'

export function DashboardPage() {
  const { usuario } = useAuth()
  const { data: cofres, isLoading } = useCofres()

  const primeiroNome = usuario?.full_name.split(' ')[0] ?? ''
  const ativos = cofres?.filter((c) => c.state === 'ativo').length ?? 0
  const selados = cofres?.filter((c) => c.state === 'selado').length ?? 0

  return (
    <>
      <header>
        <h1 className="display">Olá, {primeiroNome}</h1>
        <p className="sub">Aqui está o resumo dos seus cofres.</p>
      </header>

      {isLoading ? (
        <Carregando />
      ) : (
        <>
          <div className="cards-3">
            <CardMetrica rotulo="Cofres com acesso" valor={cofres?.length ?? 0} tom="brand" />
            <CardMetrica rotulo="Cofres ativos" valor={ativos} tom="success" />
            <CardMetrica rotulo="Cofres selados" valor={selados} tom="danger" />
          </div>

          <Card titulo="Seus cofres">
            {!cofres || cofres.length === 0 ? (
              <Vazio
                titulo="Nenhum cofre ainda"
                descricao="Peça acesso a um administrador para começar."
              />
            ) : (
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {cofres.slice(0, 5).map((cofre) => (
                  <li key={cofre.id} style={{ padding: '6px 0' }}>
                    <Link
                      to={`/cofres/${cofre.name}`}
                      style={{ color: 'var(--brand-text)', textDecoration: 'none' }}
                    >
                      {cofre.display_name}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {!usuario?.mfa_enabled && (
            <Card>
              <div className="row between wrap">
                <div>
                  <h2 className="title">Ative a verificação em duas etapas</h2>
                  <p className="sub" style={{ margin: '4px 0 0' }}>
                    Um segundo fator protege seus cofres mesmo que a senha vaze.
                  </p>
                </div>
                <span className="badge b-warning">Pendente</span>
              </div>
            </Card>
          )}
        </>
      )}
    </>
  )
}
