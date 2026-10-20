import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError, request } from '@/shared/api/client'
import { Alerta, Botao, Campo } from '@/shared/ui/components'

type InicioResposta = {
  mensagem: string
  pode_usar_autenticador: boolean
}

type Etapa = 'email' | 'autenticador' | 'pedido' | 'pronto'

/**
 * Recuperação de senha.
 *
 * Dois caminhos, e a tela não decide qual antes de perguntar: quem tem o
 * segundo fator prova identidade pelo código e troca a senha na hora; quem
 * não tem abre um pedido que um administrador aprova.
 *
 * O texto da resposta é o mesmo para e-mail que existe e que não existe —
 * senão esta tela viraria um oráculo de quem tem conta na empresa.
 */
export function RecuperarPage() {
  const [etapa, setEtapa] = useState<Etapa>('email')
  const [email, setEmail] = useState('')
  const [codigo, setCodigo] = useState('')
  const [senha, setSenha] = useState('')
  const [confirmacao, setConfirmacao] = useState('')
  const [motivo, setMotivo] = useState('')
  const [mensagem, setMensagem] = useState('')
  const [erro, setErro] = useState<string | null>(null)

  const comecar = useMutation({
    mutationFn: () =>
      request<InicioResposta>('/recuperar', {
        method: 'POST',
        body: { email },
      }),
    onSuccess: (dados) => {
      setErro(null)
      setMensagem(dados.mensagem)
      setEtapa(dados.pode_usar_autenticador ? 'autenticador' : 'pedido')
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível continuar.'),
  })

  const redefinir = useMutation({
    mutationFn: () =>
      request<{ mensagem: string }>('/recuperar/autenticador', {
        method: 'POST',
        body: { email, codigo, nova_senha: senha },
      }),
    onSuccess: (dados) => {
      setErro(null)
      setMensagem(dados.mensagem)
      setEtapa('pronto')
    },
    onError: (e) =>
      setErro(
        e instanceof ApiError ? e.message : 'Não foi possível redefinir.',
      ),
  })

  const pedir = useMutation({
    mutationFn: () =>
      request<{ mensagem: string }>('/recuperar/pedido', {
        method: 'POST',
        body: { email, motivo },
      }),
    onSuccess: (dados) => {
      setErro(null)
      setMensagem(dados.mensagem)
      setEtapa('pronto')
    },
    onError: (e) =>
      setErro(e instanceof ApiError ? e.message : 'Não foi possível pedir.'),
  })

  const senhasConferem = senha.length >= 12 && senha === confirmacao

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="logo" style={{ marginBottom: 20 }}>
          <span className="mark" aria-hidden="true">
            <strong>V</strong>
          </span>
          <span>
            <b>Vault</b>
            <small>de senhas</small>
          </span>
        </div>

        <h1 className="title">Recuperar acesso</h1>

        {erro && <Alerta tom="danger">{erro}</Alerta>}

        {etapa === 'email' && (
          <div className="col" style={{ gap: 14 }}>
            <p className="sub" style={{ margin: 0 }}>
              Informe seu e-mail. Se você tem o segundo fator ativo, o código
              do aplicativo autenticador já resolve — sem precisar de ninguém.
            </p>
            <Campo
              rotulo="E-mail"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
            />
            <Botao
              onClick={() => comecar.mutate()}
              disabled={!email.includes('@') || comecar.isPending}
            >
              {comecar.isPending ? 'Verificando…' : 'Continuar'}
            </Botao>
          </div>
        )}

        {etapa === 'autenticador' && (
          <div className="col" style={{ gap: 14 }}>
            <Alerta tom="warning">
              Abra o aplicativo autenticador e use o código de 6 dígitos que
              está sendo exibido agora para <b>{email}</b>.
            </Alerta>
            <Campo
              rotulo="Código do autenticador"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ''))}
              inputMode="numeric"
              maxLength={6}
              className="code-input"
              autoFocus
            />
            <Campo
              rotulo="Nova senha"
              type="password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              ajuda="Ao menos 12 caracteres."
            />
            <Campo
              rotulo="Repita a nova senha"
              type="password"
              value={confirmacao}
              onChange={(e) => setConfirmacao(e.target.value)}
              erro={
                confirmacao && !senhasConferem
                  ? 'As senhas não conferem ou são curtas demais.'
                  : undefined
              }
            />
            <Botao
              onClick={() => redefinir.mutate()}
              disabled={
                codigo.length !== 6 || !senhasConferem || redefinir.isPending
              }
            >
              {redefinir.isPending ? 'Redefinindo…' : 'Redefinir senha'}
            </Botao>
            <Botao variante="ghost" pequeno onClick={() => setEtapa('pedido')}>
              Perdi o celular com o autenticador
            </Botao>
          </div>
        )}

        {etapa === 'pedido' && (
          <div className="col" style={{ gap: 14 }}>
            <p className="sub" style={{ margin: 0 }}>
              Sem o segundo fator, um administrador precisa confirmar sua
              identidade antes de liberar a redefinição. Ele vai procurar você
              pelo canal de sempre.
            </p>
            <Campo
              rotulo="O que aconteceu"
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              ajuda="Ajuda quem vai te atender. Opcional."
              autoFocus
            />
            <Botao onClick={() => pedir.mutate()} disabled={pedir.isPending}>
              {pedir.isPending ? 'Enviando…' : 'Pedir redefinição'}
            </Botao>
          </div>
        )}

        {etapa === 'pronto' && (
          <div className="col" style={{ gap: 14 }}>
            <Alerta tom="warning">{mensagem}</Alerta>
            <Link to="/">
              <Botao>Ir para o login</Botao>
            </Link>
          </div>
        )}

        {etapa !== 'pronto' && (
          <p className="help" style={{ marginTop: 18, textAlign: 'center' }}>
            <Link to="/">Voltar ao login</Link>
          </p>
        )}
      </div>
    </div>
  )
}
