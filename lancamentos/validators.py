from django.core.exceptions import ValidationError


class SenhaForteValidator:
    """Exige pelo menos 1 número e 1 símbolo."""

    def validate(self, password, user=None):
        erros = []
        if not any(c.isdigit() for c in password):
            erros.append(
                ValidationError("A senha deve ter pelo menos 1 número.", code="sem_numero")
            )
        if not any(not c.isalnum() and not c.isspace() for c in password):
            erros.append(
                ValidationError(
                    "A senha deve ter pelo menos 1 símbolo (por exemplo ! @ # $ %).",
                    code="sem_simbolo",
                )
            )
        if erros:
            raise ValidationError(erros)

    def get_help_text(self):
        return "Sua senha deve ter pelo menos 1 número e 1 símbolo (por exemplo ! @ # $ %)."