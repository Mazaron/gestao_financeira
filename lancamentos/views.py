import calendar
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .forms import CartaoForm, LancamentoForm, PerfilForm
from .models import Cartao, Lancamento


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
def excluir_cartao(request, pk):
    cartao = get_object_or_404(Cartao, pk=pk, usuario=request.user)
    if request.method == "POST":
        try:
            cartao.delete()
            messages.success(request, "Cartão excluído.")
        except ProtectedError:
            messages.error(request, "Este cartão tem lançamentos e não pode ser excluído.")
    return redirect("cartoes")


