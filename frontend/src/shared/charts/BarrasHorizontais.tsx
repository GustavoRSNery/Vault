/**
 * Ranking em barras horizontais, com eixo de valores.
 *
 * Horizontal porque os rótulos de ranking são nomes de pessoa e caminhos de
 * segredo — texto longo, que na vertical exigiria rótulo inclinado e ficaria
 * ilegível.
 */

import { escalaDoEixo, posicaoNoEixo } from './escala'
import { EixoHorizontal, Quadro } from './primitivos'

export type ItemDoRanking = { rotulo: string; quantas: number }

const CORTE_DO_NOME = 30

export function BarrasHorizontais({
  itens,
  largura = 760,
  larguraNome = 190,
  alturaLinha = 30,
  descricao,
  classeBarra = 'barra-h',
}: {
  itens: ItemDoRanking[]
  largura?: number
  larguraNome?: number
  alturaLinha?: number
  descricao: string
  classeBarra?: string
}) {
  if (itens.length === 0) return null

  // Espaço à direita para o número escrito no fim da barra.
  const MARGEM_VALOR = 44
  const altura = itens.length * alturaLinha + 24
  const { teto, marcas } = escalaDoEixo(Math.max(...itens.map((i) => i.quantas)))
  const areaBarra = largura - larguraNome - MARGEM_VALOR

  return (
    <Quadro largura={largura} altura={altura} descricao={descricao}>
      <EixoHorizontal
        marcas={marcas}
        teto={teto}
        inicio={larguraNome}
        comprimento={areaBarra}
        alturaGrade={altura - 20}
        yRotulos={altura - 6}
      />

      {itens.map((item, i) => {
        const y = i * alturaLinha + 4
        // Mínimo de 2px: barra de valor 1 contra teto 300 arredondaria para
        // zero e sumiria, sugerindo ausência onde há ocorrência.
        const comprimento = Math.max(posicaoNoEixo(item.quantas, teto, areaBarra), 2)
        const alturaBarra = alturaLinha - 12

        return (
          <g key={item.rotulo}>
            <text className="nome" x={0} y={y + alturaLinha / 2 - 4}>
              {item.rotulo.length > CORTE_DO_NOME
                ? `${item.rotulo.slice(0, CORTE_DO_NOME - 1)}…`
                : item.rotulo}
              {/* O nome inteiro fica no título: o corte é visual, não perda. */}
              <title>{item.rotulo}</title>
            </text>
            <rect
              className={classeBarra}
              x={larguraNome}
              y={y}
              width={comprimento}
              height={alturaBarra}
            />
            {/* O valor escrito ao lado: a barra dá a comparação, o número dá
                a quantidade, e nenhum dos dois sozinho basta. */}
            <text
              className="valor"
              x={larguraNome + comprimento + 8}
              y={y + alturaBarra / 2}
            >
              {item.quantas}
            </text>
          </g>
        )
      })}
    </Quadro>
  )
}
