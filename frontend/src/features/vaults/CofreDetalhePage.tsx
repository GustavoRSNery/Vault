import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'
import { request } from '@/shared/api/client'
import { CampoSegredo } from '@/features/secrets/CampoSegredo'
import { Card, Carregando, Vazio } from '@/shared/ui/components'

type Segredo = {
  id: string
  name: string
  kind: string
  description: string
  current_version: number
  updated_at: string
}

const ROTULO_TIPO: Record<string, string> = {
  senha: 'Senha',
  chave_api: 'Chave de API',
  chave_ssh: 'Chave SSH',
  certificado: 'Certificado',
  token: 'Token',
  nota: 'Nota',
}

function formatarData(iso: string): string {
  // O design system fixa o formato das trilhas: 16/10/2026 14:32.
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return '—'
  return data.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function CofreDetalhePage() {
  const { nome = '' } = useParams<{ nome: string }>()
  const [aberto, setAberto] = useState<string | null>(null)

  const { data: segredos, isLoading, error } = useQuery({
    queryKey: ['segredos', nome],
    queryFn: () => request<Segredo[]>(`/cofres/${encodeURIComponent(nome)}/segredos`),
    enabled: nome !== '',
  })

  if (isLoading) return <Carregando texto="Carregando segredos…" />
  if (error) {
    return (
      <Vazio
        titulo="Não foi possível abrir o cofre"
        descricao="Você pode não ter acesso a ele, ou o cofre pode estar selado."
      />
    )
  }

  return (
    <>
      <header>
        <nav className="crumbs" style={{ marginBottom: 6 }}>
          <Link to="/cofres">Cofres</Link> <span aria-hidden="true">›</span> {nome}
        </nav>
        <h1 className="display">{nome}</h1>
        <p className="sub">
          {segredos?.length ?? 0} segredo{(segredos?.length ?? 0) === 1 ? '' : 's'}.
          Todo valor nasce mascarado e cada revelação é registrada em auditoria.
        </p>
      </header>

      <Card>
        {!segredos || segredos.length === 0 ? (
          <Vazio
            titulo="Nenhum segredo neste cofre"
            descricao="Os segredos criados aqui aparecerão nesta lista."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Segredo</th>
                  <th>Tipo</th>
                  <th>Versão</th>
                  <th>Atualizado</th>
                  <th>Valor</th>
                </tr>
              </thead>
              <tbody>
                {segredos.map((segredo) => (
                  <tr key={segredo.id}>
                    <td className="strong">
                      {segredo.name}
                      {segredo.description && (
                        <div className="help">{segredo.description}</div>
                      )}
                    </td>
                    <td className="muted">
                      {ROTULO_TIPO[segredo.kind] ?? segredo.kind}
                    </td>
                    <td className="secret-sm">v{segredo.current_version}</td>
                    <td className="muted">{formatarData(segredo.updated_at)}</td>
                    <td style={{ minWidth: 340 }}>
                      {aberto === segredo.name ? (
                        <CampoSegredo cofre={nome} segredo={segredo.name} />
                      ) : (
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={() => setAberto(segredo.name)}
                        >
                          Acessar
                        </button>
                      )}
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
