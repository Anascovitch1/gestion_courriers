from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("connexion/", auth_views.LoginView.as_view(
        template_name="courriers/login.html"), name="login"),
    path("deconnexion/", auth_views.LogoutView.as_view(), name="logout"),

    # Courriers
    path("courriers/", views.courrier_list, name="courrier_list"),
    path("courriers/nouveau/", views.courrier_create, name="courrier_create"),
    path("courriers/<int:pk>/", views.courrier_detail, name="courrier_detail"),
    path("courriers/<int:pk>/piece/", views.piece_ajouter, name="piece_ajouter"),
    path("courriers/<int:pk>/affecter/", views.affecter, name="affecter"),
    path("courriers/<int:pk>/traiter/", views.traiter, name="traiter"),
    path("courriers/<int:pk>/valider/", views.valider, name="valider"),
    path("courriers/<int:pk>/envoyer/", views.envoyer, name="envoyer"),
    path("courriers/<int:pk>/accuse/", views.accuse_reception, name="accuse_reception"),
    path("courriers/<int:pk>/archiver/", views.archiver, name="archiver"),
    path("courriers/bordereau/", views.bordereau_courriers, name="bordereau"),
    path("archives/", views.archives, name="archives"),
    path("statistiques/", views.statistiques, name="statistiques"),

    # Contribuables
    path("contribuables/", views.contribuable_list, name="contribuable_list"),
    path("contribuables/nouveau/", views.contribuable_create, name="contribuable_create"),
    path("contribuables/import/", views.contribuable_import, name="contribuable_import"),
    path("contribuables/recherche/", views.contribuable_recherche, name="contribuable_recherche"),

    # Notifications
    path("notifications/", views.notifications_list, name="notifications"),
]
