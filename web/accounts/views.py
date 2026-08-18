"""Public account registration views."""

from django.contrib import messages
from django.shortcuts import redirect, render

from web.accounts.forms import RegistrationForm


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Votre demande a été enregistrée. Un administrateur doit "
            "maintenant valider votre compte et vos droits.",
        )
        return redirect("login")
    return render(request, "registration/register.html", {"form": form})
