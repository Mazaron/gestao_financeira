from allauth.account.decorators import secure_admin_login
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

# O login do admin não passa pelo allauth, então não teria rate limit nem 2FA.
# Esta linha obriga a pessoa a entrar primeiro pelo login protegido.
admin.autodiscover()
admin.site.login = secure_admin_login(admin.site.login)

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("lancamentos.urls")),
]