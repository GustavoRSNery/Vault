/**
 * O conteúdo de cada aba do painel.
 *
 * Uma aba por página do grupo "Segredos" do menu, mais o resumo. A ideia é
 * que o painel responda **antes** de a pessoa abrir a página: a aba mostra o
 * estado do domínio e aponta o que precisa de ação, e o link leva à lista
 * completa quando ela quiser agir.
 *
 * Nenhuma aba lista recursos um a um — isso é trabalho da página de destino,
 * que tem filtro, busca e paginação. Duplicar a lista aqui criaria duas
 * telas para manter e duas versões da mesma verdade.
 */

import { Link } from 'react-router-dom'
import { Card, CardMetrica } from '@/shared/ui/components'
import { BarraDeProporcao } from '@/shared/charts'

export type Destaque = { rotulo: string; quantas: number; tom: string }

export type Panorama = {
  cofres: {
    total: number
    ativos: number
    selados: number
    segredos: number
    na_lixeira: number
    destaques: Destaque[]
  }
  credenciais: {
    total: number
    em_custodia: number
    custodia_vencida: number
    rotacao_atrasada: number
    nunca_rotacionadas: number
    destaques: Destaque[]
  }
  certificados: {
    total: number
    vencidos: number
    vencendo: number
    validos: number
    proximo_nome: string
    proximo_dias: number | null
    destaques: Destaque[]
  }
  chaves: {
    total: number
    ativas: number
    revogadas: number
    expiradas: number
    sem_vencimento: number
    destaques: Destaque[]
  }
  dispositivos: {
    total: number
    ativos: number
    com_acesso_remoto: number
    sem_credencial: number
    destaques: Destaque[]
  }
}

/**
 * Linha de destaque: "3 vencidos".
 *
 * Em zero, a linha muda de tom e de texto em vez de sumir. Um bloco que
 * desaparece quando está tudo bem faz a ausência parecer falta de dado — e
 * "nenhum vencido" é informação que vale ser lida.
 */
function LinhaDeDestaque({ destaque }: { destaque: Destaque }) {
  const zerado = destaque.quantas === 0
  return (
    <div className="row between" style={{ gap: 12 }}>
      <span className="row" style={{ gap: 8 }}>
        <span
          className={`ponto d-${zerado ? 'muted' : destaque.tom}`}
          aria-hidden="true"
        />
        <span className={zerado ? 'help' : undefined}>{destaque.rotulo}</span>
      </span>
      <b
        style={{
          color: zerado ? 'var(--ink-muted)' : `var(--${destaque.tom}-text, var(--ink))`,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {destaque.quantas}
      </b>
    </div>
  )
}

function Destaques({ itens }: { itens: Destaque[] }) {
  return (
    <div className="col" style={{ gap: 10 }}>
      {itens.map((d) => (
        <LinhaDeDestaque key={d.rotulo} destaque={d} />
      ))}
    </div>
  )
}

function VerTudo({ para, texto }: { para: string; texto: string }) {
  return (
    <Link to={para} className="btn btn-secondary btn-sm">
      {texto} →
    </Link>
  )
}

export function AbaCofres({ dados }: { dados: Panorama['cofres'] }) {
  return (
    <>
      <div className="cards-3">
        <CardMetrica rotulo="Cofres" valor={dados.total} tom="brand" />
        <CardMetrica
          rotulo="Ativos"
          valor={dados.ativos}
          tom="success"
          de={dados.total}
        />
        <CardMetrica
          rotulo="Selados"
          valor={dados.selados}
          tom="danger"
          de={dados.total}
        />
      </div>

      <div className="cards-2">
        <Card titulo="Segredos guardados" acao={<VerTudo para="/cofres" texto="Abrir cofres" />}>
          <div className="col" style={{ gap: 14 }}>
            <div className="row" style={{ gap: 24, alignItems: 'baseline' }}>
              <span>
                <span className="val" style={{ fontSize: 30, fontWeight: 700 }}>
                  {dados.segredos}
                </span>{' '}
                <span className="help">ativos</span>
              </span>
              <span>
                <span style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink-muted)' }}>
                  {dados.na_lixeira}
                </span>{' '}
                <span className="help">na lixeira</span>
              </span>
            </div>
            <p className="help" style={{ margin: 0 }}>
              O que está na lixeira continua recuperável e não conta como acervo
              ativo.
            </p>
          </div>
        </Card>

        <Card titulo="Atenção">
          <Destaques itens={dados.destaques} />
        </Card>
      </div>
    </>
  )
}

export function AbaCredenciais({ dados }: { dados: Panorama['credenciais'] }) {
  return (
    <>
      <div className="cards-3">
        <CardMetrica rotulo="Credenciais" valor={dados.total} tom="brand" />
        <CardMetrica
          rotulo="Em custódia"
          valor={dados.em_custodia}
          tom="warning"
          de={dados.total}
        />
        <CardMetrica
          rotulo="Rotação atrasada"
          valor={dados.rotacao_atrasada}
          tom="danger"
          de={dados.total}
        />
      </div>

      <div className="cards-2">
        <Card
          titulo="Situação da rotação"
          acao={<VerTudo para="/credenciais" texto="Abrir credenciais" />}
        >
          <div className="col" style={{ gap: 12 }}>
            <BarraDeProporcao
              partes={[
                { nome: 'Em dia', valor: dados.total - dados.rotacao_atrasada, classe: 'k-sucesso' },
                { nome: 'Atrasada', valor: dados.rotacao_atrasada, classe: 'k-negado' },
              ]}
            />
            <div className="g-legenda">
              <span className="item">
                <span className="chave k-sucesso" /> Em dia ·{' '}
                {dados.total - dados.rotacao_atrasada}
              </span>
              <span className="item">
                <span className="chave k-negado" /> Atrasada · {dados.rotacao_atrasada}
              </span>
            </div>
            {dados.nunca_rotacionadas > 0 && (
              <p className="help" style={{ margin: 0 }}>
                <b style={{ color: 'var(--warning-text)' }}>
                  {dados.nunca_rotacionadas} nunca foi rotacionada
                </b>{' '}
                — pode ainda ser a senha de fábrica.
              </p>
            )}
          </div>
        </Card>

        <Card titulo="Atenção">
          <Destaques itens={dados.destaques} />
        </Card>
      </div>
    </>
  )
}

export function AbaCertificados({ dados }: { dados: Panorama['certificados'] }) {
  return (
    <>
      <div className="cards-3">
        <CardMetrica rotulo="Certificados" valor={dados.total} tom="brand" />
        <CardMetrica
          rotulo="Vencidos"
          valor={dados.vencidos}
          tom="danger"
          de={dados.total}
        />
        <CardMetrica
          rotulo="Vencendo"
          valor={dados.vencendo}
          tom="warning"
          de={dados.total}
        />
      </div>

      <div className="cards-2">
        <Card
          titulo="Próximo a vencer"
          acao={<VerTudo para="/certificados" texto="Abrir certificados" />}
        >
          {dados.proximo_nome ? (
            <div className="col" style={{ gap: 10 }}>
              <div className="row" style={{ gap: 12, alignItems: 'baseline' }}>
                <span
                  style={{
                    fontSize: 30,
                    fontWeight: 700,
                    color:
                      (dados.proximo_dias ?? 999) <= 30
                        ? 'var(--warning-text)'
                        : 'var(--ink)',
                  }}
                >
                  {dados.proximo_dias}
                </span>
                <span className="help">dia(s)</span>
              </div>
              <b>{dados.proximo_nome}</b>
              <p className="help" style={{ margin: 0 }}>
                Certificado vencido derruba conexão TLS — e renovar emissão
                manual leva dias.
              </p>
            </div>
          ) : (
            <p className="help" style={{ margin: 0 }}>
              Nenhum certificado cadastrado.
            </p>
          )}
        </Card>

        <Card titulo="Atenção">
          <Destaques itens={dados.destaques} />
        </Card>
      </div>
    </>
  )
}

export function AbaChaves({ dados }: { dados: Panorama['chaves'] }) {
  return (
    <>
      <div className="cards-3">
        <CardMetrica rotulo="Chaves de API" valor={dados.total} tom="brand" />
        <CardMetrica
          rotulo="Ativas"
          valor={dados.ativas}
          tom="success"
          de={dados.total}
        />
        <CardMetrica
          rotulo="Revogadas"
          valor={dados.revogadas}
          tom="muted"
          de={dados.total}
        />
      </div>

      <div className="cards-2">
        <Card
          titulo="Ciclo de vida"
          acao={<VerTudo para="/chaves-api" texto="Abrir chaves" />}
        >
          <div className="col" style={{ gap: 12 }}>
            <BarraDeProporcao
              partes={[
                { nome: 'Ativas', valor: dados.ativas, classe: 'k-sucesso' },
                { nome: 'Expiradas', valor: dados.expiradas, classe: 'k-negado' },
                { nome: 'Revogadas', valor: dados.revogadas, classe: 'k-volume' },
              ]}
            />
            <div className="g-legenda">
              <span className="item">
                <span className="chave k-sucesso" /> Ativas · {dados.ativas}
              </span>
              <span className="item">
                <span className="chave k-negado" /> Expiradas · {dados.expiradas}
              </span>
              <span className="item">
                <span className="chave k-volume" /> Revogadas · {dados.revogadas}
              </span>
            </div>
            {dados.sem_vencimento > 0 && (
              <p className="help" style={{ margin: 0 }}>
                <b style={{ color: 'var(--warning-text)' }}>
                  {dados.sem_vencimento} ativa(s) sem vencimento
                </b>{' '}
                — sem prazo, ninguém decide quando elas saem de circulação.
              </p>
            )}
          </div>
        </Card>

        <Card titulo="Atenção">
          <Destaques itens={dados.destaques} />
        </Card>
      </div>
    </>
  )
}

export function AbaDispositivos({ dados }: { dados: Panorama['dispositivos'] }) {
  return (
    <>
      <div className="cards-3">
        <CardMetrica rotulo="Dispositivos" valor={dados.total} tom="brand" />
        <CardMetrica
          rotulo="Ativos"
          valor={dados.ativos}
          tom="success"
          de={dados.total}
        />
        <CardMetrica
          rotulo="Com acesso remoto"
          valor={dados.com_acesso_remoto}
          tom="warning"
          de={dados.total}
        />
      </div>

      <div className="cards-2">
        <Card
          titulo="Cobertura"
          acao={<VerTudo para="/dispositivos" texto="Abrir dispositivos" />}
        >
          <div className="col" style={{ gap: 12 }}>
            <BarraDeProporcao
              partes={[
                {
                  nome: 'Com credencial',
                  valor: dados.total - dados.sem_credencial,
                  classe: 'k-sucesso',
                },
                { nome: 'Sem credencial', valor: dados.sem_credencial, classe: 'k-volume' },
              ]}
            />
            <p className="help" style={{ margin: 0 }}>
              Dispositivo sem credencial no cofre é acesso que ainda mora fora
              dele — em planilha, bilhete ou na memória de alguém.
            </p>
          </div>
        </Card>

        <Card titulo="Atenção">
          <Destaques itens={dados.destaques} />
        </Card>
      </div>
    </>
  )
}
