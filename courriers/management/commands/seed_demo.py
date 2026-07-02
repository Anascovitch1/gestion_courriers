"""Crée des données de démonstration : organigramme, comptes par rôle, contribuables.

Usage :  python manage.py seed_demo
Mot de passe commun à tous les comptes de démo : demo1234
"""
from django.core.management.base import BaseCommand

from courriers.models import Contribuable, Structure, Utilisateur

MDP = "demo1234"


class Command(BaseCommand):
    help = "Crée des données de démonstration (structures, utilisateurs, contribuables)."

    def handle(self, *args, **options):
        direction, _ = Structure.objects.get_or_create(
            nom="Direction des Grandes Entreprises", type=Structure.DIRECTION)
        division, _ = Structure.objects.get_or_create(
            nom="Division Vérification", type=Structure.DIVISION, parent=direction)
        section, _ = Structure.objects.get_or_create(
            nom="Section Contrôle sur place", type=Structure.SECTION, parent=division)

        comptes = [
            ("admin", "Admin", "Système", Utilisateur.ADMIN, direction, True),
            ("secretaire", "Awa", "Mensah", Utilisateur.SECRETAIRE, direction, False),
            ("directeur", "Kossi", "Adjavon", Utilisateur.DIRECTEUR, direction, False),
            ("chefdivision", "Yawa", "Bani", Utilisateur.CHEF_DIVISION, division, False),
            ("chefsection", "Komi", "Doe", Utilisateur.CHEF_SECTION, section, False),
            ("agent", "Ama", "Kodjo", Utilisateur.AGENT, section, False),
        ]
        for username, prenom, nom, role, structure, superuser in comptes:
            u, cree = Utilisateur.objects.get_or_create(
                username=username,
                defaults=dict(first_name=prenom, last_name=nom, role=role,
                              structure=structure, is_staff=superuser, is_superuser=superuser),
            )
            if cree:
                u.set_password(MDP)
                u.save()
                self.stdout.write(self.style.SUCCESS(f"  + compte {username} ({role})"))
            else:
                self.stdout.write(f"  = compte {username} déjà présent")

        demo_contribuables = [
            ("1000123456", "SARL TOGO NEGOCE", "Commerce général", "Lomé, Bd du 13 janvier"),
            ("1000654321", "ETS LA PROVIDENCE", "BTP", "Lomé, Agoè"),
            ("1000789012", "SOCIETE AGROVITAL SA", "Agroalimentaire", "Lomé, Zone portuaire"),
        ]
        for nif, rs, act, adr in demo_contribuables:
            Contribuable.objects.get_or_create(
                nif=nif, defaults=dict(raison_sociale=rs, activite=act, adresse=adr))

        self.stdout.write(self.style.SUCCESS(
            f"\nDonnées de démo prêtes. Connectez-vous avec n'importe quel identifiant "
            f"ci-dessus (mot de passe : {MDP})."))
