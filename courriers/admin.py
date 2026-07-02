from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (Acheminement, Contribuable, Courrier, Notification,
                     PieceJointe, Structure, Utilisateur)


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    list_display = ("username", "get_full_name", "role", "structure", "is_active")
    list_filter = ("role", "structure", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Profil administration", {"fields": ("role", "structure", "fonction", "telephone")}),
    )


@admin.register(Structure)
class StructureAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "parent")
    list_filter = ("type",)


@admin.register(Contribuable)
class ContribuableAdmin(admin.ModelAdmin):
    list_display = ("nif", "raison_sociale", "activite", "telephone")
    search_fields = ("nif", "raison_sociale")


class PieceInline(admin.TabularInline):
    model = PieceJointe
    extra = 0


class AcheminementInline(admin.TabularInline):
    model = Acheminement
    extra = 0
    readonly_fields = ("date",)


@admin.register(Courrier)
class CourrierAdmin(admin.ModelAdmin):
    list_display = ("reference", "type", "objet", "contribuable", "statut", "detenteur_courant")
    list_filter = ("type", "statut")
    search_fields = ("reference", "objet", "contribuable__nif", "contribuable__raison_sociale")
    inlines = [PieceInline, AcheminementInline]


admin.site.register(Notification)
admin.site.site_header = "Gestion des courriers — Administration"
admin.site.site_title = "Gestion des courriers"
