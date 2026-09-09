"""
Modèles de données — Gestion des courriers d'une administration fiscale.

Entités :
  - Structure       : organigramme (Direction / Division / Section)
  - Utilisateur     : compte + rôle + structure de rattachement
  - Contribuable    : identifié par son NIF (base importable)
  - Courrier        : courrier entrant ou sortant
  - PieceJointe     : document scanné rattaché à un courrier
  - Acheminement    : trace chaque mouvement (cœur de la traçabilité)
  - Notification    : alerte un utilisateur quand un courrier lui parvient
"""
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils import timezone


class Structure(models.Model):
    DIRECTION = "DIRECTION"
    DIVISION = "DIVISION"
    SECTION = "SECTION"
    TYPE_CHOICES = [
        (DIRECTION, "Direction"),
        (DIVISION, "Division"),
        (SECTION, "Section"),
    ]
    nom = models.CharField("Nom", max_length=150)
    type = models.CharField("Type", max_length=20, choices=TYPE_CHOICES)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="enfants", verbose_name="Structure parente",
    )

    class Meta:
        verbose_name = "Structure"
        verbose_name_plural = "Structures"
        ordering = ["type", "nom"]

    def __str__(self):
        return f"{self.get_type_display()} - {self.nom}"


class Utilisateur(AbstractUser):
    """Compte utilisateur étendu : rôle hiérarchique + structure."""

    ADMIN = "ADMIN"
    SECRETAIRE = "SECRETAIRE"
    DIRECTEUR = "DIRECTEUR"
    CHEF_DIVISION = "CHEF_DIVISION"
    CHEF_SECTION = "CHEF_SECTION"
    AGENT = "AGENT"
    ROLE_CHOICES = [
        (ADMIN, "Administrateur"),
        (SECRETAIRE, "Secrétaire"),
        (DIRECTEUR, "Directeur"),
        (CHEF_DIVISION, "Chef de division"),
        (CHEF_SECTION, "Chef de section"),
        (AGENT, "Agent"),
    ]

    role = models.CharField("Rôle", max_length=20, choices=ROLE_CHOICES, default=AGENT)
    structure = models.ForeignKey(
        Structure, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="membres", verbose_name="Structure de rattachement",
    )
    fonction = models.CharField("Fonction", max_length=150, blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"

    def __str__(self):
        nom = self.get_full_name().strip()
        return f"{nom} ({self.get_role_display()})" if nom else self.username


class Contribuable(models.Model):
    """Contribuable identifié par son NIF — base importable depuis Excel."""

    nif = models.CharField("NIF", max_length=30, unique=True)
    raison_sociale = models.CharField("Raison sociale", max_length=255)
    activite = models.CharField("Activité", max_length=255, blank=True)
    adresse = models.CharField("Adresse", max_length=255, blank=True)
    telephone = models.CharField("Téléphone", max_length=30, blank=True)
    email = models.EmailField("E-mail", blank=True)
    regime = models.CharField("Régime fiscal", max_length=100, blank=True)

    class Meta:
        verbose_name = "Contribuable"
        verbose_name_plural = "Contribuables"
        ordering = ["raison_sociale"]

    def __str__(self):
        return f"{self.nif} - {self.raison_sociale}"


class Courrier(models.Model):
    ENTRANT = "ENTRANT"
    SORTANT = "SORTANT"
    TYPE_CHOICES = [(ENTRANT, "Entrant"), (SORTANT, "Sortant")]

    ENREGISTRE = "ENREGISTRE"
    EN_AFFECTATION = "EN_AFFECTATION"
    EN_TRAITEMENT = "EN_TRAITEMENT"
    EN_VALIDATION = "EN_VALIDATION"
    PRET_ENVOI = "PRET_ENVOI"
    ENVOYE = "ENVOYE"
    STATUT_CHOICES = [
        (ENREGISTRE, "Enregistré"),
        (EN_AFFECTATION, "En cours d'affectation"),
        (EN_TRAITEMENT, "En traitement"),
        (EN_VALIDATION, "En validation"),
        (PRET_ENVOI, "Prêt à envoyer"),
        (ENVOYE, "Envoyé au contribuable"),
    ]

    reference = models.CharField("Référence", max_length=40, unique=True, blank=True)
    type = models.CharField("Type", max_length=10, choices=TYPE_CHOICES, default=ENTRANT)
    contribuable = models.ForeignKey(
        Contribuable, on_delete=models.PROTECT, related_name="courriers",
        verbose_name="Contribuable",
    )
    objet = models.CharField("Objet", max_length=255)
    description = models.TextField("Description", blank=True)
    date_courrier = models.DateField("Date du courrier", default=timezone.localdate)
    date_enregistrement = models.DateTimeField("Enregistré le", auto_now_add=True)
    statut = models.CharField("Statut", max_length=20, choices=STATUT_CHOICES, default=ENREGISTRE)
    enregistre_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="courriers_enregistres", verbose_name="Enregistré par",
    )
    detenteur_courant = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="courriers_en_charge", verbose_name="Détenteur actuel",
    )
    courrier_parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="reponses", verbose_name="Courrier d'origine",
    )
    archive = models.BooleanField("Archivé", default=False)
    date_archivage = models.DateTimeField("Archivé le", null=True, blank=True)

    class Meta:
        verbose_name = "Courrier"
        verbose_name_plural = "Courriers"
        ordering = ["-date_enregistrement"]

    def __str__(self):
        return f"{self.reference} - {self.objet}"

    def get_absolute_url(self):
        return reverse("courrier_detail", args=[self.pk])

    def save(self, *args, **kwargs):
        if not self.reference:
            prefix = "CE" if self.type == self.ENTRANT else "CS"
            annee = timezone.now().year
            n = Courrier.objects.filter(type=self.type, reference__startswith=f"{prefix}-{annee}").count() + 1
            self.reference = f"{prefix}-{annee}-{n:04d}"
        super().save(*args, **kwargs)


class PieceJointe(models.Model):
    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name="pieces")
    fichier = models.FileField("Fichier scanné", upload_to="courriers/%Y/%m/",blank=True, null=True)
    libelle = models.CharField("Libellé", max_length=200, blank=True)
    date_ajout = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"

    def __str__(self):
        return self.libelle or self.fichier.name


class Acheminement(models.Model):
    """Une ligne par mouvement du courrier - assure le suivi et la traçabilité."""

    AFFECTATION = "AFFECTATION"
    TRAITEMENT = "TRAITEMENT"
    VALIDATION = "VALIDATION"
    REJET = "REJET"
    ENVOI = "ENVOI"
    ENREGISTREMENT = "ENREGISTREMENT"
    ACTION_CHOICES = [
        (ENREGISTREMENT, "Enregistrement"),
        (AFFECTATION, "Affectation"),
        (TRAITEMENT, "Traitement"),
        (VALIDATION, "Validation"),
        (REJET, "Rejet / renvoi pour correction"),
        (ENVOI, "Envoi au contribuable"),
    ]

    DESCENDANT = "DESCENDANT"
    REMONTANT = "REMONTANT"
    SENS_CHOICES = [(DESCENDANT, "Descendant"), (REMONTANT, "Remontant")]

    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, related_name="acheminements")
    de_utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="De",
    )
    vers_utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="+", verbose_name="Vers",
    )
    action = models.CharField("Action", max_length=20, choices=ACTION_CHOICES)
    sens = models.CharField("Sens", max_length=12, choices=SENS_CHOICES, blank=True)
    commentaire = models.TextField("Commentaire / instructions", blank=True)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acheminement"
        verbose_name_plural = "Acheminements"
        ordering = ["date"]

    def __str__(self):
        return f"{self.courrier.reference} : {self.get_action_display()}"


class Notification(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    courrier = models.ForeignKey(Courrier, on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    lu = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date"]

    def __str__(self):
        return self.message
