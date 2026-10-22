import { describe, expect, it } from 'vitest'
import { lerCredenciais, paraIdentificador } from './importar'

describe('paraIdentificador', () => {
  it('tira acento, espaço e maiúscula', () => {
    expect(paraIdentificador('Servidor de Produção')).toBe('servidor-de-producao')
  })

  it('não deixa hífen sobrando nas pontas', () => {
    expect(paraIdentificador('  --Banco!!  ')).toBe('banco')
  })

  it('respeita o limite de 64 do identificador', () => {
    expect(paraIdentificador('a'.repeat(100))).toHaveLength(64)
  })
})

describe('lerCredenciais — formato próprio', () => {
  it('lê de volta o que esta tela exporta', () => {
    const r = lerCredenciais(
      JSON.stringify({
        nome: 'senha-root',
        usuario: 'root',
        descricao: 'Acesso administrativo',
        dispositivo: 'srv-db-01',
      }),
    )
    expect(r.formato).toBe('Vault')
    expect(r.credenciais).toEqual([
      {
        name: 'senha-root',
        username: 'root',
        description: 'Acesso administrativo',
        origem: 'exportação do Vault',
      },
    ])
  })

  it('aceita uma lista do próprio formato', () => {
    const r = lerCredenciais(
      JSON.stringify([
        { nome: 'a', usuario: 'ua', dispositivo: 'd1' },
        { nome: 'b', usuario: 'ub', dispositivo: 'd2' },
      ]),
    )
    expect(r.credenciais.map((c) => c.name)).toEqual(['a', 'b'])
  })
})

describe('lerCredenciais — Bitwarden', () => {
  const bitwarden = {
    items: [
      { type: 1, name: 'Servidor SSH', login: { username: 'deploy', password: 'x' } },
      { type: 2, name: 'Nota do contrato' },
      { type: 1, name: 'Painel', login: { username: 'admin' }, notes: 'interno' },
    ],
  }

  it('importa só os logins', () => {
    const r = lerCredenciais(JSON.stringify(bitwarden))
    expect(r.formato).toBe('Bitwarden')
    expect(r.credenciais.map((c) => c.name)).toEqual(['servidor-ssh', 'painel'])
  })

  it('diz o que ficou de fora em vez de sumir em silêncio', () => {
    const r = lerCredenciais(JSON.stringify(bitwarden))
    expect(r.ignorados).toEqual(['Nota do contrato (não é login)'])
  })

  it('conta quantas traziam senha, para a tela poder avisar', () => {
    expect(lerCredenciais(JSON.stringify(bitwarden)).comSenha).toBe(1)
  })

  it('NUNCA devolve o valor da senha', () => {
    const r = lerCredenciais(JSON.stringify(bitwarden))
    expect(JSON.stringify(r)).not.toContain('"x"')
    for (const c of r.credenciais) {
      expect(Object.keys(c)).toEqual(['name', 'username', 'description', 'origem'])
    }
  })
})

describe('lerCredenciais — 1Password', () => {
  it('desce até os itens dentro de contas e cofres', () => {
    const r = lerCredenciais(
      JSON.stringify({
        accounts: [
          {
            vaults: [
              {
                items: [
                  {
                    overview: { title: 'Banco Produção', url: 'https://db.interno' },
                    details: { username: 'dba', password: 'segredo' },
                  },
                ],
              },
            ],
          },
        ],
      }),
    )
    expect(r.formato).toBe('1Password')
    expect(r.credenciais[0]).toEqual({
      name: 'banco-producao',
      username: 'dba',
      description: 'https://db.interno',
      origem: '1Password',
    })
    expect(r.comSenha).toBe(1)
    expect(JSON.stringify(r)).not.toContain('segredo')
  })
})

describe('lerCredenciais — lista genérica', () => {
  it('aceita uma lista simples com name', () => {
    const r = lerCredenciais(
      JSON.stringify([{ name: 'API interna', username: 'svc', notes: 'robô' }]),
    )
    expect(r.formato).toBe('lista JSON')
    expect(r.credenciais[0]?.name).toBe('api-interna')
  })

  it('não rouba o formato próprio: a ordem das tentativas importa', () => {
    // Tem "name" (casaria com a lista genérica) E marca própria. O leitor
    // específico tem de vencer, senão `usuario` seria lido pela chave errada.
    const r = lerCredenciais(
      JSON.stringify([{ name: 'x', usuario: 'certo', dispositivo: 'd' }]),
    )
    expect(r.formato).toBe('Vault')
    expect(r.credenciais[0]?.username).toBe('certo')
  })
})

describe('lerCredenciais — recusas', () => {
  it('diz que não é JSON quando não é', () => {
    expect(() => lerCredenciais('isto não é json')).toThrow('não é um JSON válido')
  })

  it('recusa JSON válido sem credencial reconhecível', () => {
    expect(() => lerCredenciais('{"foo":"bar"}')).toThrow('Não reconheci')
  })

  it('recusa lista vazia em vez de importar nada em silêncio', () => {
    expect(() => lerCredenciais('[]')).toThrow('Não reconheci')
  })

  it('ignora entradas sem nome em vez de criar credencial anônima', () => {
    const r = lerCredenciais(
      JSON.stringify([{ name: 'boa', username: 'u' }, { username: 'sem-nome' }]),
    )
    expect(r.credenciais).toHaveLength(1)
  })
})
