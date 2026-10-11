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


]