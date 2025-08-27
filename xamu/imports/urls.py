from django.urls import path

from . import views

app_name = 'imports'

urlpatterns = [
    path("", views.ImportDashboardView.as_view(), name="dashboard"),
    path("create/", views.create_import_session, name="create"),
    path("session/<int:session_id>/", views.ImportSessionDetailView.as_view(), name="detail"),
    path("session/<int:session_id>/delete/", views.delete_import_session, name="delete"),
    path("comptes/", views.comptes_management, name="comptes_management"), # New URL for comptes management
]