import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { useConfiguracao, type Configuracao } from '@/shared/config/useConfiguracao'
import { Alerta, Botao, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

type Campo = {
  chave: keyof Configuracao
  rotulo: string
  unidade: string
  ajuda: string
}

/**
 * Os ajustes que uma instalação pode fazer.
 *
 * O que NÃO está aqui é deliberado: chave-mestra, banco e tamanhos de
 * material criptográfico ficam em variável de ambiente, e limites de
 * segurança (quórum mínimo, teto do lease) ficam no código. Configuração
 * que permite desligar a própria proteção é pior que configuração nenhuma —
 * dá impressão de flexibilidade e entrega um sistema que se desarma na
 * primeira pressa.
 */
const CAMPOS: Campo[] = [
  {
    chave: 'segundos_segredo_visivel',
    rotulo: 'Segredo visível por',
    unidade: 'segundos',
    ajuda:
      'Quanto tempo um valor revelado fica na tela antes de sumir sozinho. ' +
      'Curto demais não dá tempo de copiar; longo demais é segredo exposto ' +
      'na tela de quem saiu para o café.',
  },
  {
    chave: 'custodia_horas_padrao',
    rotulo: 'Custódia padrão',
    unidade: 'horas',
    ajuda:
      'Prazo sugerido ao retirar uma credencial. Quem retira pode escolher ' +
      'outro — é padrão, não imposição.',
  },
  {
    chave: 'alerta_certificado_dias',
    rotulo: 'Avisar de certificado',
    unidade: 'dias antes',
    ajuda:
      'Com quanta antecedência um certificado entra em "vencendo". Faixa ' +
      'muito larga deixa quase tudo em alerta, e alerta permanente é alerta ' +
      'ignorado.',
  },
  {
    chave: 'rotacao_dias_padrao',
    rotulo: 'Rotação padrão',
    unidade: 'dias',
    ajuda:
      'Prazo sugerido ao cadastrar uma credencial. Zero significa "não ' +
      'rotaciona", e é uma escolha explícita.',
  },
  {
    chave: 'trilha_limite_padrao',
    rotulo: 'Eventos por página',
    unidade: 'eventos',
    ajuda: 'Quantos eventos a trilha de auditoria mostra de uma vez.',
  },
]

/**
 * Como cada capacidade aparece na tela.
 *
 * A lista de opções vem do servidor; só os textos moram aqui. Uma capacidade
 * nova no domínio aparece na tela sozinha, com o nome técnico, em vez de
 * sumir por falta de tradução.
 */
const ROTULO_DA_CAPACIDADE: Record<string, string> = {
  admin: 'Somente administradores',
  approve: 'Administradores e gestores',
}

const AJUDA_DA_CAPACIDADE: Record<string, string> = {
  admin:
    'Quem administra a auditoria. É o padrão, e o mais restritivo: numa ' +
    'instalação nova ninguém mais vê a atividade dos colegas.',
  approve:
    'Inclui quem aprova pedidos de acesso — o perfil de gestor. Faz sentido ' +
    'quando quem decide quem vê o quê também precisa acompanhar o uso.',
}

export function ConfiguracaoPage() {
  const queryClient = useQueryClient()
  const { data: config, isLoading, error } = useConfiguracao()
  const [valores, setValores] = useState<Record<string, number>>({})
  const [erro, setErro] = useState<string | null>(null)
  const [salvo, setSalvo] = useState(false)
  // Estado próprio, separado dos campos numéricos: salvar a visibilidade dos
  // rankings junto com "segredo visível por" misturaria duas decisões de
  // natureza diferente num botão só.
  const [capacidade, setCapacidade] = useState<string | null>(null)

  // Sincroniza o formulário quando a configuração chega ou muda no servidor.
  useEffect(() => {
    if (!config) return
    setValores(
      Object.fromEntries(
        CAMPOS.map((c) => [c.chave, config[c.chave] as number]),
      ),
    )
  }, [config])

  const salvar = useMutation({
    mutationFn: () =>
      request<Configuracao>('/configuracao', { method: 'PUT', body: valores }),
    onSuccess: () => {
      setErro(null)
      setSalvo(true)
      void queryClient.invalidateQueries({ queryKey: ['configuracao'] })
      // As telas que dependem destes valores precisam reconsultar.
      void queryClient.invalidateQueries({ queryKey: ['certificados'] })
      void queryClient.invalidateQueries({ queryKey: ['auditoria'] })
    },
    onError: (e) => {
      setSalvo(false)
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.')
    },
  })

  const salvarCapacidade = useMutation({
    mutationFn: () =>
      request<Configuracao>('/configuracao', {
        method: 'PUT',
        body: { capacidade_do_ranking: capacidade },
      }),
    onSuccess: () => {
      setErro(null)
      void queryClient.invalidateQueries({ queryKey: ['configuracao'] })
      // O painel precisa reconsultar: quem passou a ver os rankings só
      // descobre isso na próxima leitura das métricas.
      void queryClient.invalidateQueries({ queryKey: ['metricas'] })
    },
    onError: (e) => {
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.')
    },
  })

  if (isLoading) return <Carregando texto="Carregando configuração…" />
  if (error || !config) {
    return (
      <Vazio
        titulo="Não foi possível ler a configuração"
        descricao="Tente recarregar a página."
      />
    )
  }

  const foraDaFaixa = CAMPOS.filter((c) => {
    const [min, max] = config.limites[c.chave as string] ?? [0, 0]
    const valor = valores[c.chave as string]
    return valor !== undefined && (valor < min || valor > max)
  })

  const mudou = CAMPOS.some(
    (c) => valores[c.chave as string] !== (config[c.chave] as number),
  )

  // Enquanto ninguém escolher nada, o rádio marcado é o que o servidor diz —
  // assim a tela nunca mostra uma seleção que não corresponde ao que vale.
  const capacidadeEscolhida = capacidade ?? config.capacidade_do_ranking
  const capacidadeMudou = capacidadeEscolhida !== config.capacidade_do_ranking

  return (
    <>
      <header>
        <h1 className="display">Configurações</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          Ajustes operacionais desta instalação. Chave-mestra, banco e limites
          de segurança <b>não</b> estão aqui — configuração que permite
          desligar a própria proteção é pior que configuração nenhuma.
        </p>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}
      {salvo && !mudou && (
        <Alerta tom="warning">
          Salvo. Os valores já valem para todas as telas.
        </Alerta>
      )}

      <Card>
        <div className="col" style={{ gap: 20 }}>
          {CAMPOS.map((campo) => {
            const [min, max] = config.limites[campo.chave as string] ?? [0, 0]
            const valor = valores[campo.chave as string] ?? 0
            const invalido = valor < min || valor > max
            return (
              <div key={campo.chave as string} className="field">
                <label htmlFor={campo.chave as string}>
                  {campo.rotulo} ({campo.unidade})
                </label>
                <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                  <input
                    id={campo.chave as string}
                    className="input"
                    type="number"
                    min={min}
                    max={max}
                    value={valor}
                    onChange={(e) =>
                      setValores((atual) => ({
                        ...atual,
                        [campo.chave as string]: Number(e.target.value),
                      }))
                    }
                    style={{ maxWidth: 140 }}
                    aria-invalid={invalido || undefined}
                  />
                  <span className="help">
                    entre {min} e {max}
                  </span>
                </div>
                <span className="help">{campo.ajuda}</span>
              </div>
            )
          })}

          {foraDaFaixa.length > 0 && (
            <Alerta tom="danger">
              Fora da faixa permitida:{' '}
              {foraDaFaixa.map((c) => c.rotulo).join(', ')}.
            </Alerta>
          )}

          <div className="row between wrap" style={{ gap: 10 }}>
            <Botao
              onClick={() => salvar.mutate()}
              disabled={!mudou || foraDaFaixa.length > 0 || salvar.isPending}
            >
              {salvar.isPending ? 'Salvando…' : 'Salvar'}
            </Botao>
            {config.atualizado_por && (
              <span className="help">
                Última alteração por {config.atualizado_por} em{' '}
                {formatarDataHora(config.atualizado_em)}
              </span>
            )}
          </div>
        </div>
      </Card>

      <Card titulo="Quem vê os rankings de atividade">
        <div className="col" style={{ gap: 14 }}>
          <p className="sub" style={{ margin: 0 }}>
            Os rankings do painel — <i>quem mais revela segredos</i> e{' '}
            <i>o que mais é revelado</i> — mostram a atividade dos colegas, e
            por isso seguem a mesma regra da trilha de auditoria. O gráfico de
            atividade continua visível a todos: ele mostra o movimento do
            cofre em agregado, sem dizer quem fez o quê.
          </p>

          <div className="col" style={{ gap: 10 }}>
            {config.capacidades_do_ranking.map((opcao) => (
              <label
                key={opcao}
                className="row"
                style={{ gap: 10, alignItems: 'flex-start', cursor: 'pointer' }}
              >
                <input
                  type="radio"
                  name="capacidade_do_ranking"
                  value={opcao}
                  checked={capacidadeEscolhida === opcao}
                  onChange={() => setCapacidade(opcao)}
                  style={{ marginTop: 3 }}
                />
                <span className="col" style={{ gap: 2 }}>
                  <b>{ROTULO_DA_CAPACIDADE[opcao] ?? opcao}</b>
                  <span className="help">
                    {AJUDA_DA_CAPACIDADE[opcao] ??
                      `Exige a capacidade "${opcao}" no caminho de auditoria.`}
                  </span>
                </span>
              </label>
            ))}
          </div>

          <div className="row between wrap" style={{ gap: 10 }}>
            <Botao
              onClick={() => salvarCapacidade.mutate()}
              disabled={!capacidadeMudou || salvarCapacidade.isPending}
            >
              {salvarCapacidade.isPending ? 'Salvando…' : 'Salvar'}
            </Botao>
            <span className="help">
              A mudança fica na trilha, com o antes e o depois.
            </span>
          </div>
        </div>
      </Card>

      <Card titulo="O que fica fora, e por quê">
        <div className="col" style={{ gap: 10 }}>
          <p className="sub" style={{ margin: 0 }}>
            A pergunta que separa o que é ajustável do que não é:{' '}
            <b>se alguém escolher o pior valor possível, isso enfraquece a
            segurança?</b>
          </p>
          <ul className="sub" style={{ margin: 0, paddingLeft: 20 }}>
            <li>
              <b>Quórum mínimo de 2 pessoas</b> — ajustável, viraria 1 na
              primeira vez que alguém se irritasse com a cerimônia, e aí selar
              não protege de nada.
            </li>
            <li>
              <b>Teto de 12h do acesso de máquina</b> — existe para que
              "temporário" signifique alguma coisa.
            </li>
            <li>
              <b>Tamanho de chave e nonce</b> — não é preferência, e mudar
              quebraria todo dado já cifrado.
            </li>
            <li>
              <b>Chave-mestra, banco e destino da exportação</b> — são
              infraestrutura, e mudá-las pela tela exigiria reiniciar o
              sistema para valer.
            </li>
          </ul>
        </div>
      </Card>
    </>
  )
}
