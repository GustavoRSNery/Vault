/**
 * Barra 100% empilhada: proporção entre poucas categorias.
 *
 * Sem eixo de propósito — a largura total *é* o 100%, e um eixo repetiria
 * isso ocupando espaço. É o único gráfico da lib sem eixo, e a exceção se
 * justifica porque a pergunta aqui é "que fatia" e não "quanto".
 *
 * Em HTML e não em SVG porque são divs com largura percentual: o navegador
 * já faz esse cálculo melhor, e o resultado reflui sozinho com o container.
 */

export type ParteDaProporcao = { nome: string; valor: number; classe: string }

export function BarraDeProporcao({ partes }: { partes: ParteDaProporcao[] }) {
  const total = partes.reduce((soma, p) => soma + p.valor, 0)
  // Sem total não há proporção: desenhar uma barra vazia sugeriria que a
  // medição ocorreu e deu zero, quando na verdade não há o que medir.
  if (total <= 0) return null

  const visiveis = partes.filter((p) => p.valor > 0)

  return (
    <div
      className="proporcao"
      role="img"
      aria-label={visiveis
        .map((p) => `${p.nome}: ${p.valor} de ${total}`)
        .join('; ')}
    >
      {visiveis.map((parte) => (
        <span
          key={parte.nome}
          className={parte.classe}
          style={{ width: `${(parte.valor / total) * 100}%` }}
          title={`${parte.nome}: ${parte.valor} (${Math.round((parte.valor / total) * 100)}%)`}
        />
      ))}
    </div>
  )
}
