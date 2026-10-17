/**
 * Componentes do design system.
 *
 * As classes vêm de design-system.css, que é o kit do próprio sistema de
 * design — nada de estilo inventado aqui.
 */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react'

type Tom = 'success' | 'danger' | 'warning' | 'brand' | 'muted'

export function Badge({ tom, children }: { tom: Tom; children: ReactNode }) {
  // A cor nunca é o único sinal: o texto do badge sempre acompanha.
  return <span className={`badge b-${tom}`}>{children}</span>
}

export function EstadoCofre({ estado }: { estado: string }) {
  if (estado === 'selado') return <Badge tom="danger">Selado</Badge>
  return <Badge tom="success">Ativo</Badge>
}

type BotaoProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variante?: 'primary' | 'secondary' | 'danger' | 'ghost'
  pequeno?: boolean
}

export function Botao({
  variante = 'primary',
  pequeno = false,
  className = '',
  ...props
}: BotaoProps) {
  const classes = ['btn', `btn-${variante}`, pequeno ? 'btn-sm' : '', className]
  return <button className={classes.filter(Boolean).join(' ')} {...props} />
}

type CampoProps = InputHTMLAttributes<HTMLInputElement> & {
  rotulo: string
  ajuda?: string
  erro?: string
}

export function Campo({ rotulo, ajuda, erro, id, ...props }: CampoProps) {
  const campoId = id ?? `campo-${rotulo.toLowerCase().replace(/\s+/g, '-')}`
  const ajudaId = ajuda || erro ? `${campoId}-ajuda` : undefined
  return (
    <div className="field">
      <label htmlFor={campoId}>{rotulo}</label>
      <input
        id={campoId}
        className="input"
        aria-describedby={ajudaId}
        aria-invalid={erro ? true : undefined}
        {...props}
      />
      {erro ? (
        <span id={ajudaId} className="help" style={{ color: 'var(--danger-text)' }}>
          {erro}
        </span>
      ) : ajuda ? (
        <span id={ajudaId} className="help">
          {ajuda}
        </span>
      ) : null}
    </div>
  )
}

export function Card({
  titulo,
  acao,
  children,
}: {
  titulo?: string
  acao?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="card">
      {(titulo || acao) && (
        <div className="row between" style={{ marginBottom: 16 }}>
          {titulo && <h2 className="title">{titulo}</h2>}
          {acao}
        </div>
      )}
      {children}
    </section>
  )
}

export function CardMetrica({
  rotulo,
  valor,
  tom = 'brand',
  icone,
}: {
  rotulo: string
  valor: string | number
  tom?: Tom
  icone?: ReactNode
}) {
  return (
    <section className="card metric">
      <div className="cap">{rotulo}</div>
      <div className="val">{valor}</div>
      {icone && (
        <div className={`icon-circle ic-${tom}`} aria-hidden="true">
          {icone}
        </div>
      )}
    </section>
  )
}

export function Vazio({ titulo, descricao, acao }: {
  titulo: string
  descricao?: string
  acao?: ReactNode
}) {
  return (
    <div className="empty">
      <strong>{titulo}</strong>
      {descricao && <span>{descricao}</span>}
      {acao}
    </div>
  )
}

export function Carregando({ texto = 'Carregando…' }: { texto?: string }) {
  return (
    <div className="empty" role="status" aria-live="polite">
      {texto}
    </div>
  )
}

export function Alerta({ tom, children }: { tom: 'danger' | 'warning'; children: ReactNode }) {
  const fundo = tom === 'danger' ? 'var(--danger-soft)' : 'var(--warning-soft)'
  const cor = tom === 'danger' ? 'var(--danger-text)' : 'var(--warning-text)'
  return (
    <div
      role="alert"
      style={{
        background: fundo,
        color: cor,
        borderRadius: 8,
        padding: '12px 14px',
        fontSize: 13.5,
        fontWeight: 500,
      }}
    >
      {children}
    </div>
  )
}
