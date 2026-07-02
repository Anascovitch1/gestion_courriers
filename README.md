# GesCourrier — Gestion des courriers d'une administration fiscale

Application web (Django) de gestion des courriers entrants et sortants, avec
circuit d'affectation hiérarchique (directeur → chef de division → chef de
section → agent), traitement, validation remontante, suivi/traçabilité,
numérisation (scan) et import Excel de la base des contribuables.

Projet réalisé dans le cadre d'un mémoire de licence en développement web.

## 1. Prérequis

- Python 3.10 ou plus

## 2. Installation

```bash
# Dans le dossier du projet
python -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Base de données et données de démonstration

```bash
python manage.py makemigrations courriers
python manage.py migrate
python manage.py seed_demo       # crée l'organigramme + un compte par rôle
```

`seed_demo` crée les comptes suivants (mot de passe commun : **demo1234**) :

| Identifiant   | Rôle             |
|---------------|------------------|
| `secretaire`  | Secrétaire       |
| `directeur`   | Directeur        |
| `chefdivision`| Chef de division |
| `chefsection` | Chef de section  |
| `agent`       | Agent            |
| `admin`       | Administrateur (superuser) |

## 4. Lancer le serveur

```bash
python manage.py runserver
```

Application : http://127.0.0.1:8000/
Administration Django : http://127.0.0.1:8000/admin/

## 5. Démonstration du circuit complet

1. **secretaire** : *Enregistrer un courrier* → recherche le contribuable par
   NIF (autocomplétion), joint le scan, enregistre, puis **Affecte** au directeur.
2. **directeur** → **Affecte** au chef de division.
3. **chefdivision** → **Affecte** au chef de section.
4. **chefsection** → **Affecte** à l'agent.
5. **agent** : **Traite** le courrier (compte rendu + projet de réponse), ce qui
   le fait remonter automatiquement par le même canal.
6. **chefsection**, **chefdivision**, **directeur** : **Valident** (ou rejettent
   pour correction) à chaque niveau.
7. **secretaire** : valide une dernière fois puis **Envoie au contribuable**.

À tout moment, la fiche d'un courrier affiche son **suivi** (timeline complète
des acheminements), ce qui permet de savoir où il se trouve.

## 6. Import de la base des contribuables

*Contribuables → Importer (Excel)*. Un modèle est fourni :
`modele_import_contribuables.xlsx`. En-têtes attendus : NIF, Raison sociale,
Activité, Adresse, Téléphone, Email, Régime. Les fiches existantes (même NIF)
sont mises à jour.

## 7. Structure du projet

```
gestion_courriers/        # configuration du projet
courriers/
  models.py               # 7 entités (dont Acheminement = traçabilité)
  workflow.py             # règles du circuit (descente / remontée)
  views.py                # auth, dashboard, workflow, contribuables
  forms.py                # formulaires
  imports.py              # import Excel (openpyxl)
  decorators.py           # contrôle d'accès par rôle
  admin.py                # administration Django
  templates/courriers/    # gabarits Bootstrap 5
  static/courriers/       # CSS
  management/commands/    # seed_demo
```

## 8. Fonctionnalités avancées

- Génération PDF : accusé de réception par courrier (bouton sur la fiche) et
  bordereau de la liste filtrée (bouton sur la liste des courriers), via ReportLab.
- Tableau de bord statistique (rôles Directeur / Administrateur, menu
  « Statistiques ») : répartition des courriers par statut et délai moyen de
  traitement par structure, avec graphiques Chart.js.
- Archivage des courriers clôturés : un courrier envoyé peut être archivé ; les
  archives sont consultables dans le menu « Archives » et n'apparaissent plus
  dans la liste active.

## 9. Pistes d'extension

- API REST (Django REST Framework) pour une application mobile native.
- Notifications par e-mail en plus des notifications internes.
- Recherche plein texte et export des archives.

## 10. Déploiement sur Render

Le projet est prêt pour Render (fichiers `build.sh` et `render.yaml`, `settings.py`
lisant ses paramètres depuis l'environnement, WhiteNoise pour les fichiers statiques,
PostgreSQL via `DATABASE_URL`).

Déploiement via Blueprint :
1. Pousser le projet sur GitHub (le `render.yaml` doit être à la racine).
2. Sur render.com : New → Blueprint → sélectionner le dépôt. Render crée la base
   PostgreSQL et le service web, et injecte `DATABASE_URL`, `SECRET_KEY`, `DEBUG=False`.
3. Après le premier déploiement, ouvrir Shell (onglet du service) et exécuter :
   `python manage.py seed_demo` (données de démo) ou
   `python manage.py createsuperuser` (compte administrateur).

Remarque : sur le plan gratuit, le système de fichiers est éphémère ; les pièces
scannées (dossier `media/`) sont perdues au redéploiement. Pour les conserver,
ajouter un disque persistant Render ou un stockage cloud (ex. Amazon S3).
