from datetime import date

from django.contrib.auth.models import User
from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .models import Cartao, Categoria, Investimento, Lancamento
from .seguranca import limitar, parece_numero_de_cartao

from .models import PerfilUsuario

from cryptography.fernet import Fernet
from .cpf import cpf_valido, decifrar_cpf


@override_settings(SECURE_SSL_REDIRECT=False)
class IsolamentoDeDadosTests(TestCase):
    def setUp(self):
        self.ana = criar_usuario("ana")
        self.beto = criar_usuario("beto")
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

def criar_usuario(nome):
    usuario = User.objects.create_user(
        nome, f"{nome}@example.com", "Senha123!x", first_name="Fulano", last_name="De Tal"
    )
    PerfilUsuario.objects.create(usuario=usuario, cpf_criptografado="valor-de-teste")
    return usuario

class CpfTests(TestCase):
    def test_validacao_dos_digitos(self):
        self.assertTrue(cpf_valido("52998224725"))
        self.assertFalse(cpf_valido("52998224726"))
        self.assertFalse(cpf_valido("11111111111"))

    @override_settings(CPF_CHAVES_CRIPTO=Fernet.generate_key().decode())
    def test_cifra_e_mascara(self):
        usuario = User.objects.create_user("dani", "dani@example.com", "Senha123!x")
        perfil = PerfilUsuario.objects.create(usuario=usuario)
        perfil.definir_cpf("52998224725")
        perfil.save()
        self.assertNotIn("52998224725", perfil.cpf_criptografado)
        self.assertEqual(perfil.cpf_mascarado, "***.***.***-25")
        self.assertEqual(decifrar_cpf(perfil.cpf_criptografado), "52998224725")


@override_settings(SECURE_SSL_REDIRECT=False)
class PerfilCompletoTests(TestCase):
    def test_usuario_sem_cpf_e_levado_a_completar(self):
        usuario = User.objects.create_user("edu", "edu@example.com", "Senha123!x")
        self.client.force_login(usuario)
        resposta = self.client.get(reverse("lista"))
        self.assertRedirects(
            resposta, reverse("completar_perfil"), fetch_redirect_response=False
        )