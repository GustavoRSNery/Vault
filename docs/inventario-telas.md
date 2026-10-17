# Inventário de telas — Vault de Senhas

> Transcrito do documento "Vault de Senhas — Arquitetura e Engenharia".

## Autenticação

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Login | /login | e-mail + senha |
| Desafio MFA | /login/mfa | código TOTP |
| Configurar MFA | /conta/mfa | QR code + códigos de recuperação |
| Esqueci a senha | /recuperar | solicitação por e-mail |
| Redefinir senha | /recuperar/:token | nova senha + critérios |
| Sistema selado | /selado | status de selagem, ação de unseal (admin) |

## Dashboard

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Dashboard pessoal | / | cards de métrica, pendências, expirações, atividade recente |
| Dashboard de segurança | /admin/dashboard | tentativas falhas, break-glass, cofres sem rotação |

## Cofres & Segredos

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Lista de cofres | /cofres | grade de cards com status e contagens |
| Novo/editar cofre | (modal) | nome, descrição, equipe dona |
| Detalhe do cofre | /cofres/:id | pastas + segredos, busca interna |
| Permissões do cofre | /cofres/:id/permissoes | papéis por grupo/usuário |
| Detalhe do segredo | /cofres/:id/segredos/:sid | valor mascarado, revelar/copiar, metadados |
| Criar/editar segredo | (modal) | tipo, chave/valor, validade |
| Versões do segredo | /…/versoes | histórico + diff + restaurar |
| Lixeira do cofre | /cofres/:id/lixeira | soft-deletados, restaurar/destruir |
| Busca global | /busca | resultados por cofre/segredo/dispositivo |

## Dispositivos

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Dispositivos | /dispositivos | lista com tipo e saúde |
| Cadastro de dispositivo | (modal) | tipo, endereço, tags |
| Credenciais | /credenciais | lista com status de rotação/custódia |
| Detalhe da credencial | /credenciais/:id | histórico de rotação, custódia atual |
| Check-out | (modal) | prazo, justificativa |
| Políticas de rotação | /admin/rotacao | agendas e executores |

## Aprovações

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Minhas solicitações | /solicitacoes | status das minhas |
| Nova solicitação | (modal) | alvo, motivo, janela |
| Fila de aprovação | /aprovacoes | pendentes do aprovador |
| Detalhe da solicitação | /aprovacoes/:id | contexto completo, aprovar/negar |

## Acesso de aplicação

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Aplicações | /apps | RPAs e serviços registrados |
| Detalhe da aplicação | /apps/:id | escopos, políticas, saúde |
| Credenciais AppRole | (modal) | role_id + secret_id (exibição única) |
| Tokens e leases | /apps/:id/leases | ativos, TTL, revogar em massa |
| Consumo | /apps/:id/consumo | log de leituras por segredo |

## Certificados

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Certificados | /certificados | lista com validade e responsável |
| Detalhe/upload | /certificados/:id | metadados, download controlado |
| Expirações | /certificados/expiracoes | linha do tempo 60/30/7 dias |

## Sessões

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Sessões ativas | /sessoes | em andamento, encerrar |
| Gravações | /sessoes/gravacoes | histórico pesquisável |
| Player de sessão | /sessoes/:id | reprodução com timeline |

## Auditoria

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Trilha de auditoria | /auditoria | tabela filtrável por ator/alvo/ação/período |
| Detalhe do evento | (drawer) | payload completo, cadeia de hash |
| Relatórios | /relatorios | galeria de relatórios prontos |
| Relatório de expirações | /relatorios/expiracoes | segredos/certificados a vencer |

## Alertas

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Central de alertas | /alertas | feed com severidade |
| Regras de notificação | /alertas/regras | evento + condição + canal |

## Pessoas & Grupos

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Usuários | /admin/usuarios | lista com papel e MFA |
| Detalhe/convite | /admin/usuarios/:id | papéis, grupos, sessões |
| Grupos | /admin/grupos | membros e políticas |
| Papéis e políticas | /admin/politicas | lista de políticas por caminho |
| Editor de política | /admin/politicas/:id | editor com preview de efeito |

## Administração

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Configurações | /admin/config | prazos, exigência de MFA, retenção |
| Integrações | /admin/integracoes | SES, WhatsApp, webhook SIEM, LDAP (fase 3) |
| Selagem e chaves | /admin/selagem | status KMS, selar, histórico de re-key |
| Backups | /admin/backups | agendas, último backup, restaurar |
| Saúde do sistema | /admin/saude | fila, latência, erros |

## Comuns

| Tela | Rota | Conteúdo |
| --- | --- | --- |
| Perfil | /conta | dados, sessões ativas, trocar senha |
| Estados vazios e erro | (padrão) | vazio, sem permissão, erro de rede |
| 404 | * | não encontrado |
