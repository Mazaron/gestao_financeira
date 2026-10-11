from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Categoria(models.Model):
    TIPOS = [("R", "Receita"), ("D", "Despesa")]

    nome = models.CharField(max_length=50)
    tipo = models.CharField(max_length=1, choices=TIPOS)

    def __str__(self):
        return self.nome


class Cartao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=50)
    dia_fechamento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)]
    )

    def __str__(self):
        return self.nome


class Lancamento(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT)
    descricao = models.CharField(max_length=100)
    valor_centavos = models.PositiveIntegerField()
    data = models.DateField()
    grupo = models.UUIDField(null=True, blank=True)
    parcela_atual = models.PositiveSmallIntegerField(null=True, blank=True)
    total_parcelas = models.PositiveSmallIntegerField(null=True, blank=True)
    cartao = models.ForeignKey(Cartao, null=True, blank=True, on_delete=models.PROTECT)
    data_compra = models.DateField(null=True, blank=True)

    @property
    def valor_reais(self):
        return self.valor_centavos / 100

    def __str__(self):
        return f"{self.descricao} ({self.valor_centavos / 100:.2f})"

class Investimento(models.Model):
    TIPOS = [
        ("renda_fixa", "Renda fixa tributada (CDB, LC...)"),
        ("renda_fixa_isenta", "LCI, LCA, CRI, CRA (isentos de IR)"),
        ("tesouro", "Tesouro Direto"),
        ("poupanca", "Poupança"),
        ("acoes", "Ações"),
        ("fii", "Fundos imobiliários"),
        ("fundo", "Fundos de investimento"),
        ("etf", "ETFs e BDRs"),
        ("cripto", "Criptomoedas"),
        ("previdencia", "Previdência"),
        ("outro", "Outro"),
    ]
    TIPOS_TAXA = [
        ("nenhuma", "Sem taxa definida (variável)"),
        ("prefixada", "Prefixada (% ao ano)"),
        ("cdi", "Pós-fixada (% do CDI)"),
        ("ipca", "IPCA + taxa (% ao ano)"),
        ("selic", "Selic + taxa (% ao ano)"),
    ]
    LIQUIDEZ = [
        ("diaria", "Diária"),
        ("vencimento", "No vencimento"),
        ("outra", "Outra / a consultar"),
    ]

    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPOS)
    instituicao = models.CharField(max_length=100, blank=True)
    data_aplicacao = models.DateField()
    valor_aplicado_centavos = models.PositiveIntegerField()
    valor_atual_centavos = models.PositiveIntegerField(null=True, blank=True)
    data_vencimento = models.DateField(null=True, blank=True)
    tipo_taxa = models.CharField(max_length=10, choices=TIPOS_TAXA, default="nenhuma")
    taxa = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    liquidez = models.CharField(max_length=10, choices=LIQUIDEZ, default="diaria")
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    # ---------- aportes e resgates ----------
    @property
    def valor_aplicado_reais(self):
        return self.valor_aplicado_centavos / 100

    @property
    def aportado_centavos(self):
        extras = sum(
            m.valor_centavos for m in self.movimentacoes.all() if m.tipo == "aporte"
        )
        return self.valor_aplicado_centavos + extras

    @property
    def aportado_reais(self):
        return self.aportado_centavos / 100

    @property
    def resgatado_centavos(self):
        return sum(
            m.valor_centavos for m in self.movimentacoes.all() if m.tipo == "resgate"
        )

    @property
    def resgatado_reais(self):
        return self.resgatado_centavos / 100

    # ---------- valor atual e rentabilidade ----------
    @property
    def tem_valor_informado(self):
        return self.valor_atual_centavos is not None or len(self.posicoes.all()) > 0

    def valor_em(self, data):
        """Valor estimado em `data`: última posição informada até lá,
        mais os movimentos feitos depois dela."""
        movs = [m for m in self.movimentacoes.all() if m.data <= data]
        posicoes = [p for p in self.posicoes.all() if p.data <= data]
        if posicoes:
            base = max(posicoes, key=lambda p: (p.data, p.id))
            valor = base.valor_centavos
            movs = [m for m in movs if m.data > base.data]
        else:
            valor = self.valor_aplicado_centavos if self.data_aplicacao <= data else 0
        for m in movs:
            valor += m.valor_centavos if m.tipo == "aporte" else -m.valor_centavos
        return max(valor, 0)

    @property
    def atual_centavos(self):
        # Registros antigos: valor informado direto no cadastro, sem histórico
        if self.valor_atual_centavos is not None and not self.posicoes.all():
            return self.valor_atual_centavos
        return self.valor_em(timezone.localdate())

    @property
    def atual_reais(self):
        return self.atual_centavos / 100

    @property
    def lucro_centavos(self):
        return self.atual_centavos + self.resgatado_centavos - self.aportado_centavos

    @property
    def rentabilidade_pct(self):
        if not self.tem_valor_informado or not self.aportado_centavos:
            return None
        return self.lucro_centavos / self.aportado_centavos * 100

    def informar_valor(self, centavos, data=None):
        """Registra o valor total do investimento em uma data (padrão: hoje)."""
        Posicao.objects.update_or_create(
            investimento=self,
            data=data or timezone.localdate(),
            defaults={"valor_centavos": centavos},
        )
        if self.valor_atual_centavos is not None:  # converte registro antigo
            self.valor_atual_centavos = None
            self.save(update_fields=["valor_atual_centavos"])

    # ---------- taxa e prazo ----------
    @property
    def taxa_formatada(self):
        if self.taxa is None or self.tipo_taxa == "nenhuma":
            return "—"
        numero = f"{self.taxa:.2f}".replace(".", ",")
        if self.tipo_taxa == "prefixada":
            return f"{numero}% a.a."
        if self.tipo_taxa == "cdi":
            return f"{numero}% do CDI"
        if self.tipo_taxa == "ipca":
            return f"IPCA + {numero}% a.a."
        return f"Selic + {numero}% a.a."

    @property
    def dias_para_vencer(self):
        if not self.data_vencimento:
            return None
        return (self.data_vencimento - timezone.localdate()).days

    @property
    def prazo_texto(self):
        dias = self.dias_para_vencer
        if dias is None:
            return "Sem prazo"
        if dias == 0:
            return "Vence hoje"
        if dias == 1:
            return "Vence amanhã"
        if dias == -1:
            return "Venceu ontem"
        if dias < 0:
            return f"Venceu há {-dias} dias"
        return f"Em {dias} dias"


class Movimentacao(models.Model):
    TIPOS = [("aporte", "Aporte"), ("resgate", "Resgate")]

    investimento = models.ForeignKey(
        Investimento, on_delete=models.CASCADE, related_name="movimentacoes"
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    data = models.DateField()
    valor_centavos = models.PositiveIntegerField()

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name_plural = "movimentações"

    @property
    def valor_reais(self):
        return self.valor_centavos / 100


class Posicao(models.Model):
    investimento = models.ForeignKey(
        Investimento, on_delete=models.CASCADE, related_name="posicoes"
    )
    data = models.DateField()
    valor_centavos = models.PositiveIntegerField()

    class Meta:
        ordering = ["-data", "-id"]
        verbose_name_plural = "posições"
        constraints = [
            models.UniqueConstraint(
                fields=["investimento", "data"], name="uma_posicao_por_dia"
            )
        ]

    @property
    def valor_reais(self):
        return self.valor_centavos / 100