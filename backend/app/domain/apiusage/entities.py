"""Chamadas que o Vault RECEBE pela API, e o que se governa sobre elas.

A trilha de auditoria responde *o que foi feito* — "segredo revelado",
"cofre selado". Este domínio responde outra coisa: **quem está batendo na
API, em quais rotas, com que resultado**. São perguntas diferentes, e a
segunda não se extrai da primeira: uma varredura que leva 401 em todas as
tentativas não produz nenhum evento de negócio, e é exatamente o que mais
interessa ver.

## O recorte: chamada externa, não chamada da própria tela

O Vault é uma aplicação web; cada tela faz dezenas de requisições por
minuto. Registrar isso afogaria o que importa — o consumo de fora — numa
massa de chamadas da própria interface. Então o registro cobre **quem
consome a API de fora**: aplicações e RPAs autenticados por AppRole,
scripts com `curl`, integrações de parceiros.

A classificação está em `Origem.classificar`, e ela erra para o lado de
**registrar**: diante da dúvida, a chamada entra. Uma linha a mais no
relatório é barulho; uma a menos é um consumidor invisível.

## O corpo da requisição não entra aqui — em lugar nenhum

Nenhuma entidade deste módulo tem campo para o conteúdo enviado. Só o
**tamanho** em bytes, que vem do cabeçalho e não exige ler o fluxo. A razão
é direta: uma requisição que cria um segredo carrega a senha no corpo, e
guardá-la numa tabela de log desfaz todo o resto do sistema — a senha
estaria em claro, fora do cofre, sem cifragem de envelope e sem política.

Isso é uma restrição do **domínio**, não da tela: não existe campo a
preencher, então nenhum adaptador futuro pode passar a gravar o corpo sem
alterar esta entidade de propósito.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from ..shared.errors import ValidationError
from ..shared.value_objects import new_id, utcnow

# Teto do caminho guardado. Caminho mais longo que isto é tentativa de
# estouro de buffer ou URL de ataque; guardar o começo basta para
# reconhecê-la, e guardar tudo encheria a tabela a mando de quem ataca.
CAMINHO_MAXIMO = 400

# O mesmo para o agente declarado pelo cliente: campo livre, controlado por
# quem chama, e por isso limitado aqui.
AGENTE_MAXIMO = 200


class Origem(StrEnum):
    """De onde partiu a chamada.

    `TELA` é a própria interface do Vault no navegador. É a única que fica
    **fora** do relatório, porque é o próprio sistema conversando consigo
    mesmo.
    """

    TELA = "tela"
    APLICACAO = "aplicacao"
    EXTERNA = "externa"

    @staticmethod
    def classificar(*, tem_lease: bool, origin: str | None, sec_fetch_site: str | None,
                    origens_da_tela: tuple[str, ...]) -> Origem:
        """Decide a origem a partir do que a requisição traz.

        Ordem deliberada:

        1. **Lease de aplicação** vence tudo. Um RPA autenticado por AppRole
           é consumo de máquina mesmo que, por configuração estranha, os
           cabeçalhos cheguem parecidos com os da tela.
        2. **`Sec-Fetch-Site: same-origin`** é a tela. Quem decide é este
           cabeçalho e não o `Origin`, porque `Sec-Fetch-Site` é preenchido
           pelo **navegador** e JavaScript não consegue alterá-lo; `curl` e
           script podem mandar o valor que quiserem em `Origin`, mas aí não
           há navegador, e é exatamente o consumo que queremos ver.

           Quando `Origin` **vem**, ele ainda precisa bater com a lista: é o
           caso do front servido de outra porta (dev server), em que o
           navegador manda os dois.

           `Origin` ausente é o caso NORMAL em produção, não uma anomalia: a
           página e a API ficam no mesmo host atrás do nginx, e o navegador
           omite `Origin` em GET same-origin. Exigi-lo foi um bug — toda a
           navegação entrava no relatório como externa, e o recorte pedido
           deixava de valer justo no ambiente que importa.
        3. Qualquer outra coisa é externa.

        O passo 2 é a única porta para sair do relatório, e ela é estreita
        de propósito: na dúvida, registra.
        """
        if tem_lease:
            return Origem.APLICACAO
        if sec_fetch_site == "same-origin" and (
            origin is None or origin in origens_da_tela
        ):
            return Origem.TELA
        return Origem.EXTERNA


class Resultado(StrEnum):
    """O desfecho, em faixas de status HTTP.

    Faixa e não o número cru porque é assim que se lê um relatório de uso:
    "quantas recusadas" importa mais que a diferença entre 401 e 403, e o
    status exato continua guardado no registro.
    """

    OK = "ok"                    # 2xx
    REDIRECIONADO = "redirecionado"  # 3xx
    RECUSADO = "recusado"        # 401, 403
    INVALIDO = "invalido"        # demais 4xx
    ERRO = "erro"                # 5xx

    @staticmethod
    def da_resposta(status: int) -> Resultado:
        if status in (401, 403):
            return Resultado.RECUSADO
        if 200 <= status < 300:
            return Resultado.OK
        if 300 <= status < 400:
            return Resultado.REDIRECIONADO
        if 400 <= status < 500:
            return Resultado.INVALIDO
        return Resultado.ERRO


@dataclass(frozen=True, slots=True)
class ChamadaDeApi:
    """Uma requisição recebida, do ponto de vista de quem governa a API.

    Imutável: um registro de uso que pode ser corrigido depois não serve
    para auditar nada.
    """

    id: str
    recebida_em: datetime
    metodo: str
    caminho: str
    status: int
    resultado: Resultado
    origem: Origem
    # Quem chamou, quando dá para saber. Aplicação e pessoa são exclusivos
    # entre si: uma chamada tem lease OU token de pessoa, nunca os dois.
    aplicacao_id: str | None
    aplicacao_nome: str
    usuario_id: str | None
    usuario_email: str
    ip: str
    agente: str
    duracao_ms: int
    # Tamanho declarado no `Content-Length`. O CONTEÚDO não é guardado em
    # lugar nenhum — ver a nota no topo do módulo.
    bytes_recebidos: int

    def __post_init__(self) -> None:
        if not self.metodo:
            raise ValidationError("A chamada precisa de método HTTP.")
        if not self.caminho:
            raise ValidationError("A chamada precisa de caminho.")
        if len(self.caminho) > CAMINHO_MAXIMO:
            raise ValidationError(
                f"O caminho excede {CAMINHO_MAXIMO} caracteres."
            )
        if len(self.agente) > AGENTE_MAXIMO:
            raise ValidationError(f"O agente excede {AGENTE_MAXIMO} caracteres.")
        if self.duracao_ms < 0:
            raise ValidationError("A duração não pode ser negativa.")
        if self.bytes_recebidos < 0:
            raise ValidationError("O tamanho recebido não pode ser negativo.")
        if self.aplicacao_id is not None and self.usuario_id is not None:
            # Lease e token de pessoa são caminhos de autenticação
            # distintos. As duas coisas juntas significa que o adaptador
            # misturou identidades, e um registro de uso com dois donos não
            # responde "quem chamou" — que é a única pergunta que ele existe
            # para responder.
            raise ValidationError(
                "Uma chamada não pode ser de aplicação e de pessoa ao mesmo tempo."
            )

    @property
    def quem(self) -> str:
        """Rótulo de quem chamou, para listar sem precisar cruzar tabelas."""
        if self.aplicacao_nome:
            return self.aplicacao_nome
        if self.usuario_email:
            return self.usuario_email
        return "anônimo"

    @property
    def anonima(self) -> bool:
        """Chamada sem identidade reconhecida.

        É o caso de quem erra a credencial: ninguém sabe quem é, e é a linha
        que mais interessa quando aparecem muitas seguidas.
        """
        return self.aplicacao_id is None and self.usuario_id is None


def registrar_chamada(
    *,
    metodo: str,
    caminho: str,
    status: int,
    origem: Origem,
    duracao_ms: int,
    ip: str = "",
    agente: str = "",
    aplicacao_id: str | None = None,
    aplicacao_nome: str = "",
    usuario_id: str | None = None,
    usuario_email: str = "",
    bytes_recebidos: int = 0,
    quando: datetime | None = None,
) -> ChamadaDeApi:
    """Monta o registro, derivando o que é derivável.

    O caminho e o agente são **truncados**, não recusados: a chamada já
    aconteceu e já foi respondida, e perder o registro dela porque a URL era
    comprida inverteria a finalidade — justo a requisição anômala sumiria.
    """
    return ChamadaDeApi(
        id=new_id(),
        recebida_em=quando or utcnow(),
        metodo=metodo.upper()[:10],
        caminho=caminho[:CAMINHO_MAXIMO],
        status=status,
        resultado=Resultado.da_resposta(status),
        origem=origem,
        aplicacao_id=aplicacao_id,
        aplicacao_nome=aplicacao_nome[:200],
        usuario_id=usuario_id,
        usuario_email=usuario_email[:254],
        ip=ip[:60],
        agente=agente[:AGENTE_MAXIMO],
        duracao_ms=duracao_ms,
        bytes_recebidos=bytes_recebidos,
    )
