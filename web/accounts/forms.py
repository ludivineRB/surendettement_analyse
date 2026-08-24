"""Public account registration forms."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms

from web.accounts.services import ROLE_NAMES


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(label="Adresse électronique", required=True)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Un compte utilise déjà cette adresse électronique."
            )
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_active = False
        if commit:
            user.save()
        return user


class AccountManagementForm(forms.ModelForm):
    role = forms.ChoiceField(
        label="Rôle applicatif",
        required=False,
        choices=(
            ("", "Aucun rôle"),
            ("viewer", "Lecteur"),
            ("analyst", "Analyste"),
            ("administrator", "Administrateur applicatif"),
        ),
    )

    class Meta:
        model = get_user_model()
        fields = (
            "username", "email", "first_name", "last_name",
            "is_active", "is_staff", "is_superuser",
        )
        labels = {
            "username": "Identifiant",
            "email": "Adresse électronique",
            "first_name": "Prénom",
            "last_name": "Nom",
            "is_active": "Compte actif",
            "is_staff": "Accès à l’administration Django",
            "is_superuser": "Superuser",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role = self.instance.groups.filter(name__in=ROLE_NAMES).values_list(
            "name", flat=True
        ).first()
        self.fields["role"].initial = role or ""
