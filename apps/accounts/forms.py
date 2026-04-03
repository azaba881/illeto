import hashlib

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .models import User


class IlletoPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class ProfileForm(forms.ModelForm):
    """Profil (nom, email, téléphone) — commun étudiant / entreprise."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone_number")
        labels = {
            "first_name": "Prénom",
            "last_name": "Nom",
            "email": "Email",
            "phone_number": "Téléphone",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.fields:
            self.fields[name].widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if not email:
            raise ValidationError("L’adresse e-mail est obligatoire.")
        qs = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Cette adresse e-mail est déjà utilisée.")
        return email


class IlletoAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email ou nom d'utilisateur",
        widget=forms.TextInput(
            attrs={
                "class": "auth-input",
                "placeholder": "vous@exemple.bj ou votre identifiant",
                "autocomplete": "username",
                "id": "login-identifier",
            }
        ),
    )
    password = forms.CharField(
        label="Mot de passe",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "class": "auth-input auth-input-password pr-10",
                "placeholder": "••••••••",
                "autocomplete": "current-password",
                "id": "login-pass",
            }
        ),
    )
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Identifiants invalides. Vérifiez votre email ou nom d'utilisateur et votre mot de passe.",
    }


class RegisterForm(UserCreationForm):
    accept_terms = forms.BooleanField(
        required=True,
        label="",
        error_messages={
            "required": "Vous devez accepter les conditions d'utilisation et la politique de confidentialité.",
        },
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].label = "Email"
        self.fields["email"].widget = forms.EmailInput(
            attrs={
                "class": "auth-input",
                "placeholder": "vous@exemple.bj",
                "autocomplete": "email",
                "id": "reg-email",
            }
        )
        self.fields["password1"].label = "Mot de passe"
        self.fields["password1"].help_text = ""
        self.fields["password1"].widget = forms.PasswordInput(
            attrs={
                "class": "auth-input auth-input-password pr-10",
                "placeholder": "Au moins 8 caractères",
                "autocomplete": "new-password",
                "id": "reg-pass",
            }
        )
        self.fields["password2"].label = "Confirmer le mot de passe"
        self.fields["password2"].help_text = ""
        self.fields["password2"].widget = forms.PasswordInput(
            attrs={
                "class": "auth-input auth-input-password pr-10",
                "placeholder": "Répétez le mot de passe",
                "autocomplete": "new-password",
                "id": "reg-pass2",
            }
        )
        self.fields["accept_terms"].widget = forms.CheckboxInput(
            attrs={
                "class": "mt-1 rounded border-white/20 bg-transparent",
                "required": True,
            }
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if email and User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email

    @staticmethod
    def _username_from_email(email: str) -> str:
        """Remplit le champ obligatoire username à partir de l'email (unique)."""
        normalized = User.objects.normalize_email((email or "").strip()).lower()
        if len(normalized) <= 150:
            base = normalized
        else:
            base = hashlib.sha256(normalized.encode()).hexdigest()[:150]
        if not User.objects.filter(username__iexact=base).exists():
            return base
        for i in range(1, 10_000):
            suffix = f"_{i}"
            candidate = (base[: 150 - len(suffix)] + suffix)[:150]
            if not User.objects.filter(username__iexact=candidate).exists():
                return candidate
        raise ValidationError("Impossible de générer un identifiant interne unique.")

    def _post_clean(self):
        email = self.cleaned_data.get("email")
        if email:
            try:
                self.instance.username = self._username_from_email(email)
            except ValidationError as e:
                self.add_error("email", e)
                return
        super()._post_clean()
