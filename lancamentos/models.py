from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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