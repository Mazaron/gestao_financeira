from datetime import timedelta

from django.utils import timezone

from .models import Investimento

DIAS_DE_AVISO = 30


def avisos(request):
    if not request.user.is_authenticated:
        return {}
    limite = timezone.localdate() + timedelta(days=DIAS_DE_AVISO)
    vencendo = Investimento.objects.filter(
        usuario=request.user,
        ativo=True,
        data_vencimento__isnull=False,
        data_vencimento__lte=limite,
    ).order_by("data_vencimento")
    return {"investimentos_vencendo": list(vencendo)}