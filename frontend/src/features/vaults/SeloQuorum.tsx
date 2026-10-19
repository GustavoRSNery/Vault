import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card, Vazio } from '@/shared/ui/components'
import { formatarDataHora } from '@/shared/lib/formato'

type Selo = {
  limiar: number
  total_quinhoes: number
  portadores: string[]
  selado_por: string
  selado_em: string
}

type Quinhao = {
  indice: number
  portador: string
  valor: string
}

type Selagem = {
  selo: Selo
  quinhoes: Quinhao[]
  aviso: string
}

/**
 * Selagem com quórum de um cofre.
 *
 * Os quinhões aparecem uma única vez, logo após a selagem, e o sistema não os
 * guarda. A tela precisa deixar isso evidente ANTES de a pessoa fechar a
 * janela — quem acha que dá para consultar depois descobre tarde demais que
 * não dá, e aí o cofre não abre mais.
 */
export function SeloQuorum({ cofre, selado }: { cofre: string; selado: boolean }) {
  const queryClient = useQueryClient()
  const [selando, setSelando] = useState(false)
  const [abrindo, setAbrindo] = useState(false)
  const [emitidos, setEmitidos] = useState<Selagem | null>(null)
  const [erro, setErro] = useState<string | null>(null)

  const { data: selo } = useQuery({
    queryKey: ['selo', cofre],
    queryFn: () => request<Selo | null>(`/cofres/${encodeURIComponent(cofre)}/selo`),
    retry: false,
  })

  const invalidar = () => {
    void queryClient.invalidateQueries({ queryKey: ['selo', cofre] })
    void queryClient.invalidateQueries({ queryKey: ['cofres'] })
    void queryClient.invalidateQueries({ queryKey: ['segredos', cofre] })
  }

  if (emitidos) {
    return (
      <QuinhoesEmitidos
        selagem={emitidos}
        aoFechar={() => {
          setEmitidos(null)
          invalidar()
        }}
      />
    )
  }

  return (
    <Card
      titulo="Selagem com quórum"
      acao={
        selo ? (
          <Botao variante="secondary" pequeno onClick={() => setAbrindo(!abrindo)}>
            {abrindo ? 'Cancelar' : 'Abrir com quinhões'}
          </Botao>
        ) : (
          <Botao variante="secondary" pequeno onClick={() => setSelando(!selando)}>
            {selando ? 'Cancelar' : 'Selar com quórum'}
          </Botao>
        )
      }
    >
      <div className="col" style={{ gap: 14 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        {!selo ? (
          <>
            <p className="sub" style={{ margin: 0 }}>
              Selar com quórum faz a abertura exigir várias pessoas. Sem isso,
              selar é frágil: quem sela desela sozinho, e um administrador
              comprometido abre o cofre na mesma sessão.
            </p>
            {selando && (
              <FormularioSelagem
                cofre={cofre}
                aoSelar={(dados) => {
                  setSelando(false)
                  setErro(null)
                  setEmitidos(dados)
                }}
                aoErro={setErro}
              />
            )}
          </>
        ) : (
          <>
            <div className="row wrap" style={{ gap: 10, alignItems: 'center' }}>
              <Badge tom="danger">
                Exige {selo.limiar} de {selo.total_quinhoes}
              </Badge>
              <span className="help">
                Selado por {selo.selado_por} em {formatarDataHora(selo.selado_em)}
              </span>
            </div>

            <div className="col" style={{ gap: 6 }}>
              <span className="help" style={{ fontWeight: 600 }}>
                Quem precisa ser chamado
              </span>
              <div className="row wrap" style={{ gap: 6 }}>
                {selo.portadores.map((p) => (
                  <Badge key={p} tom="muted">
                    {p}
                  </Badge>
                ))}
              </div>
            </div>

            {!selado && (
              <Alerta tom="warning">
                O cofre consta como ativo, mas tem selo com quórum pendente.
                Isso não deveria acontecer — vale conferir.
              </Alerta>
            )}

            {abrindo && (
              <FormularioAbertura
                cofre={cofre}
                selo={selo}
                aoAbrir={() => {
                  setAbrindo(false)
                  setErro(null)
                  invalidar()
                }}
                aoErro={setErro}
              />
            )}
          </>
        )}
      </div>
    </Card>
  )
}

function FormularioSelagem({
  cofre,
  aoSelar,
  aoErro,
}: {
  cofre: string
  aoSelar: (dados: Selagem) => void
  aoErro: (mensagem: string) => void
}) {
  const [texto, setTexto] = useState('')
  const [limiar, setLimiar] = useState(2)

  const portadores = texto
    .split(/[\n,;]/)
    .map((p) => p.trim())
    .filter(Boolean)

  const selar = useMutation({
    mutationFn: () =>
      request<Selagem>(`/cofres/${encodeURIComponent(cofre)}/selar-com-quorum`, {
        method: 'POST',
        body: { portadores, limiar },
      }),
    onSuccess: aoSelar,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível selar.'),
  })

  const repetidos = portadores.length !== new Set(portadores).size
  const invalido =
    portadores.length < 2 || limiar < 2 || limiar > portadores.length || repetidos

  return (
    <div className="col" style={{ gap: 14 }}>
      <div className="field">
        <label htmlFor="portadores">Portadores dos quinhões</label>
        <textarea
          id="portadores"
          className="input"
          rows={4}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder={'ana@empresa.com.br\nbruno@empresa.com.br\ncarla@empresa.com.br'}
        />
        <span className="help">
          Um por linha. Cada pessoa recebe um quinhão diferente — a mesma
          pessoa duas vezes reduziria o quórum real sem ninguém perceber.
        </span>
      </div>

      <div className="field">
        <label htmlFor="limiar">Quantas pessoas para abrir</label>
        <select
          id="limiar"
          className="input"
          value={limiar}
          onChange={(e) => setLimiar(Number(e.target.value))}
        >
          {Array.from({ length: Math.max(portadores.length - 1, 1) }, (_, i) => i + 2)
            .filter((n) => n <= Math.max(portadores.length, 2))
            .map((n) => (
              <option key={n} value={n}>
                {n} de {portadores.length || '…'}
              </option>
            ))}
        </select>
        <span className="help">
          Mínimo 2: com 1, selar não protegeria de ninguém.
        </span>
      </div>

      {repetidos && (
        <Alerta tom="warning">
          Há portador repetido. A mesma pessoa com dois quinhões faz o quórum
          valer menos do que parece.
        </Alerta>
      )}

      <Alerta tom="warning">
        Os quinhões aparecerão <b>uma única vez</b>, na tela seguinte. O
        sistema não os guarda: se todos forem perdidos, este cofre não poderá
        mais ser aberto.
      </Alerta>

      <div className="row" style={{ gap: 10 }}>
        <Botao onClick={() => selar.mutate()} disabled={invalido || selar.isPending}>
          {selar.isPending ? 'Selando…' : `Selar exigindo ${limiar} de ${portadores.length || '…'}`}
        </Botao>
      </div>
    </div>
  )
}

function QuinhoesEmitidos({
  selagem,
  aoFechar,
}: {
  selagem: Selagem
  aoFechar: () => void
}) {
  const [confirmou, setConfirmou] = useState(false)

  return (
    <Card titulo="Quinhões emitidos">
      <div className="col" style={{ gap: 16 }}>
        <Alerta tom="danger">{selagem.aviso}</Alerta>

        <div className="col" style={{ gap: 12 }}>
          {selagem.quinhoes.map((q) => (
            <div
              key={q.indice}
              className="col"
              style={{
                gap: 6,
                padding: 14,
                borderRadius: 10,
                background: 'var(--surface-2, rgba(0,0,0,.03))',
              }}
            >
              <div className="row between wrap" style={{ gap: 8 }}>
                <b>{q.portador}</b>
                <Badge tom="muted">quinhão {q.indice}</Badge>
              </div>
              <code
                className="secret-sm"
                style={{ wordBreak: 'break-all', lineHeight: 1.5 }}
              >
                {q.valor}
              </code>
              <Botao
                variante="ghost"
                pequeno
                onClick={() => void navigator.clipboard?.writeText(q.valor)}
              >
                Copiar
              </Botao>
            </div>
          ))}
        </div>

        <label className="row" style={{ gap: 8, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={confirmou}
            onChange={(e) => setConfirmou(e.target.checked)}
          />
          <span className="help">
            Entreguei cada quinhão ao seu portador e entendo que eles não
            poderão ser consultados novamente.
          </span>
        </label>

        <div className="row" style={{ gap: 10 }}>
          <Botao onClick={aoFechar} disabled={!confirmou}>
            Concluir
          </Botao>
        </div>
      </div>
    </Card>
  )
}

function FormularioAbertura({
  cofre,
  selo,
  aoAbrir,
  aoErro,
}: {
  cofre: string
  selo: Selo
  aoAbrir: () => void
  aoErro: (mensagem: string) => void
}) {
  const [texto, setTexto] = useState('')

  const quinhoes = texto
    .split(/[\n,;\s]+/)
    .map((q) => q.trim())
    .filter(Boolean)

  const abrir = useMutation({
    mutationFn: () =>
      request(`/cofres/${encodeURIComponent(cofre)}/desselar-com-quorum`, {
        method: 'POST',
        body: { quinhoes },
      }),
    onSuccess: aoAbrir,
    onError: (e) =>
      aoErro(e instanceof ApiError ? e.message : 'Não foi possível abrir.'),
  })

  return (
    <div className="col" style={{ gap: 14 }}>
      <Campo
        rotulo="Quinhões"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
        ajuda={`Cole ${selo.limiar} ou mais quinhões, um por linha.`}
        autoFocus
      />

      <span className="help">
        {quinhoes.length} de {selo.limiar} necessário
        {selo.limiar === 1 ? '' : 's'}
      </span>

      <div className="row" style={{ gap: 10 }}>
        <Botao
          onClick={() => abrir.mutate()}
          disabled={quinhoes.length < selo.limiar || abrir.isPending}
        >
          {abrir.isPending ? 'Abrindo…' : 'Abrir cofre'}
        </Botao>
      </div>
    </div>
  )
}

export function SeloVazio() {
  return <Vazio titulo="Sem selagem com quórum" />
}
