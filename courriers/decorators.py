"""Décorateurs : restreindre une vue à certains rôles."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def role_requis(*roles):
    def decorateur(vue):
        @wraps(vue)
        def _wrap(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if request.user.role not in roles and not request.user.is_superuser:
                messages.error(request, "Vous n'avez pas les droits pour cette action.")
                return redirect("dashboard")
            return vue(request, *args, **kwargs)
        return _wrap
    return decorateur
