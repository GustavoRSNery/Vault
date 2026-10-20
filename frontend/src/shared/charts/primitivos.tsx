/**
 * Primitivos de desenho: as peças que todo gráfico reaproveita.
 *
 * Eixo, grade, legenda e moldura. Um gráfico novo monta-se com estas peças
 * mais o cálculo de `escala.ts` — é o que impede que o quinto gráfico volte
 * a reimplementar marcação de eixo do zero.
 *
 * As cores nunca aparecem aqui como valor: vêm das classes do design system
 * (`design-system.css`). Um hexadecimal escrito neste arquivo seria uma cor
 * que o tema não alcança.
 */

import type { ReactNode } from 'react'

import { posicaoNoEixo } from './escala'

/** Margens internas do quadro, onde moram os rótulos dos eixos. */
export type Margem = { topo: number; direita: number; baixo: number; esquerda: number }

export const MARGEM_PADRAO: Margem = { topo: 12, direita: 8, baixo: 28, esquerda: 38 }

/**
 * Moldura do gráfico: o `<svg>` com viewBox e o rótulo acessível.
 *
 * `role="img"` com `aria-label` é o que faz o gráfico existir para quem usa
 * leitor de tela. Sem isso, o SVG inteiro é anunciado como nada — e um
 * gráfico que só funciona para quem enxerga é meio gráfico.
 */
export function Quadro({
  largura,
  altura,
  descricao,
  children,
}: {
  largura: number
  altura: number
  descricao: string
  children: ReactNode
}) {
  return (
    <svg
      className="gx"
      viewBox={`0 0 ${largura} ${altura}`}
      role="img"
      aria-label={descricao}
      preserveAspectRatio="xMidYMid meet"
    >
      {children}
    </svg>
  )
}

/**
 * Eixo de valores na vertical, com grade horizontal.
 *
 * A grade é desenhada antes das barras (vem primeiro no SVG) para ficar
 * atrás delas: linha de grade por cima de barra sugere divisão que não
 * existe no dado.
 */
export function EixoVertical({
  marcas,
  teto,
  area,
  margem,
  larguraTotal,
  formatar = (v: number) => String(v),
}: {
  marcas: number[]
  teto: number
  area: { largura: number; altura: number }
  margem: Margem
  larguraTotal: number
  formatar?: (valor: number) => string
}) {
  const emY = (valor: number) =>
    margem.topo + posicaoNoEixo(valor, teto, area.altura, { invertido: true })

  return (
    <g>
      {marcas.map((marca) => (
        <g key={marca}>
          <line
            className="grade"
            x1={margem.esquerda}
            x2={larguraTotal - margem.direita}
            y1={emY(marca)}
            y2={emY(marca)}
          />
          <text className="marca marca-y" x={margem.esquerda - 8} y={emY(marca)}>
            {formatar(marca)}
          </text>
        </g>
      ))}
      {/* A linha do zero é mais forte: é a base de leitura de todas as barras. */}
      <line
        className="eixo"
        x1={margem.esquerda}
        x2={larguraTotal - margem.direita}
        y1={emY(0)}
        y2={emY(0)}
      />
    </g>
  )
}

/** Eixo de valores na horizontal, com grade vertical. Usado por rankings. */
export function EixoHorizontal({
  marcas,
  teto,
  inicio,
  comprimento,
  alturaGrade,
  yRotulos,
  formatar = (v: number) => String(v),
}: {
  marcas: number[]
  teto: number
  inicio: number
  comprimento: number
  alturaGrade: number
  yRotulos: number
  formatar?: (valor: number) => string
}) {
  return (
    <g>
      {marcas.map((marca) => {
        const x = inicio + posicaoNoEixo(marca, teto, comprimento)
        return (
          <g key={marca}>
            <line className="grade" x1={x} x2={x} y1={0} y2={alturaGrade} />
            <text className="marca marca-x" x={x} y={yRotulos}>
              {formatar(marca)}
            </text>
          </g>
        )
      })}
    </g>
  )
}

/**
 * Área transparente que captura o ponteiro e carrega o `<title>`.
 *
 * Existe porque mirar numa faixa de 2px de altura é impossível na prática. O
 * alvo cobre a coluna inteira, e o `<title>` é como o número exato chega a
 * quem lê — tanto no ponteiro quanto no leitor de tela.
 */
export function AlvoDeLeitura({
  x,
  y,
  largura,
  altura,
  descricao,
}: {
  x: number
  y: number
  largura: number
  altura: number
  descricao: string
}) {
  return (
    <rect className="alvo" x={x} y={y} width={largura} height={altura}>
      <title>{descricao}</title>
    </rect>
  )
}

export type ItemDeLegenda = { chave: string; rotulo: string; classe: string }

/**
 * Legenda em texto.
 *
 * Obrigatória sempre que o gráfico tem mais de uma série: cor não pode ser o
 * único sinal, porque daltonismo e impressão em preto e branco apagam a
 * diferença entre as faixas.
 */
export function Legenda({ itens }: { itens: ItemDeLegenda[] }) {
  return (
    <div className="g-legenda">
      {itens.map((item) => (
        <span className="item" key={item.chave}>
          <span className={`chave ${item.classe}`} />
          {item.rotulo}
        </span>
      ))}
    </div>
  )
}
