import re
from functools import wraps

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import render


# ---------- Rate limit para as telas que gravam dados ----------
def limitar(nome, limite, segundos):
    """Limita quantos POSTs cada usuário pode fazer em uma janela de tempo."""

    def decorador(view):
        @wraps(view)
        def envolvida(request, *args, **kwargs):
            if request.method == "POST":
                if request.user.is_authenticated:
                    quem = request.user.pk
                else:
                    quem = request.META.get("REMOTE_ADDR", "desconhecido")
                chave = f"limite:{nome}:{quem}"

                if cache.add(chave, 1, timeout=segundos):  # primeira requisição da janela
                    contagem = 1
                else:
                    try:
                        contagem = cache.incr(chave)
                    except ValueError:  # a chave expirou entre as duas chamadas
                        cache.set(chave, 1, timeout=segundos)
                        contagem = 1

                if contagem > limite:
                    return render(request, "429.html", status=429)
            return view(request, *args, **kwargs)

        return envolvida

    return decorador


# Um limite compartilhado por todas as telas que gravam: 60 envios por minuto por usuário
limite_de_escrita = limitar("escrita", limite=60, segundos=60)


# ---------- Bloqueio de número de cartão digitado por engano ----------
PADRAO_CARTAO = re.compile(r"(?:\d[ -]?){13,19}")


def _luhn_valido(digitos):
    soma = 0
    for posicao, caractere in enumerate(reversed(digitos)):
        n = int(caractere)
        if posicao % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        soma += n
    return soma % 10 == 0


def parece_numero_de_cartao(texto):
    for trecho in PADRAO_CARTAO.findall(texto or ""):
        digitos = re.sub(r"\D", "", trecho)
        if 13 <= len(digitos) <= 19 and _luhn_valido(digitos):
            return True
    return False


def validar_sem_cartao(texto):
    if parece_numero_de_cartao(texto):
        raise ValidationError(
            "Isto parece um número de cartão. Por segurança, não guarde esse dado aqui."
        )