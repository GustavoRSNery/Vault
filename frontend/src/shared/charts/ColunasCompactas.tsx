/**
 * Colunas compactas: a faixa de atividade por dia, no formato da referência.
 *
 * É o mesmo dado de `BarrasEmpilhadas`, com uma gramática visual diferente —
 * e a diferença é deliberada, não decorativa:
 *
 * - **Altura baixa e fixa** (~64px contra 200px). Um gráfico alto obriga a
 *   percorrer a tela para ver uma série que cabe numa tira, e a altura extra
 *   não acrescenta precisão: o número exato está no tooltip e o total vem
 *   escrito ao lado.
 * - **Sem eixo Y e sem grade.** A pergunta aqui é "em que dias houve
 *   movimento, e quando ele foi atípico" — comparação de forma, não leitura
 *   de valor. O eixo volta a fazer sentido em `BarrasEmpilhadas`, que serve
 *   para quando a pergunta é "quanto".
 * - **Colunas largas e encostadas**, topo arredondado e base reta. Assentar
 *   todas na mesma linha de base é o que deixa a silhueta legível.
 * - **Uma cor clara para o volume e uma saturada para o que importa**, em
 *   vez de três faixas disputando atenção.
 *
 * **Por que o SVG usa `preserveAspectRatio="none"`:** só assim a altura pode
 * ser fixada em pixels sem que a largura do container a arraste junto — com
 * `meet`, um container de 1300px forçaria ~120px de altura e a tira deixaria
 * de ser tira. A distorção que isso causa é absorvida porque as colunas são
 * retângulos, que esticam sem parecer errados. Texto, não: por isso os
 * rótulos de data ficam em HTML, fora do SVG.
 */

import { escalaDoEixo, passoDosRotulos, posicaoNoEixo } from './escala'

export type ColunaDoDia = {
  /** Rótulo do eixo X, já formatado. */
  rotulo: string
  /** Altura total da coluna. */
  total: number
  /** Parte que recebe o destaque saturado (0 esconde a faixa). */
  destaque?: number
  /** Texto do tooltip. Sem ele, o valor só existe para quem enxerga a forma. */
  descricao?: string
}

/** Unidades internas do desenho. A altura real vem de `altura`, em pixels. */
const LARGURA = 1200
const ALTURA = 100

export function ColunasCompactas({
  colunas,
  altura = 64,
  descricao,
  classeBase = 'col-base',
  classeDestaque = 'col-destaque',
}: {
  colunas: ColunaDoDia[]
  /** Altura renderizada, em pixels. */
  altura?: number
  descricao: string
  classeBase?: string
  classeDestaque?: string
}) {
  if (colunas.length === 0) return null

  const { teto } = escalaDoEixo(Math.max(...colunas.map((c) => c.total), 0))
  const passo = LARGURA / colunas.length
  // Encostadas, com um fio de respiro: é o que forma a silhueta contínua da
  // referência, em vez de barras soltas.
  const larguraColuna = Math.max(passo - 5, 2)
  const aCada = passoDosRotulos(colunas.length, 12)

  return (
    <div className="tira">
      <svg
        className="gx tira-svg"
        viewBox={`0 0 ${LARGURA} ${ALTURA}`}
        role="img"
        aria-label={descricao}
        preserveAspectRatio="none"
        style={{ height: altura }}
      >
        {colunas.map((coluna, i) => {
          const x = passo * i + 2.5
          const h = posicaoNoEixo(coluna.total, teto, ALTURA)
          const destaque = coluna.destaque ?? 0
          const hDestaque =
            destaque > 0 ? posicaoNoEixo(destaque, teto, ALTURA) : 0

          return (
            <g key={coluna.rotulo}>
              {h > 0 && (
                <>
                  {/* Topo arredondado e base reta: `rx` arredondaria os quatro
                      cantos e a coluna pareceria flutuar acima da linha. */}
                  <path
                    className={classeBase}
                    d={cantoSuperiorArredondado(x, ALTURA - h, larguraColuna, h, 6)}
                  />
                  {hDestaque > 0 && (
                    <rect
                      className={classeDestaque}
                      x={x}
                      y={ALTURA - hDestaque}
                      width={larguraColuna}
                      height={hDestaque}
                    />
                  )}
                </>
              )}
              {/* Alvo cobrindo a coluna inteira, inclusive o vão: numa tira
                  de 64px, mirar na barra em si seria sofrido. */}
              <rect className="alvo" x={passo * i} y={0} width={passo} height={ALTURA}>
                <title>{coluna.descricao ?? `${coluna.rotulo}: ${coluna.total}`}</title>
              </rect>
            </g>
          )
        })}
      </svg>

      {/* Rótulos em HTML, não em <text>: dentro do SVG esticado eles sairiam
          deformados. Em grade de colunas iguais, cada um cai sob a sua. */}
      <div
        className="tira-rotulos"
        style={{ gridTemplateColumns: `repeat(${colunas.length}, 1fr)` }}
        aria-hidden="true"
      >
        {colunas.map((coluna, i) => (
          <span key={coluna.rotulo}>{i % aCada === 0 ? coluna.rotulo : ''}</span>
        ))}
      </div>
    </div>
  )
}

/**
 * Retângulo com os dois cantos de cima arredondados.
 *
 * O raio é limitado a metade da largura e à própria altura: numa coluna de
 * 3 unidades de altura, um raio de 6 inverteria a curva e desenharia uma gota.
 */
function cantoSuperiorArredondado(
  x: number,
  y: number,
  largura: number,
  altura: number,
  raio: number,
): string {
  const r = Math.min(raio, largura / 2, altura)
  return [
    `M ${x} ${y + altura}`,
    `L ${x} ${y + r}`,
    `Q ${x} ${y} ${x + r} ${y}`,
    `L ${x + largura - r} ${y}`,
    `Q ${x + largura} ${y} ${x + largura} ${y + r}`,
    `L ${x + largura} ${y + altura}`,
    'Z',
  ].join(' ')
}
