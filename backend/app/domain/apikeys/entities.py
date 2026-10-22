"""Chaves de API: o governo de uma credencial de serviço.

Uma chave de API não é uma senha qualquer, e tratá-la como tal é o que faz
empresas descobrirem, no vazamento, que tinham 40 chaves ativas e não sabiam
de quais serviços nem de quem.

O que uma senha não tem e uma chave de API tem:

- **serviço e ambiente** — a mesma chave existe em produção e homologação, e
  confundi-las é incidente;
- **escopo** — "leitura de notas fiscais" não é "emitir pagamento", e sem
  registrar isso ninguém sabe o estrago possível se ela vazar;
- **onde está em uso** — chave que ninguém sabe onde roda é chave que ninguém
  troca, porque trocar pode quebrar algo invisível;
- **validade** — muitas expiram, e descobrir isso quando o robô para é a pior
  hora.

O **valor** continua sendo um segredo do cofre, cifrado como qualquer outro.
Esta entidade é o governo: ela aponta para o segredo, não o guarda.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum

from ..shared.errors import ConflictError, ValidationError
from ..shared.value_objects import PolicyPath, Slug, new_id, utcnow

# Faixa de alerta de validade. Igual à de certificados, pelo mesmo motivo:
# é o prazo mínimo para renovar algo que depende de terceiro sem virar
# urgência.
DIAS_DE_ALERTA = 30


class AmbienteDaChave(StrEnum):
    """Onde a chave vale. Misturar produção e teste é incidente clássico."""

    PRODUCAO = "producao"
    HOMOLOGACAO = "homologacao"
    DESENVOLVIMENTO = "desenvolvimento"


class EstadoDaChave(StrEnum):
    ATIVA = "ativa"
    REVOGADA = "revogada"
    EXPIRADA = "expirada"


class MetodoHttp(StrEnum):
    """Verbo da requisição de exemplo.

    Importa no exemplo porque `GET` e `POST` mudam o que a pessoa precisa
    enviar — e um exemplo que não roda é pior que nenhum.
    """

    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class FormatoDaChave(StrEnum):
    """Como a chave é apresentada ao serviço.

    Importa para quem vai usá-la: `Bearer <token>` e `?api_key=<token>` não
    são intercambiáveis, e a pessoa que pega a chave precisa saber qual é.
    """

    BEARER = "bearer"
    BASICO = "basico"          # usuário:senha em Base64
    CABECALHO = "cabecalho"    # cabeçalho próprio, ex.: X-API-Key
    QUERY = "query"            # parâmetro na URL
    OUTRO = "outro"


@dataclass(slots=True)
class ChaveDeApi:
    """Metadados de uma chave de API. O valor vive no cofre, cifrado."""

    name: Slug
    display_name: str
    servico: str
    ambiente: AmbienteDaChave = AmbienteDaChave.PRODUCAO
    formato: FormatoDaChave = FormatoDaChave.BEARER
    # Nome do cabeçalho ou do parâmetro, quando o formato exige.
    nome_do_campo: str = ""
    escopo: str = ""
    usada_em: list[str] = field(default_factory=list)
    responsavel: str = ""
    documentacao_url: str = ""
    # **Endereço e rota de exemplo.** Saber que a chave vai em
    # `Authorization: Bearer` não diz *contra o quê*: sem a URL, quem pega a
    # chave ainda precisa caçar a documentação para a primeira chamada. Com
    # ela, a tela monta uma requisição copiável.
    #
    # Opcionais de propósito: nem todo serviço tem uma rota única que sirva de
    # exemplo, e exigir inventaria endereços falsos — que é pior que o vazio.
    url_base: str = ""
    metodo: MetodoHttp = MetodoHttp.GET
    rota_exemplo: str = ""
    secret_id: str | None = None
    vault_name: str = ""
    secret_name: str = ""
    expira_em: datetime | None = None
    estado: EstadoDaChave = EstadoDaChave.ATIVA
    revogada_em: datetime | None = None
    criado_por: str = ""
    created_at: datetime = field(default_factory=utcnow)
    id: str = field(default_factory=new_id)

    def __post_init__(self) -> None:
        if not self.display_name.strip():
            raise ValidationError("A chave precisa de um nome visível.")
        if not self.servico.strip():
            raise ValidationError(
                "Informe o serviço. Chave sem serviço conhecido é chave que "
                "ninguém sabe o que quebra ao revogar."
            )
        if not self.responsavel.strip():
            raise ValidationError(
                "A chave precisa de um responsável. Credencial sem dono é "
                "credencial que ninguém revoga."
            )
        if self.formato in (FormatoDaChave.CABECALHO, FormatoDaChave.QUERY):
            if not self.nome_do_campo.strip():
                raise ValidationError(
                    "Informe o nome do cabeçalho ou do parâmetro: sem ele, "
                    "quem pegar a chave não sabe como enviá-la."
                )
        self.url_base = self.url_base.strip().rstrip("/")
        if self.url_base and not self.url_base.startswith(("http://", "https://")):
            raise ValidationError(
                "O endereço precisa começar com http:// ou https://. Sem o "
                "esquema, o exemplo não roda em lugar nenhum."
            )
        # Lugar de uso repetido só polui o relatório.
        self.usada_em = sorted({u.strip() for u in self.usada_em if u.strip()})

    @property
    def path(self) -> PolicyPath:
        return PolicyPath(f"chaves-api/{self.name}")

    @property
    def esta_ativa(self) -> bool:
        return self.estado is EstadoDaChave.ATIVA

    def dias_para_vencer(self, now: datetime | None = None) -> int | None:
        if self.expira_em is None or not self.esta_ativa:
            return None
        return (self.expira_em - (now or utcnow())).days

    def situacao(self, now: datetime | None = None) -> EstadoDaChave:
        """Estado efetivo, considerando a validade.

        Expiração não precisa de alguém marcar: ela acontece pelo relógio, e
        depender de um job para refletir isso faria o painel mentir enquanto
        o job não roda.
        """
        if self.estado is EstadoDaChave.REVOGADA:
            return EstadoDaChave.REVOGADA
        if self.expira_em is not None and (now or utcnow()) >= self.expira_em:
            return EstadoDaChave.EXPIRADA
        return EstadoDaChave.ATIVA

    def vencendo(self, dias: int = DIAS_DE_ALERTA, now: datetime | None = None) -> bool:
        restantes = self.dias_para_vencer(now)
        return restantes is not None and 0 <= restantes <= dias

    def revogar(self, at: datetime | None = None) -> None:
        if self.estado is EstadoDaChave.REVOGADA:
            raise ConflictError("Esta chave já foi revogada.")
        self.estado = EstadoDaChave.REVOGADA
        self.revogada_em = at or utcnow()

    def como_usar(self) -> str:
        """Instrução pronta para quem vai consumir a chave.

        O valor nunca aparece aqui — sai como marcador. Quem precisa do valor
        revela o segredo no cofre, e isso vira evento de auditoria.
        """
        if self.formato is FormatoDaChave.BEARER:
            return "Authorization: Bearer <valor>"
        if self.formato is FormatoDaChave.BASICO:
            return "Authorization: Basic <usuario:senha em Base64>"
        if self.formato is FormatoDaChave.CABECALHO:
            return f"{self.nome_do_campo}: <valor>"
        if self.formato is FormatoDaChave.QUERY:
            return f"?{self.nome_do_campo}=<valor>"
        return "Consulte a documentação do serviço."

    def endereco_exemplo(self) -> str:
        """URL completa do exemplo, já com a chave quando ela vai na query."""
        if not self.url_base:
            return ""
        rota = self.rota_exemplo.strip()
        if rota and not rota.startswith("/"):
            rota = "/" + rota
        url = f"{self.url_base}{rota}"
        if self.formato is FormatoDaChave.QUERY and self.nome_do_campo:
            juncao = "&" if "?" in url else "?"
            url = f"{url}{juncao}{self.nome_do_campo}=<valor>"
        return url

    def requisicao_exemplo(self) -> list[tuple[str, str]]:
        """A requisição montada, em pares (rótulo, valor).

        Pares e não texto pronto: a tela precisa dos pedaços separados para
        destacar o cabeçalho, oferecer cópia por linha e montar o `curl`. Uma
        string única obrigaria a tela a cortá-la de volta — e aí cada tela
        cortaria de um jeito.

        O valor **nunca** entra: sai como `<valor>`. Exemplo com chave de
        verdade vira chave em print, em chamado e em histórico de navegador.
        """
        linhas: list[tuple[str, str]] = []
        endereco = self.endereco_exemplo()
        if endereco:
            linhas.append(("metodo", f"{self.metodo} {endereco}"))
        if self.formato is not FormatoDaChave.QUERY:
            linhas.append(("cabecalho", self.como_usar()))
        return linhas

    def curl_exemplo(self) -> str:
        """O mesmo exemplo como comando `curl`, pronto para colar.

        Vazio sem endereço: um `curl` sem URL não ensina nada e ainda dá a
        impressão de que falta só preencher um buraco.
        """
        endereco = self.endereco_exemplo()
        if not endereco:
            return ""
        partes = ["curl"]
        if self.metodo is not MetodoHttp.GET:
            partes.append(f"-X {self.metodo}")
        if self.formato is not FormatoDaChave.QUERY:
            partes.append(f"-H '{self.como_usar()}'")
        partes.append(f"'{endereco}'")
        return " ".join(partes)


def expirar_vencidas(
    chaves: list[ChaveDeApi], now: datetime | None = None
) -> list[ChaveDeApi]:
    """Marca como expiradas as que passaram da validade.

    Função pura sobre a lista: quem chama decide quando rodar. O estado
    efetivo já é calculado por `situacao`, então isto serve só para
    persistir a mudança — a tela não depende dele para mostrar a verdade.
    """
    agora = now or utcnow()
    mudaram = []
    for chave in chaves:
        if (
            chave.estado is EstadoDaChave.ATIVA
            and chave.expira_em is not None
            and agora >= chave.expira_em
        ):
            chave.estado = EstadoDaChave.EXPIRADA
            mudaram.append(chave)
    return mudaram
