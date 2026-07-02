"""
Règles du circuit du courrier.

Descente (affectation) :  Secrétaire -> Directeur -> Chef division -> Chef section -> Agent
Remontée (validation)  :  Agent -> Chef section -> Chef division -> Directeur -> Secrétaire -> envoi
"""
from .models import Acheminement, Notification, Utilisateur

# Rôle vers lequel on affecte (descente)
NIVEAU_INFERIEUR = {
    Utilisateur.SECRETAIRE: Utilisateur.DIRECTEUR,
    Utilisateur.DIRECTEUR: Utilisateur.CHEF_DIVISION,
    Utilisateur.CHEF_DIVISION: Utilisateur.CHEF_SECTION,
    Utilisateur.CHEF_SECTION: Utilisateur.AGENT,
}

# Rôles autorisés à valider (remontée).
# La secrétaire ne valide pas : après validation du directeur, le courrier lui
# revient « prêt à envoyer » et elle l'expédie directement au contribuable.
ROLES_VALIDATION = {
    Utilisateur.CHEF_SECTION,
    Utilisateur.CHEF_DIVISION,
    Utilisateur.DIRECTEUR,
}


def superieur_pour(courrier, utilisateur):
    """Retourne la personne qui a affecté ce courrier à `utilisateur`
    (le supérieur direct dans ce circuit précis). None si introuvable."""
    ach = (
        courrier.acheminements
        .filter(vers_utilisateur=utilisateur, action=Acheminement.AFFECTATION)
        .order_by("-date")
        .first()
    )
    return ach.de_utilisateur if ach else None


def subordonne_pour(courrier, utilisateur):
    """Retourne la dernière personne qui a fait remonter le courrier à `utilisateur`
    (pour un renvoi en correction). None si introuvable."""
    ach = (
        courrier.acheminements
        .filter(vers_utilisateur=utilisateur, sens=Acheminement.REMONTANT)
        .order_by("-date")
        .first()
    )
    return ach.de_utilisateur if ach else None


def notifier(utilisateur, courrier, message):
    if utilisateur:
        Notification.objects.create(utilisateur=utilisateur, courrier=courrier, message=message)
