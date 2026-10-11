from django.contrib import admin

from .models import Categoria, Lancamento


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo")
    list_filter = ("tipo",)


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ("data", "descricao", "categoria", "valor_centavos", "usuario")
    list_filter = ("categoria", "data")
    search_fields = ("descricao",)