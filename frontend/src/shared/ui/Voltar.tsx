import { Link } from 'react-router-dom'

/**
 * O caminho de volta de uma subtela.
 *
 * **Por que um destino explícito e não só `history.back()`.** Quem chega por
 * link direto — de um chamado, de um e-mail, de um favorito — não tem
 * histórico para voltar, e o botão não faria nada. Pior: numa aba recém-aberta
 * `back()` sai do sistema. Com o destino declarado, o botão leva para a
 * listagem que faz sentido, tenha a pessoa vindo de onde vier.
 *
 * Renderiza um `<Link>` de verdade, não um botão: o meio-clique abre em nova
 * aba e o endereço aparece ao passar o mouse, que é o que se espera de algo
 * que navega.
 */
export function Voltar({ para, rotulo }: { para: string; rotulo: string }) {
  return (
    <Link to={para} className="voltar">
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M15 18l-6-6 6-6" />
      </svg>
      <span>{rotulo}</span>
    </Link>
  )
}
