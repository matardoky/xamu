"""
URLs spécifiques aux tenants.
Toutes ces URLs seront préfixées par /<tenant_code>/
"""

from django.urls import path, include
from django.views.generic import TemplateView

from .utils import tenant_required

app_name = 'tenant'

urlpatterns = [
    # Dashboard principal du tenant
    path('dashboard/', 
         tenant_required(TemplateView.as_view(template_name='schools/dashboard.html')), 
         name='dashboard'),
    
    # Gestion des utilisateurs dans le contexte tenant (pour l'instant, URLs utilisateurs standard)
    path('users/', include('xamu.users.urls')),
    
    # Pages génériques avec contexte tenant
    path('', 
         tenant_required(TemplateView.as_view(template_name='schools/home.html')), 
         name='home'),
]