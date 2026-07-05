import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .decorators import role_requis
from .forms import (AffectationForm, ContribuableForm, CourrierForm,
                    ImportContribuableForm, PieceJointeForm, TraitementForm,
                    ValidationForm)
from .imports import importer_contribuables
from .pdf import generer_accuse, generer_bordereau
from .models import (Acheminement, Contribuable, Courrier, Notification,
                     PieceJointe, Utilisateur)
from .workflow import (NIVEAU_INFERIEUR, ROLES_VALIDATION, notifier,
                       subordonne_pour, superieur_pour)


# --------------------------------------------------------------------------- #
#  Tableau de bord                                                            #
# --------------------------------------------------------------------------- #
@login_required
def dashboard(request):
    u = request.user
    a_traiter = Courrier.objects.filter(detenteur_courant=u).exclude(statut=Courrier.ENVOYE)
    contexte = {
        "a_traiter": a_traiter,
        "nb_a_traiter": a_traiter.count(),
        "total_courriers": Courrier.objects.count(),
        "nb_entrants": Courrier.objects.filter(type=Courrier.ENTRANT).count(),
        "nb_sortants": Courrier.objects.filter(type=Courrier.SORTANT).count(),
        "nb_envoyes": Courrier.objects.filter(statut=Courrier.ENVOYE).count(),
        "derniers": Courrier.objects.all()[:8],
    }
    return render(request, "courriers/dashboard.html", contexte)


# --------------------------------------------------------------------------- #
#  Courriers : liste / détail / enregistrement                               #
# --------------------------------------------------------------------------- #
@login_required
def courrier_list(request):
    courriers = Courrier.objects.select_related("contribuable", "detenteur_courant").filter(archive=False)
    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    type_ = request.GET.get("type", "").strip()
    if q:
        courriers = courriers.filter(
            Q(reference__icontains=q) | Q(objet__icontains=q)
            | Q(contribuable__nif__icontains=q) | Q(contribuable__raison_sociale__icontains=q)
        )
    if statut:
        courriers = courriers.filter(statut=statut)
    if type_:
        courriers = courriers.filter(type=type_)
    contexte = {
        "courriers": courriers,
        "q": q, "statut": statut, "type": type_,
        "statuts": Courrier.STATUT_CHOICES, "types": Courrier.TYPE_CHOICES,
    }
    return render(request, "courriers/courrier_list.html", contexte)


@login_required
def courrier_detail(request, pk):
    courrier = get_object_or_404(
        Courrier.objects.select_related("contribuable", "enregistre_par", "detenteur_courant"), pk=pk)
    contexte = {
        "courrier": courrier,
        "acheminements": courrier.acheminements.select_related("de_utilisateur", "vers_utilisateur"),
        "pieces": courrier.pieces.all(),
        "peut_affecter": _peut_affecter(request.user, courrier),
        "peut_traiter": _peut_traiter(request.user, courrier),
        "peut_valider": _peut_valider(request.user, courrier),
        "peut_envoyer": _peut_envoyer(request.user, courrier),
        "peut_archiver": (request.user.role in (Utilisateur.SECRETAIRE, Utilisateur.ADMIN)
                          and courrier.statut == Courrier.ENVOYE and not courrier.archive),
    }
    return render(request, "courriers/courrier_detail.html", contexte)


@role_requis(Utilisateur.SECRETAIRE)
def courrier_create(request):
    if request.method == "POST":
        form = CourrierForm(request.POST)
        pj_form = PieceJointeForm(request.POST, request.FILES)
        if form.is_valid() and pj_form.is_valid():
            courrier = form.save(commit=False)
            courrier.enregistre_par = request.user
            courrier.detenteur_courant = request.user
            courrier.statut = Courrier.ENREGISTRE
            courrier.save()
            if pj_form.cleaned_data.get("fichier"):
                pj = pj_form.save(commit=False)
                pj.courrier = courrier
                pj.save()
            Acheminement.objects.create(
                courrier=courrier, de_utilisateur=None, vers_utilisateur=request.user,
                action=Acheminement.ENREGISTREMENT, commentaire="Courrier enregistré.")
            messages.success(request, f"Courrier {courrier.reference} enregistré.")
            return redirect("courrier_detail", pk=courrier.pk)
    else:
        form = CourrierForm()
        pj_form = PieceJointeForm()
    return render(request, "courriers/courrier_form.html", {"form": form, "pj_form": pj_form})


@login_required
def piece_ajouter(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if request.method == "POST":
        pj_form = PieceJointeForm(request.POST, request.FILES)
        if pj_form.is_valid() and pj_form.cleaned_data.get("fichier"):
            pj = pj_form.save(commit=False)
            pj.courrier = courrier
            pj.save()
            messages.success(request, "Pièce jointe ajoutée.")
    return redirect("courrier_detail", pk=pk)


# --------------------------------------------------------------------------- #
#  Workflow : affecter / traiter / valider / envoyer                         #
# --------------------------------------------------------------------------- #
def _est_detenteur(user, courrier):
    return courrier.detenteur_courant_id == user.id


def _peut_affecter(user, courrier):
    return (_est_detenteur(user, courrier)
            and user.role in NIVEAU_INFERIEUR
            and courrier.statut in (Courrier.ENREGISTRE, Courrier.EN_AFFECTATION))


def _peut_traiter(user, courrier):
    return (_est_detenteur(user, courrier)
            and user.role == Utilisateur.AGENT
            and courrier.statut == Courrier.EN_TRAITEMENT)


def _peut_valider(user, courrier):
    return (_est_detenteur(user, courrier)
            and user.role in ROLES_VALIDATION
            and courrier.statut == Courrier.EN_VALIDATION)


def _peut_envoyer(user, courrier):
    return (_est_detenteur(user, courrier)
            and user.role == Utilisateur.SECRETAIRE
            and courrier.statut == Courrier.PRET_ENVOI)


@login_required
def affecter(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if not _peut_affecter(request.user, courrier):
        messages.error(request, "Affectation impossible à cette étape.")
        return redirect("courrier_detail", pk=pk)
    role_cible = NIVEAU_INFERIEUR[request.user.role]
    if request.method == "POST":
        form = AffectationForm(request.POST, role_cible=role_cible)
        if form.is_valid():
            cible = form.cleaned_data["destinataire"]
            Acheminement.objects.create(
                courrier=courrier, de_utilisateur=request.user, vers_utilisateur=cible,
                action=Acheminement.AFFECTATION, sens=Acheminement.DESCENDANT,
                commentaire=form.cleaned_data["commentaire"])
            courrier.detenteur_courant = cible
            courrier.statut = (Courrier.EN_TRAITEMENT if role_cible == Utilisateur.AGENT
                               else Courrier.EN_AFFECTATION)
            courrier.save()
            notifier(cible, courrier, f"Nouveau courrier à traiter : {courrier.reference}")
            messages.success(request, f"Courrier affecté à {cible}.")
            return redirect("courrier_detail", pk=pk)
    else:
        form = AffectationForm(role_cible=role_cible)
    return render(request, "courriers/action_form.html", {
        "courrier": courrier, "form": form, "titre": "Affecter le courrier",
        "intro": f"Transmettre vers le niveau : {dict(Utilisateur.ROLE_CHOICES)[role_cible]}."})


@login_required
def traiter(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if not _peut_traiter(request.user, courrier):
        messages.error(request, "Traitement impossible à cette étape.")
        return redirect("courrier_detail", pk=pk)
    if request.method == "POST":
        form = TraitementForm(request.POST, request.FILES)
        if form.is_valid():
            if form.cleaned_data.get("fichier"):
                PieceJointe.objects.create(
                    courrier=courrier, fichier=form.cleaned_data["fichier"],
                    libelle="Projet de réponse")
            superieur = superieur_pour(courrier, request.user)
            Acheminement.objects.create(
                courrier=courrier, de_utilisateur=request.user, vers_utilisateur=superieur,
                action=Acheminement.TRAITEMENT, sens=Acheminement.REMONTANT,
                commentaire=form.cleaned_data["commentaire"])
            courrier.detenteur_courant = superieur
            courrier.statut = Courrier.EN_VALIDATION
            courrier.save()
            notifier(superieur, courrier, f"Courrier traité à valider : {courrier.reference}")
            messages.success(request, "Courrier traité et transmis pour validation.")
            return redirect("courrier_detail", pk=pk)
    else:
        form = TraitementForm()
    return render(request, "courriers/action_form.html", {
        "courrier": courrier, "form": form, "titre": "Traiter le courrier",
        "intro": "Rédigez le compte rendu et joignez le projet de réponse."})


@login_required
def valider(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if not _peut_valider(request.user, courrier):
        messages.error(request, "Validation impossible à cette étape.")
        return redirect("courrier_detail", pk=pk)
    if request.method == "POST":
        form = ValidationForm(request.POST)
        if form.is_valid():
            commentaire = form.cleaned_data["commentaire"]
            if form.cleaned_data["decision"] == "VALIDER":
                superieur = superieur_pour(courrier, request.user)
                if superieur and superieur.role == Utilisateur.SECRETAIRE:
                    # Dernière validation (directeur) : le courrier revient à la
                    # secrétaire « prêt à envoyer ». Elle ne valide plus, elle expédie.
                    Acheminement.objects.create(
                        courrier=courrier, de_utilisateur=request.user, vers_utilisateur=superieur,
                        action=Acheminement.VALIDATION, sens=Acheminement.REMONTANT,
                        commentaire=commentaire or "Validation finale.")
                    courrier.detenteur_courant = superieur
                    courrier.statut = Courrier.PRET_ENVOI
                    notifier(superieur, courrier, f"Courrier prêt à envoyer : {courrier.reference}")
                    messages.success(request, "Validé : le courrier est prêt à être envoyé au contribuable.")
                elif superieur:  # on remonte encore (chef de section -> division -> directeur)
                    Acheminement.objects.create(
                        courrier=courrier, de_utilisateur=request.user, vers_utilisateur=superieur,
                        action=Acheminement.VALIDATION, sens=Acheminement.REMONTANT,
                        commentaire=commentaire)
                    courrier.detenteur_courant = superieur
                    courrier.statut = Courrier.EN_VALIDATION
                    notifier(superieur, courrier, f"Courrier à valider : {courrier.reference}")
                    messages.success(request, "Validé et transmis au niveau supérieur.")
                else:  # cas limite : aucun supérieur trouvé -> prêt à envoyer
                    Acheminement.objects.create(
                        courrier=courrier, de_utilisateur=request.user, vers_utilisateur=request.user,
                        action=Acheminement.VALIDATION, sens=Acheminement.REMONTANT,
                        commentaire=commentaire or "Validation finale.")
                    courrier.statut = Courrier.PRET_ENVOI
                    messages.success(request, "Courrier prêt à être envoyé.")
            else:  # REJETER -> renvoi vers le subordonné
                cible = subordonne_pour(courrier, request.user)
                Acheminement.objects.create(
                    courrier=courrier, de_utilisateur=request.user, vers_utilisateur=cible,
                    action=Acheminement.REJET, sens=Acheminement.DESCENDANT,
                    commentaire=commentaire)
                courrier.detenteur_courant = cible
                courrier.statut = (Courrier.EN_TRAITEMENT if cible and cible.role == Utilisateur.AGENT
                                   else Courrier.EN_VALIDATION)
                notifier(cible, courrier, f"Courrier renvoyé pour correction : {courrier.reference}")
                messages.warning(request, "Courrier renvoyé pour correction.")
            courrier.save()
            return redirect("courrier_detail", pk=pk)
    else:
        form = ValidationForm()
    return render(request, "courriers/action_form.html", {
        "courrier": courrier, "form": form, "titre": "Valider le courrier",
        "intro": "Validez pour transmettre au niveau supérieur, ou rejetez pour renvoyer en correction."})


@login_required
def envoyer(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if not _peut_envoyer(request.user, courrier):
        messages.error(request, "Envoi impossible à cette étape.")
        return redirect("courrier_detail", pk=pk)
    if request.method == "POST":
        Acheminement.objects.create(
            courrier=courrier, de_utilisateur=request.user, vers_utilisateur=None,
            action=Acheminement.ENVOI, sens=Acheminement.REMONTANT,
            commentaire="Courrier envoyé au contribuable.")
        courrier.statut = Courrier.ENVOYE
        courrier.detenteur_courant = None
        courrier.save()
        messages.success(request, f"Courrier {courrier.reference} envoyé au contribuable.")
        return redirect("courrier_detail", pk=pk)
    return render(request, "courriers/action_form.html", {
        "courrier": courrier, "form": None, "titre": "Envoyer au contribuable",
        "intro": "Confirmez l'expédition du courrier au contribuable."})


# --------------------------------------------------------------------------- #
#  Contribuables : liste / création / import / recherche (autocomplétion)     #
# --------------------------------------------------------------------------- #
@login_required
def contribuable_list(request):
    q = request.GET.get("q", "").strip()
    contribuables = Contribuable.objects.all()
    if q:
        contribuables = contribuables.filter(Q(nif__icontains=q) | Q(raison_sociale__icontains=q))
    return render(request, "courriers/contribuable_list.html",
                  {"contribuables": contribuables, "q": q})


@role_requis(Utilisateur.SECRETAIRE, Utilisateur.ADMIN)
def contribuable_create(request):
    form = ContribuableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        c = form.save()
        messages.success(request, f"Contribuable {c} créé.")
        if "next" in request.GET:
            return redirect(request.GET["next"])
        return redirect("contribuable_list")
    return render(request, "courriers/contribuable_form.html", {"form": form})


@role_requis(Utilisateur.SECRETAIRE, Utilisateur.ADMIN)
def contribuable_import(request):
    resultat = None
    if request.method == "POST":
        form = ImportContribuableForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                crees, maj, erreurs = importer_contribuables(form.cleaned_data["fichier"])
                resultat = {"crees": crees, "maj": maj, "erreurs": erreurs}
                messages.success(request, f"Import terminé : {crees} créé(s), {maj} mis à jour.")
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"Erreur de lecture du fichier : {exc}")
    else:
        form = ImportContribuableForm()
    return render(request, "courriers/contribuable_import.html",
                  {"form": form, "resultat": resultat})


@login_required
def contribuable_recherche(request):
    """Autocomplétion : renvoie les contribuables correspondant à ?q=."""
    q = request.GET.get("q", "").strip()
    data = []
    if q:
        for c in Contribuable.objects.filter(
                Q(nif__icontains=q) | Q(raison_sociale__icontains=q))[:15]:
            data.append({"id": c.id, "nif": c.nif, "raison_sociale": c.raison_sociale,
                         "activite": c.activite})
    return JsonResponse({"resultats": data})


# --------------------------------------------------------------------------- #
#  Notifications                                                              #
# --------------------------------------------------------------------------- #
@login_required
def notifications_list(request):
    notifs = request.user.notifications.all()
    request.user.notifications.filter(lu=False).update(lu=True)
    return render(request, "courriers/notifications.html", {"notifs": notifs})


# --------------------------------------------------------------------------- #
#  Documents PDF : accusé de réception / bordereau                            #
# --------------------------------------------------------------------------- #
@login_required
def accuse_reception(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    pdf = generer_accuse(courrier)
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="accuse_{courrier.reference}.pdf"'
    return resp


@login_required
def bordereau_courriers(request):
    """Bordereau PDF de la liste filtrée (mêmes filtres que la liste des courriers)."""
    courriers = Courrier.objects.select_related("contribuable").filter(archive=False)
    q = request.GET.get("q", "").strip()
    statut = request.GET.get("statut", "").strip()
    type_ = request.GET.get("type", "").strip()
    if q:
        courriers = courriers.filter(
            Q(reference__icontains=q) | Q(objet__icontains=q)
            | Q(contribuable__nif__icontains=q) | Q(contribuable__raison_sociale__icontains=q))
    if statut:
        courriers = courriers.filter(statut=statut)
    if type_:
        courriers = courriers.filter(type=type_)
    pdf = generer_bordereau(courriers, titre="Bordereau des courriers")
    resp = HttpResponse(pdf, content_type="application/pdf")
    resp["Content-Disposition"] = 'inline; filename="bordereau_courriers.pdf"'
    return resp


# --------------------------------------------------------------------------- #
#  Statistiques : délais de traitement par structure                         #
# --------------------------------------------------------------------------- #
@role_requis(Utilisateur.ADMIN, Utilisateur.DIRECTEUR)
def statistiques(request):
    # Répartition par statut
    statut_labels, statut_values = [], []
    for code, libelle in Courrier.STATUT_CHOICES:
        statut_labels.append(libelle)
        statut_values.append(Courrier.objects.filter(statut=code).count())

    # Délais de traitement (enregistrement -> envoi) des courriers expédiés
    delais = []
    par_structure = {}
    for c in Courrier.objects.filter(statut=Courrier.ENVOYE):
        envoi = c.acheminements.filter(action=Acheminement.ENVOI).order_by("-date").first()
        if not envoi:
            continue
        jours = (envoi.date - c.date_enregistrement).total_seconds() / 86400.0
        delais.append(jours)
        traitement = c.acheminements.filter(action=Acheminement.TRAITEMENT).first()
        agent = traitement.de_utilisateur if traitement else None
        nom = agent.structure.nom if (agent and agent.structure) else "Non précisé"
        par_structure.setdefault(nom, []).append(jours)

    delai_moyen = round(sum(delais) / len(delais), 1) if delais else 0
    struct_labels = list(par_structure.keys())
    struct_moy = [round(sum(v) / len(v), 1) for v in par_structure.values()]
    struct_table = [(lab, len(par_structure[lab]), moy)
                    for lab, moy in zip(struct_labels, struct_moy)]

    contexte = {
        "total": Courrier.objects.count(),
        "nb_envoyes": Courrier.objects.filter(statut=Courrier.ENVOYE).count(),
        "nb_archives": Courrier.objects.filter(archive=True).count(),
        "delai_moyen": delai_moyen,
        "struct_table": struct_table,
        "donnees_json": json.dumps({
            "statut_labels": statut_labels, "statut_values": statut_values,
            "struct_labels": struct_labels, "struct_moy": struct_moy,
        }),
    }
    return render(request, "courriers/statistiques.html", contexte)


# --------------------------------------------------------------------------- #
#  Archivage des courriers clôturés                                          #
# --------------------------------------------------------------------------- #
@role_requis(Utilisateur.SECRETAIRE, Utilisateur.ADMIN)
def archiver(request, pk):
    courrier = get_object_or_404(Courrier, pk=pk)
    if courrier.statut != Courrier.ENVOYE:
        messages.error(request, "Seul un courrier envoyé peut être archivé.")
        return redirect("courrier_detail", pk=pk)
    if request.method == "POST":
        courrier.archive = True
        courrier.date_archivage = timezone.now()
        courrier.save()
        messages.success(request, f"Courrier {courrier.reference} archivé.")
    return redirect("courrier_detail", pk=pk)


@login_required
def archives(request):
    q = request.GET.get("q", "").strip()
    courriers = Courrier.objects.select_related("contribuable").filter(archive=True)
    if q:
        courriers = courriers.filter(
            Q(reference__icontains=q) | Q(objet__icontains=q)
            | Q(contribuable__nif__icontains=q) | Q(contribuable__raison_sociale__icontains=q))
    return render(request, "courriers/archives.html", {"courriers": courriers, "q": q})
