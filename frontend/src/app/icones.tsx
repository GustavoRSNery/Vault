/**
 * Ícones da navegação.
 *
 * Desenhados aqui, em SVG, pelo mesmo motivo da lib de gráficos: são poucos
 * traços, e uma biblioteca de ícones custaria centenas de KB para entregar
 * vinte formas — além de trazer um estilo que não é o do design system.
 *
 * Todos seguem o mesmo contrato: caixa de 24×24, traço de 1.6 e
 * `currentColor`, para que herdem a cor do item de menu (inclusive no estado
 * ativo) sem nenhuma regra extra.
 *
 * São decorativos: o rótulo em texto sempre acompanha no menu, então levam
 * `aria-hidden` e não entram na leitura de tela. Ícone sozinho obrigaria a
 * decorar o que cada desenho significa.
 */

type Props = { className?: string }

function Base({ children, className }: Props & { children: React.ReactNode }) {
  return (
    <svg
      className={className}
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  )
}

export function IconePainel(p: Props) {
  return (
    <Base {...p}>
      <rect x="3" y="3" width="7" height="9" rx="1.5" />
      <rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" />
      <rect x="3" y="16" width="7" height="5" rx="1.5" />
    </Base>
  )
}

export function IconeBusca(p: Props) {
  return (
    <Base {...p}>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </Base>
  )
}

export function IconeAlerta(p: Props) {
  return (
    <Base {...p}>
      <path d="M12 3.5 2.8 19a1.2 1.2 0 0 0 1 1.8h16.4a1.2 1.2 0 0 0 1-1.8Z" />
      <path d="M12 9.5v4.2" />
      <path d="M12 17.3h.01" />
    </Base>
  )
}

export function IconeCofre(p: Props) {
  return (
    <Base {...p}>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <circle cx="12" cy="12" r="3.6" />
      <path d="M12 8.4V6.8M12 17.2v-1.6M15.6 12h1.6M6.8 12h1.6" />
    </Base>
  )
}

export function IconeDispositivo(p: Props) {
  return (
    <Base {...p}>
      <rect x="2.5" y="4" width="19" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </Base>
  )
}

export function IconeCredencial(p: Props) {
  return (
    <Base {...p}>
      <circle cx="8.5" cy="9" r="3" />
      <path d="M3.5 19c.6-2.8 2.6-4.2 5-4.2S13 16.2 13.5 19" />
      <path d="M16 8h5M16 12h5M16 16h3" />
    </Base>
  )
}

export function IconeCertificado(p: Props) {
  return (
    <Base {...p}>
      <path d="M6 3h8l4 4v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" />
      <path d="M14 3v4h4" />
      <circle cx="11" cy="19" r="2.4" />
      <path d="m9.4 20.8-.9 2.2 2.5-1 2.5 1-.9-2.2" />
    </Base>
  )
}

export function IconeChave(p: Props) {
  return (
    <Base {...p}>
      <circle cx="7.5" cy="12" r="4" />
      <path d="M11.5 12H21M18 12v3M14.8 12v2.4" />
    </Base>
  )
}

export function IconeSolicitacao(p: Props) {
  return (
    <Base {...p}>
      <path d="M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1Z" />
      <path d="m8.5 12 2.4 2.4 4.6-4.8" />
    </Base>
  )
}

export function IconeSessao(p: Props) {
  return (
    <Base {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7v5l3.2 1.9" />
    </Base>
  )
}

export function IconeGravacao(p: Props) {
  return (
    <Base {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M10.2 9.3v5.4l4.4-2.7Z" />
    </Base>
  )
}

export function IconeTrilha(p: Props) {
  return (
    <Base {...p}>
      <path d="M6 3.5h9l4 4V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
      <path d="M15 3.5v4h4" />
      <path d="M8.5 12.5h7M8.5 16h4.5" />
    </Base>
  )
}

export function IconePerfil(p: Props) {
  return (
    <Base {...p}>
      <circle cx="12" cy="8.5" r="3.6" />
      <path d="M5 20c.8-3.5 3.5-5.2 7-5.2s6.2 1.7 7 5.2" />
    </Base>
  )
}

export function IconePessoas(p: Props) {
  return (
    <Base {...p}>
      <circle cx="9" cy="8.5" r="3.2" />
      <path d="M3 19.5c.7-3.1 3-4.6 6-4.6s5.3 1.5 6 4.6" />
      <path d="M16.5 6.2a3.2 3.2 0 0 1 0 6M18 15.2c2 .6 3.2 2 3.6 4.3" />
    </Base>
  )
}

export function IconePolitica(p: Props) {
  return (
    <Base {...p}>
      <path d="M12 3 4.5 6v5.5c0 4.3 3 8.1 7.5 9.5 4.5-1.4 7.5-5.2 7.5-9.5V6Z" />
      <path d="m9 12 2.2 2.2L15.2 10" />
    </Base>
  )
}

export function IconeConvite(p: Props) {
  return (
    <Base {...p}>
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <path d="m3.8 6.4 7.4 5.6a1.3 1.3 0 0 0 1.6 0l7.4-5.6" />
    </Base>
  )
}

export function IconeAplicacao(p: Props) {
  return (
    <Base {...p}>
      <rect x="3" y="3.5" width="7.5" height="7.5" rx="1.6" />
      <rect x="13.5" y="3.5" width="7.5" height="7.5" rx="1.6" />
      <rect x="3" y="13" width="7.5" height="7.5" rx="1.6" />
      <circle cx="17.2" cy="16.8" r="3.8" />
    </Base>
  )
}

export function IconeIntegracao(p: Props) {
  return (
    <Base {...p}>
      <circle cx="6" cy="7" r="2.6" />
      <circle cx="6" cy="17.5" r="2.6" />
      <circle cx="18" cy="12.2" r="2.6" />
      <path d="M8.5 8.2l7 3M8.5 16.3l7-3" />
    </Base>
  )
}

export function IconeConfiguracao(p: Props) {
  return (
    <Base {...p}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M19.2 14.4a1.4 1.4 0 0 0 .3 1.5l.1.1a1.7 1.7 0 1 1-2.4 2.4l-.1-.1a1.4 1.4 0 0 0-1.5-.3 1.4 1.4 0 0 0-.9 1.3v.2a1.7 1.7 0 0 1-3.4 0v-.1a1.4 1.4 0 0 0-1-1.3 1.4 1.4 0 0 0-1.5.3l-.1.1a1.7 1.7 0 1 1-2.4-2.4l.1-.1a1.4 1.4 0 0 0 .3-1.5 1.4 1.4 0 0 0-1.3-.9h-.2a1.7 1.7 0 0 1 0-3.4h.1a1.4 1.4 0 0 0 1.3-1 1.4 1.4 0 0 0-.3-1.5l-.1-.1a1.7 1.7 0 1 1 2.4-2.4l.1.1a1.4 1.4 0 0 0 1.5.3h.1a1.4 1.4 0 0 0 .9-1.3v-.2a1.7 1.7 0 0 1 3.4 0v.1a1.4 1.4 0 0 0 .9 1.3 1.4 1.4 0 0 0 1.5-.3l.1-.1a1.7 1.7 0 1 1 2.4 2.4l-.1.1a1.4 1.4 0 0 0-.3 1.5v.1a1.4 1.4 0 0 0 1.3.9h.2a1.7 1.7 0 0 1 0 3.4h-.1a1.4 1.4 0 0 0-1.3.9Z" />
    </Base>
  )
}

export function IconeSair(p: Props) {
  return (
    <Base {...p}>
      <path d="M9.5 20H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3.5" />
      <path d="M15.5 16.2 19.8 12l-4.3-4.2M19.2 12H9.6" />
    </Base>
  )
}

export function IconeConsumoApi(p: Props) {
  // Setas entrando num bloco: chamadas que CHEGAM na API, que e o recorte
  // da tela. Setas saindo diriam o contrario.
  return (
    <Base {...p}>
      <rect x="13.5" y="4.5" width="6.5" height="15" rx="1.8" />
      <path d="M4 8.5h6.5M4 15.5h6.5" />
      <path d="M8 6l2.5 2.5L8 11M8 13l2.5 2.5L8 18" />
    </Base>
  )
}
