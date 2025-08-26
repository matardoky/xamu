"""
URLs spécifiques aux tenants.
Toutes ces URLs seront préfixées par /<tenant_code>/
"""

from django.urls import include
from django.urls import path

from . import views

app_name = "tenant"

urlpatterns = [
    # Page d'accueil du tenant
    path("", views.HomeView.as_view(), name="home"),

    # Dashboard principal du tenant
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),

    # Invitation dans le contexte tenant (accessible sans authentification)
    path("invitation/<uuid:token>/", views.AcceptInvitationView.as_view(), name="accept_invitation"),

    # Gestion des utilisateurs dans le contexte tenant
    path("users/", include("xamu.users.urls", namespace="users")),
    path("no-tenant/", views.NoTenantView.as_view(), name="no_tenant"),
]
