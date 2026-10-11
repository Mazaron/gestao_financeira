import calendar
from datetime import date


def adicionar_meses(data, meses):
    """Soma `meses` a uma data, respeitando o último dia de cada mês."""
    total = data.year * 12 + (data.month - 1) + meses
    ano, mes = divmod(total, 12)
    mes += 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(data.day, ultimo_dia))

def formatar_reais(centavos):
    """Converte 112300 em '1.123,00'."""
    reais, cents = divmod(centavos, 100)
    return f"{reais:,}".replace(",", ".") + f",{cents:02d}"


def data_valida(ano, mes, dia):
    """Cria uma data; se o dia não existir no mês (ex.: 31 em fevereiro), usa o último dia."""
    ultimo = calendar.monthrange(ano, mes)[1]
    return date(ano, mes, min(dia, ultimo))


def vencimentos_da_compra(data_compra, dia_fechamento, dia_vencimento, parcelas):
    """Devolve a data de vencimento de cada parcela de uma compra no cartão."""
    # 1) Em qual fatura a compra cai? (conta em "meses desde o ano 0")
    meses = data_compra.year * 12 + data_compra.month - 1
    ultimo_dia = calendar.monthrange(data_compra.year, data_compra.month)[1]
    if data_compra.day > min(dia_fechamento, ultimo_dia):
        meses += 1  # a fatura já fechou: vai para a do mês seguinte

    # 2) O vencimento é no mesmo mês do fechamento ou no mês seguinte?
    if dia_vencimento <= dia_fechamento:
        meses += 1

    # 3) Uma parcela por fatura, mês após mês
    datas = []
    for i in range(parcelas):
        ano, mes0 = divmod(meses + i, 12)
        datas.append(data_valida(ano, mes0 + 1, dia_vencimento))
    return datas