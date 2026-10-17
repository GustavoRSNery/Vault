import { useQuery } from '@tanstack/react-query'
import { request } from '@/shared/api/client'
import { Alerta, Badge, Card, Carregando, Vazio } from '@/shared/ui/components'

type Evento = {
  id: string
  sequence: number
  action: string
  actor_label: string
  target_path: string
  outcome: string
  reason: string
  ip_address: string | null
  occurred_at: string
}

type Trilha = {
  eventos: Evento[]
  total: number
  escopo: 'tudo' | 'proprios'
}

type Integridade = {
  integra: boolean
  eventos_verificados: number
  ancoras_conferidas: number
  quebras: string[]
  aviso: string | null
}

const ROTULO_ACAO: Record<string, string> = {
  login_sucesso: 'Entrou',
  login_falha: 'Falha ao entrar',
  logout: 'Saiu',
  mfa_cadastrado: 'Ativou o segundo fator',
  segredo_criado: 'Criou segredo',
  segredo_revelado: 'Revelou segredo',
  segredo_atualizado: 'Atualizou segredo',
  segredo_excluido: 'Moveu para a lixeira',
  segredo_restaurado: 'Restaurou segredo',
  cofre_criado: 'Criou cofre',
  cofre_selado: 'Selou cofre',
  cofre_desselado: 'Desselou cofre',
  permissao_concedida: 'Concedeu permissão',
  permissao_revogada: 'Revogou permissão',
  acesso_negado: 'Acesso negado',
}

function formatarData(iso: string): string {
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return '—'
  return data.toLocaleString('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function AuditoriaPage() {
  const { data: trilha, isLoading } = useQuery({
    queryKey: ['auditoria'],
    queryFn: () => request<Trilha>('/auditoria?limite=200'),
  })

  // A verificação só existe para administradores; o 403 é esperado e não
  // deve virar erro na tela de quem não é.
  const { data: integridade } = useQuery({
    queryKey: ['auditoria', 'integridade'],
    queryFn: () => request<Integridade>('/auditoria/integridade'),
    retry: false,
    enabled: trilha?.escopo === 'tudo',
  })

  if (isLoading) return <Carregando texto="Carregando trilha…" />

  return (
    <>
      <header>
        <h1 className="display">Auditoria</h1>
        <p className="sub">
          {trilha?.escopo === 'tudo'
            ? 'Todos os eventos registrados no sistema.'
            : 'Os eventos registrados em seu nome.'}{' '}
          {trilha?.total ?? 0} no total.
        </p>
      </header>

      {integridade && (
        <Card titulo="Integridade da trilha">
          <div className="col" style={{ gap: 12 }}>
            <div className="row" style={{ gap: 12 }}>
              {integridade.integra ? (
                <Badge tom="success">Cadeia íntegra</Badge>
              ) : (
                <Badge tom="danger">Cadeia rompida</Badge>
              )}
              <span className="muted">
                {integridade.eventos_verificados} eventos verificados ·{' '}
                {integridade.ancoras_conferidas} âncora(s) externa(s)
              </span>
            </div>

            {/* Sem âncora, "íntegra" garante menos do que parece. Dizer isso
                evita que o selo verde passe uma confiança que ele não tem. */}
            {integridade.aviso && <Alerta tom="warning">{integridade.aviso}</Alerta>}

            {integridade.quebras.map((quebra) => (
              <Alerta key={quebra} tom="danger">
                {quebra}
              </Alerta>
            ))}
          </div>
        </Card>
      )}

      <Card>
        {!trilha || trilha.eventos.length === 0 ? (
          <Vazio titulo="Nenhum evento ainda" />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Quando</th>
                  <th>Quem</th>
                  <th>O quê</th>
                  <th>Alvo</th>
                  <th>Resultado</th>
                </tr>
              </thead>
              <tbody>
                {trilha.eventos.map((evento) => (
                  <tr key={evento.id}>
                    <td className="secret-sm muted">{evento.sequence}</td>
                    <td className="muted" style={{ whiteSpace: 'nowrap' }}>
                      {formatarData(evento.occurred_at)}
                    </td>
                    <td className="strong">{evento.actor_label}</td>
                    <td>{ROTULO_ACAO[evento.action] ?? evento.action}</td>
                    <td className="secret-sm muted">{evento.target_path}</td>
                    <td>
                      {evento.outcome === 'sucesso' ? (
                        <Badge tom="success">Sucesso</Badge>
                      ) : (
                        <Badge tom="danger">Falha</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </>
  )
}
