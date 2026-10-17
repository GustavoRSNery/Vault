import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Card, Carregando, EstadoCofre, Vazio } from '@/shared/ui/components'

export type Cofre = {
  id: string
  name: string
  display_name: string
  description: string
  state: string
  created_at: string
}

export function useCofres() {
  return useQuery({
    queryKey: ['cofres'],
    queryFn: () => request<Cofre[]>('/cofres'),
  })
}

export function CofresPage() {
  const { data: cofres, isLoading, error } = useCofres()

  if (isLoading) return <Carregando texto="Carregando cofres…" />
  if (error) {
    return (
      <Vazio
        titulo="Não foi possível carregar os cofres"
        descricao="Tente novamente em instantes."
      />
    )
  }

  return (
    <>
      <header>
        <h1 className="display">Cofres</h1>
        <p className="sub">Os cofres a que você tem acesso.</p>
      </header>

      <Card>
        {!cofres || cofres.length === 0 ? (
          <Vazio
            titulo="Nenhum cofre disponível"
            descricao="Você ainda não tem acesso a nenhum cofre. Peça acesso a um administrador."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Cofre</th>
                  <th>Descrição</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {cofres.map((cofre) => (
                  <tr key={cofre.id}>
                    <td className="strong">
                      <Link
                        to={`/cofres/${cofre.name}`}
                        style={{ color: 'var(--brand-text)', textDecoration: 'none' }}
                      >
                        {cofre.display_name}
                      </Link>
                    </td>
                    <td className="muted">{cofre.description || '—'}</td>
                    <td>
                      <EstadoCofre estado={cofre.state} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
