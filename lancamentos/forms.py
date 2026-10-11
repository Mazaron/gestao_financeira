import re
import uuid
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User
from django.utils import timezone

from .models import Cartao, Investimento, Lancamento, Movimentacao
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


def reais_para_decimal(texto):
    """Converte '1.123,00' em Decimal('1123.00'); levanta erro se o formato for inválido."""
    texto = texto.strip()
    if not PADRAO_VALOR.fullmatch(texto):
        raise forms.ValidationError("Digite o valor no formato 1.123,00.")
    valor = Decimal(texto.replace(".", "").replace(",", "."))
    if valor > VALOR_MAXIMO:
        raise forms.ValidationError("Valor muito alto.")
    return valor


def _campo_dinheiro(label, obrigatorio=True, ajuda=""):
    return forms.CharField(
        label=label,
        required=obrigatorio,
        help_text=ajuda,
        widget=forms.TextInput(attrs={
            "placeholder": "0,00",
            "inputmode": "numeric",
            "autocomplete": "off",
            "data-mascara": "dinheiro",
        }),
    )


def _campo_data(label, obrigatorio=True):
    return forms.DateField(
        label=label,
        required=obrigatorio,
        input_formats=["%d/%m/%Y"],
        error_messages={"invalid": "Use o formato dd/mm/aaaa."},
        widget=forms.DateInput(format="%d/%m/%Y", attrs={
            "placeholder": "dd/mm/aaaa",
            "inputmode": "numeric",
            "autocomplete": "off",
            "data-mascara": "data",
        }),
    )


class InvestimentoForm(forms.ModelForm):
    valor_aplicado = _campo_dinheiro(
        "Valor do primeiro aporte (R$)",
        ajuda="Aportes seguintes e resgates são registrados na página do investimento.",
    )
    valor_atual = _campo_dinheiro(
        "Valor atual (R$)",
        obrigatorio=False,
        ajuda="Opcional. Registra o valor de hoje no histórico (gráfico e rentabilidade).",
    )
    data_aplicacao = _campo_data("Data do primeiro aporte")
    data_vencimento = _campo_data("Vencimento (se houver)", obrigatorio=False)
    taxa = forms.CharField(
        label="Taxa (%)",
        required=False,
        help_text="Ex.: 12,50 (prefixada), 110 (% do CDI) ou 6,20 (IPCA + 6,20% a.a.).",
        widget=forms.TextInput(attrs={
            "placeholder": "12,50",
            "inputmode": "decimal",
            "autocomplete": "off",
        }),
    )

    class Meta:
        model = Investimento
        fields = [
            "nome", "tipo", "instituicao", "data_aplicacao", "valor_aplicado",
            "valor_atual", "tipo_taxa", "taxa", "data_vencimento", "liquidez",
            "ativo", "observacoes",
        ]
        labels = {
            "nome": "Nome do investimento",
            "tipo": "Tipo",
            "instituicao": "Instituição (banco ou corretora)",
            "tipo_taxa": "Tipo de taxa",
            "liquidez": "Liquidez",
            "ativo": "Investimento ativo (desmarque se já resgatou)",
            "observacoes": "Observações",
        }
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inv = self.instance
        if inv.pk and not self.is_bound:
            self.initial["valor_aplicado"] = formatar_reais(inv.valor_aplicado_centavos)
            if inv.tem_valor_informado:
                self.initial["valor_atual"] = formatar_reais(inv.atual_centavos)
            if inv.taxa is not None:
                self.initial["taxa"] = f"{inv.taxa:.2f}".replace(".", ",")
        elif not inv.pk:
            self.fields["data_aplicacao"].initial = timezone.localdate

    def clean_valor_aplicado(self):
        valor = reais_para_decimal(self.cleaned_data["valor_aplicado"])
        if valor <= 0:
            raise forms.ValidationError("O valor deve ser maior que zero.")
        return valor

    def clean_valor_atual(self):
        texto = self.cleaned_data["valor_atual"].strip()
        if not texto:
            return None
        return reais_para_decimal(texto)

    def clean_taxa(self):
        texto = self.cleaned_data["taxa"].strip()
        if not texto:
            return None
        if not re.fullmatch(r"\d{1,4}(,\d{1,2})?", texto):
            raise forms.ValidationError("Digite a taxa no formato 12,50.")
        return Decimal(texto.replace(",", "."))

    def clean(self):
        dados = super().clean()
        tipo_taxa = dados.get("tipo_taxa")
        if tipo_taxa == "nenhuma":
            dados["taxa"] = None
        elif tipo_taxa and dados.get("taxa") is None and "taxa" not in self.errors:
            self.add_error("taxa", "Informe a taxa para esse tipo.")

        aplicacao = dados.get("data_aplicacao")
        vencimento = dados.get("data_vencimento")
        if aplicacao and vencimento and vencimento < aplicacao:
            self.add_error("data_vencimento", "O vencimento não pode ser antes da aplicação.")
        return dados

    def save(self, commit=True):
        inv = super().save(commit=False)
        inv.valor_aplicado_centavos = int(self.cleaned_data["valor_aplicado"] * 100)
        if commit:
            inv.save()
        return inv

class _BaseMovimento(forms.Form):
    data = _campo_data("Data")

    def __init__(self, *args, investimento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.investimento = investimento
        if not self.is_bound:
            self.fields["data"].initial = timezone.localdate

    def clean_data(self):
        data = self.cleaned_data["data"]
        if self.investimento and data < self.investimento.data_aplicacao:
            raise forms.ValidationError("A data não pode ser anterior ao primeiro aporte.")
        return data


class MovimentacaoForm(_BaseMovimento):
    tipo = forms.ChoiceField(label="Tipo", choices=Movimentacao.TIPOS)
    valor = _campo_dinheiro("Valor (R$)")

    field_order = ["tipo", "data", "valor"]

    def clean_valor(self):
        valor = reais_para_decimal(self.cleaned_data["valor"])
        if valor <= 0:
            raise forms.ValidationError("O valor deve ser maior que zero.")
        return valor


class PosicaoForm(_BaseMovimento):
    valor = _campo_dinheiro("Valor total nessa data (R$)")

    def clean_valor(self):
        return reais_para_decimal(self.cleaned_data["valor"])