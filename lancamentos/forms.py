import re
import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Cartao, Lancamento
from .utils import adicionar_meses, formatar_reais, vencimentos_da_compra

# Aceita: 1.123,00 | 1123,00 | 1123 | 12,5 | 0,99
PADRAO_VALOR = re.compile(r"(\d{1,3}(\.\d{3})+|\d+)(,\d{1,2})?")
VALOR_MAXIMO = Decimal("9999999.99")


class LancamentoForm(forms.ModelForm):
    valor = forms.CharField(
        label="Valor total (R$)",
        widget=forms.TextInput(attrs={
            "placeholder": "0,00",
            "inputmode": "numeric",
            "autocomplete": "off",
            "data-mascara": "dinheiro",
        }),
    )
    data = forms.DateField(
        label="Data (da compra, se for no cartão)",
        input_formats=["%d/%m/%Y"],
        error_messages={"invalid": "Use o formato dd/mm/aaaa."},
        widget=forms.DateInput(format="%d/%m/%Y", attrs={
            "placeholder": "dd/mm/aaaa",
            "inputmode": "numeric",
            "autocomplete": "off",
            "data-mascara": "data",
        }),
    )
    cartao = forms.ModelChoiceField(
        queryset=Cartao.objects.none(),
        required=False,
        label="Cartão",
        empty_label="Sem cartão (dinheiro, débito, Pix)",
        help_text="No cartão, as parcelas caem no vencimento de cada fatura.",
    )
    parcelas = forms.IntegerField(
        label="Número de parcelas",
        min_value=1,
        max_value=60,
        initial=1,
        help_text="1 = à vista. O valor total será dividido entre as parcelas.",
    )

    class Meta:
        model = Lancamento
        fields = ["descricao", "categoria", "data"]

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Editando um lançamento que já existe
            del self.fields["parcelas"]
            del self.fields["cartao"]
            self.fields["valor"].label = "Valor (R$)"
            if self.instance.cartao_id:
                self.fields["data"].label = "Vencimento da parcela"
            else:
                self.fields["data"].label = "Data"
            if not self.is_bound:
                self.initial["valor"] = formatar_reais(self.instance.valor_centavos)
        else:
            self.fields["data"].initial = timezone.localdate
            self.fields["cartao"].queryset = Cartao.objects.filter(usuario=usuario)

    def clean_valor(self):
        texto = self.cleaned_data["valor"].strip()
        if not PADRAO_VALOR.fullmatch(texto):
            raise forms.ValidationError("Digite o valor no formato 1.123,00.")
        valor = Decimal(texto.replace(".", "").replace(",", "."))
        if valor <= 0:
            raise forms.ValidationError("O valor deve ser maior que zero.")
        if valor > VALOR_MAXIMO:
            raise forms.ValidationError("Valor muito alto.")
        return valor

    def clean(self):
        dados = super().clean()
        valor = dados.get("valor")
        parcelas = dados.get("parcelas")
        if valor and parcelas and int(valor * 100) < parcelas:
            raise forms.ValidationError(
                "O valor é pequeno demais para esse número de parcelas."
            )
        categoria = dados.get("categoria")
        if dados.get("cartao") and categoria and categoria.tipo == "R":
            raise forms.ValidationError(
                "Compras no cartão precisam ter uma categoria de despesa."
            )
        return dados

    def save(self, commit=True):
        """Usado na edição de um lançamento existente."""
        lancamento = super().save(commit=False)
        lancamento.valor_centavos = int(self.cleaned_data["valor"] * 100)
        if commit:
            lancamento.save()
        return lancamento

    def salvar_para(self, usuario):
        """Usado na criação: gera uma ou várias parcelas. Devolve a data da primeira."""
        dados = self.cleaned_data
        total_centavos = int(dados["valor"] * 100)
        n = dados["parcelas"]
        base, resto = divmod(total_centavos, n)
        parcelado = n > 1
        grupo = uuid.uuid4() if parcelado else None
        cartao = dados["cartao"]

        if cartao:
            datas = vencimentos_da_compra(
                dados["data"], cartao.dia_fechamento, cartao.dia_vencimento, n
            )
        else:
            datas = [adicionar_meses(dados["data"], i) for i in range(n)]

        lancamentos = []
        for i, data in enumerate(datas):
            lancamentos.append(
                Lancamento(
                    usuario=usuario,
                    categoria=dados["categoria"],
                    descricao=dados["descricao"],
                    valor_centavos=base + (1 if i < resto else 0),
                    data=data,
                    cartao=cartao,
                    data_compra=dados["data"] if cartao else None,
                    grupo=grupo,
                    parcela_atual=i + 1 if parcelado else None,
                    total_parcelas=n if parcelado else None,
                )
            )
        Lancamento.objects.bulk_create(lancamentos)
        return datas[0]


class CartaoForm(forms.ModelForm):
    class Meta:
        model = Cartao
        fields = ["nome", "dia_fechamento", "dia_vencimento"]
        labels = {
            "nome": "Nome do cartão",
            "dia_fechamento": "Dia do fechamento da fatura",
            "dia_vencimento": "Dia do vencimento",
        }


class PerfilForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name"]
        labels = {"first_name": "Nome"}