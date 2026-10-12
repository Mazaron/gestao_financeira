from django.urls import path

from . import views

urlpatterns = [
    path("", views.lista_lancamentos, name="lista"),
    path("novo/", views.novo_lancamento, name="novo"),
    path("lancamento/<int:pk>/editar/", views.editar_lancamento, name="editar"),
    path("lancamento/<int:pk>/excluir/", views.excluir_lancamento, name="excluir"),
    path("perfil/", views.perfil, name="perfil"),
    path("ajuda/", views.ajuda, name="ajuda"),
    path("cartoes/", views.cartoes, name="cartoes"),
    path("cartoes/<int:pk>/excluir/", views.excluir_cartao, name="excluir_cartao"),
    path("investimentos/", views.investimentos, name="investimentos"),
    path("investimentos/novo/", views.novo_investimento, name="novo_investimento"),
    path("investimentos/<int:pk>/editar/", views.editar_investimento, name="editar_investimento"),
    path("investimentos/<int:pk>/excluir/", views.excluir_investimento, name="excluir_investimento"),
    path("investimentos/<int:pk>/", views.detalhe_investimento, name="detalhe_investimento"),
    path("completar-perfil/", views.completar_perfil, name="completar_perfil"),


]
