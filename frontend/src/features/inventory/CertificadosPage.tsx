import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'
import { baixarJson } from '@/shared/lib/baixar'
import { NovoCertificado } from './NovoCertificado'
import { TerminalCertificado } from './TerminalCertificado'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'

type Certificado = {
  id: string
  name: string
  display_name: string
  subject: string
  issuer: string
  serial: string
  owner_label: string
  not_before: string
  not_after: string
  description: string
  estado: string
  dias_restantes: number
  tem_arquivo: boolean
  arquivo_nome: string
  arquivo_cofre: string
}

/**
 * Faixas da linha do tempo de expirações.
 *
 * São ACUMULADAS: "até 30 dias" inclui o que vence em 7. Ler cada uma como
 * fatia isolada inverte a leitura — alguém veria "até 7 = 0" ao lado de
 * "até 30 = 1" e concluiria que falta um certificado em algum lugar.
 */
const FAIXAS = [
  { rotulo: 'Vencidos', limite: 0 },
  { rotulo: 'Vencem em até 7 dias', limite: 7 },
  { rotulo: 'Em até 30 dias', limite: 30 },
  { rotulo: 'Em até 60 dias', limite: 60 },
]

export function CertificadosPage() {
  const [criando, setCriando] = useState(false)
  const tour = useTour('certificados')
  const queryClient = useQueryClient()

  const { data: certificados, isLoading, error } = useQuery({
    queryKey: ['certificados'],
    queryFn: () => request<Certificado[]>('/certificados'),
  })

  if (isLoading) return <Carregando texto="Carregando certificados…" />
  if (error) {
    return (
      <Vazio
        titulo="Nenhum certificado acessível"
        descricao="Você pode não ter permissão no caminho de certificados."
      />
    )
  }

  const lista = certificados ?? []
  const vencidos = lista.filter((c) => c.estado === 'vencido')
  const vencendo = lista.filter((c) => c.estado === 'vencendo')

  const contarFaixa = (limite: number) =>
    limite === 0
      ? vencidos.length
      : lista.filter((c) => c.dias_restantes >= 0 && c.dias_restantes <= limite).length

  return (
    <>
      <Tour id="certificados" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Certificados</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {lista.length} certificado{lista.length === 1 ? '' : 's'}, ordenados
              pelo que vence primeiro. Aqui ficam só os dados do certificado; a
              chave privada, quando guardada, fica cifrada no cofre.
            </p>
          </div>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Certificados"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/certificados',
                  descricao:
                    'Ordenados pelo que vence primeiro. Traz titular, emissor, serial, validade e se há arquivo guardado — nunca o arquivo.',
                  exemplo:
                    '[{"name":"portal","estado":"vencendo","dias_restantes":17,"tem_arquivo":true}]',
                },
                {
                  metodo: 'GET',
                  caminho: '/certificados/{nome}/exportar',
                  descricao:
                    'Os metadados de um certificado em JSON, para alimentar um monitoramento externo de vencimento.',
                },
              ]}
              observacao="Baixar o arquivo é outra rota e exige permissão de revelar no cofre: um .pfx carrega a chave privada."
            />
            <Botao
              pequeno
              data-tour="novo-certificado"
              onClick={() => setCriando(true)}
            >
              Novo certificado
            </Botao>
          </div>
        </div>
      </header>

      {vencidos.length > 0 && (
        <Alerta tom="danger">
          {vencidos.length === 1
            ? '1 certificado já venceu.'
            : `${vencidos.length} certificados já venceram.`}{' '}
          Certificado vencido derruba conexão TLS: o estado é terminal até a
          substituição.
        </Alerta>
      )}
      {vencidos.length === 0 && vencendo.length > 0 && (
        <Alerta tom="warning">
          {vencendo.length === 1
            ? '1 certificado vence nos próximos 30 dias.'
            : `${vencendo.length} certificados vencem nos próximos 30 dias.`}{' '}
          Trinta dias é o prazo mínimo para renovar emissão manual sem virar
          urgência.
        </Alerta>
      )}

      <p className="sub" style={{ margin: '0 0 -8px' }}>
        As faixas abaixo são acumuladas: o que vence em 7 dias também conta em
        30 e em 60.
      </p>

      <div className="cards" data-tour="faixas">
        {FAIXAS.map((faixa) => (
          <CardMetrica
            key={faixa.rotulo}
            rotulo={faixa.rotulo}
            valor={contarFaixa(faixa.limite)}
            tom={faixa.limite === 0 ? 'danger' : faixa.limite <= 30 ? 'warning' : 'brand'}
          />
        ))}
      </div>

      {criando && (
        <NovoCertificado
          aoFechar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            void queryClient.invalidateQueries({ queryKey: ['certificados'] })
          }}
        />
      )}

      <Card>
        {lista.length === 0 ? (
          <Vazio
            titulo="Nenhum certificado cadastrado"
            descricao="Cadastre os certificados para acompanhar vencimento antes de ele derrubar algo."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Certificado</th>
                  <th>Emissor</th>
                  <th>Responsável</th>
                  <th>Vence em</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lista.map((c) => (
                  <LinhaCertificado
                    key={c.id}
                    certificado={c}
                    aoMudar={() =>
                      void queryClient.invalidateQueries({ queryKey: ['certificados'] })
                    }
                  />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}

function LinhaCertificado({
  certificado,
  aoMudar,
}: {
  certificado: Certificado
  aoMudar: () => void
}) {
  const [aberto, setAberto] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const exportar = useMutation({
    mutationFn: () =>
      request<Record<string, unknown>>(`/certificados/${certificado.name}/exportar`),
    onSuccess: (dados) => baixarJson(dados, `certificado-${certificado.name}.json`),
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível exportar.'),
  })

  const excluir = useMutation({
    mutationFn: () =>
      request<void>(`/certificados/${certificado.name}`, { method: 'DELETE' }),
    onSuccess: () => {
      setConfirmando(false)
      aoMudar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível excluir.'),
  })

  return (
    <>
      <tr>
        <td className="strong">
          {certificado.display_name}
          <div className="help">{certificado.subject}</div>
        </td>
        <td className="muted">{certificado.issuer}</td>
        <td className="muted">{certificado.owner_label || '—'}</td>
        <td className="muted">{formatarDataHora(certificado.not_after)}</td>
        <td>
          <EstadoCertificado certificado={certificado} />
        </td>
        <td>
          <div className="row" style={{ gap: 6, justifyContent: 'flex-end' }}>
            <Botao
              pequeno
              variante="secondary"
              data-tour="ver-certificado"
              onClick={() => setAberto(!aberto)}
            >
              {aberto ? 'Fechar' : 'Ver'}
            </Botao>
            <Botao
              pequeno
              variante="secondary"
              disabled={exportar.isPending}
              onClick={() => exportar.mutate()}
            >
              {exportar.isPending ? 'Gerando…' : 'Exportar JSON'}
            </Botao>
            <Botao pequeno variante="secondary" onClick={() => setConfirmando(true)}>
              Excluir
            </Botao>
          </div>
        </td>
      </tr>

      {(aberto || confirmando || erro) && (
        <tr>
          <td colSpan={6}>
            <div className="col" style={{ gap: 10, padding: '4px 0 10px' }}>
              {erro && <Alerta tom="danger">{erro}</Alerta>}

              {aberto && (
                <div className="col" style={{ gap: 4 }}>
                  <Detalhe rotulo="Titular" valor={certificado.subject} />
                  <Detalhe rotulo="Emissor" valor={certificado.issuer} />
                  <Detalhe rotulo="Série" valor={certificado.serial || '—'} />
                  <Detalhe
                    rotulo="Válido de"
                    valor={formatarDataHora(certificado.not_before)}
                  />
                  <Detalhe
                    rotulo="Válido até"
                    valor={formatarDataHora(certificado.not_after)}
                  />
                  <Detalhe
                    rotulo="Responsável"
                    valor={certificado.owner_label || 'sem responsável definido'}
                  />
                  {certificado.description && (
                    <Detalhe rotulo="Observação" valor={certificado.description} />
                  )}
                  {certificado.tem_arquivo && (
                    <Detalhe
                      rotulo="Arquivo"
                      valor={`${certificado.arquivo_nome} — cofre ${certificado.arquivo_cofre}`}
                    />
                  )}
                  <span className="help">
                    A chave privada, quando guardada, vive cifrada no cofre e não
                    aparece aqui nem na exportação.
                  </span>
                </div>
              )}

              {aberto && (
                <TerminalCertificado
                  nomeDoCertificado={certificado.name}
                  arquivoNome={certificado.arquivo_nome}
                  temArquivo={certificado.tem_arquivo}
                />
              )}

              {confirmando && (
                <>
                  <Alerta tom="warning">
                    Excluir remove <strong>{certificado.display_name}</strong> do
                    acompanhamento de vencimento. Se o certificado ainda estiver
                    em uso, ninguém será avisado quando ele vencer — e certificado
                    vencido derruba conexão TLS.
                  </Alerta>
                  <div className="row" style={{ gap: 10 }}>
                    <Botao
                      variante="danger"
                      disabled={excluir.isPending}
                      onClick={() => excluir.mutate()}
                    >
                      {excluir.isPending ? 'Excluindo…' : 'Excluir certificado'}
                    </Botao>
                    <Botao
                      variante="secondary"
                      onClick={() => {
                        setConfirmando(false)
                        setErro(null)
                      }}
                    >
                      Cancelar
                    </Botao>
                  </div>
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  )
}

function Detalhe({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div className="row" style={{ gap: 8 }}>
      <span className="help" style={{ minWidth: 110 }}>
        {rotulo}
      </span>
      <span>{valor}</span>
    </div>
  )
}

function EstadoCertificado({ certificado }: { certificado: Certificado }) {
  if (certificado.estado === 'vencido') {
    const dias = Math.abs(certificado.dias_restantes)
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="danger">Vencido</Badge>
        <span className="help">
          há {dias} dia{dias === 1 ? '' : 's'}
        </span>
      </div>
    )
  }
  if (certificado.estado === 'vencendo') {
    return (
      <div className="col" style={{ gap: 4 }}>
        <Badge tom="warning">Vencendo</Badge>
        <span className="help">
          em {certificado.dias_restantes} dia
          {certificado.dias_restantes === 1 ? '' : 's'}
        </span>
      </div>
    )
  }
  return (
    <div className="col" style={{ gap: 4 }}>
      <Badge tom="success">Válido</Badge>
      <span className="help">
        {certificado.dias_restantes} dias restantes
      </span>
    </div>
  )
}
