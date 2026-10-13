from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


TAGS_PADRAO = ["Alimentação", "Educação", "Lazer", "Transporte", "Vestuario"]


def criar_tags_padrao(apps, schema_editor):
    Tag = apps.get_model("lancamentos", "Tag")
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Tag.objects.bulk_create(
        [
            Tag(usuario_id=usuario_id, nome=nome)
            for usuario_id in User.objects.values_list("pk", flat=True)
            for nome in TAGS_PADRAO
        ],
        ignore_conflicts=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("lancamentos", "0006_perfilusuario"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=40)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tags", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["nome"]},
        ),
        migrations.AddConstraint(
            model_name="tag",
            constraint=models.UniqueConstraint(fields=("usuario", "nome"), name="tag_unica_por_usuario"),
        ),
        migrations.AddField(
            model_name="lancamento",
            name="tags",
            field=models.ManyToManyField(blank=True, related_name="lancamentos", to="lancamentos.tag"),
        ),
        migrations.RunPython(criar_tags_padrao, migrations.RunPython.noop),
    ]
