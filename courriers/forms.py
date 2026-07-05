from django import forms

from .models import Contribuable, Courrier, PieceJointe, Utilisateur


class DateInput(forms.DateInput):
    input_type = "date"


class ContribuableForm(forms.ModelForm):
    class Meta:
        model = Contribuable
        fields = ["nif", "raison_sociale", "activite", "adresse", "telephone", "email", "regime"]
        widgets = {f: forms.TextInput(attrs={"class": "form-control"}) for f in
                   ["nif", "raison_sociale", "activite", "adresse", "telephone", "regime"]}
        widgets["email"] = forms.EmailInput(attrs={"class": "form-control"})


class CourrierForm(forms.ModelForm):
    class Meta:
        model = Courrier
        fields = ["type", "contribuable", "objet", "description", "date_courrier", "courrier_parent"]
        widgets = {
            "type": forms.Select(attrs={"class": "form-select"}),
            "contribuable": forms.Select(attrs={"class": "form-select", "id": "id_contribuable"}),
            "objet": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "date_courrier": DateInput(attrs={"class": "form-control"}),
            "courrier_parent": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["courrier_parent"].required = False
        self.fields["courrier_parent"].queryset = Courrier.objects.filter(type=Courrier.ENTRANT)
        self.fields["courrier_parent"].label = "Courrier d'origine (si réponse)"


class PieceJointeForm(forms.ModelForm):
    class Meta:
        model = PieceJointe
        fields = ["fichier", "libelle"]
        widgets = {
            "fichier": forms.ClearableFileInput(attrs={"class": "form-control"}),
            "libelle": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex. : courrier scanné"}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le scan est facultatif à l'enregistrement.
        self.fields["fichier"].required = False
        self.fields["libelle"].required = False

class AffectationForm(forms.Form):
    destinataire = forms.ModelChoiceField(
        queryset=Utilisateur.objects.none(), label="Affecter à",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    commentaire = forms.CharField(
        label="Instructions", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )

    def __init__(self, *args, role_cible=None, **kwargs):
        super().__init__(*args, **kwargs)
        if role_cible:
            self.fields["destinataire"].queryset = Utilisateur.objects.filter(role=role_cible, is_active=True)


class TraitementForm(forms.Form):
    commentaire = forms.CharField(
        label="Compte rendu du traitement",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    fichier = forms.FileField(
        label="Projet de réponse (scan / fichier)", required=False,
        widget=forms.ClearableFileInput(attrs={"class": "form-control"}),
    )


class ValidationForm(forms.Form):
    DECISION = [("VALIDER", "Valider et transmettre"), ("REJETER", "Rejeter / renvoyer pour correction")]
    decision = forms.ChoiceField(
        choices=DECISION, widget=forms.RadioSelect, label="Décision")
    commentaire = forms.CharField(
        label="Observation", required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 2}),
    )


class ImportContribuableForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier Excel (.xlsx)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": ".xlsx"}),
    )
