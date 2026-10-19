import { Link, useLocation } from 'react-router-dom'
import { Botao, Card } from '@/shared/ui/components'

/**
 * Página 404.
 *
 * Substitui o redirecionamento silencioso para a home. Mandar de volta sem
 * avisar faz o usuário achar que clicou errado — ou pior, que perdeu o
 * acesso a algo que existia. Dizer que a rota não existe é mais honesto e
 * mais fácil de reportar.
 */
export function NaoEncontrada() {
  const { pathname } = useLocation()

  return (
    <>
      <header>
        <h1 className="display">Página não encontrada</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          O endereço <code className="secret-sm">{pathname}</code> não existe
          nesta aplicação.
        </p>
      </header>

      <Card>
        <div className="col" style={{ gap: 14 }}>
          <p className="sub" style={{ margin: 0 }}>
            Se você chegou aqui por um link de dentro do sistema, vale reportar:
            é provavelmente um erro nosso, não seu.
          </p>
          <div className="row wrap" style={{ gap: 10 }}>
            <Link to="/">
              <Botao pequeno>Ir para o dashboard</Botao>
            </Link>
            <Link to="/busca">
              <Botao variante="secondary" pequeno>
                Buscar
              </Botao>
            </Link>
          </div>
        </div>
      </Card>
    </>
  )
}
