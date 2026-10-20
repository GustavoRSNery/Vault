import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, CardMetrica, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'
import { baixarJson } from '@/shared/lib/baixar'

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
      <header>
        <div className="row between wrap">
          <div>
            <h1 className="display">Certificados</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {lista.length} certificado{lista.length === 1 ? '' : 's'}, ordenados
              pelo que vence primeiro. Só metadados e validade — a chave privada,
              quando guardada, vive cifrada no cofre.
            </p>
          </div>
          <Botao pequeno onClick={() => setCriando(true)}>
            Novo certificado
          </Botao>
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

      <div className="cards">
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
            <Botao pequeno variante="secondary" onClick={() => setAberto(!aberto)}>
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
                  <span className="help">
                    A chave privada, quando guardada, vive cifrada no cofre e não
                    aparece aqui nem na exportação.
                  </span>
                </div>
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

function NovoCertificado({
  aoFechar,
  aoCriar,
}: {
  aoFechar: () => void
  aoCriar: () => void
}) {
  const [nome, setNome] = useState('')
  const [titular, setTitular] = useState('')
  const [emissor, setEmissor] = useState('')
  const [responsavel, setResponsavel] = useState('')
  const [inicio, setInicio] = useState('')
  const [fim, setFim] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const identificador = nome
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
    .slice(0, 64)

  const criar = useMutation({
    mutationFn: () =>
      request<Certificado>('/certificados', {
        method: 'POST',
        body: {
          name: identificador,
          display_name: nome,
          subject: titular || `CN=${nome}`,
          issuer: emissor,
          owner_label: responsavel,
          // O input date devolve só a data; a API espera instante com fuso.
          not_before: new Date(`${inicio}T00:00:00`).toISOString(),
          not_after: new Date(`${fim}T23:59:59`).toISOString(),
        },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível cadastrar.'),
  })

  const invalido =
    identificador === '' || emissor.trim() === '' || inicio === '' || fim === ''

  return (
    <Card titulo="Novo certificado">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda={
            identificador ? `Identificador: ${identificador}` : 'Ex.: api.exemplo.com.br.'
          }
          autoFocus
        />
        <Campo
          rotulo="Titular (subject)"
          value={titular}
          onChange={(e) => setTitular(e.target.value)}
          ajuda={`Opcional. Em branco, usa CN=${nome || '…'}.`}
        />
        <Campo
          rotulo="Emissor"
          value={emissor}
          onChange={(e) => setEmissor(e.target.value)}
          ajuda="Ex.: Let's Encrypt, DigiCert, AC interna."
        />
        <Campo
          rotulo="Responsável"
          value={responsavel}
          onChange={(e) => setResponsavel(e.target.value)}
          ajuda="Quem renova. Opcional, mas é quem será procurado no vencimento."
        />
        <Campo
          rotulo="Válido de"
          type="date"
          value={inicio}
          onChange={(e) => setInicio(e.target.value)}
        />
        <Campo
          rotulo="Válido até"
          type="date"
          value={fim}
          onChange={(e) => setFim(e.target.value)}
        />

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={() => criar.mutate()} disabled={invalido || criar.isPending}>
            {criar.isPending ? 'Cadastrando…' : 'Cadastrar'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
