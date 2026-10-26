import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Badge, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { formatarDataHora } from '@/shared/lib/formato'
import { formatarDuracao, TabelaSessoes, type Sessao } from './SessoesPage'
import { perfilDeAtividade } from './perfil'

/**
 * Catálogo de gravações.
 *
 * **Por que grade de cartões e não tabela.** Uma gravação é assistida, não
 * comparada: a pergunta é "qual delas eu abro", não "qual tem mais eventos".
 * A tabela de oito colunas era boa para auditar um conjunto e ruim para
 * escolher um item — e escolher é o que se faz aqui.
 *
 * A tabela continua disponível num alternador, porque a comparação lado a
 * lado ainda serve para a revisão periódica. As duas vistas lêem a mesma
 * lista: nenhuma filtra nada por conta própria.
 */
export function GravacoesPage() {
  const [termo, setTermo] = useState('')
  const [vista, setVista] = useState<'grade' | 'tabela'>('grade')
  const tour = useTour('gravacoes')

  const { data: gravacoes, isFetching } = useQuery({
    queryKey: ['gravacoes', termo.trim()],
    queryFn: () =>
      request<Sessao[]>(
        `/sessoes/gravacoes${termo.trim() ? `?termo=${encodeURIComponent(termo.trim())}` : ''}`,
      ),
  })

  const lista = gravacoes ?? []

  return (
    <>
      <Tour id="gravacoes" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <div>
            <h1 className="display">Gravações</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              Sessões encerradas. Quem não administra vê só as próprias — uma
              gravação mostra o que a pessoa digitou em produção, e isso é mais
              sensível que a maioria dos segredos.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
          <BotaoTour aoAbrir={tour.abrir} />
          <TutorialApi
            titulo="Gravações"
            endpoints={[
              {
                metodo: 'GET',
                caminho: '/sessoes/gravacoes',
                descricao:
                  'As sessões encerradas que você pode ver, com alvo, motivo, duração e contagem de eventos. Aceita ?termo= para filtrar.',
                exemplo:
                  '[{"alvo":"srv-producao","motivo":"incidente","duracao_ms":443000,"eventos":87}]',
              },
              {
                metodo: 'GET',
                caminho: '/sessoes/{id}',
                descricao:
                  'Uma gravação com a linha do tempo completa, para reproduzir fora daqui. Abrir a gravação de outra pessoa vira evento de auditoria.',
              },
            ]}
            observacao="Abrir a gravação de outra pessoa fica registrado, com o seu nome e o horário."
          />
          </div>
        </div>
      </header>

      <Card>
        <div className="col" style={{ gap: 16 }}>
          <div className="row between wrap" style={{ gap: 12, alignItems: 'flex-end' }}>
            <div style={{ flex: '1 1 320px' }}>
              <Campo
                rotulo="Buscar"
                value={termo}
                onChange={(e) => setTermo(e.target.value)}
                ajuda="Por alvo ou motivo. Para procurar DENTRO de uma gravação, abra-a."
                placeholder="srv-producao, manutenção…"
              />
            </div>
            <div className="trilho" role="tablist" aria-label="Formato da lista">
              <button
                type="button"
                role="tab"
                aria-selected={vista === 'grade'}
                className={`aba${vista === 'grade' ? ' ativa' : ''}`}
                onClick={() => setVista('grade')}
              >
                Cartões
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={vista === 'tabela'}
                className={`aba${vista === 'tabela' ? ' ativa' : ''}`}
                onClick={() => setVista('tabela')}
              >
                Tabela
              </button>
            </div>
          </div>

          {isFetching ? (
            <Carregando texto="Buscando…" />
          ) : lista.length === 0 ? (
            <Vazio
              titulo={
                termo.trim()
                  ? `Nada encontrado para "${termo.trim()}"`
                  : 'Nenhuma sessão encerrada ainda'
              }
              descricao={
                termo.trim()
                  ? 'A busca olha alvo e motivo. O conteúdo digitado só é pesquisável dentro de cada gravação.'
                  : 'As gravações aparecem aqui quando uma sessão é encerrada.'
              }
            />
          ) : (
            <>
              <span className="help">
                {lista.length} gravaç{lista.length === 1 ? 'ão' : 'ões'}
              </span>
              {vista === 'grade' ? (
                <div className="grade-gravacoes">
                  {lista.map((s) => (
                    <CartaoGravacao key={s.id} sessao={s} />
                  ))}
                </div>
              ) : (
                <TabelaSessoes sessoes={lista} />
              )}
            </>
          )}
        </div>
      </Card>
    </>
  )
}

/**
 * Um cartão de gravação.
 *
 * A "miniatura" é a barra de atividade: cada traço é uma fatia do tempo da
 * sessão, mais alta onde houve mais eventos. Não é enfeite — ela responde
 * "esta sessão foi intensa ou esparsa" antes de abrir, que numa lista de
 * trinta gravações é o que faz escolher uma.
 */
function CartaoGravacao({ sessao }: { sessao: Sessao }) {
  const barras = perfilDeAtividade(sessao.id, sessao.eventos, sessao.duracao_ms)

  return (
    <Link to={`/sessoes/${sessao.id}`} className="cartao-gravacao" data-tour="linha-gravacao">
      <div className="gravacao-capa">
        <div className="gravacao-barras" aria-hidden="true" data-tour="barra-atividade">
          {barras.map((altura, i) => (
            <span
              key={`${sessao.id}-${i}`}
              style={{ height: `${Math.max(altura * 100, 6)}%` }}
            />
          ))}
        </div>
        <span className="gravacao-duracao">
          {formatarDuracao(sessao.duracao_ms)}
        </span>
        {sessao.captura_automatica ? (
          <span className="gravacao-selo selo-auto">capturada</span>
        ) : (
          <span className="gravacao-selo selo-manual">anotada</span>
        )}
      </div>

      <div className="gravacao-corpo">
        <b className="gravacao-alvo">{sessao.alvo}</b>
        <span className="help">{sessao.usuario_nome || sessao.usuario_label}</span>
        <div className="row wrap" style={{ gap: 6, marginTop: 6 }}>
          <Badge tom="muted">{sessao.tipo}</Badge>
          {sessao.motivo && <Badge tom="muted">{sessao.motivo}</Badge>}
        </div>
        <span className="help" style={{ marginTop: 6 }}>
          {formatarDataHora(sessao.iniciada_em)} · {sessao.eventos} evento
          {sessao.eventos === 1 ? '' : 's'}
        </span>
      </div>
    </Link>
  )
}
