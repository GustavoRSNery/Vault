"""Configurações operacionais ajustáveis pela interface.

A pergunta que separa o que entra aqui do que não entra: **se alguém escolher
o pior valor possível, isso enfraquece a segurança do sistema?**

Entram as decisões operacionais — quanto tempo um segredo fica visível, prazo
padrão de custódia, faixa de alerta de certificado. O pior valor delas é
inconveniente, não inseguro.

Ficam de fora, deliberadamente, como constantes no código:

- `LIMIAR_MINIMO = 2` do quórum. Ajustável, viraria 1 na primeira vez que
  alguém se irritasse com a cerimônia — e aí selar não protege de nada.
- `TOKEN_BYTES`, `SECRET_ID_BYTES`, `DEK_BYTES`. Tamanho de material
  criptográfico não é preferência; ajustável, é só o caminho para alguém
  enfraquecê-lo sem saber o que está fazendo.
- `LEASE_MINUTOS_MAXIMO`. O teto existe para que "temporário" signifique algo.
- `NONCE_BYTES`. Mudar quebraria todo dado já cifrado.

Configuração que permite desligar a própria proteção é pior que configuração
nenhuma: dá a impressão de flexibilidade e entrega um sistema que se desarma
sozinho na primeira pressa.

Há exatamente **uma linha** de configuração por instalação. Não é por
simplicidade: configuração por cofre ou por equipe produziria combinações que
ninguém revisa, e a pergunta "qual prazo vale aqui?" deixaria de ter resposta
única.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..shared.errors import ValidationError
from ..shared.value_objects import utcnow

# Limites de cada ajuste. São amplos onde o risco é baixo e estreitos onde não
# é — o objetivo é impedir o valor absurdo, não tutelar a escolha.
SEGUNDOS_VISIVEL_MIN, SEGUNDOS_VISIVEL_MAX = 5, 300
CUSTODIA_HORAS_MIN, CUSTODIA_HORAS_MAX = 1, 720
ALERTA_CERTIFICADO_MIN, ALERTA_CERTIFICADO_MAX = 7, 180
ROTACAO_PADRAO_MIN, ROTACAO_PADRAO_MAX = 0, 3650
TRILHA_LIMITE_MIN, TRILHA_LIMITE_MAX = 50, 1000


@dataclass(slots=True)
class ConfiguracaoOperacional:
    """Os ajustes que uma instalação pode fazer sem tocar no código."""

    segundos_segredo_visivel: int = 30
    custodia_horas_padrao: int = 4
    alerta_certificado_dias: int = 30
    rotacao_dias_padrao: int = 90
    trilha_limite_padrao: int = 200
    atualizado_por: str = ""
    atualizado_em: datetime = field(default_factory=utcnow)
    id: str = "unica"

    def __post_init__(self) -> None:
        self._faixa(
            "segundos_segredo_visivel",
            self.segundos_segredo_visivel,
            SEGUNDOS_VISIVEL_MIN,
            SEGUNDOS_VISIVEL_MAX,
            "Menos de 5 s não dá tempo de copiar; mais de 5 min é segredo "
            "exposto na tela de quem saiu para o café.",
        )
        self._faixa(
            "custodia_horas_padrao",
            self.custodia_horas_padrao,
            CUSTODIA_HORAS_MIN,
            CUSTODIA_HORAS_MAX,
            "O prazo de custódia vai de 1 hora a 30 dias.",
        )
        self._faixa(
            "alerta_certificado_dias",
            self.alerta_certificado_dias,
            ALERTA_CERTIFICADO_MIN,
            ALERTA_CERTIFICADO_MAX,
            "Menos de 7 dias não dá tempo de renovar emissão manual; mais de "
            "180 deixa quase tudo em alerta permanente, e alerta permanente "
            "é alerta ignorado.",
        )
        self._faixa(
            "rotacao_dias_padrao",
            self.rotacao_dias_padrao,
            ROTACAO_PADRAO_MIN,
            ROTACAO_PADRAO_MAX,
            "O prazo padrão de rotação vai de 0 (não rotaciona) a 10 anos.",
        )
        self._faixa(
            "trilha_limite_padrao",
            self.trilha_limite_padrao,
            TRILHA_LIMITE_MIN,
            TRILHA_LIMITE_MAX,
            "A trilha mostra de 50 a 1000 eventos por página.",
        )

    @staticmethod
    def _faixa(campo: str, valor: int, minimo: int, maximo: int, porque: str) -> None:
        if not minimo <= valor <= maximo:
            raise ValidationError(
                f"{campo}: {valor} fora da faixa {minimo}–{maximo}. {porque}"
            )

    def com(self, **mudancas) -> ConfiguracaoOperacional:  # noqa: ANN003
        """Devolve uma cópia com os campos alterados, já validada.

        Validar na construção e não no `setattr` é o que garante que nunca
        existe uma configuração inválida em memória, nem por um instante.
        """
        atual = {
            "segundos_segredo_visivel": self.segundos_segredo_visivel,
            "custodia_horas_padrao": self.custodia_horas_padrao,
            "alerta_certificado_dias": self.alerta_certificado_dias,
            "rotacao_dias_padrao": self.rotacao_dias_padrao,
            "trilha_limite_padrao": self.trilha_limite_padrao,
            "atualizado_por": self.atualizado_por,
        }
        atual.update({k: v for k, v in mudancas.items() if v is not None})
        return ConfiguracaoOperacional(**atual, atualizado_em=utcnow())

    def diferencas(self, outra: ConfiguracaoOperacional) -> list[str]:
        """O que mudou, em texto — para a trilha de auditoria.

        A trilha precisa dizer o antes e o depois: "configuração alterada" não
        permite revisar nada, e é justamente o tipo de mudança silenciosa que
        uma auditoria procura.
        """
        campos = [
            ("segundos_segredo_visivel", "segredo visível"),
            ("custodia_horas_padrao", "custódia padrão"),
            ("alerta_certificado_dias", "alerta de certificado"),
            ("rotacao_dias_padrao", "rotação padrão"),
            ("trilha_limite_padrao", "limite da trilha"),
        ]
        return [
            f"{rotulo}: {getattr(self, campo)} -> {getattr(outra, campo)}"
            for campo, rotulo in campos
            if getattr(self, campo) != getattr(outra, campo)
        ]
