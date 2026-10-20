/**
 * Barras empilhadas sobre um eixo de categorias (tipicamente datas).
 *
 * Genérico de propósito: recebe as séries que deve empilhar, não três faixas
 * fixas. O gráfico de atividade do cofre é *um uso* deste componente, não o
 * componente em si — é o que permite o próximo gráfico empilhado nascer sem
 * copiar nada.
 */

import { empilhar, escalaDoEixo, passoDosRotulos } from './escala'
import {
  AlvoDeLeitura,
  EixoVertical,
  MARGEM_PADRAO,
  Quadro,
  type Margem,
} from './primitivos'

/** Uma série: a parcela que ela contribui em cada ponto. */
export type Serie<T> = {
  chave: string
  rotulo: string
  /** Classe CSS do preenchimento, dos tokens do design system. */
  classe: string
  valor: (ponto: T) => number
}

export function BarrasEmpilhadas<T>({
  pontos,
  series,
  rotuloDoPonto,
  largura = 760,
  altura = 200,
  margem = MARGEM_PADRAO,
  descricao,
}: {
  pontos: T[]
  series: Serie<T>[]
  rotuloDoPonto: (ponto: T) => string
  largura?: number
  altura?: number
  margem?: Margem
  /** Resumo para leitor de tela. Sem ele o gráfico não existe sem visão. */
  descricao: string
}) {
  const area = {
    largura: largura - margem.esquerda - margem.direita,
    altura: altura - margem.topo - margem.baixo,
  }

  const totalDe = (ponto: T) => series.reduce((soma, s) => soma + s.valor(ponto), 0)
  const { teto, marcas } = escalaDoEixo(Math.max(...pontos.map(totalDe), 0))

  const passo = area.largura / Math.max(pontos.length, 1)
  // A barra ocupa 70% do passo: o vão restante é o que separa visualmente um
  // ponto do outro sem precisar de borda.
  const larguraBarra = Math.max(Math.min(passo * 0.7, 28), 2)
  const aCada = passoDosRotulos(pontos.length)

  return (
    <Quadro largura={largura} altura={altura} descricao={descricao}>
      <EixoVertical
        marcas={marcas}
        teto={teto}
        area={area}
        margem={margem}
        larguraTotal={largura}
      />

      {pontos.map((ponto, i) => {
        const centro = margem.esquerda + passo * i + passo / 2
        const faixas = empilhar(
          series.map((s) => ({ chave: s.chave, valor: s.valor(ponto) })),
          teto,
          area.altura,
          margem.topo,
        )
        const classeDe = (chave: string) =>
          series.find((s) => s.chave === chave)?.classe ?? ''
        const detalhe = series
          .map((s) => `${s.valor(ponto)} ${s.rotulo.toLowerCase()}`)
          .join(', ')

        return (
          <g key={rotuloDoPonto(ponto)}>
            {faixas.map((faixa) => (
              <rect
                key={faixa.chave}
                className={classeDe(faixa.chave)}
                x={centro - larguraBarra / 2}
                y={faixa.y}
                width={larguraBarra}
                height={faixa.altura}
              />
            ))}
            <AlvoDeLeitura
              x={margem.esquerda + passo * i}
              y={margem.topo}
              largura={passo}
              altura={area.altura}
              descricao={`${rotuloDoPonto(ponto)} · ${totalDe(ponto)} no total: ${detalhe}`}
            />
            {i % aCada === 0 && (
              <text className="marca marca-x" x={centro} y={altura - 8}>
                {rotuloDoPonto(ponto)}
              </text>
            )}
          </g>
        )
      })}
    </Quadro>
  )
}
