import { describe, expect, it } from 'vitest'
import { AREAS, areaDoCaminho, type Area } from './Layout'

/**
 * As áreas e os itens do menu real, por nome.
 *
 * Nomear em vez de indexar (`AREAS[2].itens[1]`) para que reordenar o menu
 * quebre o teste com "não existe mais" em vez de silenciosamente passar a
 * testar outro item — que continuaria verde medindo a coisa errada.
 */
function area(id: string): Area {
  const achada = AREAS.find((a) => a.id === id)
  if (!achada) throw new Error(`área '${id}' não existe mais em AREAS`)
  return achada
}

function item(area: Area, para: string) {
  const achado = area.itens.find((i) => i.para === para)
  if (!achado) throw new Error(`'${para}' não está mais na área '${area.id}'`)
  return achado
}

/**
 * A barra de cima marca a área pelo caminho aberto. Errar aqui não quebra a
 * navegação — ela continua funcionando — mas acende a área errada e troca a
 * lista da lateral por outra, que é pior que não marcar nada: a pessoa
 * procura "Gravações" na lateral de "Segredos" e conclui que sumiu.
 */
describe('areaDoCaminho', () => {
  it('casa o caminho exato de um item', () => {
    expect(areaDoCaminho('/cofres').id).toBe('segredos')
    expect(areaDoCaminho('/auditoria').id).toBe('uso')
    expect(areaDoCaminho('/perfil').id).toBe('conta')
  })

  it('leva o filho para a área do pai', () => {
    // A rota de detalhe não está no menu; sem o casamento por prefixo a
    // lateral trocaria para "Visão geral" ao abrir um cofre.
    expect(areaDoCaminho('/cofres/producao').id).toBe('segredos')
    expect(areaDoCaminho('/sessoes/42').id).toBe('uso')
  })

  it('prefere o prefixo mais longo, não o primeiro declarado', () => {
    // No menu real `/sessoes` e `/sessoes/gravacoes` são a MESMA área, então
    // escolher o item errado não muda o id e o erro não aparece. Aqui os dois
    // ficam em áreas diferentes — e o item genérico vem primeiro, que é a
    // ordem em que "o primeiro que casar" acerta por sorte no menu real.
    const uso = area('uso')
    const sessoes = item(uso, '/sessoes')
    const gravacoes = item(uso, '/sessoes/gravacoes')
    const areas: Area[] = [
      area('visao-geral'),
      { ...uso, id: 'generica', itens: [sessoes] },
      { ...uso, id: 'especifica', itens: [gravacoes] },
    ]
    expect(areaDoCaminho('/sessoes/gravacoes', areas).id).toBe('especifica')
    // E o caminho do item genérico continua no genérico: o "mais longo" não
    // pode puxar para a área específica o que não é filho dela.
    expect(areaDoCaminho('/sessoes', areas).id).toBe('generica')
  })

  it('não deixa a raiz disputar com os outros caminhos', () => {
    // "/" casa por prefixo com TUDO, então fica fora da disputa e a raiz é
    // atendida pelo fallback.
    //
    // No menu real a raiz está na primeira área, a mesma que o fallback
    // devolve — então deixá-la disputar daria o mesmo resultado por
    // coincidência, e o erro ficaria escondido até alguém reordenar as
    // áreas. Aqui ela está na SEGUNDA: se disputasse, "/" devolveria
    // 'tem-a-raiz' em vez da primeira área.
    const areas: Area[] = [
      { ...area('segredos'), id: 'primeira' },
      { ...area('visao-geral'), id: 'tem-a-raiz' },
    ]
    expect(areaDoCaminho('/', areas).id).toBe('primeira')
    // E um caminho qualquer continua indo para o fallback, não para a raiz.
    expect(areaDoCaminho('/nao-existe', areas).id).toBe('primeira')
  })

  it('não deixa um nome mais longo invadir a área do mais curto', () => {
    // `/cofres-antigos` começa com "/cofres" como texto, mas não é filho
    // dele. Sem exigir a barra, abriria "Segredos" para uma rota que não
    // pertence a nenhuma área.
    expect(areaDoCaminho('/cofres-antigos').id).toBe('visao-geral')
  })

  it('cai na primeira área quando o caminho não é de ninguém', () => {
    // A 404 passa por aqui. Sem o fallback, nenhuma pílula ficaria marcada.
    expect(areaDoCaminho('/rota-que-nao-existe').id).toBe('visao-geral')
    expect(areaDoCaminho('/').id).toBe('visao-geral')
  })

  it('ignora as áreas que não foram passadas', () => {
    // Quem não administra não recebe a área de admin. Se `/admin/usuarios`
    // casasse mesmo assim, a barra marcaria uma pílula que não está na tela.
    const semAdmin = AREAS.filter((area) => !area.admin)
    expect(areaDoCaminho('/admin/usuarios', semAdmin).id).toBe('visao-geral')
    expect(areaDoCaminho('/admin/usuarios').id).toBe('admin')
  })

  it('todo item do menu encontra a própria área', () => {
    // Varredura: um item novo adicionado à área errada, ou com caminho que
    // não bate com a rota, aparece aqui em vez de na tela de alguém.
    for (const area of AREAS) {
      for (const item of area.itens) {
        if (item.para === '/') continue
        expect(areaDoCaminho(item.para).id, `item ${item.para}`).toBe(area.id)
      }
    }
  })
})
