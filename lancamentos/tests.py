from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import Cartao, Categoria, Investimento, Lancamento
from .seguranca import limitar, parece_numero_de_cartao


@override_settings(SECURE_SSL_REDIRECT=False)
class IsolamentoDeDadosTests(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user("ana", "ana@example.com", "Senha123!x")
        self.beto = User.objects.create_user("beto", "beto@example.com", "Senha123!x")
        categoria = Categoria.objects.create(nome="Mercado", tipo="D")
        self.lancamento = Lancamento.objects.create(
            usuario=self.ana, categoria=categoria, descricao="Compra",
            valor_centavos=1000, data=date(2026, 10, 1),
        )
        self.investimento = Investimento.objects.create(
            usuario=self.ana, nome="CDB", tipo="renda_fixa",
            data_aplicacao=date(2026, 1, 1), valor_aplicado_centavos=100000,
        )
        self.cartao = Cartao.objects.create(
            usuario=self.ana, nome="Cartão", dia_fechamento=25, dia_vencimento=5
        )

    def test_visitante_e_mandado_para_o_login(self):
        for nome in ["lista", "novo", "cartoes", "investimentos", "perfil"]:
            resposta = self.client.get(reverse(nome))
            self.assertEqual(resposta.status_code, 302, nome)
            self.assertIn("login", resposta["Location"], nome)

    def test_outro_usuario_recebe_404(self):
        self.client.force_login(self.beto)
        enderecos = [
            reverse("editar", args=[self.lancamento.pk]),
            reverse("excluir", args=[self.lancamento.pk]),
            reverse("detalhe_investimento", args=[self.investimento.pk]),
            reverse("editar_investimento", args=[self.investimento.pk]),
        ]
        for endereco in enderecos:
            self.assertEqual(self.client.get(endereco).status_code, 404, endereco)

    def test_outro_usuario_nao_consegue_excluir(self):
        self.client.force_login(self.beto)
        self.client.post(reverse("excluir", args=[self.lancamento.pk]))
        self.client.post(reverse("excluir_cartao", args=[self.cartao.pk]))
        self.client.post(reverse("excluir_investimento", args=[self.investimento.pk]))
        self.assertTrue(Lancamento.objects.filter(pk=self.lancamento.pk).exists())
        self.assertTrue(Cartao.objects.filter(pk=self.cartao.pk).exists())
        self.assertTrue(Investimento.objects.filter(pk=self.investimento.pk).exists())

    def test_dono_acessa_normalmente(self):
        self.client.force_login(self.ana)
        resposta = self.client.get(reverse("detalhe_investimento", args=[self.investimento.pk]))
        self.assertEqual(resposta.status_code, 200)


class LimiteDeTaxaTests(TestCase):
    def test_bloqueia_depois_do_limite(self):
        cache.clear()

        @limitar("teste", limite=3, segundos=60)
        def view(request):
            return HttpResponse("ok")

        usuario = User.objects.create_user("carla", "carla@example.com", "Senha123!x")
        codigos = []
        for _ in range(5):
            requisicao = RequestFactory().post("/qualquer/")
            requisicao.user = usuario
            codigos.append(view(requisicao).status_code)
        self.assertEqual(codigos, [200, 200, 200, 429, 429])


class NumeroDeCartaoTests(TestCase):
    def test_detecta_cartao_valido(self):
        self.assertTrue(parece_numero_de_cartao("compra 4111 1111 1111 1111"))

    def test_ignora_textos_normais(self):
        self.assertFalse(parece_numero_de_cartao("parcela 12/12 de 850,00"))
        self.assertFalse(parece_numero_de_cartao("4111111111111112"))  # não passa no Luhn