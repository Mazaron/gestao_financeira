from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from .models import PerfilUsuario


class PerfilCompletoMiddleware:
    """Quem entrou (por exemplo, pelo Google) mas ainda não informou nome,
    sobrenome e CPF é levado a uma página para completar o cadastro."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if self._precisa_completar(request):
            return redirect("completar_perfil")
        return self.get_response(request)

    def _precisa_completar(self, request):
        usuario = request.user
        if not usuario.is_authenticated:
            return False
        livres = ("/accounts/", "/static/", "/" + settings.ADMIN_URL, reverse("completar_perfil"))
        if request.path.startswith(livres):
            return False
        if not (usuario.first_name and usuario.last_name):
            return True
        return not (
            PerfilUsuario.objects.filter(usuario=usuario)
            .exclude(cpf_criptografado="")
            .exists()
        )