from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Etablissement


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    """
    Interface admin pour la gestion des établissements.
    """
    list_display = ['code', 'nom', 'is_active', 'site', 'created_at']
    list_filter = ['is_active', 'created_at', 'site']
    search_fields = ['code', 'nom', 'email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        (_("Informations de base"), {
            'fields': ('code', 'nom', 'is_active')
        }),
        (_("Contact"), {
            'fields': ('email', 'telephone', 'adresse'),
            'classes': ('collapse',)
        }),
        (_("Configuration technique"), {
            'fields': ('site',),
            'description': _("Configuration pour le système multi-tenant")
        }),
        (_("Métadonnées"), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Override pour les super-admins uniquement"""
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # Les non-superusers ne voient que leur établissement
        if hasattr(request.user, 'etablissement'):
            return qs.filter(id=request.user.etablissement.id)
        return qs.none()
    
    def has_add_permission(self, request):
        """Seuls les superusers peuvent ajouter des établissements"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Permission de modification selon le niveau utilisateur"""
        if request.user.is_superuser:
            return True
        if obj and hasattr(request.user, 'etablissement'):
            return obj == request.user.etablissement
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Seuls les superusers peuvent supprimer des établissements"""
        return request.user.is_superuser
