import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { request } from '@/shared/api/client'
import { Campo, Card, Carregando, Vazio } from '@/shared/ui/components'
import { TabelaSessoes, type Sessao } from './SessoesPage'

export function GravacoesPage() {
  const [termo, setTermo] = useState('')

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
      <header>
        <h1 className="display">Gravações</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          Sessões encerradas. Quem não administra vê só as próprias — uma
          gravação mostra o que a pessoa digitou em produção, e isso é mais
          sensível que a maioria dos segredos.
        </p>
      </header>

      <Card>
        <div className="col" style={{ gap: 16 }}>
          <Campo
            rotulo="Buscar"
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
            ajuda="Por alvo ou motivo. Para procurar DENTRO de uma gravação, abra-a."
            placeholder="srv-producao, manutenção…"
          />

          {isFetching ? (
            <Carregando texto="Buscando…" />
          ) : lista.length === 0 ? (
            <Vazio
              titulo={
                termo.trim()
                  ? `Nada encontrado para "${termo.trim()}"`
                  : 'Nenhuma sessão encerrada ainda'
              }
            />
          ) : (
            <>
              <span className="help">
                {lista.length} gravaç{lista.length === 1 ? 'ão' : 'ões'}
              </span>
              <TabelaSessoes sessoes={lista} />
            </>
          )}
        </div>
      </Card>
    </>
  )
}
