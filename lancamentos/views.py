import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import CartaoForm, InvestimentoForm, LancamentoForm, PerfilForm
from .models import Cartao, Investimento, Lancamento

from .calculos import estimar_impostos, evolucao
from .forms import (
    CartaoForm,
    InvestimentoForm,
    LancamentoForm,
    MovimentacaoForm,
    PerfilForm,
    PosicaoForm,
)
from .models import Cartao, Investimento, Lancamento, Movimentacao, Posicao

from .seguranca import limite_de_escrita



@login_required
def lista_lancamentos(request):
    hoje = timezone.localdate()
    try:
        ano = int(request.GET.get("ano", hoje.year))
        mes = int(request.GET.get("mes", hoje.month))
        if not 1 <= mes <= 12 or not 1900 <= ano <= 2200:
            raise ValueError
    except ValueError:
        ano, mes = hoje.year, hoje.month

    hora = timezone.localtime().hour
    if hora < 12:
        saudacao = "Bom dia"
    elif hora < 18:
        saudacao = "Boa tarde"
    else:
        saudacao = "Boa noite"

    # Dia clicado no calendário (opcional)
    dia_selecionado = None
    if request.GET.get("dia"):
        try:
            dia_selecionado = date(ano, mes, int(request.GET["dia"]))
        except ValueError:
            dia_selecionado = None

    do_mes = Lancamento.objects.filter(
        usuario=request.user, data__year=ano, data__month=mes
    )

    receitas = do_mes.filter(categoria__tipo="R").aggregate(total=Sum("valor_centavos"))["total"] or 0
    despesas = do_mes.filter(categoria__tipo="D").aggregate(total=Sum("valor_centavos"))["total"] or 0

    por_categoria = (
        do_mes.filter(categoria__tipo="D")
        .values("categoria__nome")
        .annotate(total=Sum("valor_centavos"))
        .order_by("-total")
    )
    grafico = {
        "labels": [item["categoria__nome"] for item in por_categoria],
        "valores": [item["total"] / 100 for item in por_categoria],
    }

    gastos_por_dia = {
        item["data"].day: item["total"] / 100
        for item in do_mes.filter(categoria__tipo="D")
        .values("data")
        .annotate(total=Sum("valor_centavos"))
    }

    semanas = []
    for semana in calendar.Calendar(firstweekday=6).monthdayscalendar(ano, mes):
        linha = []
        for dia in semana:
            if dia == 0:
                linha.append(None)
            else:
                data_dia = date(ano, mes, dia)
                linha.append({
                    "dia": dia,
                    "gasto": gastos_por_dia.get(dia),
                    "hoje": data_dia == hoje,
                    "selecionado": data_dia == dia_selecionado,
                })
        semanas.append(linha)

    if mes == 1:
        anterior = {"ano": ano - 1, "mes": 12}
    else:
        anterior = {"ano": ano, "mes": mes - 1}
    if mes == 12:
        proximo = {"ano": ano + 1, "mes": 1}
    else:
        proximo = {"ano": ano, "mes": mes + 1}

    lancamentos = do_mes.select_related("categoria", "cartao").order_by("-data")
    if dia_selecionado:
        lancamentos = lancamentos.filter(data=dia_selecionado)

    contexto = {
        "lancamentos": lancamentos,
        "receitas": receitas / 100,
        "despesas": despesas / 100,
        "saldo": (receitas - despesas) / 100,
        "periodo": date(ano, mes, 1),
        "dia_selecionado": dia_selecionado,
        "anterior": anterior,
        "proximo": proximo,
        "grafico": grafico,
        "semanas": semanas,
        "saudacao": saudacao,
    }
    return render(request, "lancamentos/lista.html", contexto)

def _lista_do_mes(data):
    """Redireciona para a lista do mês de uma data."""
    return redirect(f"{reverse('lista')}?ano={data.year}&mes={data.month}")


@login_required
@limite_de_escrita
def novo_lancamento(request):
    if request.method == "POST":
        form = LancamentoForm(request.POST, usuario=request.user)
        if form.is_valid():
            primeira_data = form.salvar_para(request.user)
            return _lista_do_mes(primeira_data)
    else:
        form = LancamentoForm(usuario=request.user)
    return render(request, "lancamentos/form.html", {"form": form, "editando": False})


@login_required
@limite_de_escrita
def editar_lancamento(request, pk):
    
    lancamento = get_object_or_404(Lancamento, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = LancamentoForm(request.POST, instance=lancamento)
        if form.is_valid():
            lancamento = form.save()
            return _lista_do_mes(lancamento.data)
    else:
        form = LancamentoForm(instance=lancamento)
    return render(request, "lancamentos/form.html", {"form": form, "editando": True})


@login_required
@limite_de_escrita
def excluir_lancamento(request, pk):
    lancamento = get_object_or_404(Lancamento, pk=pk, usuario=request.user)
    if request.method == "POST":
        if lancamento.grupo and request.POST.get("escopo") == "todas":
            Lancamento.objects.filter(
                usuario=request.user, grupo=lancamento.grupo
            ).delete()
        else:
            lancamento.delete()
        return _lista_do_mes(lancamento.data)

    qtd_grupo = 0
    if lancamento.grupo:
        qtd_grupo = Lancamento.objects.filter(
            usuario=request.user, grupo=lancamento.grupo
        ).count()
    return render(
        request,
        "lancamentos/confirmar_exclusao.html",
        {"lancamento": lancamento, "qtd_grupo": qtd_grupo},
    )


@login_required
@limite_de_escrita
def perfil(request):
    if request.method == "POST":
        form = PerfilForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Dados atualizados.")
            return redirect("perfil")
    else:
        form = PerfilForm(instance=request.user)
    return render(request, "lancamentos/perfil.html", {"form": form})


@login_required
def ajuda(request):
    return render(request, "lancamentos/ajuda.html")


@login_required
@limite_de_escrita
def cartoes(request):
    if request.method == "POST":
        form = CartaoForm(request.POST)
        if form.is_valid():
            cartao = form.save(commit=False)
            cartao.usuario = request.user
            cartao.save()
            messages.success(request, "Cartão adicionado.")
            return redirect("cartoes")
    else:
        form = CartaoForm()

    hoje = timezone.localdate()
    lista = list(Cartao.objects.filter(usuario=request.user))
    for c in lista:
        do_cartao = Lancamento.objects.filter(usuario=request.user, cartao=c)
        no_mes = do_cartao.filter(data__year=hoje.year, data__month=hoje.month)
        c.fatura_mes = (no_mes.aggregate(t=Sum("valor_centavos"))["t"] or 0) / 100
        a_vencer = do_cartao.filter(data__gte=hoje)
        c.a_vencer = (a_vencer.aggregate(t=Sum("valor_centavos"))["t"] or 0) / 100
    return render(request, "lancamentos/cartoes.html", {"cartoes": lista, "form": form})


@login_required
@limite_de_escrita
def excluir_cartao(request, pk):

    cartao = get_object_or_404(Cartao, pk=pk, usuario=request.user)
    if request.method == "POST":
        try:
            cartao.delete()
            messages.success(request, "Cartão excluído.")
        except ProtectedError:
            messages.error(request, "Este cartão tem lançamentos e não pode ser excluído.")
    return redirect("cartoes")


@login_required
def investimentos(request):
    todos = list(
        Investimento.objects.filter(usuario=request.user)
        .prefetch_related("movimentacoes", "posicoes")
        .order_by("tipo", "nome")
    )
    hoje = timezone.localdate()
    for i in todos:
        i.impostos = estimar_impostos(i, hoje)

    ativos = [i for i in todos if i.ativo]
    resgatados = [i for i in todos if not i.ativo]

    total_aportado = sum(i.aportado_centavos for i in ativos)
    total_atual = sum(i.atual_centavos for i in ativos)
    lucro = sum(i.lucro_centavos for i in ativos)
    rentabilidade = lucro / total_aportado * 100 if total_aportado else 0

    por_tipo = {}
    for i in ativos:
        rotulo = i.get_tipo_display()
        por_tipo[rotulo] = por_tipo.get(rotulo, 0) + i.atual_centavos
    grafico = {
        "labels": list(por_tipo.keys()),
        "valores": [v / 100 for v in por_tipo.values()],
    }

    datas, investido, valores = evolucao(todos)
    serie = {
        "labels": [d.strftime("%d/%m/%Y") for d in datas],
        "investido": investido,
        "valores": valores,
    }

    com_prazo = [i for i in ativos if i.data_vencimento]
    proximos = sorted(com_prazo, key=lambda i: i.data_vencimento)[:5]

    contexto = {
        "ativos": ativos,
        "resgatados": resgatados,
        "proximos": proximos,
        "total_aportado": total_aportado / 100,
        "total_atual": total_atual / 100,
        "lucro": lucro / 100,
        "rentabilidade": rentabilidade,
        "grafico": grafico,
        "evolucao": serie,
    }
    return render(request, "lancamentos/investimentos.html", contexto)


@login_required
@limite_de_escrita
def novo_investimento(request):
    if request.method == "POST":
        form = InvestimentoForm(request.POST)
        if form.is_valid():
            investimento = form.save(commit=False)
            investimento.usuario = request.user
            investimento.save()
            valor = form.cleaned_data["valor_atual"]
            if valor is not None:
                investimento.informar_valor(int(valor * 100))
            messages.success(request, "Investimento cadastrado.")
            return redirect("investimentos")
    else:
        form = InvestimentoForm()
    return render(
        request, "lancamentos/investimento_form.html", {"form": form, "editando": False}
    )


@login_required
@limite_de_escrita
def editar_investimento(request, pk):
    investimento = get_object_or_404(Investimento, pk=pk, usuario=request.user)
    if request.method == "POST":
        form = InvestimentoForm(request.POST, instance=investimento)
        if form.is_valid():
            investimento = form.save()
            valor = form.cleaned_data["valor_atual"]
            if valor is not None:
                centavos = int(valor * 100)
                antigo = investimento.valor_atual_centavos is not None
                if (
                    antigo
                    or not investimento.tem_valor_informado
                    or centavos != investimento.atual_centavos
                ):
                    investimento.informar_valor(centavos)
            messages.success(request, "Investimento atualizado.")
            return redirect("investimentos")
    else:
        form = InvestimentoForm(instance=investimento)
    return render(
        request, "lancamentos/investimento_form.html", {"form": form, "editando": True}
    )


@login_required
@limite_de_escrita
def detalhe_investimento(request, pk):
    inv = get_object_or_404(
        Investimento.objects.prefetch_related("movimentacoes", "posicoes"),
        pk=pk,
        usuario=request.user,
    )
    form_mov = MovimentacaoForm(prefix="mov", investimento=inv)
    form_val = PosicaoForm(prefix="val", investimento=inv)

    if request.method == "POST":
        acao = request.POST.get("acao")

        if acao == "movimentacao":
            form_mov = MovimentacaoForm(request.POST, prefix="mov", investimento=inv)
            if form_mov.is_valid():
                d = form_mov.cleaned_data
                Movimentacao.objects.create(
                    investimento=inv,
                    tipo=d["tipo"],
                    data=d["data"],
                    valor_centavos=int(d["valor"] * 100),
                )
                messages.success(request, "Movimentação registrada.")
                return redirect("detalhe_investimento", pk=inv.pk)

        elif acao == "valor":
            form_val = PosicaoForm(request.POST, prefix="val", investimento=inv)
            if form_val.is_valid():
                d = form_val.cleaned_data
                inv.informar_valor(int(d["valor"] * 100), d["data"])
                messages.success(request, "Valor registrado.")
                return redirect("detalhe_investimento", pk=inv.pk)

        elif acao in ("excluir_mov", "excluir_pos"):
            item_id = request.POST.get("id", "")
            if item_id.isdigit():
                modelo = Movimentacao if acao == "excluir_mov" else Posicao
                modelo.objects.filter(pk=item_id, investimento=inv).delete()
                messages.success(request, "Item excluído.")
            return redirect("detalhe_investimento", pk=inv.pk)

    datas, investido, valores = evolucao([inv])
    contexto = {
        "inv": inv,
        "movimentacoes": inv.movimentacoes.all(),
        "posicoes": inv.posicoes.all(),
        "aportado": inv.aportado_centavos / 100,
        "resgatado": inv.resgatado_centavos / 100,
        "atual": inv.atual_centavos / 100,
        "lucro": inv.lucro_centavos / 100,
        "rentab": inv.rentabilidade_pct,
        "impostos": estimar_impostos(inv, timezone.localdate()),
        "evolucao": {
            "labels": [d.strftime("%d/%m/%Y") for d in datas],
            "investido": investido,
            "valores": valores,
        },
        "form_mov": form_mov,
        "form_val": form_val,
    }
    return render(request, "lancamentos/investimento_detalhe.html", contexto)


@login_required
@limite_de_escrita
def excluir_investimento(request, pk):
    investimento = get_object_or_404(Investimento, pk=pk, usuario=request.user)
    if request.method == "POST":
        investimento.delete()
        messages.success(request, "Investimento excluído.")
    return redirect("investimentos")