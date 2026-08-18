"""Public account registration forms."""

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms


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
