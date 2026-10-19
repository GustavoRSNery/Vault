import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { request } from '@/shared/api/client'
import { Badge, Campo, Card, Carregando, Vazio } from '@/shared/ui/components'

type Resultado = {
  tipo: 'cofre' | 'segredo' | 'dispositivo' | 'credencial' | 'certificado'
  titulo: string
  subtitulo: string
  caminho: string
  rota: string
}

type Busca = {
  termo: string
  total: number
  resultados: Resultado[]
}

const ROTULO: Record<Resultado['tipo'], string> = {
  cofre: 'Cofre',
  segredo: 'Segredo',
  dispositivo: 'Dispositivo',
  credencial: 'Credencial',
  certificado: 'Certificado',
}

const TOM: Record<Resultado['tipo'], 'brand' | 'success' | 'warning' | 'muted'> = {
  cofre: 'brand',
  segredo: 'success',
  dispositivo: 'muted',
  credencial: 'warning',
  certificado: 'muted',
}

export function BuscaPage() {
  const [termo, setTermo] = useState('')
  const pronto = termo.trim().length >= 2

  const { data, isFetching } = useQuery({
    queryKey: ['busca', termo.trim()],
    queryFn: () => request<Busca>(`/busca?termo=${encodeURIComponent(termo.trim())}`),
    enabled: pronto,
  })

  return (
    <>
      <header>
        <h1 className="display">Busca</h1>
        <p className="sub" style={{ margin: '4px 0 0' }}>
          Procura em cofres, segredos, dispositivos, credenciais e certificados
          — sempre dentro do que você pode ver. O <b>valor</b> de um segredo
          nunca entra na busca.
        </p>
      </header>

      <Card>
        <div className="col" style={{ gap: 16 }}>
          <Campo
            rotulo="O que você procura"
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
            ajuda="Ao menos 2 letras. Nome, descrição, endereço ou etiqueta."
            placeholder="sefaz, firewall, 10.0.0.1, postgres…"
            autoFocus
          />

          {!pronto ? (
            <Vazio
              titulo="Digite para buscar"
              descricao="Buscar por uma letra só devolveria quase tudo."
            />
          ) : isFetching ? (
            <Carregando texto="Buscando…" />
          ) : !data || data.total === 0 ? (
            <Vazio
              titulo={`Nada encontrado para "${termo.trim()}"`}
              descricao="Se existir algo fora do seu acesso, ele também não aparece aqui — e é assim de propósito."
            />
          ) : (
            <div className="col" style={{ gap: 10 }}>
              <span className="help">
                {data.total} resultado{data.total === 1 ? '' : 's'}
              </span>
              {data.resultados.map((r) => (
                <Link
                  key={`${r.tipo}-${r.caminho}`}
                  to={r.rota}
                  className="row between"
                  style={{
                    gap: 12,
                    padding: '12px 14px',
                    borderRadius: 10,
                    background: 'var(--surface-2, rgba(0,0,0,.03))',
                    textDecoration: 'none',
                    color: 'inherit',
                  }}
                >
                  <span className="col" style={{ gap: 2 }}>
                    <b>{r.titulo}</b>
                    <span className="help">{r.subtitulo}</span>
                    <code className="secret-sm muted">{r.caminho}</code>
                  </span>
                  <Badge tom={TOM[r.tipo]}>{ROTULO[r.tipo]}</Badge>
                </Link>
              ))}
            </div>
          )}
        </div>
      </Card>
    </>
  )
}
