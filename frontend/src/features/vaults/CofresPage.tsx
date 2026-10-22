import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Card, Carregando, EstadoCofre, Vazio } from '@/shared/ui/components'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'

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
  const navegar = useNavigate()
  const tour = useTour('cofres')

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
      <Tour id="cofres" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <h1 className="display">Cofres</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              Os cofres a que você tem acesso. É aqui que o <b>valor</b> de um
              segredo mora, cifrado.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Cofres"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/cofres',
                  descricao:
                    'Os cofres que o seu token alcança. A filtragem é no servidor: cofre sem permissão não aparece na resposta.',
                  exemplo: '[{"name":"infra","display_name":"Infra","state":"ativo"}]',
                },
                {
                  metodo: 'GET',
                  caminho: '/cofres/{nome}/segredos',
                  descricao:
                    'Os segredos de um cofre: nome, tipo e versão atual. O valor NÃO vem — para isso existe a rota de revelar, que audita.',
                  exemplo:
                    '[{"name":"senha-root","kind":"senha","current_version":3}]',
                },
              ]}
            />
          </div>
        </div>
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
                {cofres.map((cofre, indice) => (
                  // A linha inteira abre o cofre. Alvo de clique do tamanho
                  // do texto obriga a mirar; a linha toda é o que a pessoa
                  // já tenta clicar antes de descobrir que não funciona.
                  //
                  // `role="link"` e `tabIndex` porque `<tr>` não é focável:
                  // sem isso, quem navega por teclado não alcança o cofre.
                  <tr
                    key={cofre.id}
                    className="linha-clicavel"
                    role="link"
                    tabIndex={0}
                    data-tour={indice === 0 ? 'linha-cofre' : undefined}
                    onClick={() => navegar(`/cofres/${cofre.name}`)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        navegar(`/cofres/${cofre.name}`)
                      }
                    }}
                  >
                    <td className="strong">
                      <span style={{ color: 'var(--brand-text)' }}>
                        {cofre.display_name}
                      </span>
                      <div className="help">{cofre.name}</div>
                    </td>
                    <td className="muted">{cofre.description || '—'}</td>
                    <td data-tour={indice === 0 ? 'estado-cofre' : undefined}>
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
