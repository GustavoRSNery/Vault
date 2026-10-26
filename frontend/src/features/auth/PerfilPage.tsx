import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useRef, useState } from 'react'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Badge, Botao, Campo, Card } from '@/shared/ui/components'
import { BotaoTour, Tour, useTour } from '@/shared/tour/Tour'
import { TutorialApi } from '@/shared/tour/TutorialApi'
import { useAuth } from './AuthContext'

type StatusMfa = { mfa_enabled: boolean }
type IniciarMfa = { provisioning_uri: string }

type Perfil = {
  id: string
  email: string
  full_name: string
  apelido: string
  foto: string
  mfa_enabled: boolean
}

/** Extrai o segredo da URI otpauth, para quem digita à mão no autenticador. */
function segredoDaUri(uri: string): string | null {
  try {
    return new URL(uri).searchParams.get('secret')
  } catch {
    return null
  }
}

/**
 * Formatos que o navegador converte e o servidor aceita.
 *
 * SVG fica de fora de propósito, aqui e no servidor: ele carrega script, e
 * uma foto de perfil que executa JavaScript na tela de quem olha é XSS
 * armazenado com o rosto de alguém em cima. Esta lista é conveniência; o
 * controle é a validação do servidor.
 */
const FORMATOS_ACEITOS = 'image/png,image/jpeg,image/webp'

/** 512 KB, o mesmo limite do servidor. Conferir aqui evita upload inútil. */
const FOTO_MAXIMA_BYTES = 512 * 1024

/** Lado máximo depois de reduzir. Suficiente para um avatar nítido. */
const LADO_MAXIMO = 320

/**
 * Reduz a imagem no navegador antes de enviar.
 *
 * **Por que reduzir em vez de recusar o arquivo grande.** Foto de celular tem
 * 3 a 8 MB; recusá-la mandaria a pessoa procurar um editor de imagem para
 * conseguir usar o próprio sistema. Reduzir resolve o caso comum sem pedir
 * nada, e o limite do servidor continua valendo para quem chama a API direto.
 *
 * Sai como JPEG, exceto PNG pequeno — ali costuma haver transparência, que o
 * JPEG perderia. PNG de foto de câmera fica maior que o original, e o limite
 * voltaria a estourar.
 */
async function reduzirImagem(arquivo: File): Promise<string> {
  const bitmap = await createImageBitmap(arquivo)
  const escala = Math.min(1, LADO_MAXIMO / Math.max(bitmap.width, bitmap.height))
  const largura = Math.max(1, Math.round(bitmap.width * escala))
  const altura = Math.max(1, Math.round(bitmap.height * escala))

  const canvas = document.createElement('canvas')
  canvas.width = largura
  canvas.height = altura
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('Não foi possível processar a imagem neste navegador.')
  ctx.drawImage(bitmap, 0, 0, largura, altura)
  bitmap.close()

  const preferePng = arquivo.type === 'image/png' && arquivo.size < 200 * 1024
  const dados = preferePng
    ? canvas.toDataURL('image/png')
    : canvas.toDataURL('image/jpeg', 0.85)

  const bytes = Math.ceil(((dados.length - dados.indexOf(',') - 1) * 3) / 4)
  if (bytes > FOTO_MAXIMA_BYTES) {
    throw new Error(
      'A imagem continua grande demais depois de reduzida. Tente uma foto menor.',
    )
  }
  return dados
}

/** Iniciais para quem não tem foto. Duas letras: mais que isso vira sopa. */
export function iniciais(nome: string): string {
  const partes = nome.trim().split(/\s+/).filter(Boolean)
  if (partes.length === 0) return '?'
  const primeira = partes[0]?.[0] ?? ''
  const ultima = partes.length > 1 ? (partes[partes.length - 1]?.[0] ?? '') : ''
  return (primeira + ultima).toUpperCase()
}

function Avatar({ foto, nome }: { foto: string; nome: string }) {
  if (foto) {
    return <img className="avatar-foto" src={foto} alt={`Foto de ${nome}`} />
  }
  return (
    <div className="avatar-foto avatar-iniciais" aria-hidden="true">
      {iniciais(nome)}
    </div>
  )
}

export function PerfilPage() {
  const { usuario, recarregarUsuario } = useAuth()
  const queryClient = useQueryClient()
  const tour = useTour('perfil')

  const { data: perfil } = useQuery({
    queryKey: ['perfil'],
    queryFn: () => request<Perfil>('/perfil'),
  })

  // O cabeçalho vive do AuthContext, não desta query: sem recarregar, o nome
  // antigo ficaria na tela e pareceria que a edição não salvou.
  async function atualizarTudo() {
    await queryClient.invalidateQueries({ queryKey: ['perfil'] })
    await recarregarUsuario()
  }

  return (
    <>
      <Tour id="perfil" aberto={tour.aberto} aoFechar={tour.fechar} />

      <header>
        <div className="row between wrap" style={{ gap: 12 }}>
          <h1 className="display">Perfil</h1>
          <div className="row wrap" style={{ gap: 8 }}>
            <BotaoTour aoAbrir={tour.abrir} />
            <TutorialApi
              titulo="Perfil"
              endpoints={[
                {
                  metodo: 'GET',
                  caminho: '/perfil',
                  descricao: 'Seus dados: nome, apelido, foto e se o MFA está ativo.',
                },
              ]}
            />
          </div>
        </div>
        <p className="sub">Seus dados e a segurança da sua conta.</p>
      </header>

      <DadosDaConta
        perfil={perfil}
        nomeAtual={usuario?.full_name ?? ''}
        aoSalvar={atualizarTudo}
      />

      <TrocarEmail
        emailAtual={perfil?.email ?? usuario?.email ?? ''}
        aoTrocar={atualizarTudo}
      />

      <TrocarSenha />

      <SegundoFator />
    </>
  )
}

// ------------------------------------------------------------ dados da conta

function DadosDaConta({
  perfil,
  nomeAtual,
  aoSalvar,
}: {
  perfil: Perfil | undefined
  nomeAtual: string
  aoSalvar: () => Promise<void>
}) {
  const [editando, setEditando] = useState(false)
  const [nome, setNome] = useState('')
  const [apelido, setApelido] = useState('')
  const [foto, setFoto] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [salvo, setSalvo] = useState(false)
  const arquivoRef = useRef<HTMLInputElement>(null)

  function abrirEdicao() {
    // Carrega do servidor, não do que estava na tela: começar a editar com
    // valor obsoleto faria o salvamento reverter alteração feita em outra aba.
    setNome(perfil?.full_name ?? '')
    setApelido(perfil?.apelido ?? '')
    setFoto(perfil?.foto ?? '')
    setErro(null)
    setSalvo(false)
    setEditando(true)
  }

  const salvar = useMutation({
    mutationFn: () =>
      request<Perfil>('/perfil', {
        method: 'PUT',
        body: { full_name: nome.trim(), apelido: apelido.trim(), foto },
      }),
    onSuccess: async () => {
      await aoSalvar()
      setEditando(false)
      setSalvo(true)
      setErro(null)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível salvar.'),
  })

  async function escolherArquivo(arquivo: File | undefined) {
    if (!arquivo) return
    setErro(null)
    if (arquivo.size > 20 * 1024 * 1024) {
      setErro('Essa imagem é enorme. Escolha uma foto de até 20 MB.')
      return
    }
    try {
      setFoto(await reduzirImagem(arquivo))
    } catch (e) {
      setErro(e instanceof Error ? e.message : 'Não foi possível ler a imagem.')
    }
  }

  const nomeExibido = perfil?.apelido || perfil?.full_name || nomeAtual

  if (!editando) {
    return (
      <Card
        titulo="Dados da conta"
        acao={
          <Botao variante="secondary" pequeno onClick={abrirEdicao}>
            Editar
          </Botao>
        }
      >
        <div className="row wrap" style={{ gap: 16, alignItems: 'center' }}>
          <Avatar foto={perfil?.foto ?? ''} nome={nomeExibido} />
          <dl className="kv" style={{ margin: 0 }}>
            <dt>Nome</dt>
            <dd>{perfil?.full_name ?? nomeAtual}</dd>
            <dt>Como prefere ser chamado</dt>
            <dd>{perfil?.apelido || <span className="muted">não definido</span>}</dd>
            <dt>E-mail</dt>
            <dd>{perfil?.email}</dd>
          </dl>
        </div>
        {salvo && <p className="help">Alterações salvas.</p>}
      </Card>
    )
  }

  return (
    <Card titulo="Dados da conta">
      <div className="col" style={{ gap: 16 }} data-tour="editar-perfil">
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        <div className="row wrap" style={{ gap: 16, alignItems: 'center' }}>
          <Avatar foto={foto} nome={apelido || nome} />
          <div className="col" style={{ gap: 8 }}>
            <div className="row wrap" style={{ gap: 8 }}>
              <Botao
                variante="secondary"
                pequeno
                onClick={() => arquivoRef.current?.click()}
              >
                {foto ? 'Trocar foto' : 'Escolher foto'}
              </Botao>
              {foto && (
                <Botao variante="secondary" pequeno onClick={() => setFoto('')}>
                  Remover
                </Botao>
              )}
            </div>
            <span className="help">
              PNG, JPEG ou WebP. A imagem é reduzida aqui no navegador antes de subir.
            </span>
            <input
              ref={arquivoRef}
              type="file"
              accept={FORMATOS_ACEITOS}
              hidden
              onChange={(e) => {
                void escolherArquivo(e.target.files?.[0])
                // Zera para que escolher o MESMO arquivo de novo dispare o
                // evento: sem isto, corrigir um erro reenviando o mesmo
                // arquivo não faria nada.
                e.target.value = ''
              }}
            />
          </div>
        </div>

        <Campo
          rotulo="Nome completo"
          value={nome}
          onChange={(e) => setNome(e.target.value)}
          maxLength={200}
          ajuda="Aparece na trilha de auditoria e nas sessões — é o que identifica você numa investigação."
        />

        <Campo
          rotulo="Como prefere ser chamado"
          value={apelido}
          onChange={(e) => setApelido(e.target.value)}
          maxLength={60}
          ajuda="Opcional. Usado nas telas; a auditoria continua usando o nome completo."
        />

        <div className="row wrap" style={{ gap: 10 }}>
          <Botao
            onClick={() => salvar.mutate()}
            disabled={!nome.trim() || salvar.isPending}
          >
            {salvar.isPending ? 'Salvando…' : 'Salvar'}
          </Botao>
          <Botao
            variante="secondary"
            onClick={() => {
              setEditando(false)
              setErro(null)
            }}
          >
            Cancelar
          </Botao>
        </div>
      </div>
    </Card>
  )
}

// -------------------------------------------------------------------- e-mail

function TrocarEmail({
  emailAtual,
  aoTrocar,
}: {
  emailAtual: string
  aoTrocar: () => Promise<void>
}) {
  const [aberto, setAberto] = useState(false)
  const [novoEmail, setNovoEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [trocado, setTrocado] = useState(false)

  const trocar = useMutation({
    mutationFn: () =>
      request<Perfil>('/perfil/email', {
        method: 'PUT',
        body: { novo_email: novoEmail.trim(), senha_atual: senha },
      }),
    onSuccess: async () => {
      await aoTrocar()
      setAberto(false)
      setNovoEmail('')
      setSenha('')
      setErro(null)
      setTrocado(true)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível trocar o e-mail.'),
  })

  return (
    <Card
      titulo="E-mail de acesso"
      acao={
        !aberto ? (
          <Botao variante="secondary" pequeno onClick={() => setAberto(true)}>
            Trocar
          </Botao>
        ) : undefined
      }
    >
      <div className="col" style={{ gap: 16 }}>
        {!aberto ? (
          <>
            <dl className="kv" style={{ margin: 0 }}>
              <dt>E-mail</dt>
              <dd>{emailAtual}</dd>
            </dl>
            {trocado && (
              <p className="help">E-mail trocado. Use o novo no próximo acesso.</p>
            )}
          </>
        ) : (
          <>
            {erro && <Alerta tom="danger">{erro}</Alerta>}
            {/* A consequência vem ANTES, não depois: é com este e-mail que a
                pessoa entra, e trocá-lo sem perceber tranca a conta. */}
            <Alerta tom="warning">
              É com este e-mail que você entra no sistema. O endereço anterior fica
              registrado na trilha, para que os eventos antigos continuem ligados a
              você.
            </Alerta>

            <Campo
              rotulo="Novo e-mail"
              type="email"
              value={novoEmail}
              onChange={(e) => setNovoEmail(e.target.value)}
              autoComplete="email"
            />
            <Campo
              rotulo="Sua senha atual"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              autoComplete="current-password"
              ajuda="Pedimos a senha porque, sem ela, quem roubasse seu acesso trocaria o e-mail e tomaria a conta."
            />

            <div className="row wrap" style={{ gap: 10 }}>
              <Botao
                onClick={() => trocar.mutate()}
                disabled={!novoEmail.trim() || !senha || trocar.isPending}
              >
                {trocar.isPending ? 'Trocando…' : 'Trocar e-mail'}
              </Botao>
              <Botao
                variante="secondary"
                onClick={() => {
                  setAberto(false)
                  setNovoEmail('')
                  setSenha('')
                  setErro(null)
                }}
              >
                Cancelar
              </Botao>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

// --------------------------------------------------------------------- senha

/** Mesmo mínimo do servidor. Conferir aqui evita uma ida à rede para nada. */
const SENHA_MINIMA = 12

function TrocarSenha() {
  const [aberto, setAberto] = useState(false)
  const [atual, setAtual] = useState('')
  const [nova, setNova] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [trocada, setTrocada] = useState(false)

  function limpar() {
    setAtual('')
    setNova('')
    setConfirmacao('')
    setErro(null)
  }

  const trocar = useMutation({
    mutationFn: () =>
      request<void>('/perfil/senha', {
        method: 'PUT',
        body: { senha_atual: atual, nova_senha: nova },
      }),
    onSuccess: () => {
      limpar()
      setAberto(false)
      setTrocada(true)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível trocar a senha.'),
  })

  // A confirmação é checada aqui e não no servidor: ela existe para pegar erro
  // de digitação, e o servidor não tem como saber o que a pessoa quis digitar.
  const naoConfere = confirmacao.length > 0 && nova !== confirmacao
  const curta = nova.length > 0 && nova.length < SENHA_MINIMA

  return (
    <Card
      titulo="Senha"
      acao={
        !aberto ? (
          <Botao variante="secondary" pequeno onClick={() => setAberto(true)}>
            Trocar senha
          </Botao>
        ) : undefined
      }
    >
      <div className="col" style={{ gap: 16 }}>
        {!aberto ? (
          <>
            <p className="sub" style={{ margin: 0 }}>
              Troque a senha quando quiser. Pedimos a atual para confirmar que é você.
            </p>
            {trocada && <p className="help">Senha trocada.</p>}
          </>
        ) : (
          <>
            {erro && <Alerta tom="danger">{erro}</Alerta>}

            <Campo
              rotulo="Senha atual"
              type="password"
              value={atual}
              onChange={(e) => setAtual(e.target.value)}
              autoComplete="current-password"
            />
            <Campo
              rotulo="Senha nova"
              type="password"
              value={nova}
              onChange={(e) => setNova(e.target.value)}
              autoComplete="new-password"
              erro={curta ? `Use ao menos ${SENHA_MINIMA} caracteres.` : undefined}
              ajuda={`Mínimo de ${SENHA_MINIMA} caracteres. Uma frase comprida é mais forte e mais fácil de lembrar que símbolos trocados.`}
            />
            <Campo
              rotulo="Repita a senha nova"
              type="password"
              value={confirmacao}
              onChange={(e) => setConfirmacao(e.target.value)}
              autoComplete="new-password"
              erro={naoConfere ? 'As duas não são iguais.' : undefined}
            />

            <div className="row wrap" style={{ gap: 10 }}>
              <Botao
                onClick={() => trocar.mutate()}
                disabled={
                  !atual ||
                  nova.length < SENHA_MINIMA ||
                  nova !== confirmacao ||
                  trocar.isPending
                }
              >
                {trocar.isPending ? 'Trocando…' : 'Trocar senha'}
              </Botao>
              <Botao
                variante="secondary"
                onClick={() => {
                  setAberto(false)
                  limpar()
                }}
              >
                Cancelar
              </Botao>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}

// -------------------------------------------------------------- segundo fator

function SegundoFator() {
  const queryClient = useQueryClient()
  const [uri, setUri] = useState<string | null>(null)
  const [codigo, setCodigo] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const { data: status } = useQuery({
    queryKey: ['mfa', 'status'],
    queryFn: () => request<StatusMfa>('/mfa/status'),
  })

  const iniciar = useMutation({
    mutationFn: () => request<IniciarMfa>('/mfa/iniciar', { method: 'POST' }),
    onSuccess: (dados) => {
      setUri(dados.provisioning_uri)
      setErro(null)
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível gerar o segredo.'),
  })

  const confirmar = useMutation({
    mutationFn: () =>
      request<StatusMfa>('/mfa/confirmar', { method: 'POST', body: { code: codigo } }),
    onSuccess: () => {
      setUri(null)
      setCodigo('')
      setErro(null)
      void queryClient.invalidateQueries({ queryKey: ['mfa', 'status'] })
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível confirmar o código.'),
  })

  const segredo = uri ? segredoDaUri(uri) : null

  return (
    <Card
      titulo="Verificação em duas etapas"
      acao={
        status?.mfa_enabled ? (
          <Badge tom="success">Ativa</Badge>
        ) : (
          <Badge tom="warning">Pendente</Badge>
        )
      }
    >
      <div className="col" style={{ gap: 16 }}>
        {erro && <Alerta tom="danger">{erro}</Alerta>}

        {status?.mfa_enabled ? (
          <p className="sub" style={{ margin: 0 }}>
            Sua conta pede um código do aplicativo autenticador a cada acesso.
          </p>
        ) : !uri ? (
          <>
            <p className="sub" style={{ margin: 0 }}>
              Um segundo fator protege seus cofres mesmo que a senha vaze.
            </p>
            <div>
              <Botao onClick={() => iniciar.mutate()} disabled={iniciar.isPending}>
                {iniciar.isPending ? 'Gerando…' : 'Ativar segundo fator'}
              </Botao>
            </div>
          </>
        ) : (
          <>
            <p className="sub" style={{ margin: 0 }}>
              Cadastre a chave abaixo no seu aplicativo autenticador e informe o
              código de 6 dígitos para concluir.
            </p>

            {/* A chave aparece uma única vez e não é persistida em lugar
                nenhum do navegador: some ao sair desta tela. */}
            {segredo && (
              <div className="secret-box">
                <span className="secret" style={{ wordBreak: 'break-all' }}>
                  {segredo}
                </span>
              </div>
            )}

            <Campo
              rotulo="Código do aplicativo"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, '').slice(0, 6))}
              inputMode="numeric"
              autoComplete="one-time-code"
              ajuda="6 dígitos, trocados a cada 30 segundos."
            />

            <div className="row" style={{ gap: 10 }}>
              <Botao
                onClick={() => confirmar.mutate()}
                disabled={codigo.length !== 6 || confirmar.isPending}
              >
                {confirmar.isPending ? 'Confirmando…' : 'Confirmar e ativar'}
              </Botao>
              <Botao
                variante="secondary"
                onClick={() => {
                  setUri(null)
                  setCodigo('')
                  setErro(null)
                }}
              >
                Cancelar
              </Botao>
            </div>
          </>
        )}
      </div>
    </Card>
  )
}
