import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { CampoSegredo } from '@/features/secrets/CampoSegredo'
import { SeloQuorum } from './SeloQuorum'
import { Alerta, Badge, Botao, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

type Segredo = {
  id: string
  name: string
  kind: string
  description: string
  current_version: number
  updated_at: string
}

type Versao = {
  version: number
  created_by: string
  created_at: string
  is_current: boolean
}

type Cofre = {
  name: string
  display_name: string
  state: string
}

const ROTULO_TIPO: Record<string, string> = {
  senha: 'Senha',
  chave_api: 'Chave de API',
  chave_ssh: 'Chave SSH',
  certificado: 'Certificado',
  token: 'Token',
  nota: 'Nota',
}

export function CofreDetalhePage() {
  const { nome = '' } = useParams<{ nome: string }>()
  const queryClient = useQueryClient()
  const [aberto, setAberto] = useState<string | null>(null)
  const [historicoDe, setHistoricoDe] = useState<string | null>(null)
  const [criando, setCriando] = useState(false)
  const [verLixeira, setVerLixeira] = useState(false)
  const [erro, setErro] = useState<string | null>(null)

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['segredos', nome] })
    void queryClient.invalidateQueries({ queryKey: ['lixeira', nome] })
    void queryClient.invalidateQueries({ queryKey: ['cofres'] })
  }

  const { data: cofres } = useQuery({
    queryKey: ['cofres'],
    queryFn: () => request<Cofre[]>('/cofres'),
  })
  const cofre = cofres?.find((c) => c.name === nome)
  const selado = cofre?.state === 'selado'

  const { data: segredos, isLoading, error } = useQuery({
    queryKey: ['segredos', nome],
    queryFn: () => request<Segredo[]>(`/cofres/${encodeURIComponent(nome)}/segredos`),
    enabled: nome !== '',
  })

  const { data: lixeira } = useQuery({
    queryKey: ['lixeira', nome],
    queryFn: () => request<Segredo[]>(`/cofres/${encodeURIComponent(nome)}/lixeira`),
    enabled: nome !== '' && verLixeira,
  })

  const { data: versoes } = useQuery({
    queryKey: ['versoes', nome, historicoDe],
    queryFn: () =>
      request<Versao[]>(
        `/cofres/${encodeURIComponent(nome)}/segredos/${encodeURIComponent(historicoDe ?? '')}/versoes`,
      ),
    enabled: historicoDe !== null,
  })

  const alternarSelo = useMutation({
    mutationFn: () =>
      request<Cofre>(
        `/cofres/${encodeURIComponent(nome)}/${selado ? 'desselar' : 'selar'}`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível alterar o selo.'),
  })

  const excluir = useMutation({
    mutationFn: (segredo: string) =>
      request<Segredo>(
        `/cofres/${encodeURIComponent(nome)}/segredos/${encodeURIComponent(segredo)}`,
        { method: 'DELETE' },
      ),
    onSuccess: () => {
      setAberto(null)
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível excluir.'),
  })

  const restaurar = useMutation({
    mutationFn: (segredo: string) =>
      request<Segredo>(
        `/cofres/${encodeURIComponent(nome)}/segredos/${encodeURIComponent(segredo)}/restaurar`,
        { method: 'POST' },
      ),
    onSuccess: () => {
      setErro(null)
      invalidar()
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível restaurar.'),
  })

  if (isLoading) return <Carregando texto="Carregando segredos…" />
  if (error) {
    return (
      <Vazio
        titulo="Não foi possível abrir o cofre"
        descricao="Você pode não ter acesso a ele."
      />
    )
  }

  return (
    <>
      <header>
        <nav className="crumbs" style={{ marginBottom: 6 }}>
          <Link to="/cofres">Cofres</Link> <span aria-hidden="true">›</span>{' '}
          {cofre?.display_name ?? nome}
        </nav>
        <div className="row between wrap">
          <div>
            <h1 className="display">{cofre?.display_name ?? nome}</h1>
            <p className="sub" style={{ margin: '4px 0 0' }}>
              {segredos?.length ?? 0} segredo{(segredos?.length ?? 0) === 1 ? '' : 's'}.
              Todo valor nasce mascarado e cada revelação é registrada em auditoria.
            </p>
          </div>
          <div className="row" style={{ gap: 10 }}>
            {selado && <Badge tom="danger">Selado</Badge>}
            <Botao
              variante="secondary"
              pequeno
              onClick={() => alternarSelo.mutate()}
              disabled={alternarSelo.isPending}
            >
              {selado ? 'Desselar cofre' : 'Selar cofre'}
            </Botao>
            <Botao pequeno onClick={() => setCriando(true)} disabled={selado}>
              Novo segredo
            </Botao>
          </div>
        </div>
      </header>

      {erro && <Alerta tom="danger">{erro}</Alerta>}
      {selado && (
        <Alerta tom="warning">
          Este cofre está selado: nenhum segredo pode ser lido ou alterado até que
          um administrador o desselasse.
        </Alerta>
      )}

      <SeloQuorum cofre={nome} selado={selado} />

      {criando && (
        <NovoSegredo
          cofre={nome}
          aoFechar={() => setCriando(false)}
          aoCriar={() => {
            setCriando(false)
            invalidar()
          }}
        />
      )}

      <Card>
        {!segredos || segredos.length === 0 ? (
          <Vazio
            titulo="Nenhum segredo neste cofre"
            descricao="Os segredos criados aqui aparecerão nesta lista."
          />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Segredo</th>
                  <th>Tipo</th>
                  <th>Versão</th>
                  <th>Atualizado</th>
                  <th>Valor</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {segredos.map((segredo) => (
                  <tr key={segredo.id}>
                    <td className="strong">
                      {segredo.name}
                      {segredo.description && (
                        <div className="help">{segredo.description}</div>
                      )}
                    </td>
                    <td className="muted">{ROTULO_TIPO[segredo.kind] ?? segredo.kind}</td>
                    <td className="secret-sm">
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() =>
                          setHistoricoDe(
                            historicoDe === segredo.name ? null : segredo.name,
                          )
                        }
                      >
                        v{segredo.current_version}
                      </button>
                    </td>
                    <td className="muted">{formatarDataHora(segredo.updated_at)}</td>
                    <td style={{ minWidth: 340 }}>
                      {aberto === segredo.name ? (
                        <CampoSegredo cofre={nome} segredo={segredo.name} />
                      ) : (
                        <Botao
                          variante="secondary"
                          pequeno
                          onClick={() => setAberto(segredo.name)}
                          disabled={selado}
                        >
                          Acessar
                        </Botao>
                      )}
                    </td>
                    <td>
                      <Botao
                        variante="ghost"
                        pequeno
                        onClick={() => excluir.mutate(segredo.name)}
                        disabled={selado || excluir.isPending}
                      >
                        Excluir
                      </Botao>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {historicoDe && versoes && (
        <Card titulo={`Histórico de ${historicoDe}`}>
          <p className="sub" style={{ marginTop: 0 }}>
            O histórico mostra quando e por quem cada versão foi gravada — nunca os
            valores anteriores.
          </p>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Versão</th>
                  <th>Gravada em</th>
                  <th>Situação</th>
                </tr>
              </thead>
              <tbody>
                {versoes.map((versao) => (
                  <tr key={versao.version}>
                    <td className="secret-sm strong">v{versao.version}</td>
                    <td className="muted">{formatarDataHora(versao.created_at)}</td>
                    <td>
                      {versao.is_current ? (
                        <Badge tom="brand">Atual</Badge>
                      ) : (
                        <Badge tom="muted">Anterior</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card
        titulo="Lixeira"
        acao={
          <Botao variante="ghost" pequeno onClick={() => setVerLixeira(!verLixeira)}>
            {verLixeira ? 'Ocultar' : 'Mostrar'}
          </Botao>
        }
      >
        {!verLixeira ? (
          <p className="sub" style={{ margin: 0 }}>
            Segredos excluídos continuam recuperáveis.
          </p>
        ) : !lixeira || lixeira.length === 0 ? (
          <Vazio titulo="A lixeira está vazia" />
        ) : (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Segredo</th>
                  <th>Versões</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {lixeira.map((segredo) => (
                  <tr key={segredo.id}>
                    <td className="strong">{segredo.name}</td>
                    <td className="secret-sm muted">{segredo.current_version}</td>
                    <td>
                      <Botao
                        variante="secondary"
                        pequeno
                        onClick={() => restaurar.mutate(segredo.name)}
                        disabled={selado || restaurar.isPending}
                      >
                        Restaurar
                      </Botao>
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

function NovoSegredo({
  cofre,
  aoFechar,
  aoCriar,
}: {
  cofre: string
  aoFechar: () => void
  aoCriar: () => void
}) {
  const [nome, setNome] = useState('')
  const [valor, setValor] = useState('')
  const [descricao, setDescricao] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const criar = useMutation({
    mutationFn: () =>
      request(`/cofres/${encodeURIComponent(cofre)}/segredos`, {
        method: 'POST',
        body: { name: nome, value: valor, description: descricao, kind: 'senha' },
      }),
    onSuccess: aoCriar,
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível criar o segredo.'),
  })

  return (
    <Card titulo="Novo segredo">
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}
        <Campo
          rotulo="Nome"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          ajuda="Letras minúsculas, números e hífen. Ex.: senha-root."
          autoFocus
        />
        <Campo
          rotulo="Valor"
          type="password"
          value={valor}
          onChange={(e) => setValor(e.target.value)}
          ajuda="É cifrado antes de sair do servidor e nunca fica legível no banco."
        />
        <Campo
          rotulo="Descrição"
          value={descricao}
          onChange={(e) => setDescricao(e.target.value)}
          ajuda="Opcional."
        />
        <div className="row" style={{ gap: 10 }}>
          <Botao
            onClick={() => criar.mutate()}
            disabled={!nome || !valor || criar.isPending}
          >
            {criar.isPending ? 'Criando…' : 'Criar segredo'}
          </Botao>
          <Botao variante="secondary" onClick={aoFechar}>
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}
