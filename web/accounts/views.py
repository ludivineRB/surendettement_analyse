"""Public account registration views."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from web.accounts.forms import AccountManagementForm, RegistrationForm
from web.accounts.services import ROLE_NAMES, assign_role, delete_account_data


ROLE_LABELS = {
    "viewer": "Lecteur",
    "analyst": "Analyste",
    "administrator": "Administrateur applicatif",
}


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


@login_required
def access_requests(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    if request.method == "POST":
        role = request.POST.get("role")
        if role not in ROLE_NAMES:
            messages.error(request, "Le rôle sélectionné est invalide.")
            return redirect("access-requests")
        user = get_object_or_404(
            get_user_model(),
            pk=request.POST.get("user_id"),
            is_active=False,
        )
        assign_role(user, role)
        user.is_active = True
        user.save(update_fields=("is_active",))
        messages.success(
            request,
            f"Le compte {user.username} a été approuvé comme {ROLE_LABELS[role].lower()}.",
        )
        return redirect("access-requests")

    pending_users = get_user_model().objects.filter(is_active=False).order_by(
        "date_joined", "username"
    )
    users = get_user_model().objects.prefetch_related("groups").order_by(
        "username"
    )
    return render(
        request,
        "accounts/access_requests.html",
        {
            "pending_users": pending_users,
            "users": users,
            "role_labels": ROLE_LABELS,
        },
    )


@login_required
def edit_account(request, user_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    user = get_object_or_404(get_user_model(), pk=user_id)
    was_active_superuser = user.is_superuser and user.is_active
    form = AccountManagementForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        removes_last_superuser = (
            was_active_superuser
            and (not form.cleaned_data["is_superuser"] or not form.cleaned_data["is_active"])
            and not get_user_model().objects.filter(
                is_superuser=True, is_active=True
            ).exclude(pk=user.pk).exists()
        )
        if removes_last_superuser:
            form.add_error(
                "is_superuser",
                "Le dernier superuser actif ne peut pas être rétrogradé ou désactivé.",
            )
        else:
            updated_user = form.save()
            role = form.cleaned_data["role"]
            if role:
                assign_role(updated_user, role)
            else:
                updated_user.groups.remove(
                    *updated_user.groups.filter(name__in=ROLE_NAMES)
                )
            messages.success(request, f"Le compte {updated_user.username} a été modifié.")
            return redirect("access-requests")
    return render(
        request,
        "accounts/edit_account.html",
        {"form": form, "managed_user": user},
    )


@login_required
def delete_account(request, user_id):
    if not request.user.is_superuser:
        raise PermissionDenied
    user = get_object_or_404(get_user_model(), pk=user_id)
    if user.pk == request.user.pk:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte connecté.")
        return redirect("access-requests")
    if (
        user.is_superuser
        and user.is_active
        and not get_user_model().objects.filter(
            is_superuser=True, is_active=True
        ).exclude(pk=user.pk).exists()
    ):
        messages.error(request, "Le dernier superuser actif ne peut pas être supprimé.")
        return redirect("access-requests")
    if request.method == "POST":
        username = user.username
        conversations = delete_account_data(user)
        messages.success(
            request,
            f"Le compte {username} et {conversations} conversation(s) ont été supprimés.",
        )
        return redirect("access-requests")
    return render(
        request,
        "accounts/delete_account.html",
        {"managed_user": user, "conversation_count": user.assistant_conversations.count()},
    )
