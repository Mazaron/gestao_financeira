import re

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def somente_digitos(texto):
    return re.sub(r"\D", "", texto or "")


def cpf_valido(cpf):
    """Confere o tamanho e os dois dígitos verificadores."""
    if len(cpf) != 11 or not cpf.isdigit() or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if (soma * 10 % 11) % 10 != int(cpf[tamanho]):
            return False
    return True


def mascarar_cpf(cpf):
    return f"***.***.***-{cpf[-2:]}"


def _fernet():
    chaves = [c.strip() for c in settings.CPF_CHAVES_CRIPTO.split(",") if c.strip()]
    if not chaves:
        raise ImproperlyConfigured("Defina CPF_ENCRYPTION_KEYS no ambiente (.env).")
    return MultiFernet([Fernet(c.encode()) for c in chaves])


def cifrar_cpf(cpf):
    return _fernet().encrypt(cpf.encode()).decode()


def decifrar_cpf(token):
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as erro:
        raise ValueError("Não foi possível decifrar o CPF.") from erro