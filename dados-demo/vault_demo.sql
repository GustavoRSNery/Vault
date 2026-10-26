--
-- PostgreSQL database dump
--

\restrict f5frQXSzRgi8PwdaQ7Stpm3hwCJ6LU1f4m1OuxQwBRs4BIDXqVVrIQVI51s2hi2

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

ALTER TABLE IF EXISTS ONLY public.usuarios_papeis DROP CONSTRAINT IF EXISTS usuarios_papeis_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.usuarios_papeis DROP CONSTRAINT IF EXISTS usuarios_papeis_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.solicitacoes_acesso DROP CONSTRAINT IF EXISTS solicitacoes_acesso_requester_id_fkey;
ALTER TABLE IF EXISTS ONLY public.solicitacoes_acesso DROP CONSTRAINT IF EXISTS solicitacoes_acesso_decided_by_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sessoes DROP CONSTRAINT IF EXISTS sessoes_usuario_id_fkey;
ALTER TABLE IF EXISTS ONLY public.sessoes_eventos DROP CONSTRAINT IF EXISTS sessoes_eventos_sessao_id_fkey;
ALTER TABLE IF EXISTS ONLY public.segredos_versoes DROP CONSTRAINT IF EXISTS segredos_versoes_secret_id_fkey;
ALTER TABLE IF EXISTS ONLY public.segredos DROP CONSTRAINT IF EXISTS segredos_vault_id_fkey;
ALTER TABLE IF EXISTS ONLY public.politicas_regras DROP CONSTRAINT IF EXISTS politicas_regras_policy_id_fkey;
ALTER TABLE IF EXISTS ONLY public.papeis_politicas DROP CONSTRAINT IF EXISTS papeis_politicas_role_id_fkey;
ALTER TABLE IF EXISTS ONLY public.papeis_politicas DROP CONSTRAINT IF EXISTS papeis_politicas_policy_id_fkey;
ALTER TABLE IF EXISTS ONLY public.integracoes_entregas DROP CONSTRAINT IF EXISTS integracoes_entregas_destino_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credenciais DROP CONSTRAINT IF EXISTS credenciais_secret_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credenciais DROP CONSTRAINT IF EXISTS credenciais_device_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credenciais_custodias DROP CONSTRAINT IF EXISTS credenciais_custodias_user_id_fkey;
ALTER TABLE IF EXISTS ONLY public.credenciais_custodias DROP CONSTRAINT IF EXISTS credenciais_custodias_credential_id_fkey;
ALTER TABLE IF EXISTS ONLY public.cofres_selos DROP CONSTRAINT IF EXISTS cofres_selos_vault_id_fkey;
ALTER TABLE IF EXISTS ONLY public.chaves_api DROP CONSTRAINT IF EXISTS chaves_api_secret_id_fkey;
ALTER TABLE IF EXISTS ONLY public.certificados DROP CONSTRAINT IF EXISTS certificados_secret_id_fkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes_leases DROP CONSTRAINT IF EXISTS aplicacoes_leases_secret_id_usado_fkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes_leases DROP CONSTRAINT IF EXISTS aplicacoes_leases_application_id_fkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes_credenciais DROP CONSTRAINT IF EXISTS aplicacoes_credenciais_application_id_fkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes DROP CONSTRAINT IF EXISTS aplicacoes_application_role_id_fkey;
DROP INDEX IF EXISTS public.uq_selo_ativo_por_cofre;
DROP INDEX IF EXISTS public.uq_custodia_aberta;
DROP INDEX IF EXISTS public.ix_usuarios_email;
DROP INDEX IF EXISTS public.ix_solicitacoes_acesso_status;
DROP INDEX IF EXISTS public.ix_solicitacoes_acesso_requester_id;
DROP INDEX IF EXISTS public.ix_solicitacoes_acesso_path;
DROP INDEX IF EXISTS public.ix_sessoes_usuario_id;
DROP INDEX IF EXISTS public.ix_sessoes_eventos_sessao_id;
DROP INDEX IF EXISTS public.ix_sessoes_estado;
DROP INDEX IF EXISTS public.ix_sessoes_alvo;
DROP INDEX IF EXISTS public.ix_segredo_cofre_ativo;
DROP INDEX IF EXISTS public.ix_pedidos_redefinicao_email;
DROP INDEX IF EXISTS public.ix_pedidos_redefinicao_atendido;
DROP INDEX IF EXISTS public.ix_integracoes_entregas_tipo;
DROP INDEX IF EXISTS public.ix_integracoes_entregas_proxima_em;
DROP INDEX IF EXISTS public.ix_integracoes_entregas_id_evento;
DROP INDEX IF EXISTS public.ix_integracoes_entregas_estado;
DROP INDEX IF EXISTS public.ix_integracoes_entregas_destino_id;
DROP INDEX IF EXISTS public.ix_integracoes_destinos_estado;
DROP INDEX IF EXISTS public.ix_evento_sessao_ordem;
DROP INDEX IF EXISTS public.ix_dispositivos_name;
DROP INDEX IF EXISTS public.ix_custodia_credencial;
DROP INDEX IF EXISTS public.ix_credenciais_name;
DROP INDEX IF EXISTS public.ix_convites_token_hash;
DROP INDEX IF EXISTS public.ix_convites_expira_em;
DROP INDEX IF EXISTS public.ix_convites_estado;
DROP INDEX IF EXISTS public.ix_convites_email;
DROP INDEX IF EXISTS public.ix_cofres_selos_vault_id;
DROP INDEX IF EXISTS public.ix_cofres_name;
DROP INDEX IF EXISTS public.ix_chaves_api_servico;
DROP INDEX IF EXISTS public.ix_chaves_api_name;
DROP INDEX IF EXISTS public.ix_chaves_api_expira_em;
DROP INDEX IF EXISTS public.ix_chaves_api_estado;
DROP INDEX IF EXISTS public.ix_chaves_api_ambiente;
DROP INDEX IF EXISTS public.ix_certificados_not_after;
DROP INDEX IF EXISTS public.ix_certificados_name;
DROP INDEX IF EXISTS public.ix_auditoria_ocorrido;
DROP INDEX IF EXISTS public.ix_auditoria_eventos_target_path;
DROP INDEX IF EXISTS public.ix_auditoria_eventos_sequence;
DROP INDEX IF EXISTS public.ix_auditoria_eventos_action;
DROP INDEX IF EXISTS public.ix_auditoria_ator;
DROP INDEX IF EXISTS public.ix_aplicacoes_role_id;
DROP INDEX IF EXISTS public.ix_aplicacoes_name;
DROP INDEX IF EXISTS public.ix_aplicacoes_leases_token_hash;
DROP INDEX IF EXISTS public.ix_aplicacoes_leases_expires_at;
DROP INDEX IF EXISTS public.ix_aplicacoes_leases_application_id;
DROP INDEX IF EXISTS public.ix_aplicacoes_credenciais_secret_hash;
DROP INDEX IF EXISTS public.ix_aplicacoes_credenciais_application_id;
DROP INDEX IF EXISTS public.ix_api_chamadas_status;
DROP INDEX IF EXISTS public.ix_api_chamadas_resultado;
DROP INDEX IF EXISTS public.ix_api_chamadas_recebida;
DROP INDEX IF EXISTS public.ix_api_chamadas_origem_tempo;
DROP INDEX IF EXISTS public.ix_api_chamadas_origem;
DROP INDEX IF EXISTS public.ix_api_chamadas_metodo;
DROP INDEX IF EXISTS public.ix_api_chamadas_caminho;
DROP INDEX IF EXISTS public.ix_api_chamadas_aplicacao;
ALTER TABLE IF EXISTS ONLY public.usuarios DROP CONSTRAINT IF EXISTS usuarios_pkey;
ALTER TABLE IF EXISTS ONLY public.usuarios_papeis DROP CONSTRAINT IF EXISTS usuarios_papeis_pkey;
ALTER TABLE IF EXISTS ONLY public.segredos_versoes DROP CONSTRAINT IF EXISTS uq_versao_por_segredo;
ALTER TABLE IF EXISTS ONLY public.segredos DROP CONSTRAINT IF EXISTS uq_segredo_nome_por_cofre;
ALTER TABLE IF EXISTS ONLY public.credenciais DROP CONSTRAINT IF EXISTS uq_credencial_por_dispositivo;
ALTER TABLE IF EXISTS ONLY public.auditoria_eventos DROP CONSTRAINT IF EXISTS uq_auditoria_sequencia;
ALTER TABLE IF EXISTS ONLY public.solicitacoes_acesso DROP CONSTRAINT IF EXISTS solicitacoes_acesso_pkey;
ALTER TABLE IF EXISTS ONLY public.sessoes DROP CONSTRAINT IF EXISTS sessoes_pkey;
ALTER TABLE IF EXISTS ONLY public.sessoes_eventos DROP CONSTRAINT IF EXISTS sessoes_eventos_pkey;
ALTER TABLE IF EXISTS ONLY public.segredos_versoes DROP CONSTRAINT IF EXISTS segredos_versoes_pkey;
ALTER TABLE IF EXISTS ONLY public.segredos DROP CONSTRAINT IF EXISTS segredos_pkey;
ALTER TABLE IF EXISTS ONLY public.politicas_regras DROP CONSTRAINT IF EXISTS politicas_regras_pkey;
ALTER TABLE IF EXISTS ONLY public.politicas DROP CONSTRAINT IF EXISTS politicas_pkey;
ALTER TABLE IF EXISTS ONLY public.politicas DROP CONSTRAINT IF EXISTS politicas_name_key;
ALTER TABLE IF EXISTS ONLY public.pedidos_redefinicao DROP CONSTRAINT IF EXISTS pedidos_redefinicao_pkey;
ALTER TABLE IF EXISTS ONLY public.papeis_politicas DROP CONSTRAINT IF EXISTS papeis_politicas_pkey;
ALTER TABLE IF EXISTS ONLY public.papeis DROP CONSTRAINT IF EXISTS papeis_pkey;
ALTER TABLE IF EXISTS ONLY public.papeis DROP CONSTRAINT IF EXISTS papeis_name_key;
ALTER TABLE IF EXISTS ONLY public.integracoes_entregas DROP CONSTRAINT IF EXISTS integracoes_entregas_pkey;
ALTER TABLE IF EXISTS ONLY public.integracoes_destinos DROP CONSTRAINT IF EXISTS integracoes_destinos_pkey;
ALTER TABLE IF EXISTS ONLY public.integracoes_destinos DROP CONSTRAINT IF EXISTS integracoes_destinos_name_key;
ALTER TABLE IF EXISTS ONLY public.dispositivos DROP CONSTRAINT IF EXISTS dispositivos_pkey;
ALTER TABLE IF EXISTS ONLY public.credenciais DROP CONSTRAINT IF EXISTS credenciais_pkey;
ALTER TABLE IF EXISTS ONLY public.credenciais_custodias DROP CONSTRAINT IF EXISTS credenciais_custodias_pkey;
ALTER TABLE IF EXISTS ONLY public.convites DROP CONSTRAINT IF EXISTS convites_pkey;
ALTER TABLE IF EXISTS ONLY public.configuracao DROP CONSTRAINT IF EXISTS configuracao_pkey;
ALTER TABLE IF EXISTS ONLY public.cofres_selos DROP CONSTRAINT IF EXISTS cofres_selos_pkey;
ALTER TABLE IF EXISTS ONLY public.cofres DROP CONSTRAINT IF EXISTS cofres_pkey;
ALTER TABLE IF EXISTS ONLY public.chaves_api DROP CONSTRAINT IF EXISTS chaves_api_pkey;
ALTER TABLE IF EXISTS ONLY public.certificados DROP CONSTRAINT IF EXISTS certificados_pkey;
ALTER TABLE IF EXISTS ONLY public.auditoria_eventos DROP CONSTRAINT IF EXISTS auditoria_eventos_pkey;
ALTER TABLE IF EXISTS ONLY public.auditoria_ancoras DROP CONSTRAINT IF EXISTS auditoria_ancoras_sequence_key;
ALTER TABLE IF EXISTS ONLY public.auditoria_ancoras DROP CONSTRAINT IF EXISTS auditoria_ancoras_pkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes DROP CONSTRAINT IF EXISTS aplicacoes_pkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes_leases DROP CONSTRAINT IF EXISTS aplicacoes_leases_pkey;
ALTER TABLE IF EXISTS ONLY public.aplicacoes_credenciais DROP CONSTRAINT IF EXISTS aplicacoes_credenciais_pkey;
ALTER TABLE IF EXISTS ONLY public.api_chamadas DROP CONSTRAINT IF EXISTS api_chamadas_pkey;
DROP TABLE IF EXISTS public.usuarios_papeis;
DROP TABLE IF EXISTS public.usuarios;
DROP TABLE IF EXISTS public.solicitacoes_acesso;
DROP TABLE IF EXISTS public.sessoes_eventos;
DROP TABLE IF EXISTS public.sessoes;
DROP TABLE IF EXISTS public.segredos_versoes;
DROP TABLE IF EXISTS public.segredos;
DROP TABLE IF EXISTS public.politicas_regras;
DROP TABLE IF EXISTS public.politicas;
DROP TABLE IF EXISTS public.pedidos_redefinicao;
DROP TABLE IF EXISTS public.papeis_politicas;
DROP TABLE IF EXISTS public.papeis;
DROP TABLE IF EXISTS public.integracoes_entregas;
DROP TABLE IF EXISTS public.integracoes_destinos;
DROP TABLE IF EXISTS public.dispositivos;
DROP TABLE IF EXISTS public.credenciais_custodias;
DROP TABLE IF EXISTS public.credenciais;
DROP TABLE IF EXISTS public.convites;
DROP TABLE IF EXISTS public.configuracao;
DROP TABLE IF EXISTS public.cofres_selos;
DROP TABLE IF EXISTS public.cofres;
DROP TABLE IF EXISTS public.chaves_api;
DROP TABLE IF EXISTS public.certificados;
DROP TABLE IF EXISTS public.auditoria_eventos;
DROP TABLE IF EXISTS public.auditoria_ancoras;
DROP TABLE IF EXISTS public.aplicacoes_leases;
DROP TABLE IF EXISTS public.aplicacoes_credenciais;
DROP TABLE IF EXISTS public.aplicacoes;
DROP TABLE IF EXISTS public.api_chamadas;
SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api_chamadas; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.api_chamadas (
    id character varying(36) NOT NULL,
    recebida_em timestamp with time zone NOT NULL,
    metodo character varying(10) NOT NULL,
    caminho character varying(400) NOT NULL,
    status integer NOT NULL,
    resultado character varying(20) NOT NULL,
    origem character varying(20) NOT NULL,
    aplicacao_id character varying(36),
    aplicacao_nome character varying(200) NOT NULL,
    usuario_id character varying(36),
    usuario_email character varying(254) NOT NULL,
    ip character varying(60) NOT NULL,
    agente character varying(200) NOT NULL,
    duracao_ms integer NOT NULL,
    bytes_recebidos integer NOT NULL
);


ALTER TABLE public.api_chamadas OWNER TO vault;

--
-- Name: aplicacoes; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.aplicacoes (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    description text NOT NULL,
    owner_label character varying(200) NOT NULL,
    status character varying(20) NOT NULL,
    lease_minutos integer NOT NULL,
    role_id character varying(36) NOT NULL,
    application_role_id character varying(36),
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.aplicacoes OWNER TO vault;

--
-- Name: aplicacoes_credenciais; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.aplicacoes_credenciais (
    id character varying(36) NOT NULL,
    application_id character varying(36) NOT NULL,
    secret_hash character varying(64) NOT NULL,
    label character varying(200) NOT NULL,
    created_by character varying(254) NOT NULL,
    expires_at timestamp with time zone,
    revoked_at timestamp with time zone,
    last_used_at timestamp with time zone,
    usos integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.aplicacoes_credenciais OWNER TO vault;

--
-- Name: aplicacoes_leases; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.aplicacoes_leases (
    id character varying(36) NOT NULL,
    application_id character varying(36) NOT NULL,
    secret_id_usado character varying(36) NOT NULL,
    token_hash character varying(64) NOT NULL,
    caminhos json NOT NULL,
    capacidades json NOT NULL,
    negados json NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked_at timestamp with time zone,
    leituras integer NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.aplicacoes_leases OWNER TO vault;

--
-- Name: auditoria_ancoras; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.auditoria_ancoras (
    id character varying(36) NOT NULL,
    sequence integer NOT NULL,
    fingerprint character varying(64) NOT NULL,
    exported_to character varying(100) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.auditoria_ancoras OWNER TO vault;

--
-- Name: auditoria_eventos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.auditoria_eventos (
    id character varying(36) NOT NULL,
    sequence integer NOT NULL,
    previous_hash character varying(64) NOT NULL,
    action character varying(50) NOT NULL,
    actor_id character varying(36),
    actor_label character varying(254) NOT NULL,
    target_path character varying(256) NOT NULL,
    outcome character varying(20) NOT NULL,
    reason text NOT NULL,
    ip_address character varying(45),
    user_agent character varying(500),
    event_metadata json NOT NULL,
    occurred_at timestamp with time zone NOT NULL
);


ALTER TABLE public.auditoria_eventos OWNER TO vault;

--
-- Name: certificados; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.certificados (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    subject character varying(300) NOT NULL,
    issuer character varying(300) NOT NULL,
    serial character varying(100) NOT NULL,
    owner_label character varying(200) NOT NULL,
    not_before timestamp with time zone NOT NULL,
    not_after timestamp with time zone NOT NULL,
    secret_id character varying(36),
    description text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    arquivo_nome character varying(255) DEFAULT ''::character varying NOT NULL,
    arquivo_cofre character varying(64) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.certificados OWNER TO vault;

--
-- Name: chaves_api; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.chaves_api (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    servico character varying(200) NOT NULL,
    ambiente character varying(20) NOT NULL,
    formato character varying(20) NOT NULL,
    nome_do_campo character varying(100) NOT NULL,
    escopo text NOT NULL,
    usada_em json NOT NULL,
    responsavel character varying(200) NOT NULL,
    documentacao_url character varying(500) NOT NULL,
    secret_id character varying(36),
    vault_name character varying(64) NOT NULL,
    secret_name character varying(64) NOT NULL,
    expira_em timestamp with time zone,
    estado character varying(20) NOT NULL,
    revogada_em timestamp with time zone,
    criado_por character varying(254) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    url_base character varying(500) DEFAULT ''::character varying NOT NULL,
    metodo character varying(10) DEFAULT 'GET'::character varying NOT NULL,
    rota_exemplo character varying(300) DEFAULT ''::character varying NOT NULL
);


ALTER TABLE public.chaves_api OWNER TO vault;

--
-- Name: cofres; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.cofres (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    description text NOT NULL,
    state character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.cofres OWNER TO vault;

--
-- Name: cofres_selos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.cofres_selos (
    id character varying(36) NOT NULL,
    vault_id character varying(36) NOT NULL,
    limiar integer NOT NULL,
    total_quinhoes integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    portadores json NOT NULL,
    selado_por character varying(254) NOT NULL,
    selado_em timestamp with time zone NOT NULL,
    desselado_em timestamp with time zone,
    desselado_por character varying(254) NOT NULL
);


ALTER TABLE public.cofres_selos OWNER TO vault;

--
-- Name: configuracao; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.configuracao (
    id character varying(16) NOT NULL,
    segundos_segredo_visivel integer NOT NULL,
    custodia_horas_padrao integer NOT NULL,
    alerta_certificado_dias integer NOT NULL,
    rotacao_dias_padrao integer NOT NULL,
    trilha_limite_padrao integer NOT NULL,
    atualizado_por character varying(254) NOT NULL,
    atualizado_em timestamp with time zone NOT NULL,
    capacidade_do_ranking character varying(20) DEFAULT 'admin'::character varying NOT NULL
);


ALTER TABLE public.configuracao OWNER TO vault;

--
-- Name: convites; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.convites (
    id character varying(36) NOT NULL,
    email character varying(254) NOT NULL,
    tipo character varying(20) NOT NULL,
    token_hash character varying(64) NOT NULL,
    estado character varying(20) NOT NULL,
    nome_sugerido character varying(200) NOT NULL,
    papeis json NOT NULL,
    criado_por character varying(254) NOT NULL,
    expira_em timestamp with time zone NOT NULL,
    usado_em timestamp with time zone,
    criado_em timestamp with time zone NOT NULL
);


ALTER TABLE public.convites OWNER TO vault;

--
-- Name: credenciais; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.credenciais (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    device_id character varying(36) NOT NULL,
    secret_id character varying(36),
    username character varying(200) NOT NULL,
    description text NOT NULL,
    rotation_days integer NOT NULL,
    last_rotated_at timestamp with time zone,
    status character varying(20) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.credenciais OWNER TO vault;

--
-- Name: credenciais_custodias; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.credenciais_custodias (
    id character varying(36) NOT NULL,
    credential_id character varying(36) NOT NULL,
    user_id character varying(36) NOT NULL,
    user_label character varying(254) NOT NULL,
    reason text NOT NULL,
    due_at timestamp with time zone NOT NULL,
    taken_at timestamp with time zone NOT NULL,
    returned_at timestamp with time zone
);


ALTER TABLE public.credenciais_custodias OWNER TO vault;

--
-- Name: dispositivos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.dispositivos (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    kind character varying(30) NOT NULL,
    address character varying(200) NOT NULL,
    tags json NOT NULL,
    description text NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    acessos json DEFAULT '[]'::json NOT NULL
);


ALTER TABLE public.dispositivos OWNER TO vault;

--
-- Name: integracoes_destinos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.integracoes_destinos (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    display_name character varying(200) NOT NULL,
    url character varying(1000) NOT NULL,
    eventos json NOT NULL,
    segredo character varying(200) NOT NULL,
    estado character varying(20) NOT NULL,
    descricao text NOT NULL,
    falhas_seguidas integer NOT NULL,
    ultima_entrega_em timestamp with time zone,
    ultimo_erro text NOT NULL,
    criado_por character varying(254) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    ultima_sequencia integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.integracoes_destinos OWNER TO vault;

--
-- Name: integracoes_entregas; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.integracoes_entregas (
    id character varying(36) NOT NULL,
    destino_id character varying(36) NOT NULL,
    id_evento character varying(64) NOT NULL,
    tipo character varying(64) NOT NULL,
    corpo text NOT NULL,
    estado character varying(20) NOT NULL,
    tentativas integer NOT NULL,
    proxima_em timestamp with time zone NOT NULL,
    ultimo_status integer,
    ultimo_erro text NOT NULL,
    entregue_em timestamp with time zone,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.integracoes_entregas OWNER TO vault;

--
-- Name: papeis; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.papeis (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.papeis OWNER TO vault;

--
-- Name: papeis_politicas; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.papeis_politicas (
    role_id character varying(36) NOT NULL,
    policy_id character varying(36) NOT NULL
);


ALTER TABLE public.papeis_politicas OWNER TO vault;

--
-- Name: pedidos_redefinicao; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.pedidos_redefinicao (
    id character varying(36) NOT NULL,
    email character varying(254) NOT NULL,
    motivo text NOT NULL,
    ip_address character varying(45),
    atendido boolean NOT NULL,
    atendido_por character varying(254) NOT NULL,
    atendido_em timestamp with time zone,
    criado_em timestamp with time zone NOT NULL
);


ALTER TABLE public.pedidos_redefinicao OWNER TO vault;

--
-- Name: politicas; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.politicas (
    id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    description text NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.politicas OWNER TO vault;

--
-- Name: politicas_regras; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.politicas_regras (
    id character varying(36) NOT NULL,
    policy_id character varying(36) NOT NULL,
    path character varying(256) NOT NULL,
    capabilities json NOT NULL,
    effect character varying(10) NOT NULL
);


ALTER TABLE public.politicas_regras OWNER TO vault;

--
-- Name: segredos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.segredos (
    id character varying(36) NOT NULL,
    vault_id character varying(36) NOT NULL,
    name character varying(64) NOT NULL,
    kind character varying(30) NOT NULL,
    description text NOT NULL,
    deleted_at timestamp with time zone,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.segredos OWNER TO vault;

--
-- Name: segredos_versoes; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.segredos_versoes (
    id character varying(36) NOT NULL,
    secret_id character varying(36) NOT NULL,
    version integer NOT NULL,
    ciphertext bytea NOT NULL,
    nonce bytea NOT NULL,
    wrapped_dek bytea NOT NULL,
    key_id character varying(100) NOT NULL,
    created_by character varying(36) NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.segredos_versoes OWNER TO vault;

--
-- Name: sessoes; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.sessoes (
    id character varying(36) NOT NULL,
    usuario_id character varying(36) NOT NULL,
    usuario_label character varying(254) NOT NULL,
    tipo character varying(20) NOT NULL,
    alvo character varying(300) NOT NULL,
    motivo text NOT NULL,
    segredo_path character varying(256),
    estado character varying(20) NOT NULL,
    capturado_por character varying(64) NOT NULL,
    captura_automatica boolean NOT NULL,
    gravacao_ref character varying(300),
    gravacao_destino character varying(100) NOT NULL,
    ip_address character varying(45),
    iniciada_em timestamp with time zone NOT NULL,
    ultima_atividade_em timestamp with time zone NOT NULL,
    encerrada_em timestamp with time zone,
    encerrada_por character varying(254) NOT NULL,
    motivo_encerramento text NOT NULL,
    origem_hostname character varying(253) DEFAULT ''::character varying NOT NULL,
    origem_user_agent character varying(512) DEFAULT ''::character varying NOT NULL,
    origem_dispositivo character varying(64) DEFAULT ''::character varying NOT NULL,
    consumo_tipo character varying(20) DEFAULT 'nao_identificado'::character varying NOT NULL,
    consumo_nome character varying(200) DEFAULT ''::character varying NOT NULL,
    consumo_caminho character varying(256) DEFAULT ''::character varying NOT NULL,
    consumo_pertence_a character varying(200) DEFAULT ''::character varying NOT NULL,
    motivo_detalhe text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.sessoes OWNER TO vault;

--
-- Name: sessoes_eventos; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.sessoes_eventos (
    id character varying(36) NOT NULL,
    sessao_id character varying(36) NOT NULL,
    deslocamento_ms integer NOT NULL,
    tipo character varying(20) NOT NULL,
    conteudo text NOT NULL
);


ALTER TABLE public.sessoes_eventos OWNER TO vault;

--
-- Name: solicitacoes_acesso; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.solicitacoes_acesso (
    id character varying(36) NOT NULL,
    requester_id character varying(36) NOT NULL,
    requester_label character varying(254) NOT NULL,
    path character varying(256) NOT NULL,
    capabilities json NOT NULL,
    reason text NOT NULL,
    hours integer NOT NULL,
    status character varying(20) NOT NULL,
    decided_by_id character varying(36),
    decided_by_label character varying(254) NOT NULL,
    decision_note text NOT NULL,
    decided_at timestamp with time zone,
    granted_until timestamp with time zone,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.solicitacoes_acesso OWNER TO vault;

--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.usuarios (
    id character varying(36) NOT NULL,
    email character varying(254) NOT NULL,
    full_name character varying(200) NOT NULL,
    password_hash character varying(255) NOT NULL,
    is_active boolean NOT NULL,
    mfa_secret_ciphertext bytea,
    mfa_secret_nonce bytea,
    mfa_secret_wrapped_dek bytea,
    mfa_key_id character varying(100),
    mfa_enabled boolean NOT NULL,
    created_at timestamp with time zone NOT NULL,
    apelido character varying(60) DEFAULT ''::character varying NOT NULL,
    foto text DEFAULT ''::text NOT NULL
);


ALTER TABLE public.usuarios OWNER TO vault;

--
-- Name: usuarios_papeis; Type: TABLE; Schema: public; Owner: vault
--

CREATE TABLE public.usuarios_papeis (
    user_id character varying(36) NOT NULL,
    role_id character varying(36) NOT NULL
);


ALTER TABLE public.usuarios_papeis OWNER TO vault;

--
-- Data for Name: api_chamadas; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.api_chamadas (id, recebida_em, metodo, caminho, status, resultado, origem, aplicacao_id, aplicacao_nome, usuario_id, usuario_email, ip, agente, duracao_ms, bytes_recebidos) FROM stdin;
\.


--
-- Data for Name: aplicacoes; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.aplicacoes (id, name, display_name, description, owner_label, status, lease_minutos, role_id, application_role_id, created_at) FROM stdin;
b2c4316b-f06a-48c4-a22a-93a2acee64d7	rpa-escrituracao	RPA Escrituracao		ti@exemplo.com.br	ativa	15	9c9c011d-c18f-4b8b-83ec-607a99ce1110	200c60cf-465e-488c-8cbb-22e5530cc617	2026-10-19 15:48:18.014472+00
da85a0ee-6d51-4488-a837-551b3384331b	rpa-consumo-demo	RPA Consumo		ti@exemplo.com.br	ativa	30	69c0f432-80e1-4417-a3f1-9d13d230d72a	200c60cf-465e-488c-8cbb-22e5530cc617	2026-10-19 16:53:51.764104+00
\.


--
-- Data for Name: aplicacoes_credenciais; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.aplicacoes_credenciais (id, application_id, secret_hash, label, created_by, expires_at, revoked_at, last_used_at, usos, created_at) FROM stdin;
630ef944-7aad-4cda-bbb2-882e56a57db7	b2c4316b-f06a-48c4-a22a-93a2acee64d7	b10bcca869cd341eed96ec6539cf9d0f7081fa90b5beb83ca4bf678230113118	producao	ana.souza@exemplo.com.br	\N	\N	2026-10-19 15:48:18.08422+00	1	2026-10-19 15:48:18.058174+00
348803a3-56e5-4b80-b0f6-213643d9251e	da85a0ee-6d51-4488-a837-551b3384331b	a580ca7c4fd82a43bc452c1dc8d0c62eebf798cb4aa209aea599085852e20620	demo	ana.souza@exemplo.com.br	\N	\N	2026-10-19 16:53:51.87862+00	1	2026-10-19 16:53:51.836954+00
7b627803-71e5-4c58-bc63-0ad98e01a210	da85a0ee-6d51-4488-a837-551b3384331b	af643461971605c7e1b89323dab51ac5de68fcb07c87108031414120e5b0ea5c	demo	ana.souza@exemplo.com.br	\N	\N	2026-10-19 17:01:04.041834+00	1	2026-10-19 17:01:03.992965+00
a0c107e5-6695-4849-90a1-f392c0a0142f	da85a0ee-6d51-4488-a837-551b3384331b	3a7b60e1a5c24ba96736b74eeebd66b59589b4671beb41a7a7ee76a7859e7061	renovada de para-rotacionar	maquina:rpa-consumo-demo	\N	\N	2026-10-19 17:11:00.079542+00	1	2026-10-19 17:11:00.000678+00
ff046d8d-ed6b-4023-b129-297279e3ebc6	da85a0ee-6d51-4488-a837-551b3384331b	e48ce390493db7ceb8ef32ef260b76379a809acb02c6af66abb52ac3d40a9138	para-rotacionar	ana.souza@exemplo.com.br	2026-10-29 17:10:59.972511+00	\N	2026-10-19 17:11:00.121307+00	1	2026-10-19 17:10:59.972526+00
\.


--
-- Data for Name: aplicacoes_leases; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.aplicacoes_leases (id, application_id, secret_id_usado, token_hash, caminhos, capacidades, negados, expires_at, revoked_at, leituras, created_at) FROM stdin;
f8d084cc-d621-48be-8bfa-91059d2db348	b2c4316b-f06a-48c4-a22a-93a2acee64d7	630ef944-7aad-4cda-bbb2-882e56a57db7	c6c6b62de4de8539bd80df7fb79b89c4792230bb9a7ebd1179f551ebe2b79315	["cofres/contabil", "cofres/contabil/*"]	["list", "read", "reveal"]	["cofres/contabil/segredos/token-sefaz"]	2026-10-19 16:03:18.081374+00	2026-10-19 15:48:18.211246+00	1	2026-10-19 15:48:18.081374+00
95c6546a-0501-46e1-9b67-5e6b2a53231a	da85a0ee-6d51-4488-a837-551b3384331b	348803a3-56e5-4b80-b0f6-213643d9251e	e3b4a2c96cbba93dfe4c052ff2489d8ae688c6c079abd4f9bebe6828a9aad781	["cofres/contabil", "cofres/contabil/*"]	["list", "read", "reveal"]	["cofres/contabil/segredos/token-sefaz"]	2026-10-19 17:23:51.874803+00	\N	7	2026-10-19 16:53:51.874803+00
3b2ff8a7-f479-4206-836f-1b93d2069c5e	da85a0ee-6d51-4488-a837-551b3384331b	7b627803-71e5-4c58-bc63-0ad98e01a210	fcff709ae96ceec8eb235ef8deccf9ff4f0a285912c5d3f3ae945cdf7f2f1dd7	["cofres/contabil", "cofres/contabil/*"]	["list", "read", "reveal"]	["cofres/contabil/segredos/token-sefaz"]	2026-10-19 17:31:04.034384+00	\N	7	2026-10-19 17:01:04.034384+00
70f58271-10fe-409e-86e6-747a80afda00	da85a0ee-6d51-4488-a837-551b3384331b	a0c107e5-6695-4849-90a1-f392c0a0142f	1b56b3553737ffc6be9b87618dfed8b09ac06d02fe4df0dc930256deb8041259	["cofres/contabil", "cofres/contabil/*"]	["list", "read", "reveal"]	["cofres/contabil/segredos/token-sefaz"]	2026-10-19 17:41:00.073722+00	\N	0	2026-10-19 17:11:00.073722+00
b8f55bcb-ec1a-4dce-8c9e-22aeebc718bc	da85a0ee-6d51-4488-a837-551b3384331b	ff046d8d-ed6b-4023-b129-297279e3ebc6	7a0dec4742c3961559e0b13b5f78a22ce6eb699a19401ed3a04936298abad48e	["cofres/contabil", "cofres/contabil/*"]	["list", "read", "reveal"]	["cofres/contabil/segredos/token-sefaz"]	2026-10-19 17:41:00.118888+00	\N	0	2026-10-19 17:11:00.118888+00
\.


--
-- Data for Name: auditoria_ancoras; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.auditoria_ancoras (id, sequence, fingerprint, exported_to, created_at) FROM stdin;
b7f15c53-5d38-49e0-b5fb-fb977503911f	79	d202dc7315f6dab6e40f6d405dfa8f03adc887e11135b303f2cf4068d0c22439	arquivo:trilha.jsonl	2026-10-19 13:53:51.822735+00
64e26483-1969-426d-ae07-5082df8c5b23	80	98a44ed2d78b161f5481736df8613d8fa35cf20ad793f9a56044cb239a1632f5	arquivo:trilha.jsonl	2026-10-19 13:53:51.907049+00
29fd1a6d-285e-41fc-967f-875d4cacc3bd	81	0fbc5ad2fbd97d371c7a0d1d5ce87e80e33f209327abdbc11b7aa21b3a571932	arquivo:trilha.jsonl	2026-10-19 13:53:52.090318+00
5d2182ca-cc98-4890-97b6-9d2274741fe0	83	526e3cacc3814262a81fcbea368b4f8d14c2be99e5d22be9c4148557d3c0c930	arquivo:trilha.jsonl	2026-10-19 13:58:14.147369+00
9eecd067-b634-41bf-b9b3-84e211932898	85	ebe88e2099175facc8eaf9b1c068e6bc104a3d8c92c51aaed3a2f5288bd6b053	arquivo:trilha.jsonl	2026-10-19 13:58:37.292761+00
79a3874d-1ac1-4fd6-8050-b37bc3e98a78	86	350df2b35108a37b71857f2f363f53b15207e57ae4af7e0d9b73a02d2739d43a	arquivo:trilha.jsonl	2026-10-19 13:58:37.4067+00
\.


--
-- Data for Name: auditoria_eventos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.auditoria_eventos (id, sequence, previous_hash, action, actor_id, actor_label, target_path, outcome, reason, ip_address, user_agent, event_metadata, occurred_at) FROM stdin;
b443e306-0472-4ad0-8bb5-73e1a39e26aa	0	0000000000000000000000000000000000000000000000000000000000000000	cofre_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.784812+00
45bfc60b-5d06-4409-89a2-fea06e14a30d	1	0a64572dec70da16c4df3495b0454032456a9f6311fd1737d151e97bd9b99a38	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.801081+00
9275bba6-79ac-499d-9b8e-eafe94de6db3	2	0b7aea31d312aca4288fca8dff7519092d2e5c202613c64e43f707bfb991df62	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/certificado-ecnpj	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.805176+00
46742eba-910e-4f49-9e14-fd79a642872c	3	ad14dad755405bb341180dc6ed84c992114a786be93aa45a6b3f7cd607275879	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.809902+00
201f6e4f-b98b-4e9f-9e40-d82388b4c0ec	4	ba317443791265f8abf6010db3d0d50fe842ae0aaabd3848ff6be5aca720d6d9	cofre_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.820416+00
1365d0e6-ccc6-4c9f-a46d-80029e9660fe	5	3a389718137285465258a8e73933d8a991d09e34d230c86ebfaaf1a99344eba9	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.82441+00
1e6f2ed9-0198-4581-a91f-1d60fc2bd9b6	6	846f98be438e9785b0db046ae9f6056237d9ace76d844c6b0eabc917792d904a	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/chave-deploy	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.828773+00
66082180-bcc6-4453-bdaf-60f85b549cc2	7	e274c90b611b30070a6090b4084de36cb09be4a378c0c4e4406e539482c8f338	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/api-monitoramento	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.833533+00
f7d89038-850f-487d-aa50-f3c300d10d6d	8	a4a49164f3065afae6f564e3d9433b7c93beaaf894d9b50b8f8af4736f93d7d3	cofre_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.841827+00
31baa7d9-367a-4464-9e0d-c25d289a2c42	9	d9d71b0d2983af2640dd6edf96e10842c3a46b495fc9fdcc20061c48b5db67f7	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso		127.0.0.1	\N	{}	2026-10-17 21:37:39.845474+00
b043fc45-1d1e-4a57-8b47-43fe713933b0	10	b0ffd65534f91219f98d1b3660a667eacf18264ce1869aae98d4b2f768cd42c6	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-17 21:38:18.870616+00
74a82fa1-1ff4-4de6-917b-e8bc156adf12	11	05a53dcda91fdb8616611e7a2c9e1d1a54d5f3e0abace9fce2db3e062a708023	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-17 21:38:19.038561+00
5b0b32ab-8c3d-49f2-b1ab-529d4d5396fa	12	1374d5cb16635e07704953210bd176e489768ff51f664050cb7956e61beb29c7	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	A política não concede revelação neste caminho.	172.27.0.1	Python-urllib/3.12	{}	2026-10-17 21:38:19.110455+00
20f5f92d-e8b8-4ff1-9bb8-189f1a11b435	13	4423dd0a6b98e73362fbdaa058cc00790f2dde3112f408fca307324165e7acf6	segredo_revelado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-17 21:38:19.155506+00
ba35f327-0f4d-40a3-af77-36773876eee0	14	acca6c46927fd61733b418971f7ed57403c85888e81c883b82c0237672a5f122	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36	{}	2026-10-17 21:39:50.428989+00
248908b4-a973-4bf5-80e1-3609b36d52f0	15	1a22519acca07809c473c49dca45ca1fef5ea6efbaaa0846f485e14cf4ab7c19	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	curl/8.17.0	{}	2026-10-19 12:12:50.534451+00
c5493492-6e9b-47a1-97ae-37984360d1f8	16	e81b5a9a532cbdabc73ab302c9731ea7f2331486f58644074b08bd4a4ae105a6	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:13:11.970667+00
abd0af9c-5851-45b5-aee8-8a45d2900e50	17	7c3d0048519f80cd80c626227223967cf02ab18c8e7f487155a5b13fa39461a9	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:13:12.192672+00
ed32fde2-6445-4d54-ae68-ee1b78b2bea2	18	f13347e201d89ccc249d289a617edc720a64b23e78166b6dc60097c505335a20	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:13:12.229454+00
0e69d073-f526-4d7e-adb0-0d9606d37157	19	2608ebc2ae34f32c5c6d537c2fedbda7c2e0a5168aea9914621872665d388e26	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:13:12.251022+00
06b0787b-ad3e-41a9-af7d-c6237a62d1de	20	552e0d6abff872d581c232916a3d23fbbc07ed8fa126ceed947603e65c84897f	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:13:12.275319+00
0b456302-8b94-4db5-9596-ccfb2d5931b3	21	4783f0760fc66d72db02aff75b06938a40c091ac7fff0f4e39cc1b51789cf0a3	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:33:11.825682+00
0e02a4c3-24c3-4c05-beea-694a0ac3664b	22	915da1f1d8b07140d4dac5a34376ace096897ec6e4d29393e8193b8b1bb1a6f5	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:33:12.020975+00
12c9b585-239e-4f8c-81de-1bb3815a90ae	23	6a137cb93e25cb80cdae1c20e5704d09c1223a4b491834ec31a183ba5ecbfe1f	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:33:12.246149+00
2c82b306-3c47-4258-bddf-bf2742a6826d	24	db707e5b58c16b27031d3057ce92a6da89fcee2c4c2cce0871b9ad22d5bddfa5	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 12:34:33.165434+00
63c00084-f398-446d-9677-0cebf360bcf2	25	f72fbcea0a75f9b63d642364d59a5d052380f8829027516901affc23e6d2a4e7	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 12:35:09.976271+00
eff1298e-3010-4e8d-93e7-b62b79dd63e9	26	d96d539545ceffd9a9916e780acddea70a34cb02f70aa6ff16071d6332d9da1f	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:42:53.34975+00
fefb6439-90fa-4411-99c0-2afb20c82eee	27	bb6cd789d0d93f6139e0205ffd1b2e39a6a2891809db6a5e84789fae842ec426	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:48.824526+00
0ba6d445-d9d1-4c3d-8158-95f2ab826d99	28	0850d5f2abb988b4cd5aa8f01ac716dab1da8596cfdcf53ec7e61ec2f4e01560	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:48.990713+00
2d2f431f-0d02-4cac-b92d-9be241634b2d	29	0afcf287ea8c1767a9163ffc6d5a35beffe3f446abb24851187fed3d8d965056	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.029014+00
507c4931-7705-40b2-adb5-010dffd58cc5	30	26f5afb5c4299804de30f2feeece0f29f0909505d9814595abcb7bfb257befab	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Preciso emitir a guia da SEFAZ hoje	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.0562+00
12fef09f-7edf-48d3-ab0e-d6998ae7589b	31	700edc9e4edece110b754c05f232265f09049f897c54d8683a95744fb1c96ff3	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Sem permissão para aprovar solicitações neste caminho.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.124723+00
1acc557d-abbd-4ec6-b0a4-0d7aa551aff6	32	f109eb80ea2ba5fc70b43ddd0314bff1acc58946b8f5e69c17707d899aa5eaef	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. Ok ate o fim do dia	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.163793+00
7308f0be-a121-4553-829a-6518da2398c2	33	edb51ef1a45a7c3aba14dd3694bcbf9b7f6803a45f4b8dd8382d34df34faa46e	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.186438+00
ceb018e1-fa91-435b-ba94-573a386f3199	34	4b3a1c0b1ef90c6c2209c60e01270b1e4140baae13103f335af58cbcfa29fa0f	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	falha	Nenhuma política ou concessão permite este acesso.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.209167+00
2b476034-bf39-4dba-a5c5-62525fdf10b8	35	c3bcecad7669e083bc374d6da9dab3db8ff95193ef326b600dcc67a3d7e2b864	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso	2h para reveal. Motivo: Investigar lentidao junto com a infra	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.227226+00
8a338e9c-560d-4069-9950-4f2a1b3505b4	36	430bae1e4daf7897e65f1902af00fdf04ca6e8db63986d72c428e25bebd275e5	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso	Concedido a contador@exemplo.com.br por 2h. Acompanhada	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.248734+00
ff07840a-5571-46e6-9981-fab939e24fcc	37	0e95adbf50f2b1827736a371c204b4b5767cc45ac2f5d2e0c637d68e78386afb	segredo_revelado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso	Permitido por concessão temporária aprovada por ana.souza@exemplo.com.br; expira em 2.0h.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.290661+00
0ba378f6-2938-4579-a5dc-fe79e0e62936	38	dd3ae7cfbc179438382091945c7539df29e5f895c85955a1336492442c0473f4	acesso_revogado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso	Devolvido pelo próprio solicitante.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.310886+00
0b8b5659-5e88-4660-ba76-1ecbee6c7ffc	39	e3e1b7e47bf939c5e4ab3a226856e8482d010264b74a41b1bf738eef547a1123	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	falha	Nenhuma política ou concessão permite este acesso.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 12:56:49.328681+00
83d99473-284d-49a7-beb4-0172c7a3afe9	40	2b439640da121c6fc28853421a56340c13ff7d6520441649454de9eebecd0382	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:02:50.120874+00
967b9da6-2ad5-43d1-afdd-aa249e42938a	41	db80484d00d7efbefd1c41c6ee19a22c174af4f04083bbf6280b562688aa38da	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:02:50.243639+00
ec0e0628-6a08-428f-a5dd-58cb03ef568a	42	c3cae5e47bef0efe554c17dfb88f94e0f1de2da75dbdbf80a877899872522124	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 13:03:27.45275+00
0cb34c1f-b83f-44dc-92ef-a4d55100a18e	43	98e6e446e3fdf3f9697d69f437ad4696ff273a4d70f1cf9af08889b1042ff185	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:40.984232+00
b47f2ba5-d093-426d-97ce-b25b2d0e2b85	44	82894bd6dc035713cffa754fc9104f29e6f23c9bcd0d6c546d611a1df0866f2b	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.084766+00
fe935bd1-b310-454d-9410-73a33b6d007f	45	9bd3d48de0e87562574d4c2402d7270c7befb365e39e3b02babf33681d303823	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.108665+00
b6e76586-842a-4b16-9659-dac7fd343ab0	46	a0234a58a14d2f4a9a9c2d741b09bfbd1b2268df70c4e779ee2ac3dc5d03f664	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.133705+00
0c01d1a1-1a44-4f2b-9d7e-1c47506184c8	47	34175bdfd792f21329145a21511b9cae6151aff1a266b3d60e00fc3c062e083c	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.158995+00
418036ee-f84f-4662-a5d9-31e0475496f2	48	9a7aefdf3ac21df4042901538dd159588e6b25b05948b60294b878e87ddbcc80	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.18381+00
b2585b70-a630-4233-b223-2dce0e18a497	419	8c2488e6fd8dc8dc84babcd6bc5f72d11f5dd6f02f2685793916141c93ff1896	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:34.815224+00
aac52d4c-2152-49c1-8536-162e1244aae1	49	8fead65ce3af9abd6404913e970317dc0b93cee37c87479564c26f03dc9b2705	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.210521+00
a9414400-5eb6-4fe3-9e55-12229e16e95d	50	c7735dfb7f0ef1b6dc78c2c0d362853127d1f1fe60f50932b87a32ecb5944e83	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.258994+00
b0d4199d-acf5-4227-b5dc-62d6c6328b62	51	e6cbd1404a209b0ad54a9127b8386cbe8fe6dcb7d08c63ee319ea2d7f0e4f5b8	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.290332+00
ebc34933-60bb-4b5d-8615-533efe8401d5	52	96c84ab01c9e159aac48626efcc1d9eb273d39c84e1fda210aba125943694d82	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.316805+00
2991ad69-f5bb-4b2c-9897-646c86aac560	53	c97068af1f2592cb11750771be1fec85c90ae73f397e17e10dcaaa6e71633579	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.349106+00
f66687c6-df33-406d-b504-9f2ec0eb9003	54	a06d832f84b92da3db381ceed42f6f32a80098b197cc16ee1a741a45d9a76f4b	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:41.456053+00
fc24cec1-d3a6-47af-9473-d500fe8b2ea6	55	b8ea538806a03371e8a798c8c06385af996be7b828823f73ee13842f29930cb0	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:42.113459+00
51b6ccda-4559-4eae-b159-bcd87c4e748c	56	a9ca7def617acd54f0f64b7cbb6dfd0076a5222ee849f5dfc92ee40f3c8ee3bd	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:42.165464+00
79dbac3a-4577-4cc6-9118-ff66820fe430	57	886f4a037a16a33f8bb43e12aaad009fd3cdd7132c46820cbe4e00c0742d0da2	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:42.273266+00
52b987a7-5097-4593-a056-1bddd0718c44	58	40d630e90dfb290e466f4a6bbace8af9283fd00ffa37f5af5fa05d1e5ff92cc3	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.452851+00
c47eaba2-1344-4218-b5eb-51eb5f792047	59	8c86a45b79553c61d44875271914e0b0a4503de6ba6061536e98991d503b4875	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.553573+00
40f1b4ae-fa55-4ad0-9b5b-99a6c51bbdab	60	655eefa8d67c3d785d81f60cc362737c9d0c619d40d3ace389d91e251564d891	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.581219+00
66750028-68b5-4f74-8446-b80497190c5d	61	1ca16f441f53d71785da001884a07a0bee9448cc39055adb2c621aa9ec537340	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.604603+00
d4c69030-f45f-47df-a443-ed5a5a0f1039	62	0ed52fedde46203839eaec48b65bd8db9b9a20a0471f70d550f38ff0c137e832	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.629921+00
9fbb6842-f547-4092-848c-e38e91558761	63	cf5460dda7c68ca0f4071f28647178d54be8f5eccb09937cebb2faa32daa6b0c	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.650281+00
616c1e3c-66db-4168-81d8-a196d3d47587	64	69922c86c7d7ebd5afb934a9d44fd144490c121577b663d5a1ed161ae7b6048d	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.671698+00
9d9c2f2e-6dbb-491e-8150-a2bafadaa7f4	65	bda2ca0eda4584b543bfaf611d2ebd8e79df91bd826dcedfea170e97c5c416bc	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.716167+00
8b4955dd-d79b-4326-bb22-0f146c76809b	66	d08d2a40c912cfc3ddc91a4aba0e3ae544374b513d293d43217f7eed603a1be2	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.743814+00
87b5fe97-e791-4b04-a6a0-b08ae8c494f6	67	32c42d9b3fa9988bd583b43ca7300a6f323d8c6eec3b2b312102ec0d69bad2fd	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.767869+00
585b850e-5295-44dc-afb1-d50351c3c79e	68	dd8233df3bb003eb21f3a3cb0fba6bd49f885957d53612dbd62ea04386febdea	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.787843+00
6d3cb57f-f6ee-4c86-b669-21f4336339dd	69	0b7edaedf43e61c614f3406a705029f2d1343ce019f91229464858c4f12702d3	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:58.866032+00
a22d402b-8613-4377-abd2-75203045ecaa	70	40a86e5500fd5093dfbb5d0c845ae718a40aaa589ef8e3df8c13b777d579529c	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:59.450002+00
9beb27ae-7858-4862-82ca-43bd7fee85a7	71	b2809a8fcc24ea8276a28c1f0b5713e959af521f55f15bfb967c24282ff62881	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:59.517188+00
97910ee3-d121-4f71-93e2-abecc5a9d668	72	7d152f992fb5fd91db0272f47aba8841d0046c35f13ecfd3470559f2b26138ac	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:09:59.643863+00
50a36172-a2aa-4b80-8804-c2c8fb1efae9	73	830c0f25c4b5183ac60e0daaeeb1feee62e598e97e99066356ad760315fb94db	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 13:10:32.721792+00
9f9b7082-7644-4a49-8c97-61e34d232452	74	fc714c33d7d3b15b1bf0456e0db6d8f91f3d85d32ca6a540a9eaea838ffa4481	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:40:33.439773+00
be815d0b-3237-454f-a8c6-05b7f2aba5aa	75	b2afdd35f2dcc6fc2a860ddce71d7205621f9e49911b756eaa9524c9a771830a	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:40:33.876622+00
c73cae03-00b0-42e8-a218-34c9e4abf517	76	085cec8d744d65913b3ca552c8b477d280f4106659858374aa95e0b08d1cefce	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:40:34.141111+00
145d2aa2-6c0b-465a-aeb6-97370454ada3	77	b1ef26373b89f7fe0207ff1678985f5e363bbd1e1b09c9626ef19712f4dde106	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 13:40:52.717383+00
2d704524-189b-4916-9c7d-4fa2b30aa5f0	78	86473afb39791d6ecd60a078c1dbc020687ebfa49be71ecabecc6325649ad48c	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:53:51.542783+00
4d586c4c-87c0-4217-a012-a7afbcd74e50	79	8e9d68188c5991888925ff0506cf35732d71537e62a644c99aef9924f8abd5c5	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:53:51.685928+00
ea342e8a-d5aa-4c07-861d-fea6ac38adeb	80	d202dc7315f6dab6e40f6d405dfa8f03adc887e11135b303f2cf4068d0c22439	trilha_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auditoria	sucesso	80 evento(s) para arquivo:trilha.jsonl; âncora na sequência 79.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:53:51.825121+00
fb3077eb-266c-415c-869e-f75fa3b9a6e3	81	98a44ed2d78b161f5481736df8613d8fa35cf20ad793f9a56044cb239a1632f5	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:53:52.062918+00
e591c8ef-aba3-45d0-8e86-a0a2cdfc856f	82	0fbc5ad2fbd97d371c7a0d1d5ce87e80e33f209327abdbc11b7aa21b3a571932	trilha_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auditoria	sucesso	1 evento(s) para arquivo:trilha.jsonl; âncora na sequência 81.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:53:52.091143+00
8ba502ef-7279-4f1f-995b-5ae417eba969	83	d3d54cfd7c5071cf697dc280d1108e9f851628f22c18fc2dcb933bdc5a3e37ef	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 13:57:49.502813+00
284a39b4-fa0a-4487-a7ae-8b2a2cc915a7	84	526e3cacc3814262a81fcbea368b4f8d14c2be99e5d22be9c4148557d3c0c930	trilha_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auditoria	sucesso	2 evento(s) para arquivo:trilha.jsonl; âncora na sequência 83.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 13:58:14.148194+00
66511a87-5e01-46f1-92cd-cadc257eca77	85	f6e25d0e26fecf655c796d1e37041e174b28a049506afaf50485b8342ff6c21b	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:58:37.229317+00
d1653c7f-c457-447f-91a1-9007602a7414	86	ebe88e2099175facc8eaf9b1c068e6bc104a3d8c92c51aaed3a2f5288bd6b053	trilha_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auditoria	sucesso	2 evento(s) para arquivo:trilha.jsonl; âncora na sequência 85.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 13:58:37.29396+00
a6e98c3b-86d2-4305-97ff-f77a353a3b35	87	350df2b35108a37b71857f2f363f53b15207e57ae4af7e0d9b73a02d2739d43a	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/certificado-ecnpj	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 14:11:18.937423+00
f9672149-8cc1-4069-9113-9ef99024c826	88	23391e9e5681739317c153cd76fcdae4121dfb48fc4e12dc265527b4ecb18e75	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/chave-deploy	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 14:11:35.145244+00
7ac89c5e-ed2d-45eb-baa1-8e8ec060b801	89	19c28129cfecc09bde44829647ed2e9aed68c1f27cd6ae03401cc8425d4f05eb	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:19:11.99581+00
e78bf8bb-b8f0-4f4d-8e6a-6963d08503ed	90	cddbaa3f3b17cd84e51347f9a364d51554c27cecd23048a0ad1ecf9da5c55d95	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:19:12.039662+00
907f9787-9aad-4371-bb64-ec3626e40fbe	91	d19b2c90fc3eb887b40c52c854387f3ec5a46335a5c27a931f7881a5fb279c26	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:19:22.45282+00
6fc2346d-50e4-4693-ad90-d05a4a7e5235	92	4bec9aecfbaa7e5fc10f58f780522b761b4767d0a8ae8525eef63693ae0b146c	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:19:22.547103+00
05c58a5a-41f1-49bb-8164-3d55c37bb14b	93	6ad194bc8ea20aa5f315c49cfd3dc7416b92c8557daeae6762d93558d67895a8	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:20:47.118225+00
c2676403-8a6f-4053-ba5a-4cf5cee44f01	94	4e8c0a441473ae1b5131f9aa86719855362fc1fef90f77ab5357ff980d51a46f	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:20:47.160729+00
32dd8b66-ba79-4081-a6e2-9bb234a5bee5	95	d684acceb0fc3ed4d3dd3bbcf06cd0d00c9d86154be58a60fbc0cacc4fa75cfd	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.464203+00
59e1ff21-18f6-4533-9029-d7cebf17c65e	96	54825798d3757c8f7ed9533fba808fe9a338b9a3da1b5a59118def49d1ac80c3	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/dominio-escrita	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.488819+00
0649b9db-8176-4f6b-a6a4-7cafa78fbfee	97	11b7f5801607cd4f75a702bfbacee619e9231eeb2b06b30c9219fad8478efbc3	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/certificado-ecnpj	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.510212+00
09998dd1-6762-482d-8801-7d6e5fa3c7ae	98	744e3a226e927015ed8c2b7fc8c310b148cabcb80e2466aacd813b37f6ba424f	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.530299+00
4c29f20f-3471-4ccd-aa2b-8f24a59ef026	99	eca680fdbc29ce98feed6e18b2e02f032edd0b60f864d5452346d14233853df0	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.552743+00
0179a5a1-8d23-4189-b72c-3eec4cbd36c7	100	1aecbbbb3ff17c9b9c46c3de1dde0937b77d226dbd54617a10c738163fda820e	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/chave-deploy	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.573276+00
36e9fd1c-6508-4c0f-a5f4-b9eda6965dd7	101	b52f31ffa798bc26615925aaedc5ade9f0841966019f8b2933b769e4e8aea51c	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/api-monitoramento	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.594862+00
d769dd9d-8b12-45f8-8444-436e2c384d72	102	79a2f0d82651be8de0443e36ebd70f8b8f7226993e5d369ac74e7ba4a89c1466	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:21:01.61436+00
92fe6a65-ada8-43d8-8872-e31e11462206	103	a9d5431b07889d214f3fd796226bf7a7dddacdff972329f89d6f33428a701fcf	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:16.916001+00
7108500d-56ae-4fcc-8c6c-d808ee2063e0	104	54208c8d9a54711f6287c8d35da345361f302cf38fbce6ca379521169c57f06b	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.004034+00
8d58e296-84de-43c8-9f2d-294d94c853e0	105	2d5c41eefe4f5e4025108e547003e3a5c1d7e928f2a8bf6d00120b958691862d	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.026087+00
689e9aff-a974-40f0-9bbf-6adb66a17bb7	106	500a6c4c48f5c385077e39e63066c394dc93e50d78a4863ed311d7d89b9c82f6	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.055941+00
3326e505-de50-44fb-9d90-3a1442526f21	107	57e28e3852e4f5a9dc78b4317625ed74ffb963e66cdc9b2257ea568fad173305	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.081031+00
8608a62d-590a-4cba-904f-c4b395201e15	108	e837a0ea455bc866a3d82bbd91b6f5347d4c733b7bbd077da66c863f6b41b7e4	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.107767+00
a2037a5b-7539-4bae-91e1-264f843a6f65	109	4f5f882aa7a2f57fe3fa6664ee5c6ded874d6d238f6c609f141b8c8a10300a40	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.130712+00
ba8b4f43-e637-4f6d-b6fa-d6e482547b5a	110	0d95f294467cb43b66994a3f910bee6015c8bcc37937a0fb694c163d9cd60bd2	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.175427+00
55f6fce8-79cc-4afd-abc8-cba2a9f82559	111	8da8ec9dd18545cd579e39194ffbcffe32da60658e3458ceda5a73b0e2c0da7e	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.206143+00
d1627554-52de-41ce-88b4-97eff26299df	112	ce1f1016c2e126a99c8b65ab94ecb8b53b9a90beea649185db457b6228053033	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.228059+00
37c30d6c-a8a4-42d6-b2de-027b48f0a72f	113	81c0056bf0243334a7fdeacf42c8557c1c20a66c18030191b9242852f074149d	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.248914+00
bfd35274-47b7-469f-9581-542304bd481f	114	7bae340c4da77af0abd16a3b1156fe9427ebc5d83b1858299691bfa90dc4ad2a	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.322501+00
5402cef1-5afd-4a6d-ac3b-a61700eda74e	115	bd109e36d8699455d079c52877b30778c9b72ef0d04685131cff8c34c3f8639a	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.75902+00
ee649bc1-4dbf-43ca-b9b9-c274e9b5921b	116	7b2f86da80c00433ca31ecae858b71a5e3d626551d946c8920c5a7ace311d318	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.797166+00
4ff5b3e8-6a79-4808-8806-eb24ea0a3d7a	117	c3f1d2aea90ebbd60fbe3b6f5ec87b385434eba2bb50e41c1527d6bf114ce99f	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:24:17.877474+00
3307d471-e42e-4c5f-89f6-f24754ad721c	118	c3813e9a81f0564502ddcd95ec89458e77bdb47ec388e66cc1cee4a2040c711d	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 14:24:36.132499+00
f2fc621a-e5db-4025-8b68-8b88995054c4	119	d4c088ae8a74dacea13d04da96fba49e484912736ca38977e535bc004ceb3809	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/api-monitoramento	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 14:40:04.346747+00
2064e86f-1a4b-48e6-85dd-1f7f1ee61e09	120	285c05bb049627478c6d4c2c9374fbca997627252806ea8de1ba89a1d00bc4e6	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:20.868169+00
4bac535e-fce1-4cd2-bf18-9aac3ed0f86d	121	4667d9afe99758791efb9a23f946bf167d78fd557d09dc8899ac8c8355b94302	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:20.943803+00
b6533db3-a20c-490c-8129-3176c84d57be	122	9e8be51e6e921868b6a8190267c749dbdeb52b45cb4780604cc9e8a6e03a8ddf	cofre_selado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	sucesso	Quórum de 2 de 3: ana@exemplo.com.br, bruno@exemplo.com.br, carla@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:20.981412+00
e9bfd8d3-2436-4592-8382-0314af695cd2	123	22fc116bd2b120e3b01b77a6a820ffe39487dcd7d4768994b0d876ec68403ac7	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	falha	Tentou desselar sem quórum um cofre que exige quórum.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.033355+00
3e957c23-ab72-4baa-b2b7-27911207874c	124	c4799655672bfd9529706d09a03ad27ce54e22dd2162452e1666ea1d45ac7d4a	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	falha	Quórum não atingido ou quinhões inválidos. Dois quinhões com o mesmo índice. Um deles é cópia do outro, e cópias não somam para o quórum.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.060627+00
75ee0c9b-500a-42cb-9e09-bba957de9ce2	125	496d8e57d4c3fdec11c4248680297b44d6dd47c1433b40d9c5be4effa2da0cb3	cofre_selado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura	sucesso	Quórum de 2 de 2: x@exemplo.com.br, y@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.09137+00
afe25e76-6931-48be-aacf-57cc876ee30d	126	ffee9c2798973f54dce9fc6e66a60b58322b1edc05fe727d636680bce1604f5c	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	falha	Quórum não atingido ou quinhões inválidos. Os quinhões apresentados não abrem este cofre. Confira se todos pertencem à selagem atual.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.119542+00
f5b3cd1d-e2a5-4bf1-a718-932bc93e0cba	127	27d953afa348d193992afa9cd91287d2e56cc0222a431be420b57b135eb7af8b	cofre_desselado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura	sucesso	Quórum atingido: 2 de 2 quinhões, limiar 2.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.152558+00
892a3774-5661-4634-851d-3d9d7081dc20	128	10948db4db1899c4c6771eb06ef032dee45bd3b64ca80772cf23a1cd5b9f4fb4	cofre_desselado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh	sucesso	Quórum atingido: 2 de 3 quinhões, limiar 2.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.190219+00
094fe9a2-8cfb-472b-9210-1d7640170a1c	129	ab4a7381bf6daa3549ec188f76803567c2a088d3581c29d33a767eaca3713122	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:42:21.218261+00
bd597bb2-81d7-481a-a5b5-9eb515eda2f6	130	835af2c5cfa6dfb9652919bf3fb305783e120013b575894244b9181a10a28236	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.377919+00
1f953198-f1fa-49f5-86da-086dab85e158	131	1d4ec1afde5d302bea960fcd9a9108db9594b7dc3cf5629750aa3c94bc654083	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.482081+00
4434533b-ff59-4dce-92a0-6d6ed882debe	132	a510cd8933dfec51d78f225203025170064698d06cc818e1dff49428e3786657	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.503729+00
0734074d-18aa-4801-9cd0-d5ce0dd8d1ec	133	80f226ecd7a37925c0a44afad4e25b9286af2121c2888334eb0ecec1f19ed65c	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.52842+00
2265c16d-5a1e-4c95-a6b2-a21b1f70431c	134	db481775c2b149e644a7e5f1e9d8b8bbfe35a3268f75e384018d76348da26e58	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.548737+00
5d698113-3068-42d5-a023-8eea5f043071	135	ec386e9dc93aca64f3549265692a26d7b862e2633c6697e6da7ee44abec8c521	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.573594+00
158156e2-fa75-4200-9c21-0cf54d60d0a7	136	a78d37f5ddfd9d04d92e9e64a04d851c1b54cdfaef0beb3ba8dd73a9824b867a	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.593431+00
64f3616d-43c9-4b8b-899f-ad3d49c9d5ec	137	610de068d2b2b4d827d7cbc737423662f4f26a838ce42fde50e3e4104421302e	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.632559+00
b30a51ea-e9b4-4bb7-82e0-84baf8158d72	138	b74fb45907fd4ed7e98fcd4b8117f34f58b7cfa04ea395a8d11a09b2f7ec1866	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.653559+00
3a075cf3-3694-4c14-a088-4b0458fd5220	139	9e5db2ac5fe5d9fdb85148fdec3dbc8b7e61d259741cba5b71a9470755b3f024	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.672521+00
610a778e-e51f-4f58-9c92-555c64ae15ae	140	8880593c52d76bfa8625264ba75d3cc29490627604ae7a2a82039d5d99e97a5b	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.689924+00
594d54c3-2584-40a6-b3b3-a1508724708b	141	ddbed0ba93c2e214188205c2a2498fa95bb1915971b166b90aefe17ca65508b9	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:22.765197+00
e6d002c6-0733-4583-a47d-86ad0f0a2e7f	142	b8c3bd91bbe55be348b51d2ae38a23778b01b1bb3ed1a33993ffb8f182c6cad4	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:23.240467+00
90e340d0-99c3-4691-9639-11f6b0862470	143	647d7848a08cd7382aa66de14533afe4098d6858d479827ab9d94306b2ed5017	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:23.280256+00
8fcc9333-d022-4f34-9073-0da1b6c39fbc	144	89470d128517e455bd8f610b7462f0b341c862ca8c50bce7e595182f48cc5be9	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 14:43:23.379711+00
bd6f2125-4c75-4e11-b93a-7b766d1fbce7	145	81e5d4474cc72527ccb979a198a7174ab21f4566e5076b1a4aef65108a845530	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:43:04.984351+00
f4cc8583-5f54-41de-9a44-a7ac53900d21	146	0bc8ef9b685d5687b7125671a56cc3356b4eb8bbd57621551d0640c16dc1da4b	aplicacao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	Responsável: ti@exemplo.com.br.	172.27.0.1	\N	{}	2026-10-19 15:43:05.08896+00
9720a973-40f3-4ab7-b312-07657e00862c	147	d7f21981826a73c080e6735ef88f7c336e923551c306b0642006b4562c2a0fc5	aplicacao_credencial_emitida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	producao	172.27.0.1	\N	{}	2026-10-19 15:43:05.129024+00
1d160048-fe20-4a61-8e84-4427e8a1473d	148	c1be441f5a1451006941839b54511da4adb928c781ddf9f14952cd2870a94b78	aplicacao_autenticada	\N	maquina:rpa-escrituracao	aplicacoes/rpa-escrituracao	sucesso	Lease de 15 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 15:43:05.159749+00
41829054-fe77-48c3-bafb-ebb6fdbf17d8	149	052ba2eb26df54f76d1854f1f590e7ea51e9b1b3393879e8dd7551886ba3d396	segredo_revelado	\N	maquina:rpa-escrituracao	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 15:43:05.205358+00
285eb582-e21f-464d-b93c-9ffec8496397	150	165feacd5c186a6a0e424606dc2e1a871863a14dfce37394d611ddabd746c2a5	acesso_negado	\N	maquina:rpa-escrituracao	cofres/infraestrutura/segredos/postgres-producao	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 15:43:05.220893+00
674e374c-40c8-4e6c-bd51-f42402d3c975	151	8f00ed04de8b1a4bd224e0c6ac748e7339bc1731495100fb7a3dfdce2c89bdc8	segredo_revelado	\N	maquina:rpa-escrituracao	cofres/contabil/segredos/token-sefaz	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 15:43:05.241768+00
6f14ebeb-16c4-4f8a-b7e7-f828795a540f	152	6101dfc374844a55efe0b9710ee217c69871030d08d407b51e6b73c1259b098c	login_falha	\N	maquina:rpa-escrituracao	aplicacoes/rpa-escrituracao	falha	secret_id inválido.	\N	\N	{}	2026-10-19 15:43:05.256813+00
bd5bf544-9955-4429-9ff4-3dd0ab467b16	153	0e882e686e5d5752fc2a6c8a2318d407cfbbd124adb0c1f40face028801f97ed	login_falha	\N	maquina:nao-existe	aplicacoes	falha	role_id desconhecido.	\N	\N	{}	2026-10-19 15:43:05.270744+00
3be1bf07-23a2-43ff-846a-6aae1b60ad26	154	2d7a4dc53b5dd4fceeef6e7a7ec1f8784a32de43d9e09fb5873b8bdd447061c5	aplicacao_leases_revogados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	1 lease(s) encerrados.	172.27.0.1	\N	{}	2026-10-19 15:43:05.304099+00
4d3d3cf9-521d-4e62-a485-480b86fd7bdb	155	36347b458f166f05b21631251a137ccd2f2d3e5bfe7748877eae3e3388c5a848	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:43:25.926963+00
b2887340-8f91-4161-b0cf-8f5462231a9c	156	228ca8a839546d7d30d5829df7d1e81fabe3e571751f83a4e7d23dc360f13e38	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:48:17.923709+00
4bfa1909-c86e-4ad9-ae6c-8471fac324c7	157	bb3d60639bf0e24f512cad59dca58a635b588b63b0800166ebb23f6bcce0903f	aplicacao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	Responsável: ti@exemplo.com.br.	172.27.0.1	\N	{}	2026-10-19 15:48:18.020964+00
322045cf-cf87-4b22-895a-fde137d69a69	158	b7f4acdbdf4c944c49966b72bcf25526f65e8d14ec46877c323d1c027f078ebd	aplicacao_credencial_emitida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	producao	172.27.0.1	\N	{}	2026-10-19 15:48:18.060917+00
2a82102a-9b0e-465f-916e-2eda850df124	159	aea3cb42fa36fef896d21fc5ef02226dc7238fe950258a887b688c00eb55eca2	aplicacao_autenticada	\N	maquina:rpa-escrituracao	aplicacoes/rpa-escrituracao	sucesso	Lease de 15 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 15:48:18.087945+00
a4df0932-a771-47b1-af82-90bf9dd515cf	160	8717c069cecebd9367f6205d5413283ab0bea11e9cf49b9cae20623c49f9b051	segredo_revelado	\N	maquina:rpa-escrituracao	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 15:48:18.120652+00
d1c0a7a7-acc3-4f6c-a7ac-cbda6a058211	161	77d7fcffb21fc0de7e3b11e34b966d0138884f78bc5ab79906017b334f4ff047	acesso_negado	\N	maquina:rpa-escrituracao	cofres/infraestrutura/segredos/postgres-producao	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 15:48:18.135864+00
9a8d2a8c-4d7b-436b-b54f-4c35ec87da17	162	f1ccc6fbaef1818f5fc528ac4229c5bdf2b59279857d096b389f09734d8a5265	acesso_negado	\N	maquina:rpa-escrituracao	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 15:48:18.155917+00
db6da479-03b7-4392-87b8-ecafe10cd0cf	163	607b96b1bf2ab0529f9b6649ff353c2b27fc42c723d30a6a5abe293440e41429	login_falha	\N	maquina:rpa-escrituracao	aplicacoes/rpa-escrituracao	falha	secret_id inválido.	\N	\N	{}	2026-10-19 15:48:18.170409+00
b655d7b9-10be-47f3-8838-32c7ce0717e6	164	8c7491fa05a9968ce90bfebb521a04526c3295e7d2906f22591b6cb7aa2838b2	login_falha	\N	maquina:nao-existe	aplicacoes	falha	role_id desconhecido.	\N	\N	{}	2026-10-19 15:48:18.184842+00
17cb508e-9dda-49a0-909f-1e27f02f395a	165	485dcebb3fc6863942ba83e0f3946fa3b4a0ea3c57c48b1e99cc079608072b6b	aplicacao_leases_revogados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-escrituracao	sucesso	1 lease(s) encerrados.	172.27.0.1	\N	{}	2026-10-19 15:48:18.214423+00
d58dca77-534d-4322-a456-29cca9fb184b	166	9a844135e4fde64f777a5f350ffd350449603842c4b1b8bbdfa4a784b540a04f	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:30.848228+00
e1a44671-e306-4165-85b6-46c3e2fd2c70	167	e13cb32e69b232cea63e4bdd62f226a7693ac23013cf3dbc59d829447191c638	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:30.943215+00
c39dc193-80ee-4163-9d9f-26c1e66fb225	168	1175b254214a106d6be63fde00fbd3c0165d3f21160d27e2067f59a8c15bb2d1	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:30.969263+00
0fd2cce5-bbed-42bb-b599-58a542544a46	169	52b7433c2a99d82281a2f46c3f642a0cbfb974755d6e88b0a4311570876ad163	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:30.996548+00
7bdcd061-8a9a-47bf-9364-e09d77418fa6	170	fd7ff9c1de57a74040ec82fde1cc54ce8653f73ed14730e489752fe68de9eb45	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.023099+00
c70c5c0e-6cdd-4b2b-8484-81081daef8d6	171	7ba3c6f6a096298bbb79f4d005849a9c06e7a66a0cc6f49ca5eb75e23241e747	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.047543+00
cd0a3396-1838-456b-81b5-691e4e44a5e5	172	e50f8ea7fb37678a7718b273978d01cc10dc133ef9b89a06797f9b62d2297775	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.072074+00
bd70011d-6b8f-4286-a0f3-2705f32ad59e	173	2bd94620c5aca2a57e04c284447ffe3548f176c6d9da246845550f4dbb1c6d39	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.120617+00
3c975eef-58fc-4eb4-b330-8ef1fd19110a	174	99487ea8456220da436a3c6657c221bf66ebf781258ffd68f9e518b11364bcad	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.150852+00
f727034b-1e38-4e18-a822-cf9ca15414a3	175	2966e78a7aeaa40ca3c0738e0caab28a29a7b5a595d9ffb8f5d4cab5b3544dfc	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.180427+00
cfc80b3b-b837-466e-a0a0-dab533477fb8	176	6bd8f231ba8333069bdecf21d07478357c5a70448656ced82c4f32a7b2d24fdc	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.203142+00
e10d897d-d966-48e5-97b5-13edc8559052	177	7e9040d0424c3fa84d913b16da40d4866dc2a41f05655f5183f7a5e81e2dae5f	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.308046+00
684e359a-bf66-4ec8-900d-c7ec735e2715	178	e494574fa661e823cb0651a36510395cc5ea00d7262da6909e05188ebc3e4d25	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.835889+00
1f694699-2f0c-4ee9-a63e-20b9cdea0a57	179	b83486cc5f1b61ae0b73fa9261441fdbaa04b817a95b9316c5832d13405e3a6e	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.878182+00
ac49f4b7-5e5e-4db7-b2fe-73384f1f7f58	180	e765dfc98926ea07b5f67efa3d1954cf024b74678232de49ceffd8fe696c19c1	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 15:49:31.967522+00
256d9f8b-53e1-4370-911c-59444830b375	181	ad61b9d4800e6fa0402e0c58089e3a873135bff40ece243ed7c3dcf70d7a1a26	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 15:49:59.543154+00
9a57206d-ef4f-4c80-b6a7-cc9fa9dce888	182	66bdcedb92eef40d966fde5ddd8ccdbeef4fd749f401f8bed9f118b591c9c960	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 16:53:51.386415+00
e9891dd5-173d-485b-a265-7e07b9983225	183	75664681baa4d01a52ae4975f16c2c1fd7a00bb19f30c6f9b3b63b1b52e8dc89	aplicacao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-consumo-demo	sucesso	Responsável: ti@exemplo.com.br.	172.27.0.1	\N	{}	2026-10-19 16:53:51.777527+00
0a9eb08f-5c27-4043-91f2-4aa5649dccdc	184	76f0a5da933864f4f20cb017f9f6bcaab9339dfb85496a15b83d0d67ddf0abb5	aplicacao_credencial_emitida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-consumo-demo	sucesso	demo	172.27.0.1	\N	{}	2026-10-19 16:53:51.840603+00
d59e65ab-82d6-4e26-8beb-7e27cb583afa	185	71ab8fd24fc0fc0d986e2af27cbcdffbe7110895e710d51f45655ec79a58b0bb	aplicacao_autenticada	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	sucesso	Lease de 30 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 16:53:51.884252+00
b4076622-382c-40d5-a9ad-4035f6081ec2	186	5bb043e61e80ba4cf9777cf9762879d0b0f0ff863f5277c2d0126d50cc4ec813	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:51.933599+00
f9804012-6cd9-498a-ab9d-34b0d45ab55c	187	2d17d97e6e3e207670bf14a45e7fa6449a5eb19dd10b3c4aa8fa09e96fda626d	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:51.966421+00
e35f74fa-a5b4-4957-8b06-0a4cff951609	188	e861a65b5a51810337e02069ef7b42f6e1caeb22afc8025c6d257d216ba68c2e	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:51.995301+00
3cac416a-8e9b-416d-97b0-87d0963858c6	189	0e2d642b404087fe10fb139c0debec1fdb6566ace2a3a538341f50db73789c24	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:52.020353+00
6f9efe1e-0723-46a5-96e5-ec9ece50f9ff	190	db52480ff03ee1ba6be2c58ee65e245164d16a6382dcf2b4cddf7ae534e7dc57	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:52.048446+00
0bc26fb1-ff32-4051-a14b-811e965ccf17	191	cf704c7e7e04e44028ffa3f1c7b13d48a46830cf132f63bbd5fe53bfed167670	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/certificado-ecnpj	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:52.075791+00
6ac29503-dff3-47d6-90b1-620e9913025b	192	5c65fd81f2b13020654c8ed54bc3ee4d4d824257c1ffff30206b3195d5566674	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/certificado-ecnpj	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 16:53:52.10294+00
084eba4b-3082-4caf-b7b4-ef028f6cd19e	193	e8ef11145a72fab865e68c253944b3bcceb32d5b95e2dd1919c8285fbaae1a6a	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 16:53:52.123333+00
93ff81bb-3573-4318-be71-3c20d323c759	194	be6170193fc5cacc4cd92e4d44b2b8442f7c4a52b837ff71a4e56ad9e56e8e78	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 16:53:52.14454+00
21a57034-518e-49b0-8ac8-848a75bfda47	195	4012feccdaf2a33e631b5576941e79cab8de55f0af1c2ae2075fafa75e8a537d	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 16:53:52.165213+00
3282ef51-a288-4225-803f-1156d30bdf29	196	c4a1c76c1f79d52cb366f34bfbd13a34374f77af614d7f7d2af5e492daa287ed	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/inexistente/segredos/x	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 16:53:52.214468+00
e60c846e-a896-462c-8aa1-f9666553b2dd	197	c4a70a73e86c7d5b08b75e4d5dc0262841dfcefe9b0a7c79f2570cce34064a05	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:01:03.515887+00
b1044b76-e5ef-425d-85cd-5ed54e36d9cd	198	a79e54377c8541a037868899cf24afa3819f17019752126192a051ba1b8589b9	aplicacao_credencial_emitida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-consumo-demo	sucesso	demo	172.27.0.1	\N	{}	2026-10-19 17:01:03.997986+00
d8681e9c-712a-4bef-a111-c8cc7a9a8106	199	39329fbb9f4648cb59484be9153b77918eedcab65b7a1959e9e7d143b93ec124	aplicacao_autenticada	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	sucesso	Lease de 30 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 17:01:04.05024+00
ff43f2bc-f0b0-4c37-aefe-c604ff5b7981	200	51eee84ad9a2be8bfc3a9aa4526837a74f5e3fc29fd65c7cc126ad3dc3f5659e	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.107679+00
65806aa9-fefb-432a-a352-c2aa321dba5e	201	2790de850db262cf4a9d4d836dfdf5b6f7fa695b89d4d2959288588bdae5f883	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.141779+00
071b426c-5cd6-48bb-a452-b3f98d7e5120	202	bf428b1e6b1160dc4ab5f9c02359514475cf8f70e1c628be1ab517ea3151a953	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.180032+00
b2a4dc96-eee8-4c68-bb07-1b82d0379984	203	95f173d243fa4acf8039269f80a4a94bd5cf744c8249569be477ae312e9243f0	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.220729+00
10aa4a2c-107e-4e71-a3d2-94e2dfffb3fe	204	137d3ca23c78cfcd47e8ad830227b5bdd3803e8b3f6191bcfe1861a081da4344	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/dominio-escrita	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.260135+00
839d7bb0-0731-4cfd-b843-d6b84ff0fb54	205	045a08b93637f14f48829b53f7f00e3501488e808e9da74f338104cb28c01d64	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/certificado-ecnpj	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.301082+00
0d6f809c-3f2d-487b-9a78-c686506f6069	206	24a065fcaf31f4bc3b2737363df330fa565432d39450a3858ad54d649ff5bee7	segredo_revelado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/certificado-ecnpj	sucesso	Leitura por aplicação, via lease.	\N	\N	{}	2026-10-19 17:01:04.332042+00
3f557d66-aa27-4d63-acba-e8fe410613d1	207	a152115c420c1c87ba06ba805c8b176dd530e6a0f067f4f7e7fde3d04d88a118	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 17:01:04.356059+00
30a8ea30-3b46-4042-b98b-26880038805a	208	ade25387313cca08eeab8542c0c2d34e7279f830382e386dca1f6170ec503cdb	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 17:01:04.37912+00
bd8e2d82-537c-4a09-a56a-af6fcd50fa13	209	a803996da99670f47e41df90602ed7c84e67a5d3ae09625280167c8bea411183	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/contabil/segredos/token-sefaz	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 17:01:04.402521+00
d483fa78-2891-42e4-9933-5eb4ea9c6ec7	210	0dbae09c14b32604cf863348103aab0947e0de2af92342a8a34eca767e9b88a9	acesso_negado	\N	maquina:rpa-consumo-demo	cofres/inexistente/segredos/x	falha	Fora do escopo do lease.	\N	\N	{}	2026-10-19 17:01:04.428375+00
4cb42bf5-80fa-470f-953d-24fc71177529	211	4d8d16fd5d0581646bbdb957d31b715d52baa5b94fcb8e52307089d9729fd344	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:10:59.655449+00
455fa3b0-e994-4639-ad65-c7b8bb55efab	212	675aacdd97cbb42d859ccd39b45c4fc461118052e309b65cff14f0dad60ee823	aplicacao_credencial_emitida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aplicacoes/rpa-consumo-demo	sucesso	para-rotacionar	172.27.0.1	\N	{}	2026-10-19 17:10:59.976479+00
4e83a5c9-b2a3-4b25-978d-4d0e4823870f	213	d4b6258cfb319b813817a4c46469095070e8acf3c0ec14a41490279d95780c2f	aplicacao_credencial_rotacionada	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	sucesso	Credencial trocada pelo próprio robô; anterior vale até 19/10 17:21.	\N	\N	{}	2026-10-19 17:11:00.007113+00
acdad96e-50d7-4c96-8461-3299e6e8f1f9	214	b9f3fe0ad1bca837338110488d2dc03bb1392225e7f423b1df46d7c9d96169bc	aplicacao_autenticada	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	sucesso	Lease de 30 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 17:11:00.085463+00
33ec5451-42f8-47c3-88ff-560a0a07da01	215	06fa1d50adaa4e76d543ea74cafca35769212600238ff8a5e8a06b9f078239a6	aplicacao_autenticada	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	sucesso	Lease de 30 min em cofres/contabil, cofres/contabil/*.	\N	\N	{}	2026-10-19 17:11:00.124541+00
4971313a-ad6a-4ded-8e7b-12043af35cb6	216	4f8c5991e41f73eb69d4ff9ac8c8af4bf187c6b4c071771628db8022575b1244	login_falha	\N	maquina:rpa-consumo-demo	aplicacoes/rpa-consumo-demo	falha	secret_id inválido na renovação.	\N	\N	{}	2026-10-19 17:11:00.146442+00
d8797682-72f4-4aea-9de3-316ec0c54e8a	217	dcbdfb6d053511a78be2573431704209ed9490319f9d4794478161bb2e1a4e4a	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.716897+00
b3d649b7-cc9c-4414-aecc-972f08fb2b45	218	d7da80d7eed26a1a30420b68c8cbf599b06152892e72b5137360f1b24d64d4aa	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.873665+00
06c1c448-59e8-4b5a-a9f2-0404c95f73b9	219	d397894c57db6f73ea9f70552e133c4dc6bd2a11ada36d41a7b5a937d067b3a2	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.919962+00
2cc33db1-8583-4a4b-9603-1cbd6669a2cd	220	ca8373fc4f63f977917cb22705c759c3507a231a2b00c81a6899d98b3c23af82	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.951655+00
dbf4856e-9a52-4370-a19f-3a46eeb83c9f	221	f5e855ae2bf5f61d05a978345cd6dbec0b33c822b9875205fa0231fd11cf1cac	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.973479+00
49c32f57-a03b-42fc-9366-750b383467f0	222	4c5c8c7fdf166fc2b8317a67961fc97368d81c3ae854591fb6724db0a51e1b34	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:49.995868+00
c50459b9-7e82-46ab-82f0-e59d473983a9	223	3a8879ab6bd0b3fb2a4fd209dc302577e234729b1d7d78fad58216e3a38e6d6e	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.045139+00
9cc2dd87-174c-4fa8-84ee-69b8a8549fd3	224	7990d0b8b948d5c9683b2ac476bb4f20c31bdd0d8929ac3ceffff555bc359776	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.176157+00
d845361d-91bb-495a-bd59-71950cd958d9	225	c1254e544a7d015a2372c52355cdd3ab57c8ac19f09043e55302d660b67e9a94	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.257276+00
317c8c2d-1c40-490f-942e-9679407c583c	226	66748d3fbfbd71a7bddc064bd3f8f92882914fcee9bc5fb8e6c1f8c0ccfd20b1	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.312159+00
737db2a4-4938-470a-8543-a3f85c0c97ba	227	49c6dee2bbff7aa3d4fc12082e9b20c910fd1f1bfe47499baa907867e86ec403	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.336194+00
62a71077-a64c-46ea-a790-590610ad679d	228	23310369749f7804cd81c41dc729cd0a1aac698b3eb3497e90bc12a323f5fba7	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:50.532071+00
e4cd7896-e61d-4baf-a85c-a940a36c29ff	229	bfaf82f99fa04674e78153ce09b9ab3dd54a875a2cb9a344a0c09ce5f971a332	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:51.729349+00
29f65758-60d6-4e09-a784-4d0106e3db34	230	fc5d6b0b15ae8a10e045b93b95b74fd86db5317d1de06fbffe9de52fc5514fcc	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:51.813564+00
2fd23baa-e4ae-402f-aef0-c015554844e4	231	0a2a4c5d582eda59d76f5d8089cc22f9e8ea9ae33ce4cce32a405a288734d916	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:11:51.986508+00
ae469cbe-f47a-4f78-a79a-f35af9411ce7	232	1fc538dcb15f4dd5e9711a45d7025b666a4a25ea6e60c5ce99d5422fc7846948	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:32:23.09768+00
406dc8a9-ac9c-4e76-9cfa-445c0abb605e	233	36280044c7871170c3b650bcba11436a84e3cf493eb7e05f13e9befade430a10	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:32:23.224378+00
caa61782-ad56-45da-884b-daa631187261	234	dc5068f45a88aa43e2252071ba39d4b226add1dbaee72a25d91347014e34b7fe	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	configuracao	falha	Sem permissão para alterar a configuração.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:32:23.563387+00
42a84458-9dfd-4f8f-993f-0aa791f2fc89	235	d07b2631049c64f28ba51e06d32f9dcad776f08519640644904ee73f3a3d2f61	configuracao_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	configuracao	sucesso	alerta de certificado: 30 -> 120	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:32:23.705774+00
dd3ca8f4-a6d2-4f06-9530-62f21c548107	236	6e107fa9243d90e9b5c6b3db19d5ade579a4021a61479215c15756b12f8e575f	configuracao_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	configuracao	sucesso	alerta de certificado: 120 -> 30	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:32:23.837675+00
d90cd93d-b688-4f3a-ad75-7271f9b7bad3	237	efd5d65580809c4e3574178f6669a035d5e33157bb4308f6f62369b71aeaf5dd	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:24.820661+00
9cba432b-65ec-48df-8595-10255617a5f2	238	96809bc9725c36701feb42665a2e05bbf2c660bc09db04daae539e739636e774	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:24.957006+00
e2f9916d-18aa-4300-ae01-96e6dbaacbf5	239	b9d4416062c72d265fbb501c510af67029479147052476b1cf4628bac08d1ed6	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.010805+00
9c214a9e-b73e-4df6-8f3b-5210a9143e9a	240	9b62d059c90790058b7145a734f9a3056de7d1f52696a86cce37b30e3281a2b3	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.039546+00
05eda4ac-93a8-4a50-a377-5b8c98956a25	241	88ce01d8acbebf67c38975bb3dcd7d95ccbfc91176b8a5686802939bc52e1a74	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.060729+00
320c0696-c792-418b-b4a4-bf493a38df96	242	61e29bfb900f44e2515f6889d34d05141222994a9b56614dc34dcd39abf4e1b6	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.093876+00
ac83f0c0-aad6-43f5-8158-b29093290dd2	243	9b873f45548a2470a8f4813fe8eeab21c400ef34841316597853b959bf1b7202	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.14339+00
defea7b0-8add-4536-8f5a-75c6f41fcc1c	244	27bf65777ab27b7168f4efb2db915556866a30cfb2035ab580912cffae79acb5	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.233063+00
26645fcd-35b5-4d6c-a393-270395f8f24a	245	bfed35d1b8a360ee822dc8dab48d34123748d2ace5fd39da22464907f002e1b5	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.259376+00
66aa3b94-e7b3-4ae6-b4bb-6ab7e3f675c8	246	7114b096db86ff82ed7b8f8344b09a4211c4bbbf365b1ae62c0658d512edad61	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.284328+00
58ac49db-4ee1-4b19-bb0f-42f598613aa3	247	127439c0b8c3da4e62a0f3ba0a7836d23496bf50ec14a51b3db637ec15bbb0b6	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.331395+00
225fe704-d5f4-42f7-9a0a-baf96fd3691a	248	8d6a09e146deb903342cd67815a1010d955b75698a9af66c88e9fe29b48724c4	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:25.464813+00
e201e29e-5075-4d24-9e5f-73de30662838	249	ab70c35271d91b95c4c21f88bc9205fecea9991c1661c287b61a94d94e9e830a	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:26.357814+00
21c5f81a-cb5a-4411-9601-db4d2235309b	250	2899f57a8f30e8b0678b9d4ec6b4a255f2aa5f89f991dd84046ca09b1bbdad6d	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:26.439736+00
ab056205-42d2-477f-8a14-7994bcc628d8	251	79b2b672d860641dc035ce7fcca0e012aa407a78dbd7727830fd14f9751ba7e3	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 17:33:26.584935+00
4b4a06f7-e425-47e7-bea7-2e29a5b6f523	252	418f4d0ca129d184c5f546663fa3b6a4d4861048f1f367622f85bd633787a22d	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 17:33:51.274541+00
666017fe-5197-45e9-bf59-b66334bdf740	253	80456a00983eaa6afe22257204502f512a31e386ec3b66948499a565ab162d0b	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:34:14.822961+00
6a612511-9790-4ee2-a867-9fe2b3978d0c	254	ffb00268105bef63b7f9df0a8d48206af9f3854b46f041f888bf527c46560dee	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:34:14.963439+00
62a2803c-eab0-49a8-a4dc-ce5db4b42ee9	255	79f46c98e1622d5359afacc95db2ca8c4779b99c558ee1cbbda6c37df9187381	sessao_aberta	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	sessoes/b876623d-7642-4858-bcbc-01d21d69bc07	sucesso	banco_de_dados em pg-contabil. Conferencia do fechamento	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:34:14.999914+00
346c472e-b57e-4a2c-a360-02d0c080b556	256	606e5d14ac92c161be63ce0541218ac4990d87c321c33ebb349c6a88f1818bbf	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/b876623d-7642-4858-bcbc-01d21d69bc07	falha	Sem permissão para ver sessão alheia.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:34:15.337706+00
6b965253-0946-4d81-abf2-388bf237a17b	257	2ec88fc3a2c3dc31a498af1df62148bd0729197d9deb4c7b62da2ff687cf5d8e	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:36:16.675904+00
8d2aef0e-4c54-4dc8-9035-b222f93dea45	258	f5e4d6c68b13672c243703e22354711b48acca1e2f516bc8dbfc08a425e4f8c9	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:36:16.859305+00
d06001b0-5855-4d82-9db8-a3de98703e09	259	f43613d217fedf76346b0cc5f4afcd204721693033ea40dfec08d6a5068c06b3	sessao_aberta	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	sessoes/c223d5bf-8f13-4562-801d-9b9202ecd0e7	sucesso	banco_de_dados em pg-contabil. Conferencia do fechamento	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:36:16.901197+00
60acc6b4-cfa0-41c7-9ac5-c81570e43f2f	260	9cd8e27e27bdca3735da00472c1c92acf2f89b8d2a04d82cfc16e5900ffa4a6d	sessao_encerrada	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	sessoes/c223d5bf-8f13-4562-801d-9b9202ecd0e7	sucesso	5 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:36:17.312406+00
9b6fee64-5eb0-436f-a692-66be1048c29c	261	ec3a59cb24e255be3c0f01ca6c70e1cf243d70d94f39425ac65d6b1f817727a2	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/c223d5bf-8f13-4562-801d-9b9202ecd0e7	falha	Sem permissão para ver sessão alheia.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:36:17.490619+00
da8d3b91-1678-48fb-9406-37705461af89	262	b9e93a685e43cc3dbc1890b69a9fca5f1ec439bda80f55123f4fa907cc50b61d	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:37:09.19586+00
8ba09245-c765-4996-8074-072b646f920f	263	e728ed03cd8671086b8a3489c82df974abb2d4fed71c6152b7b10dcf2bda12ca	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:37:09.338833+00
9aa6e655-bcbf-44c4-8c90-336e904138fd	264	147e967e70e6c7d0d6bea3167a36c7bf26a792eb4ebace0f3b991ebce1bfe4e8	sessao_aberta	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	banco_de_dados em pg-contabil. Conferencia do fechamento	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:37:09.391419+00
66893fd3-ad76-4100-bdde-2eeefd5d4097	265	eaefe56d48c4177b7edf95daeb298de949e0f2caf5fef1eac9210ee5c772e413	sessao_encerrada	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	5 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:37:09.758363+00
33122ee8-0339-46de-846f-bcf14287f798	266	988649b173c3f5e5cd16d034ef99a1c88dfdf77a4ecf94b350f0afb1e1508825	sessao_reproduzida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:37:09.883496+00
2c499109-0aab-428c-bfd1-a6cc962c556a	267	60a4e36399f343d465a7b0c7c80e37bd40b333e9ac70808ecc329c9d274254df	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.510574+00
ed043fd1-a3e2-4fb1-8931-928c6daabae9	268	7ed8c9bb877a1a8464b268898d96e488a7d3ed0a6eecb7f61c56576e45e0283f	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.681046+00
88e53a75-20af-474b-a894-df92730e8cec	269	bb5658a0548c74bdea09445115c333a1711ef7b187d48123d70f4d86d6c38985	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar usuários.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.716714+00
4dbc79f1-a998-451b-b115-812371e872dc	270	275af3dcd05e530eab7bb3cc16b7424762be6f2278314478156c33a224beadaa	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar políticas.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.747589+00
e203abc6-5f65-4f7c-a1b7-d9ad5623cf68	271	9dd3f14920ad0c23438ee70e622c79d33b8be9cf54e2c9baa77a73bfba8c215b	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: listar papéis.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.77797+00
e8abd3c8-705d-4b02-b8ab-a94da62aaa35	272	6296436bb4fa1745739b1450178a825aa3d3ddaa671c15e21e8dc4d1295a35e5	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.809532+00
dce91f27-48e5-4b08-bf5a-ccfec42a6997	273	6bdb4edc294790e6f961d43daa8c89154066397d1fed10d4d7ecf473c2a4e5c5	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	admin	falha	Sem permissão de administração: alterar política.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.837381+00
53acd406-fa7d-41e6-8a7e-33d59f0116c3	274	d58d25ae2b1966923fb7172d8a2d3050f2c220a8065308a6e86cbbaa8432d8e8	acesso_solicitado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	4h para reveal. Motivo: Tentativa de furar o deny	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.907949+00
d4d5ce64-b035-4f8f-b874-b262995a169c	275	bb5fc325ff511772e0c0b91818bc480f45ae9e569f3156170f53db80d9bdff22	acesso_aprovado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/token-sefaz	sucesso	Concedido a contador@exemplo.com.br por 4h. aprovado	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.944732+00
8cc88fe8-a579-4067-9399-20ed1fd1eb38	276	49f118037e8063eca9fa6ffba4c1a4ee9828d00f6eab5ddd093ab46e47a11a23	acesso_negado	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	falha	Negado pela política contabil-leitura em cofres/contabil/segredos/token-sefaz. Uma negação explícita não é contornada por concessão temporária.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.97469+00
bfef11ea-86f7-485a-9792-904bdc14911d	277	bf6a0cd18af3540e9973ace0b2ff8f69b070e8c725ed074927632d1d1af7bc9f	acesso_solicitado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	sucesso	1h para reveal. Motivo: Pedido do proprio admin	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:43.999378+00
876a0fb8-a316-416b-a9fc-6c0f6e64a30b	278	f502bb93c0ff3a9202206686e375ac50819fe85e6da672d52129cbb695955e6b	credencial_retirada_negada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-postgres	falha	A credencial está com ana.souza@exemplo.com.br até 19/10/2026 20:32.	172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:44.156821+00
248bbaa7-0cbb-4708-b4e7-81644d92763d	279	b5cfd6ebc64cd53bc73a6e6010059a5815613a7aedf931f60f33ccf1f8c3e42d	usuario_desativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:44.967193+00
25804cdd-fc01-4505-9fda-9d44d2e033f4	280	bb3f11144c5ae27ae299f0118fd5b7adad637c54ec87b13554cb05112a19c50b	usuario_ativado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	usuarios/contador@exemplo.com.br	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:45.033395+00
b1ad8804-a297-472a-bd3e-c11185d475d2	281	6a8cc8e21ba4e973225270c28a233b19cd0c91de76ea58643d08d455a4fde1a1	login_sucesso	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-19 18:39:45.176978+00
6881c969-1bee-4453-b8ae-2f37f3d51ef4	282	43e5cd38b4c21a60c930eea7bbf48dd6f99aa0d734156d6647ad310dc7efaede	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 18:40:06.144658+00
053560f1-b911-4f6b-aecc-30c88f0c72c2	283	df6bc77f452136a3d507824d71216be8675d8351ca5c71bb8331d17b39fcabb5	sessao_reproduzida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 18:40:24.941111+00
caf83908-4acd-4cdd-923d-06313e640769	284	5d8751fe98bc4107fc6fa80fbcb0ca381a9670bf5211267d8b70de5d7a9bab43	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-19 21:23:26.967105+00
6b08bde3-d2eb-476c-8c29-d2e3459a6931	285	25198ebd65eb53bfcd4db3dca0aa89920612d65a14bbe3cdd6da57822fb19a14	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:45:50.156583+00
28ec6157-4345-44b6-9c9c-967a02f1f635	286	c64d19a3a2745ef3f68cc8fec207eea251cd458c6e8fc2ad1d941c47c13352b4	acesso_negado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	falha	Sem permissão para cadastrar esta chave.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:45:50.221015+00
f5b8df3e-daac-408a-b25a-fae699027664	287	3107d822a5c0654d7d6b5a75d4f6f5c6c4be4325db6a3d485cd97f78f27f2759	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 13:47:07.257275+00
78cb035c-cbbb-4daa-91da-6c68982387f3	288	f797040cea9ffb3bd07042f019c1204c80e130ae93924645743a716dad6ca701	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.661525+00
c9a4915c-428c-4618-97cb-920dfed9d0b6	289	b9a18f8ae81dddcb0d66dd040e0239162ea324e2cc992d1513ace61583ba0961	chave_api_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao). Responsável: fiscal@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.716505+00
8ceecd19-8ea8-4c81-a547-32c475c80225	290	cb035b043d917047f034b36569b8dc25d90a8155d06e53e2c02a8aeaefab6cdf	chave_api_revogada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao).	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.764031+00
aaee2476-13ed-4990-8ae4-10059a02753f	291	13dc22889650af4ff1b4811764cc59bc381b720ab58f066c52df73878e135c17	dispositivo_cadastrado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.811793+00
4fced388-d4f9-4bb7-8575-dccccf4b51eb	292	0a4a76171997efa7a25e7b4afe2cf3cd50ce0efdee5023e61fb3669d6b879f04	dispositivo_acessos_alterados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Métodos: rdp, anydesk, google_remote.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.836771+00
cdc45e34-21c5-4d50-a6cf-3357c20556f4	293	db577605462a8be8f63ae9a608f4205dfe69168637a91e5d7a0808f9502bf4b7	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Arquivo .rdp gerado para 10.9.9.9.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.856384+00
4954ac53-43e0-403b-8106-5aab8e175af9	294	09224e51603bf8469777a61af009ccac5c0d746acf3351159a0ce98717e88da3	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Acesso por anydesk iniciado pelo usuário.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.873797+00
4c3e228f-793b-4ff7-b06b-70fdf11baabf	295	60886e574a0afbee69fafda87bc1f31d4762f6fe00562b50804044b2c8ddca3a	credencial_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/val-root	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.911318+00
bdeb45b4-4e63-484e-be1a-764bfbc72426	296	bc8a50e48d97c7b7006c516c98c98ed5b76601e1ae15c1a9c95a52feb52a6435	credencial_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/val-root	sucesso	Governo exportado (sem o valor).	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:09.958722+00
49ae5dbc-c03f-4bf8-b6d8-3918bfc50d3f	297	c4fb97739afcbaf53a8acb3a5f5746e58c457fc5b84f3cc741b394cef29c35fc	chave_api_excluida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao). O segredo no cofre não foi apagado.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:10.006493+00
1681b783-09f5-4901-b81f-975cd5e097f6	298	76d05710ce29b014fa84ef38c2bdc5f0596cbf892b7685ef148ea7a866a48d06	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:40.604852+00
4444486e-747c-41d4-a895-d1bd474113a5	299	272510851f4e3bb1f87570eada9a08d0053590f22cdb59c41216a21e491c4709	chave_api_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao). Responsável: fiscal@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:40.679928+00
8a985294-98ab-484f-bf99-2d800e33873d	300	df9e46e4f20f0808d3972d1e5f5c12416d867105dfbe8805a5a3dc9efe498cc8	chave_api_revogada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao).	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:40.778783+00
ce9a2a68-d1dc-473f-8f85-68f306bd3225	301	983d3dc28764368171dc73cea2888ee2e6cac1327cbf6cbe67d9c99020051394	dispositivo_acessos_alterados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Métodos: rdp, anydesk, google_remote.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:40.921512+00
1cda627b-1696-402b-8e7a-c8e49c4449af	302	96b116fe13245ccbcbc63c96a4273789ab0027b1f15478f30029432eb50b8de4	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Arquivo .rdp gerado para 10.9.9.9.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:40.971029+00
bb3c887f-58cc-4edf-aa22-7bcb968758b4	303	4ab6d30a510a6b901551207773825bf2cdb35fe24838005cc124b89c24066f06	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Acesso por anydesk iniciado pelo usuário.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:41.013846+00
0f3fefb9-bdd7-4142-83ae-a5696d82eaac	304	811668ee5976ef40dccdd394712c66213f8d0483458ab20780e5881273eef56d	credencial_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/val-root	sucesso	Governo exportado (sem o valor).	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:41.170827+00
206fd042-e175-4a77-bbd9-74ce9a82d361	305	431851c58cd4aca03a2c322a9aec8848b3217ea05efc4981e1bdea3c9c9636c9	chave_api_excluida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/val-sefaz	sucesso	SEFAZ (homologacao). O segredo no cofre não foi apagado.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 13:53:41.249305+00
72eafc25-5b74-4f71-901e-edb43ae5bd2b	306	e9e1404cf72b6531f484b8d39232f036e48d838da3a3a103e6705c2993ef8f53	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 13:54:28.992418+00
2f9c0bc9-09a1-4e07-91bc-81f4b43f68b5	307	496ded7ca33638861fb1e0c52ccc3d57ac9422ced43dffa7e151e70ca8c6a894	chave_api_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/sefaz-nf-e-producao	sucesso	SEFAZ (producao). Responsável: fiscal@exemplo.com.br.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 13:56:00.869326+00
2eab4274-6288-4e17-bae3-bc4cc4dfce92	308	91ddef4c8cd569987a0375ef0e940cc4d42faff55134a227160604dd8b68ae48	chave_api_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/sefaz-nf-e-producao	sucesso	Campos alterados: ambiente, display_name, escopo, formato, nome_do_campo, responsavel, secret_name, servico, usada_em, vault_name.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 13:56:57.059386+00
b1ea2b5c-83bc-45b4-b2f9-835913355482	309	0760d8e3b892bdac9a758eb8428da7afecc09ca0de0c21ef97cb0b88f2c15aa4	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:00:16.551469+00
78cbd66d-6ea6-424e-bd8a-db875b96468a	310	6c77b03d181c2de1cdc847ae91e07432750beec41deedb8a06a5ab43280acb6b	chave_api_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	chaves-api/sefaz-nf-e-producao	sucesso	Campos alterados: ambiente, display_name, escopo, expira_em, formato, nome_do_campo, responsavel, secret_name, servico, usada_em, vault_name.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:00:40.753095+00
694c9671-8c17-49f7-b50b-7468bd57da35	311	5cc11c879ea289b089baa3c23702c7d6712bb6ea6fb1694fe47585c132317f53	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:01:15.642251+00
81eb064e-4c85-46d6-9d22-e6d1e2615b87	312	c17f344cf5db631b8903ee54dd269ae733acd46ac0bd90401ad038846a80ebf0	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Arquivo .rdp gerado para 10.9.9.9.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:01:43.315713+00
09eb0185-8405-484a-beda-4da8da836a14	313	98c6f8f0a9d9674b7e482206f94082e1761c0e45e90280111ad2b9baf1fcca51	certificado_exportado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	certificados/ecnpj-matriz	sucesso	Metadados exportados (sem chave privada).	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:02:51.647265+00
b0fab5e3-c1d5-4098-baac-d64885d7bd5a	314	3c2f84b917c4e5d06e85df7cc6e1c9ea15ffb61e7eae6f6b6e1b74b7958a0158	credencial_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/replicador	sucesso	Governo exportado (sem o valor).	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:03:07.297911+00
50a82c38-ffd2-41a1-ae88-45454e513c8c	315	ac0eab4ae117d24bf1c582681c35b88b27002946691b6af64b1f2a3b63ffe3e1	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:25:08.312362+00
41be0ab5-b501-42b9-94cf-dfafaac842a1	316	09a83caa171ec814a041365a25bf240f58c82ac62216c9e5322ab10bab91f5d8	sessao_aberta	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/2a9418b6-ff5e-403f-9eb8-ca1f70f669ef	sucesso	ssh em srv-validacao-67. Validacao	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:25:08.352638+00
2a81b245-ecfc-467e-afe5-d369a0e570ab	317	5f47793a2e8a79dc47bf88de0fd981c6ff8f9ebd83a0474ccc3a0e84581aecfa	sessao_encerrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/2a9418b6-ff5e-403f-9eb8-ca1f70f669ef	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:25:08.421157+00
78ebdafb-9bdc-4ca6-8a36-f564683447c1	318	f0ae51438c978fa42d898115cf12f5e76484b867296f8fc21e4fecef6f2b5cb4	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.444616+00
7085e145-dc4b-4442-9640-99100d658bc0	319	b51b2f5bf29e200c25357b5bd2308c88ef5ed0da2360420b95a73de659e75cd9	integracao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-validacao	sucesso	Destino SIEM de validacao. Eventos: segredo.*.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.513823+00
19271b7d-64e0-4fc1-96fe-b075ce559ed3	320	a42de288fa9fb1b4b7d60cb3a40e3485506cb75670b35a20456d9c5c56b64713	integracao_testada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-validacao	sucesso	Teste via ensaio: 1 entregue(s), 0 falha(s).	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.600299+00
8aeed2b0-3102-4796-838d-60dfcf0f1986	321	e97ee84f477563745fd89bbd0c676e150517ced7dcbaefe0c3e29a033f46bfc0	integracao_segredo_rotacionado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-validacao	sucesso	Segredo de assinatura rotacionado. O valor anterior deixou de valer imediatamente.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.655632+00
9b694f76-7ab9-4a1c-b3a9-0fc6e55f16cc	322	fb3c062b4f000dfe0dffa1bceca317721b0275600e2b3d7c095299a91896a276	integracao_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-validacao	sucesso	Destino pausado.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.680522+00
bcacdc6b-fd6b-49fa-b3d2-1c5fbd204fd0	323	a5a0fe5046b65f869e2028fe12b58e734b520d0e6a188f370449ab79bc786adb	integracao_excluida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-validacao	sucesso	Destino SIEM de validacao removido com sua fila.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:43:30.770429+00
375f0ea1-72d0-44ce-b010-03ee57770730	324	37a2a054baffb5d00f0d901de921447227158bdb42c145083a8408d72e7ba8ba	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:44:10.281783+00
4fe69445-474e-441a-b861-597231b335c0	325	205f05887048f9369829eede41ddf4ccb51a38abbfef7c26814832c5b4f74324	integracao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-corporativo	sucesso	Destino SIEM corporativo. Eventos: certificado.*, segredo.*.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:44:55.138502+00
1539bb06-a361-43c7-8cfd-66c5922c70f6	326	7bbffb0cdbe050d202bb630c9bdf0c4572daa55b9b0d257617d3b9e2089e6ad7	integracao_testada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-corporativo	sucesso	Teste via ensaio: 1 entregue(s), 0 falha(s).	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:45:07.742521+00
b3f164fd-c94e-499d-9d82-d24768a5631a	327	8359ff304a49ef0c4f82ec526ea5f4306d8b22575a440a4b32cd0220d922c56b	integracao_excluida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/siem-corporativo	sucesso	Destino SIEM corporativo removido com sua fila.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 14:45:30.110172+00
514adae1-6af1-40cc-9286-e4a866ed9d98	328	b0696d9a2c240b6940e452b90ea27eabb334b79fc9bd48b48af4b2a46db7896e	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.029132+00
a92a8b44-e780-4a31-a67a-a5c041d56b8b	329	2f60769b64487153b3dc390bc0042c3af1dea5704b1ba184acd41575b629b129	integracao_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/ciclo-real	sucesso	Destino Ciclo real. Eventos: segredo.*.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.125236+00
9395bd77-fb23-4200-9ccd-3923475089cc	330	c63f95234e40620a1462164055954a781e666e9383a0524b66b67b9805ccb835	cofre_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/ciclo	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.180914+00
2f54d0de-8475-4282-8419-78e29c6e5bdc	331	77094aca24120c1063e5b1a7218a907884c33f4c9fc54ffba81cbc3c3a910756	segredo_criado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/ciclo/segredos/senha-root	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.270345+00
f0f1ac0c-21c2-4838-ad0b-a1b0e0a8cd59	332	adc52e55d9183353a721674671eaeb642b38b5f72cb32498b617c6403415378f	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/ciclo/segredos/senha-root	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.311633+00
c88a6742-c3b9-4d1a-99ad-b27e49a916fb	333	8bcca5fdb84b818aa182c6544354957b885422090feb85c70a90273a36600042	integracao_excluida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	integracoes/ciclo-real	sucesso	Destino Ciclo real removido com sua fila.	172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.452003+00
ee95fd77-fc7e-4f7c-9acb-061d65354511	334	9d3027940c055da57e4ed5ff05f3aa1dabc5404282601c9c271615ec6db9a742	segredo_excluido	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/ciclo/segredos/senha-root	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 14:53:45.49454+00
df8d576a-b48f-4799-8d90-9e2e2e8c1379	335	3d669a620b00ad59d00cad9ffef0999bac6aa32379ddb4b900e36b71d26cbc93	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 18:01:33.757046+00
1e4bb9dd-79ca-4ed9-b56d-96dfbb11100e	336	32b7809f417d68d9bed2421cea69d85dee68ea69a566ffbdef689c6a7b9b4574	acesso_remoto_iniciado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/val-srv	sucesso	Arquivo .rdp gerado para 10.9.9.9.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 18:03:43.566056+00
1cc3e03f-7c1c-4e89-90b9-89e1ca5cb8e8	337	f945c002eaf34ab081dc9cdcc0e8e5751e017b2c4078073b27073d5a0a21c1d8	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-20 18:45:59.103553+00
ae9b2d2d-a25a-4850-a095-07da2a0ab2a5	338	52aeea6959dbc2f6e10ac7bb23406433b18dab2f41f999f557a8f1098d618c94	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 18:46:31.560009+00
272b3435-6d9c-476a-ae48-5d7fa569b7d0	339	ea3c74eb2dce1ed445978fca559f781da70a015c0b02f1bdc2ef03081208d997	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 18:51:22.082515+00
ef8d87a5-a5ac-40c9-8f0d-d1b65252b308	340	fe0fa2fda408cd956264b603d762c2f1f6bd7cfcbcb634585a682a6f5af72d52	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 18:51:53.546015+00
e5d359b0-da7c-4f27-9103-cd7923b208c8	341	2970d179b0177d35d12448d2f2880fe1c2fdda2de32bee74c25f00a2a23f9c77	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 19:03:43.615812+00
a5970e64-3e99-4b7d-872e-36f951b13a33	342	25ebe66afb9353b850aa8336de927d604fdbe31868386c9109fb9e07ec0b7ca9	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 19:27:45.08342+00
5e871528-8c0f-4b3a-b949-c24f8ae9dc89	343	ac9bf5284e2f3cde871bf82317ff886800143c80abc6e2eba28d4f88e99ca5b9	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 19:33:06.379991+00
b70fc739-0fcd-41e5-94b0-cd2985d4aa47	344	5960e75a82752a38756f43e1c34cde9e3ffb66a17449d75120d391d565b5553d	configuracao_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	configuracao	sucesso	quem vê os rankings: admin -> approve	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 19:36:14.940879+00
b80d49cf-0acd-4358-85a3-358b9c6df8c1	345	f8dfbb21e6bbfae8cd51910ea8d858a91f76c0c3b509668b3b23df3a8edb0377	configuracao_alterada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	configuracao	sucesso	quem vê os rankings: approve -> admin	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 19:36:35.551138+00
b9ff5d58-c56c-4f7d-83eb-a13a7898e7d4	346	e185aea8d5dffad4fcfb1c70307efd048104cd6617a9fdf2c1a0d099df559d25	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 20:37:10.446783+00
4a82b40c-5466-490a-9c4f-8cc0891c78b0	347	f818b5ebda7afd45b9a428a209afe0effbad1b1a7b25752e6f47a9c87f5db47e	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 20:48:09.632035+00
dcb2ce95-c80a-4c88-8350-2d7e4d6f2ffc	348	1bd22bfd5fb14741e796baae8fa1b9322cff2a97615c219b2db0fa9bbc7ce9e0	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 20:50:30.457281+00
6c8bffd8-91c0-4b25-8458-da2f6c2158cc	349	fc74770bc48e1da1f08f8d96a2a3ca9e437af7a1f2a03b400ced83b4d6ada01c	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-20 20:52:40.557228+00
d69dbfa7-65f9-4605-adb1-412213aaa673	350	c397cb8247725bd7adefb9e0d0000d12ef849b869c1b7f6005b8c786900b11b4	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 11:25:21.306478+00
a9eede47-74d0-423a-8e74-d5432d26822f	351	696ea1d94ee5841d9aabefbe83aa08b5b4e5ac511905085f4233668322de543b	sessao_reproduzida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/b876623d-7642-4858-bcbc-01d21d69bc07	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 11:40:58.432896+00
4ffea724-e000-41ea-b7c1-7b9525320771	352	88b4ccd3e22a2449c8d9da7040f4faa0ef7264ef37e4f7823fb2de97cd5c6319	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 11:53:28.904382+00
b5a510fa-41a3-407e-aaf1-e687e56cd1be	353	845c09064e234313fc64c861ac60e84c3f5b365584dc3fe3930de54f1448d75a	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 12:34:25.432214+00
7fb3fd86-19e0-4101-9b82-e2b349312f0e	354	ab15623d8986727c26b2469d330ec0b43debbd065fad8b39cd6d75367b9d1783	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:05:42.824649+00
1329f082-1472-4050-afdd-d5057747d4cb	355	057b7c906923207d43bbac4338f7399d7ae20a2fe095bd76892d30419f7f177e	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:06:21.161613+00
ae51ab5d-2037-4010-b07f-2f62947f9522	356	2b1bb3ea4c89aeaedffe91c86350993204b47b8e382d0d3259a37413698981df	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:13:02.974931+00
753d41b7-79d4-4898-8d3b-84d03fe70595	357	06dc5f6bf02705c8ddc6693ab062b75caa05280cc07eb597570953e5f1ec4fca	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:18:00.984619+00
d708f038-22de-4026-8a69-ccb121ff071a	358	b8c191102fdb3d1881fb7bf4142988cd84ce37707454931b0e881e35e9754cbd	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:45:37.312786+00
68e95e6b-9532-439e-904f-09cb06b3ce20	359	6fb0397f4914651e398fe6ae4b70750916735081807fe46d63a4bd4eea9caccd	sessao_reproduzida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 14:47:30.889988+00
6c442a17-2c9c-43a6-b34f-b5f6dcebe3da	360	71f035a2bc31674d933eb39d612740ec60540f4de05df7ff9e63bd40e1cb9d64	sessao_reproduzida	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/c223d5bf-8f13-4562-801d-9b9202ecd0e7	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 15:00:10.93195+00
eb3e5ac5-a92d-4ba4-a3cd-b2e33ef0e09b	361	931430151a44fcdd4fe020b4ba73f1d79149974009871e74e753a6b271d312c6	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/contabil/segredos/certificado-ecnpj	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 15:12:04.951783+00
ea66f569-79ad-47df-b485-321c1813c126	362	281b7be3db44a747e9598a66c60aa3add96698c9caa5edc4641664f81d6a0287	credencial_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/replicador	sucesso	Governo exportado (sem o valor).	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 15:12:41.714181+00
0eb24737-cfe5-4524-94ef-6bcd1105105f	363	29310b59f7e365662dd4ac1fafa80bb934b6897be4e2b677059d1fba42af81d3	credencial_exportada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-admin	sucesso	Governo exportado (sem o valor).	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 15:13:46.743019+00
790bcc01-fe33-40cb-b7c7-7a6ce0d96f34	364	51c91fbb58a9eb06ffdebed72d048b0eb8964dd1e28064c6416b3f7238795e71	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 17:35:45.311712+00
5ba704d9-24c4-4249-86cc-c2adcdd4cca4	365	25a7f6b39cf1692fa02cf60007a2c9d7d976d94f4a41d44072e543b9386c3d46	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.239311+00
0a5b2273-e066-4cc2-b064-bc22d469cb50	366	64a0408fc1fb0995b5de918eebd46e7fd21448722d3711c2d29a5a5d75f31699	dispositivo_cadastrado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-ssh-demo	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.28279+00
45356a61-14b1-4fdd-a077-46ecdadb58ee	367	dfe1b47754af043fbf0f5e2c9326ed147401e92154cccafd04c6190ec19526dc	dispositivo_acessos_alterados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-ssh-demo	sucesso	Métodos: ssh.	172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.323087+00
2ba135c4-9325-4151-85bd-0e8fd98418dc	368	e62844ace5e41b278da4dbbf8243b01c22da6aa6ae58d4f596506c653af23e5c	credencial_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-demo	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.477717+00
8d6bd6b6-7726-41da-a2af-98ba5d48f088	369	1769fc55c5565f37b1e2c12a477e96e10ac80da577b7e666744cdd88f0a75dae	sessao_aberta	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/fbd5c841-239c-40a0-9196-196ba254a189	sucesso	ssh em srv-ssh-demo: incidente. ticket #4417	172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.558679+00
47545e5b-e096-4f51-a1d2-336836784a1d	370	3226ec19d901fc92ccb1bfb4ea44542e2ea86c89bfcdabfc6eb5a0c077cebdae	sessao_encerrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/fbd5c841-239c-40a0-9196-196ba254a189	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-21 17:36:54.597784+00
50fa957d-2e5c-48c0-b019-60af9ce0db62	371	3607ba329ca4a4fc81bf84ca3c3bb963fbab156e0172a11e4130425e303a6156	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 17:56:54.298575+00
1a3a6bd2-6d03-4270-b7f1-71d42eca2830	372	c8e9b041fe183337710b7b83eb99d314910d2840b6678b8e4c09269d7ea3647a	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:32.83837+00
732e1217-a45f-4b6a-a4c2-cec67b5ab37d	373	18bccdff9ba32f1c44441f8652e764a76b00cc2f89825d24521573e2f0423486	dispositivo_cadastrado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-db-prod	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:32.908504+00
1d32456c-8498-424a-9b6a-59ad58eb9d7a	374	2131376e4c11726845828e1002a5db0e9a549a6aee7f29856b05f3c0bb6e4dcc	dispositivo_acessos_alterados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-db-prod	sucesso	Métodos: ssh.	172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:32.963558+00
3b93dd0d-b0f9-4cd8-a496-56805f6e11a2	375	70bfbf258b4cb41650425b79a45cc6be0b77738942add1936315945429fcbc62	credencial_cadastrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	credenciais/senha-root-db	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:33.003149+00
37fb268b-58fa-40c1-b69b-50fa08e00458	376	c6f317e7f773395a3808934712003091751ce1fbab735a51be727376591f090f	dispositivo_cadastrado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-web-01	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:33.044066+00
76da4405-165b-4473-8271-04ffa0c34936	377	18cb02a1a2fa43a9352d4c644f3ceafe54eee482f44fb4d9008a0f3d33bac171	dispositivo_acessos_alterados	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	dispositivos/srv-web-01	sucesso	Métodos: ssh.	172.27.0.1	Python-urllib/3.12	{}	2026-10-21 18:47:33.090669+00
13772738-985d-4365-8e52-a41122be6d04	378	45687383df283b6c9677ebd563c0d8f83f91646ba65f4fd9e30e5d6951466676	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 18:53:51.7609+00
d1757550-ac27-4386-abcc-1ba8e5c56012	379	e752572c869d8e748daa7199a8ddf1e43bcff6a0a33821ef785ddc37f2d08b75	sessao_aberta	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/3fc45e39-75ad-4ad3-bd06-ef6b31dcb886	sucesso	ssh em srv-db-prod: incidente. ticket #4417 - lentidao no banco	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 18:54:39.759937+00
3d6c810b-24dc-41a5-8e5e-bfee3a28d558	380	51e82a1396841aa1feaa4d3c1613878748a112d1edceab7717ceb042816ed60f	sessao_encerrada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	sessoes/3fc45e39-75ad-4ad3-bd06-ef6b31dcb886	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 18:54:53.305012+00
63ee2b56-af5b-4e72-a296-33919bdea29f	381	159864f187b0f60eef3e30cce6f5bbc5f43adc880acb52c719b5a41d40d8a8fe	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-21 20:07:05.741308+00
dc4e8d0b-b904-4f03-b5c5-4cec7bfe240f	382	f27816e1272cfb249001b76254862dc2412e54fc09583c8bc8a1e1f472925487	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 11:35:55.161572+00
da31ac9f-4e20-48be-8d5e-674d53144509	383	ed96464280701d2262d3dddc54a880dd912f59eabaeb767994e5941835a00745	login_sucesso	tst-col	bruno.colega@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 11:35:55.312604+00
2d87d569-2279-46fb-9ea7-5d34b23894ee	384	135549a8404ae2f0a82d166de5e48f09cc7f3a61905fba94be3d47337107c5a7	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/ef1039e0-4755-4493-9d82-081e4f098749	sucesso	ssh em srv-db-prod: incidente. ticket #4417 - lentidao no banco	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 11:35:55.360479+00
77e674f7-2dea-4542-8a8e-f4406bd4ab7f	385	99009603766c6891926e4acb0321b78829242f53ca58a5cd82d7d338f9c248c5	sessao_aberta	tst-col	bruno.colega@teste.example.com	sessoes/214db25e-cdee-49e6-85aa-7a8e2dabca6f	sucesso	ssh em srv-web-01: deploy. release 2.14	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 11:35:55.407285+00
b97104b7-6534-4d2e-b40d-5f9c1fe6d3da	386	205e4b8d9e2898cd081c985d1163240533b1133cde1db9b368cbabdf1b1b5a4f	sessao_aberta	tst-col	bruno.colega@teste.example.com	sessoes/4e9a474b-8503-4d3d-8de7-d5f0c6634652	sucesso	ssh em srv-ssh-demo: manutencao. limpeza de logs	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 11:35:55.438179+00
9a9faa4b-bbe9-422d-a348-f77b9aa35570	387	9b05e66ef7f464612647589f7a5e0fddd157744b464ba651a5f938bded3adf77	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 12:23:56.348504+00
2dcc6d0f-029a-4689-a226-0fbf8c8575a7	388	1466222cbc561e5972b8e9fb285d92cc1163d67639e38a607207c459e3dddaa0	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:24:23.906423+00
aea48375-c46f-48f6-84e8-1d0cc59eff80	389	33ff978e7745e4367d105a400f1c49cc6ed8f70e4a666c814985ac83b39ccee0	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:25:13.475178+00
367b751f-b212-468d-987f-7e3805f37a06	390	5e093cd956ee4292416088005bbd47b6c7c6edae18ff2e322388fd8053b6611a	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/ef1039e0-4755-4493-9d82-081e4f098749	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:25:13.521445+00
bf470e45-1902-451e-8f07-a916c9d28b26	391	442ee4b879258de2455a98394913f8ce3e4ca2fa05d262f347fa131fdcf3cf51	login_sucesso	tst-col	bruno.colega@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:25:13.60687+00
3640aca9-216b-43f7-9b03-a1ccd6c4cc3a	392	070c2e8259e9ec7f68f80cc283b512cbbb367eb61e33010d1c532215645663ea	sessao_encerrada	tst-col	bruno.colega@teste.example.com	sessoes/214db25e-cdee-49e6-85aa-7a8e2dabca6f	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:25:13.64505+00
b533f6e0-4dfb-4c0a-848d-15e1d6eb521e	393	06db3ce3d2751dac9aa0dd643c8dc47e0706d503a701dee8582e1eec3e4c60e3	sessao_encerrada	tst-col	bruno.colega@teste.example.com	sessoes/4e9a474b-8503-4d3d-8de7-d5f0c6634652	sucesso	0 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 12:25:13.662967+00
c5620334-6f42-4bd1-9627-80e8baa2478f	394	da15d516b1c06a489139007d9bc0ea57a017deb48292367d9e5699e11fc5982d	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 12:25:30.869393+00
a9e5bdf1-6f67-40df-8639-0f2e6b3b6544	395	f61654f6d8743b962d14a6ebba8f367d0af645fcaeebddd525113f322f47bef8	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.510742+00
853d2199-cec6-440f-bc67-741bed154da5	396	f743e981cf6acf3e77bf87b228f32ac089de79c522405026e0d8f148266c2b5a	cofre_criado	tst-vis	qa-visual@teste.example.com	cofres/infra	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.548223+00
e1c9c7e5-4779-4944-95c1-301d32ec9d4b	397	75ab01b00b584f1dd9d422758a4c9464522ac97300e78a2c0a196d3b3ab187ee	dispositivo_cadastrado	tst-vis	qa-visual@teste.example.com	dispositivos/srv-app-01	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.590122+00
45355508-d1d5-4b4a-a633-f42924f96ce4	398	ba3dbbe7fbd45536fc54bbdc4a8fcf805212c1ef4f74f2d0f0104b502269cf7f	credencial_cadastrada	tst-vis	qa-visual@teste.example.com	credenciais/senha-deploy	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.61725+00
8746d87a-b625-41ed-acc9-001616ab3d33	399	8245f38906ddbeabd5a1374c9804acc361cff2d0d279531cea424ab51019dd3b	certificado_cadastrado	tst-vis	qa-visual@teste.example.com	certificados/portal-demo	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.666684+00
db3373d3-5cf3-40a9-bc9d-19f18ea574bb	400	eaa9bd328c1ed9bac3e43821071650d306cbe3234ee4518c382825ea4737441d	certificado_arquivo_guardado	tst-vis	qa-visual@teste.example.com	certificados/portal-demo	sucesso	Arquivo portal.pem (1316 bytes) guardado em cofres/infra/segredos/certificado-portal-demo.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.736141+00
909b71bb-2cce-41e8-bb8c-b1c9cccfa44e	401	2f85622f2f020a9286b54ee44ffdd165f9d8cdd50bf827609ab28783fde744c9	certificado_arquivo_baixado	tst-vis	qa-visual@teste.example.com	certificados/portal-demo	sucesso	Arquivo portal.pem baixado.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.766757+00
44b6b38a-82df-4e9d-b73a-7f37b324c4fa	402	a3bd3ad47c1361968f1e4bad4c58718585de0e32742e8fe0b4a09d4df04f200f	certificado_arquivo_guardado	tst-vis	qa-visual@teste.example.com	certificados/portal-demo	sucesso	Arquivo portal.pem (1328 bytes) guardado em cofres/infra/segredos/certificado-portal-demo.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.790103+00
351cfaba-4ee0-437c-b70c-7f41f11b5337	403	318e5699de02d8b14a5c4f3ef9f00581d2adb90d1b174a70202af6b201903c46	certificado_arquivo_baixado	tst-vis	qa-visual@teste.example.com	certificados/portal-demo	sucesso	Arquivo portal.pem baixado.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.812904+00
bb26ac91-bfd4-470d-ab4a-f40f13b05680	404	a0b9c2bcbf9af9fe3c48895b9933ab8a9eea760ab570bf4d757623ee751ad10f	chave_api_cadastrada	tst-vis	qa-visual@teste.example.com	chaves-api/sefaz-demo	sucesso	SEFAZ (producao). Responsável: fiscal@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.942118+00
3c53725e-f87f-4934-8c33-9619a1c6cd3c	405	3ea61254dd58be5169e9e6f31af0e3aac1b6cad2765e7e25d0ba1a8d2aee2f67	chave_api_alterada	tst-vis	qa-visual@teste.example.com	chaves-api/sefaz-demo	sucesso	Campos alterados: rota_exemplo.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:58.978193+00
b69dc580-c62b-4210-a784-e2b8a36b0779	406	c83387edb61dfff5bbc3ce493f042dc946e3e53d2ee7955309ad3eed19d70257	chave_api_cadastrada	tst-vis	qa-visual@teste.example.com	chaves-api/query-demo	sucesso	Exemplo (producao). Responsável: ti@exemplo.com.br.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 16:15:59.011406+00
a26029ce-2b83-46e9-8587-ff17bcd87152	407	57c76d3d88c1bea38bb848f161080025702eba022b2b49e49dc1672482cafcbf	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:16:26.938718+00
8a77050b-94a2-4e47-bf8b-ccc81b882f13	408	995c7205ae5f914333ee164e6695ea8e0ad5e6c7a739abdf7a59ee0c411ba2d9	credencial_cadastrada	tst-vis	qa-visual@teste.example.com	credenciais/servidor-de-homologacao	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:18:56.013832+00
af089ff0-a45d-4372-9014-d77d4a262cca	409	ed1a68f1c4cef37ee4591e6531b3f91b19dea191f3941e8d97183751e70fd0d5	credencial_cadastrada	tst-vis	qa-visual@teste.example.com	credenciais/painel-do-roteador	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:18:56.037299+00
a5498847-3f35-41ff-a05b-5fcfb62dcd0f	410	22380e49abf461bf2a9e8efd0214d72619bbd4aa5cfca6f45df880a5a9a15b8d	credencial_cadastrada	tst-vis	qa-visual@teste.example.com	credenciais/monitoramento-zabbix	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:18:56.063242+00
7bbd8d89-e3d4-4a62-92aa-f5265c1a3ebf	411	cc7559f2597afa049c1907f06a2156a32cfe2d709fb0bbfe42d7d05c82dfaf2d	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:19:23.618586+00
9a0d11dc-61f0-4bf9-9485-59b9217366e8	412	86952c7be9878e7b1f9a0f04532dca6d5add10cc90c6de3df37682e1bcc7b4da	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 16:20:49.187128+00
7d280cb3-5f40-401b-80ee-3844d36ad639	413	baeaca1ef0a43d71a0c92c990da5309cb4288a663d73d8e88a9692fd122fc704	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 17:04:27.363357+00
f469c87a-e62a-4bed-a553-0390225f38c4	414	ba35a75ea0c92a5e2f6f315308d4681e7b936d3b500290121db4df19a2002352	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 17:05:47.783229+00
c2c99ca2-1fba-4e83-a95c-d910cee88107	415	eb3dc85494e7ec5b009310a3a69e4fa4b4234e8e3cc2ab8041634e3261262bd6	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:15.382594+00
949365b5-61c3-45e7-859e-9660370fc61f	416	d1eafffc99e10ee4bcdec5c82717816697aa8c0405a4cd1d6eddc1102c2fba1d	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/8201084d-114f-4d34-85f4-3aab81c5f6b5	sucesso	ssh em srv-db-prod: incidente. ticket #4417 - lentidao no banco	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:15.406131+00
1b0ac15b-e170-4f81-b62d-bd1ab0577c07	417	0dc1d2e6b674aea54b2a2f5456b8bfbd62e713a3821cd8b664aa302e59d75c37	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:27.120396+00
c1cf53b2-1e91-49c9-ab13-84385bfbf376	418	68733728b994c03f720c85f8232e2bccf4194bf6562612991a467ead3544d745	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/450ec570-4580-4ef6-b5e0-9c6d5c4cf102	sucesso	ssh em srv-db-prod: incidente. ticket #4417 - lentidao no banco	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:27.142687+00
a3f8574f-ccff-40d2-ad36-e95a3a194f2e	420	a3d3f350ba73c089d3bba187db69361179668e3222cc9578e90f1aa62e295cf9	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/52e1da9c-efe9-4167-9de5-d6a96f6aeeb9	sucesso	ssh em srv-db-prod: incidente. ticket #4417 - lentidao no banco	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:34.833677+00
59e0d300-06fc-4425-a240-0f18e5878db8	422	7d49379f4b0874baf73769c85023a14f563b1bf801a8db9829807105a5370477	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/2ef93475-f4db-47ad-a278-659dd04c7d42	sucesso	ssh em srv-web-01: deploy. release 2.14	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:37.238737+00
1568daf6-f979-451e-aa7c-0127e48a0abe	423	8f76302fb33a52358e92e82bfc73350bae6233adb35e130686fe9278f189fb75	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/2ef93475-f4db-47ad-a278-659dd04c7d42	sucesso	35 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:37.894819+00
257bf769-5e59-4b73-bc44-e854a7d76c3c	425	1c5c42a20a456675be0f3e9476662132318367e2dcab1247a083313ec79913d3	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/eea557c2-832c-4ad5-9181-540712643b03	sucesso	6 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:38.030869+00
b0242b5a-2efa-4d77-9c13-e7c337db9f4d	427	593947770228ca25065995f76bd1f2c030312b6ea1329537d8af8fcfd01dacc9	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/91677d73-d4af-4166-8ff0-66a8632d8ed0	sucesso	72 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:39.177129+00
24c51601-95aa-4767-b97b-47fe71d92d91	429	50f43d8972cb370d799f5d20a53f78a8e328c19b6e68028f4c621e4bb32fea5d	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/ab6eb7dd-0932-4d88-98ce-c9f6544429ee	sucesso	18 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:39.471807+00
0087db25-ddaf-4c83-b39e-c0a287185567	421	92d16280b2143931655f872b4d7af340f5c3520de262c6af43fcbe55008efe67	sessao_encerrada	tst-vis	qa-visual@teste.example.com	sessoes/52e1da9c-efe9-4167-9de5-d6a96f6aeeb9	sucesso	140 evento(s); gravação em arquivo:gravacoes.	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:37.221263+00
7758551e-23f1-4808-b499-1247d93aed5d	424	0b53948be930be2832967ffafa82c94d6778c4ff7a3910409eba653cc7da6849	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/eea557c2-832c-4ad5-9181-540712643b03	sucesso	ssh em srv-ssh-demo: manutencao. limpeza de logs	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:37.91442+00
eb61701a-fd75-4773-86b2-d2d83e65e7b1	426	7d08792bd0f550ce8f791de177d5e6535188eea8305936004b6e755af83686db	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/91677d73-d4af-4166-8ff0-66a8632d8ed0	sucesso	ssh em fw-matriz: auditoria. revisao trimestral de regras	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:38.0491+00
120938a0-1705-4585-8bf8-e5bbfbe0be40	428	503d2087fd693244be0d258bc4198cc80a95f1474100abd4239d0aee9ce63f70	sessao_aberta	tst-vis	qa-visual@teste.example.com	sessoes/ab6eb7dd-0932-4d88-98ce-c9f6544429ee	sucesso	ssh em srv-dominio: suporte. chamado 8821	172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:06:39.192458+00
74c15ed8-6b6c-46b1-9565-90c7a725862e	430	3bd56ddf0d7651a3e30f3b2385d05516b06b1a825802ea75f6dd429cf331879b	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 17:06:54.799115+00
aff6ab46-d3de-4732-bc20-2564cd5499dd	431	f9c69dbbb5ab7fef6ccc8692e50555b3f2b7d5309966705eea489d89f97f244d	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:07:11.982542+00
cdb8d73f-e565-4ad2-b0ca-7ce7f4c6f5ab	432	6aa723d8896d9a4b90fe3a08d0a0e6992ba88f6b8e4774a07de9dad98f8d0857	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:07:21.639214+00
adfcdb3d-8511-4c31-8f36-914130bf8cbb	433	962ff98e3131b2d810f8db197ed23444e5c67221a5178eb265ff6abc3211ec84	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Python-urllib/3.12	{}	2026-10-22 17:10:40.27571+00
0032cef5-cb62-430a-bc1e-ff16f9566ff2	434	9d1fa4e689bedb8781cbbab144b20504b3fee0b3e196612c450a5bb363cc2866	login_sucesso	tst-vis	qa-visual@teste.example.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-22 17:10:52.227418+00
b209c7ab-2c55-4b5f-8b42-937904d27d94	435	9ddea7e2ca9db28aa34ab9b7c2d27c67bbc5a48e3e8c798e5184bf16cf4a6e5f	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-23 14:15:49.784381+00
5cf126e4-3172-4f7d-b521-34ada8259ad6	436	951cd041c11baa78ef49718c893291ecfce754d0ef948010ab6a38362f06d84b	login_sucesso	9d9ad47d-68f4-4c61-9eff-d1a2490f0fee	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 14:18:35.971057+00
f13dbc2d-ed3b-4dda-8d71-efef4e5c5d44	437	929d5bab268f82aec11b9141254f48ffd66e9ea46aead34300ee7c54ee6c212e	login_sucesso	9d9ad47d-68f4-4c61-9eff-d1a2490f0fee	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 14:19:27.398407+00
93259268-aa48-4d42-9830-5870c2147803	438	dc95dc2c1500ced4451579a7b7cd65f30e1d295918da0603aa5a6efb7e6d68a2	login_sucesso	9d9ad47d-68f4-4c61-9eff-d1a2490f0fee	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 14:21:58.233048+00
b9e1c513-c096-480f-9447-01ca8827213f	439	b9212aa6ad7976eac208d67b366474479d1cb7e7f20b0c77dd24c64dc4355ceb	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 14:32:59.204603+00
5a6b058f-e0ba-4408-88cf-0f9e58a5fbfd	440	fc2b45b9bc80fee882fd86dab48bad0191f764fab5bfe4cf86c6131f7c4b1ee4	acesso_remoto_iniciado	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	dispositivos/val-srv	sucesso	Acesso por anydesk iniciado pelo usuário.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:01:21.205766+00
c7a3f618-75f8-474b-9b6c-2e32cbf8e246	441	694807b3aa224f53f40060b273edcb6a03171b292adfb015fd7c4e983c52c2bc	sessao_reproduzida	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	sessoes/2a9418b6-ff5e-403f-9eb8-ca1f70f669ef	sucesso	Gravação de ana.souza@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:02:16.809562+00
2ce12907-3430-405e-a94f-92ea78a888ef	442	ab4b1a4ce5b933c4651d452b914efdb7edcb654868346d85ed57d56a8bcee1f9	sessao_reproduzida	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	sessoes/adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	sucesso	Gravação de contador@exemplo.com.br reproduzida.	172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:02:28.687837+00
c5dad970-322a-42f2-948f-ac3bb30a00ca	443	75b7c8268a3ec7e7413851c6d6b50f099ac3daa58884bb9188ed74415c7296d9	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	robo-integracao/1.4	{}	2026-10-26 15:24:25.827831+00
ba695478-b6fe-41af-938c-720f6401d476	444	b1fd33c00719ecce2bd0acf9cc6a0c935e65d76f83276c109968ec3deb0d3f8f	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:25:07.16211+00
0494b993-0e3f-4116-b870-302d7735e5dc	445	7bbb3713cd727ef3701d1de673cee186b6e1d9b87385e1c97b3cf3e1a98bb879	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:31:49.544755+00
e18fad35-9b5d-4167-8f20-75fb55c0f670	446	d57f22e03e586ab3202a210ccd92d7f4e2bff36785d2404d0ebeab420fb8cf88	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	robo-integracao/1.4	{}	2026-10-26 15:32:16.973628+00
369543c5-682d-4396-ad62-3a567fff3d07	447	c72ef32e22863a661edde6815c99f8f56d561845bf336ec17dd0e5248a2f442e	login_sucesso	f8bf6968-e2eb-45b9-b997-b5220fdfa3b8	layout-teste@exemplo.com	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 15:53:44.141354+00
cf7a91ed-d55d-4432-a4be-532df60c6976	448	a4cd9489a2ca9be3aaeeb71ab81eb22ba3abb537f8ae55d643f6130282899274	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 17:50:10.90423+00
0123ad6b-071e-46a1-8f4e-aa6525ed0671	449	5efbcc633775371c7b7cc11331e57cb2acc6e94e5c279271efaa01af1a3af75a	login_sucesso	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	auth/login	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 17:50:43.790908+00
00562773-b724-414d-8213-b5f5b6d68102	450	659ce3bc32c2674cb0b1bb279b4939f02f8407083a12cf884f7dceab0d273f28	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/api-monitoramento	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 17:51:20.944946+00
1c6cb871-b8f7-4c23-83cd-a88d8924a13b	451	b9962c0e365fb5a9249602fb8761c88f24e387c1a6729bc21c97882f3b66512b	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/chave-deploy	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 17:51:23.440356+00
5a943f9e-55a5-42c9-9e62-fdcbeaf253cc	452	a9e6ddc5d2c9891e9e1d3953b86063dae06a2d1df971feb62472df1889e07eca	segredo_revelado	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	sucesso		172.27.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36	{}	2026-10-26 17:51:25.899802+00
\.


--
-- Data for Name: certificados; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.certificados (id, name, display_name, subject, issuer, serial, owner_label, not_before, not_after, secret_id, description, created_at, arquivo_nome, arquivo_cofre) FROM stdin;
e1441229-e4c1-4236-9403-1710a36c43af	api-rede	api.exemplo.com.br	CN=api.exemplo.com.br	Let's Encrypt		Infraestrutura	2026-07-21 12:32:40.899112+00	2027-01-01 12:32:40.899112+00	\N		2026-10-19 12:32:41.024774+00		
9886788b-e196-4c83-828b-34667c03ca73	portal-cliente	portal.cliente.com.br	CN=portal.cliente.com.br	DigiCert		Infraestrutura	2026-07-21 12:32:40.899112+00	2026-11-09 12:32:40.899112+00	\N		2026-10-19 12:32:41.030029+00		
cbc2d9ed-f53a-427e-b853-06b5ffaf03d5	ecnpj-matriz	ecnpj.matriz.com.br	CN=ecnpj.matriz.com.br	AC Certisign		Contabilidade	2026-07-21 12:32:40.899112+00	2026-10-11 12:32:40.899112+00	\N		2026-10-19 12:32:41.033308+00		
0203dded-5d81-4de0-9d32-243b6896141a	vpn-interna	vpn.interna.com.br	CN=vpn.interna.com.br	AC interna		Infraestrutura	2026-07-21 12:32:40.899112+00	2027-09-04 12:32:40.899112+00	\N		2026-10-19 12:32:41.03678+00		
\.


--
-- Data for Name: chaves_api; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.chaves_api (id, name, display_name, servico, ambiente, formato, nome_do_campo, escopo, usada_em, responsavel, documentacao_url, secret_id, vault_name, secret_name, expira_em, estado, revogada_em, criado_por, created_at, url_base, metodo, rota_exemplo) FROM stdin;
6684597d-a046-4f6e-9d86-645770d3c1ac	sefaz-nf-e-producao	SEFAZ NF-e producao	SEFAZ	producao	cabecalho	X-API-Key	Consulta de NF-e, somente leitura	["etl-notas", "rpa-fiscal"]	fiscal@exemplo.com.br		\N			2026-11-06 02:59:59+00	ativa	\N	ana.souza@exemplo.com.br	2026-10-20 13:56:00.854194+00		GET	
\.


--
-- Data for Name: cofres; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.cofres (id, name, display_name, description, state, created_at) FROM stdin;
dcf284ac-a683-4377-bd9b-1719986e6b9b	contabil	Contábil	Credenciais dos sistemas contábeis e fiscais.	ativo	2026-10-17 21:37:39.779174+00
73a5bd6c-3062-4652-be29-8238a376f766	infraestrutura	Infraestrutura	Acessos de servidores, bancos e rede.	ativo	2026-10-17 21:37:39.813564+00
0290d4f6-874f-4cc7-bc4d-7297033e2759	rh	Recursos Humanos	Sistemas de folha e benefícios.	ativo	2026-10-17 21:37:39.836447+00
0fe2e718-fec7-4f0d-b9a5-dae5ee391433	ciclo	Ciclo		ativo	2026-10-20 14:53:45.162393+00
d3ed09e8-f969-4fe7-8451-61003e2d991c	infra	Infraestrutura		ativo	2026-10-22 16:15:58.540205+00
\.


--
-- Data for Name: cofres_selos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.cofres_selos (id, vault_id, limiar, total_quinhoes, token_hash, portadores, selado_por, selado_em, desselado_em, desselado_por) FROM stdin;
3e908967-687f-4fe0-a7d5-e8d07874dd46	73a5bd6c-3062-4652-be29-8238a376f766	2	2	e4d82f4e025ceec4b1f83ec0dd6f9622dbccbf556d86ad3167b4345cb60a94d3	["x@exemplo.com.br", "y@exemplo.com.br"]	ana.souza@exemplo.com.br	2026-10-19 14:42:21.088606+00	2026-10-19 14:42:21.148347+00	ana.souza@exemplo.com.br
b3f8ac4d-a4e1-47e0-a22e-cd3d67e57959	0290d4f6-874f-4cc7-bc4d-7297033e2759	2	3	dc394956e69119837c6d8249353931e9548d797906cfb05f1ad1de07e18e6809	["ana@exemplo.com.br", "bruno@exemplo.com.br", "carla@exemplo.com.br"]	ana.souza@exemplo.com.br	2026-10-19 14:42:20.974018+00	2026-10-19 14:42:21.186652+00	ana.souza@exemplo.com.br
\.


--
-- Data for Name: configuracao; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.configuracao (id, segundos_segredo_visivel, custodia_horas_padrao, alerta_certificado_dias, rotacao_dias_padrao, trilha_limite_padrao, atualizado_por, atualizado_em, capacidade_do_ranking) FROM stdin;
unica	30	4	30	90	200	ana.souza@exemplo.com.br	2026-10-20 19:36:35.545394+00	admin
\.


--
-- Data for Name: convites; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.convites (id, email, tipo, token_hash, estado, nome_sugerido, papeis, criado_por, expira_em, usado_em, criado_em) FROM stdin;
\.


--
-- Data for Name: credenciais; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.credenciais (id, name, device_id, secret_id, username, description, rotation_days, last_rotated_at, status, created_at) FROM stdin;
4c4f7f13-69c9-4c06-bae8-fbd9b4539ef8	senha-admin	25286646-953c-41e1-9208-abfab07b9cbd	\N	admin		90	\N	ativa	2026-10-19 12:32:40.948091+00
598f5f3b-727f-4c54-9ab4-ecffbc79b9b6	usuario-servico	cfc8039f-19c1-4441-a4fb-6ab634cee1c2	\N	svc_dominio		90	2026-06-01 12:32:40.899112+00	ativa	2026-10-19 12:32:40.95562+00
ae17a4ef-952b-465c-bf94-c40b90678722	senha-enable	913925b2-d005-41f7-ac2f-fbaed21b70d6	\N	enable		0	\N	ativa	2026-10-19 12:32:40.963633+00
cef57ad2-8e9e-409e-8f89-d5e598086db5	replicador	6c372da5-6c28-4aad-865c-ab20b1aedab6	\N	replicator		180	2026-09-19 12:32:40.899112+00	ativa	2026-10-19 12:32:40.966232+00
b58fa1de-c603-4bb5-ad83-0af74525735e	senha-postgres	6c372da5-6c28-4aad-865c-ab20b1aedab6	\N	postgres		60	2026-10-04 12:32:40.899112+00	em_custodia	2026-10-19 12:32:40.959795+00
e9026fe7-e5bf-4e37-8ecb-420a6f5b187c	val-root	e0aed768-019b-4aa0-8c4f-65be2f0ccfad	\N	root		60	\N	ativa	2026-10-20 13:53:09.904795+00
421ea22a-61b0-4474-b3ca-735d218b34d8	senha-demo	4b16e794-eed1-46c9-8a61-04bbde2333f0	\N	root		90	\N	ativa	2026-10-21 17:36:54.468652+00
719b6ea4-471e-4202-9526-117b6ca6c0d6	senha-root-db	8e96b0e7-4ac8-446b-b9e7-5caf23336842	\N	deploy		90	\N	ativa	2026-10-21 18:47:32.989089+00
\.


--
-- Data for Name: credenciais_custodias; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.credenciais_custodias (id, credential_id, user_id, user_label, reason, due_at, taken_at, returned_at) FROM stdin;
a68a8a89-688b-4192-a179-0d4b528a2ff0	b58fa1de-c603-4bb5-ad83-0af74525735e	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	Investigação de lentidão no banco	2026-10-19 20:32:41.008021+00	2026-10-19 12:32:41.008021+00	\N
\.


--
-- Data for Name: dispositivos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.dispositivos (id, name, display_name, kind, address, tags, description, is_active, created_at, acessos) FROM stdin;
25286646-953c-41e1-9208-abfab07b9cbd	fw-matriz	Firewall Matriz	firewall	10.0.0.1	["cr\\u00edtico", "produ\\u00e7\\u00e3o"]	Firewall de borda do escritório central.	t	2026-10-19 12:32:40.902208+00	[]
cfc8039f-19c1-4441-a4fb-6ab634cee1c2	srv-dominio	Servidor Domínio	servidor	10.0.1.20	["cont\\u00e1bil", "produ\\u00e7\\u00e3o"]	Servidor de aplicação do ERP Domínio.	t	2026-10-19 12:32:40.910891+00	[]
6c372da5-6c28-4aad-865c-ab20b1aedab6	pg-producao	Postgres Produção	banco_de_dados	10.0.2.10	["cr\\u00edtico", "produ\\u00e7\\u00e3o"]	Banco principal.	t	2026-10-19 12:32:40.919676+00	[]
913925b2-d005-41f7-ac2f-fbaed21b70d6	sw-acesso	Switch de Acesso	switch	10.0.0.20	["rede"]	Switch do andar administrativo.	t	2026-10-19 12:32:40.927891+00	[]
e0aed768-019b-4aa0-8c4f-65be2f0ccfad	val-srv	Servidor de validacao	outro	10.9.9.9	[]		t	2026-10-20 13:53:09.803197+00	[{"metodo": "rdp", "identificador": "10.9.9.9", "porta": null, "usuario_sugerido": "administrador", "observacao": ""}, {"metodo": "anydesk", "identificador": "123 456 789", "porta": null, "usuario_sugerido": "", "observacao": ""}, {"metodo": "google_remote", "identificador": "val-srv", "porta": null, "usuario_sugerido": "", "observacao": ""}]
4b16e794-eed1-46c9-8a61-04bbde2333f0	srv-ssh-demo	Servidor de demonstracao	servidor	10.0.0.50	[]		t	2026-10-21 17:36:54.272182+00	[{"metodo": "ssh", "identificador": "10.0.0.50", "porta": 2222, "usuario_sugerido": "deploy", "observacao": ""}]
8e96b0e7-4ac8-446b-b9e7-5caf23336842	srv-db-prod	Banco de producao	servidor	10.0.0.5	[]		t	2026-10-21 18:47:32.889463+00	[{"metodo": "ssh", "identificador": "10.0.0.5", "porta": 2222, "usuario_sugerido": "deploy", "observacao": ""}]
341e8021-5a77-4d58-abd6-b84d8509d10f	srv-web-01	Servidor web	servidor	10.0.0.7	[]		t	2026-10-21 18:47:33.029421+00	[{"metodo": "ssh", "identificador": "10.0.0.7", "porta": null, "usuario_sugerido": "ana", "observacao": ""}]
\.


--
-- Data for Name: integracoes_destinos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.integracoes_destinos (id, name, display_name, url, eventos, segredo, estado, descricao, falhas_seguidas, ultima_entrega_em, ultimo_erro, criado_por, created_at, ultima_sequencia) FROM stdin;
\.


--
-- Data for Name: integracoes_entregas; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.integracoes_entregas (id, destino_id, id_evento, tipo, corpo, estado, tentativas, proxima_em, ultimo_status, ultimo_erro, entregue_em, created_at) FROM stdin;
\.


--
-- Data for Name: papeis; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.papeis (id, name, description, created_at) FROM stdin;
3a31e3cc-3709-4df4-b46d-4f61222390b0	administrador	Administrador do Vault.	2026-10-17 21:37:38.345402+00
200c60cf-465e-488c-8cbb-22e5530cc617	contador	Equipe contábil.	2026-10-17 21:37:39.926494+00
\.


--
-- Data for Name: papeis_politicas; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.papeis_politicas (role_id, policy_id) FROM stdin;
3a31e3cc-3709-4df4-b46d-4f61222390b0	d92022f2-7c70-43b4-b44c-06fc688e9fc6
200c60cf-465e-488c-8cbb-22e5530cc617	abf9f8c5-7aab-4f08-9333-81a87eeca28f
3a31e3cc-3709-4df4-b46d-4f61222390b0	505bad34-05d0-44bd-8341-da2a91110617
3a31e3cc-3709-4df4-b46d-4f61222390b0	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed
\.


--
-- Data for Name: pedidos_redefinicao; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.pedidos_redefinicao (id, email, motivo, ip_address, atendido, atendido_por, atendido_em, criado_em) FROM stdin;
\.


--
-- Data for Name: politicas; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.politicas (id, name, description, created_at) FROM stdin;
d92022f2-7c70-43b4-b44c-06fc688e9fc6	administracao	Acesso total a cofres e segredos.	2026-10-17 21:37:38.335441+00
abf9f8c5-7aab-4f08-9333-81a87eeca28f	contabil-leitura	Leitura e revelação no cofre Contábil, exceto o token da SEFAZ.	2026-10-17 21:37:39.925395+00
505bad34-05d0-44bd-8341-da2a91110617	auditoria-total	Leitura e verificação da trilha.	2026-10-17 21:37:39.932606+00
ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	inventario-total	Gestão de dispositivos, credenciais e certificados.	2026-10-19 12:32:40.882029+00
\.


--
-- Data for Name: politicas_regras; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.politicas_regras (id, policy_id, path, capabilities, effect) FROM stdin;
7025dabf-8a6e-49d7-803d-955c1c0b9121	d92022f2-7c70-43b4-b44c-06fc688e9fc6	cofres	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
53ef20a5-d2e3-4d6e-a56b-1d9e311a2a4d	d92022f2-7c70-43b4-b44c-06fc688e9fc6	cofres/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
68b3e0cc-6a47-443d-9b0b-f97c98c2773c	abf9f8c5-7aab-4f08-9333-81a87eeca28f	cofres/contabil	["read", "list"]	allow
4307e405-c725-461b-a3ba-9600f6c38b75	abf9f8c5-7aab-4f08-9333-81a87eeca28f	cofres/contabil/*	["read", "list", "reveal"]	allow
48200726-6753-40d4-becc-c7a7e801c0e0	abf9f8c5-7aab-4f08-9333-81a87eeca28f	cofres/contabil/segredos/token-sefaz	["reveal"]	deny
4dc6fdd8-75cd-4624-b3cd-b115cc8c4197	505bad34-05d0-44bd-8341-da2a91110617	auditoria	["read", "list", "admin"]	allow
e41e2ad3-3f56-4b1d-a92e-b0d2f255a760	d92022f2-7c70-43b4-b44c-06fc688e9fc6	admin	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
bdedb9c2-8920-4319-b821-5bf140fc9fc1	d92022f2-7c70-43b4-b44c-06fc688e9fc6	admin/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
4ce4181a-0981-42e9-ad61-706ec9c44017	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	dispositivos	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
03c2c17f-d184-466e-9eec-28d18dc7517b	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	dispositivos/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
84552cab-6642-4494-bdfe-c9e0d95c9228	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	credenciais	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
c63a034a-def6-4a13-81b6-f5b50a50d1d0	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	credenciais/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
0dfd3959-b9cc-4c7d-8cb5-835b622457d0	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	certificados	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
7886bdf9-95ae-469d-a5f7-35715754344e	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	certificados/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
b1bb0332-f600-4356-823b-b0cd34189789	d92022f2-7c70-43b4-b44c-06fc688e9fc6	aplicacoes	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
46cc53fe-29f5-4559-8bdc-b1509d740e8c	d92022f2-7c70-43b4-b44c-06fc688e9fc6	aplicacoes/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
53f18409-74ee-4e11-a55b-92872f2187b9	d92022f2-7c70-43b4-b44c-06fc688e9fc6	sessoes	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
da334869-d678-4485-9f8a-1e5d088441c2	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	chaves-api	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
d1485ca4-03dd-4709-911c-b2753f43ea0e	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	chaves-api/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
250c00c7-deb6-4b4c-b5e9-455252362467	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	integracoes	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
58a0ec96-393d-4b85-a3b8-6ea23e5da610	ffd4d6ed-da06-4462-82ff-5d1e9040f6ed	integracoes/*	["read", "reveal", "create", "update", "delete", "list", "approve", "admin"]	allow
\.


--
-- Data for Name: segredos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.segredos (id, vault_id, name, kind, description, deleted_at, created_at) FROM stdin;
842e649d-6e67-40f5-a556-c3a92e6fa016	dcf284ac-a683-4377-bd9b-1719986e6b9b	dominio-escrita	senha	Usuário de escrituração do Domínio	\N	2026-10-17 21:37:39.797728+00
02c36eb9-f7f8-4bbf-a448-20ea0bf50db2	dcf284ac-a683-4377-bd9b-1719986e6b9b	certificado-ecnpj	certificado	Senha do e-CNPJ da matriz	\N	2026-10-17 21:37:39.804118+00
2ea3f4f4-90d1-441f-8ca3-38d73c36bd15	dcf284ac-a683-4377-bd9b-1719986e6b9b	token-sefaz	token	Token de consulta da SEFAZ	\N	2026-10-17 21:37:39.808723+00
18d48a0c-ef88-41c6-9671-1a8c44ca40e8	73a5bd6c-3062-4652-be29-8238a376f766	postgres-producao	senha	Banco de produção	\N	2026-10-17 21:37:39.823265+00
2664a7dc-8cb6-4c5f-95d1-4a847c2d01d3	73a5bd6c-3062-4652-be29-8238a376f766	chave-deploy	chave_ssh	Chave SSH do pipeline de deploy	\N	2026-10-17 21:37:39.827343+00
1ef9d02b-acbc-4842-942d-da1d2cccd5f2	73a5bd6c-3062-4652-be29-8238a376f766	api-monitoramento	chave_api	Chave da API de monitoramento	\N	2026-10-17 21:37:39.832157+00
57c0d1fc-40e5-4bdf-9437-6c056c0ae654	0290d4f6-874f-4cc7-bc4d-7297033e2759	portal-folha	senha	Portal da folha de pagamento	\N	2026-10-17 21:37:39.844517+00
d0845370-d69c-4375-aae7-0dd8df668a4c	0fe2e718-fec7-4f0d-b9a5-dae5ee391433	senha-root	senha		2026-10-20 14:53:45.488229+00	2026-10-20 14:53:45.258732+00
\.


--
-- Data for Name: segredos_versoes; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.segredos_versoes (id, secret_id, version, ciphertext, nonce, wrapped_dek, key_id, created_by, created_at) FROM stdin;
1b85efb5-c2d0-4b6c-9be6-fdcb0746f73d	02c36eb9-f7f8-4bbf-a448-20ea0bf50db2	1	\\x7d599451743d699d7044b6c23e9288678bbeab60c0a8d8d2f62859bb141e94ee74dc1f8390165417841e6bb2e32d84023291	\\x0338d4f2a287e6f508b70abc	\\xc69cee82c687d9cb5d1f42204f281bd55a0aa2553ac6e66f48b3492c0a7c6bea45b7f725a24e49ff60ed7ebdf86792ea2f41bb2e117fc7c00a6b0b9b	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.802932+00
29bd1199-e631-4111-964d-a89405dede29	18d48a0c-ef88-41c6-9671-1a8c44ca40e8	1	\\x373e654b7390c7a85194abc13aa914a5b3e626d8dc90c6859c59e37ac83b28dbb041c6a2a2e953cda7b4c983a1b05f4e82aa	\\x82fa53da48f7589481113c77	\\xcc5696cdc409a79359a97cb5ea4ee0e60a31a0c569a256feaac4e846f9381295b1ee70fb289e675c93e1462592b0c38344b4f47696fcdef014b10ea8	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.822164+00
746f6009-3959-4b8c-9ae8-97532872d7f8	2664a7dc-8cb6-4c5f-95d1-4a847c2d01d3	1	\\x6d1a0a8ca6d6079b58306dc62d3ff78cb33b423c2b8314e64b44dc8d19302a076ab0e0d46b259d45dc047452e0	\\x4b11c78981938217bac7833b	\\xe430513125a055180253f89aea8de36a08ebb4c80561f5f84c3b9cde94badc72cada031f7f33c103aef26ce5b7698739a09a6d4eca20bf5d1074cbbb	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.826407+00
7bc54160-43e4-4169-92b5-6380f32875f8	57c0d1fc-40e5-4bdf-9437-6c056c0ae654	1	\\x68d99cce6c9541b0dc816150e40d2cfbfcacdf3ec46e20f94069c32bf97e4d0d94554c12ab9ff3fb4af06c8410	\\x64c820637d63a3fb74d5cace	\\xb39cec1e8d20ed1db3c6d58fc2a974a8962e4a84843c109aa6d447a85db634a5f21799d42d187577cf7b30edc8e0c83240c8d57a4779c51c46bed2dc	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.843344+00
96374065-2790-4afb-88f4-7900252e2491	842e649d-6e67-40f5-a556-c3a92e6fa016	1	\\xc983a88a7f78e225e1f14f7e83b9f4c610874d3573088531c39beeb2d988626cbac2a76bdfb17ed55bbacfb465d47885	\\x53690670beedabfc13536654	\\x1bc9b31d57354091fecd1f36a37f217e414cb1d6f5e939455ee520091fb6a3a1932e42fe609943c3c39f1efb692d89e0d188bce91bac30a2009ca186	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.793912+00
9d84a540-e68d-4514-b539-0ed13702c070	2ea3f4f4-90d1-441f-8ca3-38d73c36bd15	1	\\x2697905a92686e7a4ff1bf0a0e2786329ec2d4b57d0bb53aeed4b48fbad02a2c4176ab148662bf7d730ea892	\\x2bd5f6b0c97adb080d540a8c	\\xa2f22eb6fb6efcce76f557c65368cba3cefe9105e27bba4f29d4813267cad41e566a8c6943f958abeba8ee700599106de805cf69ca75c9021c11f94d	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.806935+00
f879d076-e41f-46ba-8fe9-739f6d8d419c	1ef9d02b-acbc-4842-942d-da1d2cccd5f2	1	\\xa3716959c00bc347bd60e9acddcd38db66222f04abc7f6daa59b82df3ea96bf3a0de53b21dc3a5e94d71788a5b0eeb2d1eb9	\\x41b3ae551dffec838731254a	\\xfa14b8974f72f503253581ee5d2f9bd7b0f91dbbbc938a30dfab94a780cb4ebc673d462bfa942723d569534f78073b3f915c0fb0b90d0af472de88d6	local-9d5dc037396d	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-17 21:37:39.830753+00
7eda8158-0570-4c5f-80fb-14f5f659e5a2	d0845370-d69c-4375-aae7-0dd8df668a4c	1	\\x9b5cbe194177f4233e0d5d8e3e972d87a90722c7df9575d1e5530cbb99d97f04ee531a193c4089728f469d83ef2ee9	\\x0fcd6c90479ebf835175cfcf	\\x01b6c323766ee416c858c9f64bf2acb086e28c7d1444d3c966debd3048f957e0ac3cc703d43a9f1bde4dc583c67305c3ca18e3d1f2e1e2a63acfb8a8	local-dev	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	2026-10-20 14:53:45.252115+00
\.


--
-- Data for Name: sessoes; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.sessoes (id, usuario_id, usuario_label, tipo, alvo, motivo, segredo_path, estado, capturado_por, captura_automatica, gravacao_ref, gravacao_destino, ip_address, iniciada_em, ultima_atividade_em, encerrada_em, encerrada_por, motivo_encerramento, origem_hostname, origem_user_agent, origem_dispositivo, consumo_tipo, consumo_nome, consumo_caminho, consumo_pertence_a, motivo_detalhe) FROM stdin;
3fc45e39-75ad-4ad3-bd06-ef6b31dcb886	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	ssh	srv-db-prod	incidente	credenciais/senha-root-db	encerrada	manual	f	3fc45e39-75ad-4ad3-bd06-ef6b31dcb886.jsonl	arquivo:gravacoes	172.27.0.1	2026-10-21 18:54:39.745701+00	2026-10-21 18:54:39.745709+00	2026-10-21 18:54:53.297355+00	ana.souza@exemplo.com.br			Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36		credencial	senha-root-db	credenciais/senha-root-db		ticket #4417 - lentidao no banco
c223d5bf-8f13-4562-801d-9b9202ecd0e7	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	banco_de_dados	pg-contabil	Conferencia do fechamento	\N	encerrada	manual	f	c223d5bf-8f13-4562-801d-9b9202ecd0e7.jsonl	arquivo:gravacoes	172.27.0.1	2026-10-19 18:36:16.892279+00	2026-10-19 18:36:17.124557+00	2026-10-19 18:36:17.303012+00	contador@exemplo.com.br	Conferencia concluida				nao_identificado				
adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	banco_de_dados	pg-contabil	Conferencia do fechamento	\N	encerrada	manual	f	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e.jsonl	arquivo:gravacoes	172.27.0.1	2026-10-19 18:37:09.376418+00	2026-10-19 18:37:09.587506+00	2026-10-19 18:37:09.75202+00	contador@exemplo.com.br	Conferencia concluida				nao_identificado				
b876623d-7642-4858-bcbc-01d21d69bc07	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	banco_de_dados	pg-contabil	Conferencia do fechamento	\N	expirada	manual	f	\N		172.27.0.1	2026-10-19 18:34:14.993469+00	2026-10-19 18:34:15.268848+00	2026-10-19 21:23:20.433249+00	sistema	Tempo esgotado.				nao_identificado				
2a9418b6-ff5e-403f-9eb8-ca1f70f669ef	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	ssh	srv-validacao-67	Validacao	cofres/contabil/segredos/token-sefaz	encerrada	manual	f	2a9418b6-ff5e-403f-9eb8-ca1f70f669ef.jsonl	arquivo:gravacoes	172.27.0.1	2026-10-20 14:25:08.341346+00	2026-10-20 14:25:08.341351+00	2026-10-20 14:25:08.415024+00	ana.souza@exemplo.com.br	fim da validacao	NOTE-TI-99	Python-urllib/3.12		chave_api	SEFAZ NF-e	cofres/contabil/segredos/token-sefaz	SEFAZ	
fbd5c841-239c-40a0-9196-196ba254a189	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	ssh	srv-ssh-demo	incidente	\N	encerrada	manual	f	fbd5c841-239c-40a0-9196-196ba254a189.jsonl	arquivo:gravacoes	172.27.0.1	2026-10-21 17:36:54.551889+00	2026-10-21 17:36:54.551894+00	2026-10-21 17:36:54.593037+00	ana.souza@exemplo.com.br	fim do teste		Python-urllib/3.12		nao_identificado				ticket #4417
\.


--
-- Data for Name: sessoes_eventos; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.sessoes_eventos (id, sessao_id, deslocamento_ms, tipo, conteudo) FROM stdin;
3c87d717-6198-4072-b92b-3540f7b92eb4	b876623d-7642-4858-bcbc-01d21d69bc07	0	entrada	psql -h pg-contabil -U contador
a7bd9bbb-ddc1-4a55-9b25-895e03123d9f	b876623d-7642-4858-bcbc-01d21d69bc07	1200	saida	psql (16.1) Type "help" for help.
9bf53349-ca50-42bc-bcc7-f8a154d46905	b876623d-7642-4858-bcbc-01d21d69bc07	3500	entrada	SELECT count(*) FROM lancamentos WHERE mes = 10;
3d3ff510-3e95-410a-b7d6-60ebdb7fb51d	b876623d-7642-4858-bcbc-01d21d69bc07	4100	saida	 count\n-------\n  8432
1d4dc6d0-4c3e-48d2-9b58-808e0c3deec7	b876623d-7642-4858-bcbc-01d21d69bc07	9000	entrada	\\q
64846d9c-bd19-432a-8405-e489a4a025e2	b876623d-7642-4858-bcbc-01d21d69bc07	10000	entrada	tarde demais
047c52bd-1d24-434f-9e07-92323c342cda	c223d5bf-8f13-4562-801d-9b9202ecd0e7	0	entrada	psql -h pg-contabil -U contador
fa25f847-4a81-44fa-be69-528ceb0c1508	c223d5bf-8f13-4562-801d-9b9202ecd0e7	1200	saida	psql (16.1) Type "help" for help.
d0815ac8-9548-406a-95f3-5f90d932dc43	c223d5bf-8f13-4562-801d-9b9202ecd0e7	3500	entrada	SELECT count(*) FROM lancamentos WHERE mes = 10;
cb61b3e5-297d-4666-a259-76057994fe3e	c223d5bf-8f13-4562-801d-9b9202ecd0e7	4100	saida	 count\n-------\n  8432
19584a8d-f163-4353-8428-e49fdb4d53f0	c223d5bf-8f13-4562-801d-9b9202ecd0e7	9000	entrada	\\q
983859a5-8a93-4805-91ec-cca57fc83695	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	0	entrada	psql -h pg-contabil -U contador
9431d5e0-5b1b-40ac-8cf4-4c086a8049cb	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	1200	saida	psql (16.1) Type "help" for help.
1f98791c-4e69-4dde-9bbb-bc28a29fdac1	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	3500	entrada	SELECT count(*) FROM lancamentos WHERE mes = 10;
077ff2c5-b457-4173-a979-a521aee515d6	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	4100	saida	 count\n-------\n  8432
230f0cc0-ae4f-4acf-b597-8846235e92fb	adb9a6e6-da01-400d-b8a3-e2ce0ec0c92e	9000	entrada	\\q
\.


--
-- Data for Name: solicitacoes_acesso; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.solicitacoes_acesso (id, requester_id, requester_label, path, capabilities, reason, hours, status, decided_by_id, decided_by_label, decision_note, decided_at, granted_until, created_at) FROM stdin;
4d6e1d0a-ac93-45a7-a5a2-ee52f122ee3d	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Preciso emitir a guia da SEFAZ hoje	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	Ok ate o fim do dia	2026-10-19 12:56:49.159472+00	2026-10-19 16:56:49.159472+00	2026-10-19 12:56:49.052662+00
7b0894fd-f27b-4ebf-978b-07a2824691e0	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/infraestrutura/segredos/postgres-producao	["reveal"]	Investigar lentidao junto com a infra	2	revogada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	Acompanhada	2026-10-19 12:56:49.247149+00	2026-10-19 12:56:49.309226+00	2026-10-19 12:56:49.226303+00
b4885038-59dd-4b66-9362-309ae790af08	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 13:09:41.286671+00	2026-10-19 17:09:41.286671+00	2026-10-19 13:09:41.254951+00
a0c7b090-0e2c-47e1-847a-34a127d552c3	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 13:09:41.346762+00
c57c4b5c-7737-49f0-b78c-f148b52abb6b	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 13:09:58.741679+00	2026-10-19 17:09:58.741679+00	2026-10-19 13:09:58.714905+00
af58a404-2757-47bf-a18b-5bec84360ac4	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 13:09:58.786315+00
af4f33a9-8b46-4f98-9b6e-3668d686ef36	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 14:24:17.203162+00	2026-10-19 18:24:17.203162+00	2026-10-19 14:24:17.171734+00
174fa9aa-1808-41db-9bf3-f4051faf536c	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 14:24:17.247452+00
5f1dc8c0-d54a-4ace-8dc0-60278a398066	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 14:43:22.651392+00	2026-10-19 18:43:22.651392+00	2026-10-19 14:43:22.629551+00
2ee3cd50-65fe-482a-95e0-e37f13120691	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 14:43:22.688699+00
4ac85d40-6a5f-4af5-bab2-552d66ea0ef8	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 15:49:31.146183+00	2026-10-19 19:49:31.146183+00	2026-10-19 15:49:31.112911+00
9b945f65-c6b4-4481-b150-00e4d317a4ff	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 15:49:31.201453+00
ace1a5dc-7243-4365-be7f-b74b7a3b2638	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 17:11:50.248531+00	2026-10-19 21:11:50.248531+00	2026-10-19 17:11:50.163067+00
3e88e4db-8523-4489-81eb-fc95e4e7860a	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 17:11:50.334729+00
cd6343da-2f04-42a7-b602-9c178f8e88dd	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 17:33:25.256844+00	2026-10-19 21:33:25.256844+00	2026-10-19 17:33:25.22961+00
c20982fa-6799-4310-8472-8dba9dc69bd7	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 17:33:25.327599+00
44344f4c-f03f-4ed3-80c8-0569ea9c977c	fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	cofres/contabil/segredos/token-sefaz	["reveal"]	Tentativa de furar o deny	4	aprovada	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	aprovado	2026-10-19 18:39:43.940336+00	2026-10-19 22:39:43.940336+00	2026-10-19 18:39:43.895818+00
cecad6fa-3940-4886-914b-f1b67f60138b	9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	cofres/rh/segredos/portal-folha	["reveal"]	Pedido do proprio admin	1	pendente	\N			\N	\N	2026-10-19 18:39:43.997681+00
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.usuarios (id, email, full_name, password_hash, is_active, mfa_secret_ciphertext, mfa_secret_nonce, mfa_secret_wrapped_dek, mfa_key_id, mfa_enabled, created_at, apelido, foto) FROM stdin;
9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	ana.souza@exemplo.com.br	Administrador	$argon2id$v=19$m=65536,t=3,p=4$bCT5uiLH6oqVwDcwRcdPjA$qQ63w76nxoSJRFFwqUldneLlkUUYWXm8YywL4DSdk7Y	t	\N	\N	\N	\N	f	2026-10-17 21:37:38.493771+00		
fa35153a-5db9-4796-b6b3-7f782b714df4	contador@exemplo.com.br	Ana Contadora	$argon2id$v=19$m=65536,t=3,p=4$B/mtCxZA/CplCUq+mZ9W2w$fkycf6U7s+RHzIVgH6UMFHUh1l2NNfHyXos5vkk7f0g	t	\N	\N	\N	\N	f	2026-10-17 21:37:39.927513+00		
\.


--
-- Data for Name: usuarios_papeis; Type: TABLE DATA; Schema: public; Owner: vault
--

COPY public.usuarios_papeis (user_id, role_id) FROM stdin;
9a2e986f-f6ce-46d1-a90b-6be2ed2e18b3	3a31e3cc-3709-4df4-b46d-4f61222390b0
fa35153a-5db9-4796-b6b3-7f782b714df4	200c60cf-465e-488c-8cbb-22e5530cc617
\.


--
-- Name: api_chamadas api_chamadas_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.api_chamadas
    ADD CONSTRAINT api_chamadas_pkey PRIMARY KEY (id);


--
-- Name: aplicacoes_credenciais aplicacoes_credenciais_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes_credenciais
    ADD CONSTRAINT aplicacoes_credenciais_pkey PRIMARY KEY (id);


--
-- Name: aplicacoes_leases aplicacoes_leases_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes_leases
    ADD CONSTRAINT aplicacoes_leases_pkey PRIMARY KEY (id);


--
-- Name: aplicacoes aplicacoes_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes
    ADD CONSTRAINT aplicacoes_pkey PRIMARY KEY (id);


--
-- Name: auditoria_ancoras auditoria_ancoras_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.auditoria_ancoras
    ADD CONSTRAINT auditoria_ancoras_pkey PRIMARY KEY (id);


--
-- Name: auditoria_ancoras auditoria_ancoras_sequence_key; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.auditoria_ancoras
    ADD CONSTRAINT auditoria_ancoras_sequence_key UNIQUE (sequence);


--
-- Name: auditoria_eventos auditoria_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.auditoria_eventos
    ADD CONSTRAINT auditoria_eventos_pkey PRIMARY KEY (id);


--
-- Name: certificados certificados_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.certificados
    ADD CONSTRAINT certificados_pkey PRIMARY KEY (id);


--
-- Name: chaves_api chaves_api_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.chaves_api
    ADD CONSTRAINT chaves_api_pkey PRIMARY KEY (id);


--
-- Name: cofres cofres_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.cofres
    ADD CONSTRAINT cofres_pkey PRIMARY KEY (id);


--
-- Name: cofres_selos cofres_selos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.cofres_selos
    ADD CONSTRAINT cofres_selos_pkey PRIMARY KEY (id);


--
-- Name: configuracao configuracao_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.configuracao
    ADD CONSTRAINT configuracao_pkey PRIMARY KEY (id);


--
-- Name: convites convites_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.convites
    ADD CONSTRAINT convites_pkey PRIMARY KEY (id);


--
-- Name: credenciais_custodias credenciais_custodias_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais_custodias
    ADD CONSTRAINT credenciais_custodias_pkey PRIMARY KEY (id);


--
-- Name: credenciais credenciais_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais
    ADD CONSTRAINT credenciais_pkey PRIMARY KEY (id);


--
-- Name: dispositivos dispositivos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.dispositivos
    ADD CONSTRAINT dispositivos_pkey PRIMARY KEY (id);


--
-- Name: integracoes_destinos integracoes_destinos_name_key; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.integracoes_destinos
    ADD CONSTRAINT integracoes_destinos_name_key UNIQUE (name);


--
-- Name: integracoes_destinos integracoes_destinos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.integracoes_destinos
    ADD CONSTRAINT integracoes_destinos_pkey PRIMARY KEY (id);


--
-- Name: integracoes_entregas integracoes_entregas_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.integracoes_entregas
    ADD CONSTRAINT integracoes_entregas_pkey PRIMARY KEY (id);


--
-- Name: papeis papeis_name_key; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.papeis
    ADD CONSTRAINT papeis_name_key UNIQUE (name);


--
-- Name: papeis papeis_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.papeis
    ADD CONSTRAINT papeis_pkey PRIMARY KEY (id);


--
-- Name: papeis_politicas papeis_politicas_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.papeis_politicas
    ADD CONSTRAINT papeis_politicas_pkey PRIMARY KEY (role_id, policy_id);


--
-- Name: pedidos_redefinicao pedidos_redefinicao_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.pedidos_redefinicao
    ADD CONSTRAINT pedidos_redefinicao_pkey PRIMARY KEY (id);


--
-- Name: politicas politicas_name_key; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.politicas
    ADD CONSTRAINT politicas_name_key UNIQUE (name);


--
-- Name: politicas politicas_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.politicas
    ADD CONSTRAINT politicas_pkey PRIMARY KEY (id);


--
-- Name: politicas_regras politicas_regras_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.politicas_regras
    ADD CONSTRAINT politicas_regras_pkey PRIMARY KEY (id);


--
-- Name: segredos segredos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos
    ADD CONSTRAINT segredos_pkey PRIMARY KEY (id);


--
-- Name: segredos_versoes segredos_versoes_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos_versoes
    ADD CONSTRAINT segredos_versoes_pkey PRIMARY KEY (id);


--
-- Name: sessoes_eventos sessoes_eventos_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.sessoes_eventos
    ADD CONSTRAINT sessoes_eventos_pkey PRIMARY KEY (id);


--
-- Name: sessoes sessoes_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.sessoes
    ADD CONSTRAINT sessoes_pkey PRIMARY KEY (id);


--
-- Name: solicitacoes_acesso solicitacoes_acesso_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.solicitacoes_acesso
    ADD CONSTRAINT solicitacoes_acesso_pkey PRIMARY KEY (id);


--
-- Name: auditoria_eventos uq_auditoria_sequencia; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.auditoria_eventos
    ADD CONSTRAINT uq_auditoria_sequencia UNIQUE (sequence);


--
-- Name: credenciais uq_credencial_por_dispositivo; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais
    ADD CONSTRAINT uq_credencial_por_dispositivo UNIQUE (device_id, name);


--
-- Name: segredos uq_segredo_nome_por_cofre; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos
    ADD CONSTRAINT uq_segredo_nome_por_cofre UNIQUE (vault_id, name);


--
-- Name: segredos_versoes uq_versao_por_segredo; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos_versoes
    ADD CONSTRAINT uq_versao_por_segredo UNIQUE (secret_id, version);


--
-- Name: usuarios_papeis usuarios_papeis_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.usuarios_papeis
    ADD CONSTRAINT usuarios_papeis_pkey PRIMARY KEY (user_id, role_id);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: ix_api_chamadas_aplicacao; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_aplicacao ON public.api_chamadas USING btree (aplicacao_id, recebida_em);


--
-- Name: ix_api_chamadas_caminho; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_caminho ON public.api_chamadas USING btree (caminho);


--
-- Name: ix_api_chamadas_metodo; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_metodo ON public.api_chamadas USING btree (metodo);


--
-- Name: ix_api_chamadas_origem; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_origem ON public.api_chamadas USING btree (origem);


--
-- Name: ix_api_chamadas_origem_tempo; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_origem_tempo ON public.api_chamadas USING btree (origem, recebida_em);


--
-- Name: ix_api_chamadas_recebida; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_recebida ON public.api_chamadas USING btree (recebida_em);


--
-- Name: ix_api_chamadas_resultado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_resultado ON public.api_chamadas USING btree (resultado);


--
-- Name: ix_api_chamadas_status; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_api_chamadas_status ON public.api_chamadas USING btree (status);


--
-- Name: ix_aplicacoes_credenciais_application_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_aplicacoes_credenciais_application_id ON public.aplicacoes_credenciais USING btree (application_id);


--
-- Name: ix_aplicacoes_credenciais_secret_hash; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_aplicacoes_credenciais_secret_hash ON public.aplicacoes_credenciais USING btree (secret_hash);


--
-- Name: ix_aplicacoes_leases_application_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_aplicacoes_leases_application_id ON public.aplicacoes_leases USING btree (application_id);


--
-- Name: ix_aplicacoes_leases_expires_at; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_aplicacoes_leases_expires_at ON public.aplicacoes_leases USING btree (expires_at);


--
-- Name: ix_aplicacoes_leases_token_hash; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_aplicacoes_leases_token_hash ON public.aplicacoes_leases USING btree (token_hash);


--
-- Name: ix_aplicacoes_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_aplicacoes_name ON public.aplicacoes USING btree (name);


--
-- Name: ix_aplicacoes_role_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_aplicacoes_role_id ON public.aplicacoes USING btree (role_id);


--
-- Name: ix_auditoria_ator; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_auditoria_ator ON public.auditoria_eventos USING btree (actor_id);


--
-- Name: ix_auditoria_eventos_action; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_auditoria_eventos_action ON public.auditoria_eventos USING btree (action);


--
-- Name: ix_auditoria_eventos_sequence; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_auditoria_eventos_sequence ON public.auditoria_eventos USING btree (sequence);


--
-- Name: ix_auditoria_eventos_target_path; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_auditoria_eventos_target_path ON public.auditoria_eventos USING btree (target_path);


--
-- Name: ix_auditoria_ocorrido; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_auditoria_ocorrido ON public.auditoria_eventos USING btree (occurred_at);


--
-- Name: ix_certificados_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_certificados_name ON public.certificados USING btree (name);


--
-- Name: ix_certificados_not_after; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_certificados_not_after ON public.certificados USING btree (not_after);


--
-- Name: ix_chaves_api_ambiente; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_chaves_api_ambiente ON public.chaves_api USING btree (ambiente);


--
-- Name: ix_chaves_api_estado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_chaves_api_estado ON public.chaves_api USING btree (estado);


--
-- Name: ix_chaves_api_expira_em; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_chaves_api_expira_em ON public.chaves_api USING btree (expira_em);


--
-- Name: ix_chaves_api_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_chaves_api_name ON public.chaves_api USING btree (name);


--
-- Name: ix_chaves_api_servico; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_chaves_api_servico ON public.chaves_api USING btree (servico);


--
-- Name: ix_cofres_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_cofres_name ON public.cofres USING btree (name);


--
-- Name: ix_cofres_selos_vault_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_cofres_selos_vault_id ON public.cofres_selos USING btree (vault_id);


--
-- Name: ix_convites_email; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_convites_email ON public.convites USING btree (email);


--
-- Name: ix_convites_estado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_convites_estado ON public.convites USING btree (estado);


--
-- Name: ix_convites_expira_em; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_convites_expira_em ON public.convites USING btree (expira_em);


--
-- Name: ix_convites_token_hash; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_convites_token_hash ON public.convites USING btree (token_hash);


--
-- Name: ix_credenciais_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_credenciais_name ON public.credenciais USING btree (name);


--
-- Name: ix_custodia_credencial; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_custodia_credencial ON public.credenciais_custodias USING btree (credential_id);


--
-- Name: ix_dispositivos_name; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_dispositivos_name ON public.dispositivos USING btree (name);


--
-- Name: ix_evento_sessao_ordem; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_evento_sessao_ordem ON public.sessoes_eventos USING btree (sessao_id, deslocamento_ms);


--
-- Name: ix_integracoes_destinos_estado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_destinos_estado ON public.integracoes_destinos USING btree (estado);


--
-- Name: ix_integracoes_entregas_destino_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_entregas_destino_id ON public.integracoes_entregas USING btree (destino_id);


--
-- Name: ix_integracoes_entregas_estado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_entregas_estado ON public.integracoes_entregas USING btree (estado);


--
-- Name: ix_integracoes_entregas_id_evento; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_entregas_id_evento ON public.integracoes_entregas USING btree (id_evento);


--
-- Name: ix_integracoes_entregas_proxima_em; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_entregas_proxima_em ON public.integracoes_entregas USING btree (proxima_em);


--
-- Name: ix_integracoes_entregas_tipo; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_integracoes_entregas_tipo ON public.integracoes_entregas USING btree (tipo);


--
-- Name: ix_pedidos_redefinicao_atendido; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_pedidos_redefinicao_atendido ON public.pedidos_redefinicao USING btree (atendido);


--
-- Name: ix_pedidos_redefinicao_email; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_pedidos_redefinicao_email ON public.pedidos_redefinicao USING btree (email);


--
-- Name: ix_segredo_cofre_ativo; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_segredo_cofre_ativo ON public.segredos USING btree (vault_id, deleted_at);


--
-- Name: ix_sessoes_alvo; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_sessoes_alvo ON public.sessoes USING btree (alvo);


--
-- Name: ix_sessoes_estado; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_sessoes_estado ON public.sessoes USING btree (estado);


--
-- Name: ix_sessoes_eventos_sessao_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_sessoes_eventos_sessao_id ON public.sessoes_eventos USING btree (sessao_id);


--
-- Name: ix_sessoes_usuario_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_sessoes_usuario_id ON public.sessoes USING btree (usuario_id);


--
-- Name: ix_solicitacoes_acesso_path; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_solicitacoes_acesso_path ON public.solicitacoes_acesso USING btree (path);


--
-- Name: ix_solicitacoes_acesso_requester_id; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_solicitacoes_acesso_requester_id ON public.solicitacoes_acesso USING btree (requester_id);


--
-- Name: ix_solicitacoes_acesso_status; Type: INDEX; Schema: public; Owner: vault
--

CREATE INDEX ix_solicitacoes_acesso_status ON public.solicitacoes_acesso USING btree (status);


--
-- Name: ix_usuarios_email; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX ix_usuarios_email ON public.usuarios USING btree (email);


--
-- Name: uq_custodia_aberta; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX uq_custodia_aberta ON public.credenciais_custodias USING btree (credential_id) WHERE (returned_at IS NULL);


--
-- Name: uq_selo_ativo_por_cofre; Type: INDEX; Schema: public; Owner: vault
--

CREATE UNIQUE INDEX uq_selo_ativo_por_cofre ON public.cofres_selos USING btree (vault_id) WHERE (desselado_em IS NULL);


--
-- Name: aplicacoes aplicacoes_application_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes
    ADD CONSTRAINT aplicacoes_application_role_id_fkey FOREIGN KEY (application_role_id) REFERENCES public.papeis(id) ON DELETE RESTRICT;


--
-- Name: aplicacoes_credenciais aplicacoes_credenciais_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes_credenciais
    ADD CONSTRAINT aplicacoes_credenciais_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.aplicacoes(id) ON DELETE CASCADE;


--
-- Name: aplicacoes_leases aplicacoes_leases_application_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes_leases
    ADD CONSTRAINT aplicacoes_leases_application_id_fkey FOREIGN KEY (application_id) REFERENCES public.aplicacoes(id) ON DELETE CASCADE;


--
-- Name: aplicacoes_leases aplicacoes_leases_secret_id_usado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.aplicacoes_leases
    ADD CONSTRAINT aplicacoes_leases_secret_id_usado_fkey FOREIGN KEY (secret_id_usado) REFERENCES public.aplicacoes_credenciais(id) ON DELETE CASCADE;


--
-- Name: certificados certificados_secret_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.certificados
    ADD CONSTRAINT certificados_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.segredos(id) ON DELETE SET NULL;


--
-- Name: chaves_api chaves_api_secret_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.chaves_api
    ADD CONSTRAINT chaves_api_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.segredos(id) ON DELETE SET NULL;


--
-- Name: cofres_selos cofres_selos_vault_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.cofres_selos
    ADD CONSTRAINT cofres_selos_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.cofres(id) ON DELETE CASCADE;


--
-- Name: credenciais_custodias credenciais_custodias_credential_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais_custodias
    ADD CONSTRAINT credenciais_custodias_credential_id_fkey FOREIGN KEY (credential_id) REFERENCES public.credenciais(id) ON DELETE CASCADE;


--
-- Name: credenciais_custodias credenciais_custodias_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais_custodias
    ADD CONSTRAINT credenciais_custodias_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: credenciais credenciais_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais
    ADD CONSTRAINT credenciais_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.dispositivos(id) ON DELETE CASCADE;


--
-- Name: credenciais credenciais_secret_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.credenciais
    ADD CONSTRAINT credenciais_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.segredos(id) ON DELETE SET NULL;


--
-- Name: integracoes_entregas integracoes_entregas_destino_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.integracoes_entregas
    ADD CONSTRAINT integracoes_entregas_destino_id_fkey FOREIGN KEY (destino_id) REFERENCES public.integracoes_destinos(id) ON DELETE CASCADE;


--
-- Name: papeis_politicas papeis_politicas_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.papeis_politicas
    ADD CONSTRAINT papeis_politicas_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.politicas(id) ON DELETE CASCADE;


--
-- Name: papeis_politicas papeis_politicas_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.papeis_politicas
    ADD CONSTRAINT papeis_politicas_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.papeis(id) ON DELETE CASCADE;


--
-- Name: politicas_regras politicas_regras_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.politicas_regras
    ADD CONSTRAINT politicas_regras_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.politicas(id) ON DELETE CASCADE;


--
-- Name: segredos segredos_vault_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos
    ADD CONSTRAINT segredos_vault_id_fkey FOREIGN KEY (vault_id) REFERENCES public.cofres(id) ON DELETE CASCADE;


--
-- Name: segredos_versoes segredos_versoes_secret_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.segredos_versoes
    ADD CONSTRAINT segredos_versoes_secret_id_fkey FOREIGN KEY (secret_id) REFERENCES public.segredos(id) ON DELETE CASCADE;


--
-- Name: sessoes_eventos sessoes_eventos_sessao_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.sessoes_eventos
    ADD CONSTRAINT sessoes_eventos_sessao_id_fkey FOREIGN KEY (sessao_id) REFERENCES public.sessoes(id) ON DELETE CASCADE;


--
-- Name: sessoes sessoes_usuario_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.sessoes
    ADD CONSTRAINT sessoes_usuario_id_fkey FOREIGN KEY (usuario_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: solicitacoes_acesso solicitacoes_acesso_decided_by_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.solicitacoes_acesso
    ADD CONSTRAINT solicitacoes_acesso_decided_by_id_fkey FOREIGN KEY (decided_by_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: solicitacoes_acesso solicitacoes_acesso_requester_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.solicitacoes_acesso
    ADD CONSTRAINT solicitacoes_acesso_requester_id_fkey FOREIGN KEY (requester_id) REFERENCES public.usuarios(id) ON DELETE RESTRICT;


--
-- Name: usuarios_papeis usuarios_papeis_role_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.usuarios_papeis
    ADD CONSTRAINT usuarios_papeis_role_id_fkey FOREIGN KEY (role_id) REFERENCES public.papeis(id) ON DELETE CASCADE;


--
-- Name: usuarios_papeis usuarios_papeis_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: vault
--

ALTER TABLE ONLY public.usuarios_papeis
    ADD CONSTRAINT usuarios_papeis_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict f5frQXSzRgi8PwdaQ7Stpm3hwCJ6LU1f4m1OuxQwBRs4BIDXqVVrIQVI51s2hi2

