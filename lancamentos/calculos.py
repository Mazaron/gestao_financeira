"""Cálculos da carteira: evolução no tempo e estimativa de IR/IOF (renda fixa)."""
from django.utils import timezone

# Regras de IR e IOF da renda fixa conferidas em 2026
# (Lei 11.033/2004 e Decreto 6.306/2007). Se a lei mudar, ajuste só aqui.
FAIXAS_IR = [(180, 225), (360, 200), (720, 175)]  # (até N dias, alíquota em milésimos)
ALIQUOTA_IR_MINIMA = 150  # acima de 720 dias: 15,0%

TIPOS_COM_IR = {"renda_fixa", "tesouro"}
TIPOS_COM_IOF = {"renda_fixa", "tesouro"}
TIPOS_ISENTOS = {"renda_fixa_isenta", "poupanca"}


def aliquota_ir(dias):
    """Alíquota de IR em milésimos (225 = 22,5%) para um prazo em dias corridos."""
    for limite, aliquota in FAIXAS_IR:
        if dias <= limite:
            return aliquota
    return ALIQUOTA_IR_MINIMA


def percentual_iof(dias):
    """% do rendimento cobrado de IOF: 96% no 1º dia, caindo até 0% a partir do 30º."""
    if dias >= 30:
        return 0
    return (30 - max(dias, 1)) * 100 // 30


def lotes_restantes(inv):
    """Lista de (data, centavos) dos aportes que ainda estão aplicados.
    Os resgates consomem os aportes mais antigos primeiro (PEPS/FIFO)."""
    movs = sorted(inv.movimentacoes.all(), key=lambda m: (m.data, m.id))
    lotes = [[inv.data_aplicacao, inv.valor_aplicado_centavos]]
    for m in movs:
        if m.tipo == "aporte":
            lotes.append([m.data, m.valor_centavos])
    lotes.sort(key=lambda lote: lote[0])

    for m in movs:
        if m.tipo != "resgate":
            continue
        falta = m.valor_centavos
        for lote in lotes:
            if falta <= 0:
                break
            usado = min(lote[1], falta)
            lote[1] -= usado
            falta -= usado
    return [(data, valor) for data, valor in lotes if valor > 0]


def estimar_impostos(inv, hoje):
    """Estimativa de IR e IOF se o investimento fosse resgatado por inteiro hoje.
    Devolve valores em reais, ou None quando não há estimativa para o tipo."""
    isento = inv.tipo in TIPOS_ISENTOS
    if not isento and inv.tipo not in TIPOS_COM_IR:
        return None

    lotes = lotes_restantes(inv)
    principal = sum(valor for _, valor in lotes)
    if principal == 0:
        return None

    bruto = inv.atual_centavos
    rendimento = max(bruto - principal, 0)
    iof = ir = 0
    if not isento:
        for data, restante in lotes:
            parte = rendimento * restante // principal  # fatia do rendimento deste aporte
            dias = (hoje - data).days
            iof_lote = 0
            if inv.tipo in TIPOS_COM_IOF:
                iof_lote = parte * percentual_iof(dias) // 100
            ir += ((parte - iof_lote) * aliquota_ir(dias) + 500) // 1000
            iof += iof_lote

    efetiva = (iof + ir) / rendimento * 100 if rendimento else 0
    return {
        "isento": isento,
        "bruto": bruto / 100,
        "rendimento": rendimento / 100,
        "iof": iof / 100,
        "ir": ir / 100,
        "liquido": (bruto - iof - ir) / 100,
        "aliquota_efetiva": efetiva,
    }


def evolucao(investimentos):
    """Série para o gráfico: datas, total investido (aportes - resgates) e valor."""
    datas = {timezone.localdate()}
    for inv in investimentos:
        datas.add(inv.data_aplicacao)
        datas.update(m.data for m in inv.movimentacoes.all())
        datas.update(p.data for p in inv.posicoes.all())
    datas = sorted(datas)

    investido, valores = [], []
    for d in datas:
        total_investido = total_valor = 0
        for inv in investimentos:
            if inv.data_aplicacao > d:
                continue
            liquido = inv.valor_aplicado_centavos
            for m in inv.movimentacoes.all():
                if m.data <= d:
                    liquido += m.valor_centavos if m.tipo == "aporte" else -m.valor_centavos
            total_investido += max(liquido, 0)
            total_valor += inv.valor_em(d)
        investido.append(total_investido / 100)
        valores.append(total_valor / 100)
    return datas, investido, valores