from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.html import format_html

from .models import Etablissement, EtablissementInvitation


class InvitationInline(admin.StackedInline):
    """
    Inline pour gérer l'invitation directement depuis l'établissement.
    """
    model = EtablissementInvitation
    extra = 0
    max_num = 1
    fields = ['email', 'expires_at', 'used', 'used_at', 'user_created']
    readonly_fields = ['used', 'used_at', 'user_created', 'token', 'created_at']
    
    def has_add_permission(self, request, obj=None):
        """Permet d'ajouter une invitation seulement si elle n'existe pas"""
        if obj and hasattr(obj, 'invitation'):
            return False
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Permet de modifier l'invitation"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Permet de supprimer l'invitation"""
        return request.user.is_superuser


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    """
    Interface admin pour la gestion des établissements avec système d'invitation.
    """
    list_display = ['code', 'nom', 'is_active', 'invitation_status', 'site', 'created_at']
    list_filter = ['is_active', 'created_at', 'site']
    search_fields = ['code', 'nom', 'email']
    readonly_fields = ['created_at', 'updated_at']
    actions = ['send_invitation', 'activate_etablissement', 'deactivate_etablissement']
    
    inlines = [InvitationInline]
    
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
    
    def invitation_status(self, obj):
        """Affiche le statut de l'invitation"""
        if not hasattr(obj, 'invitation'):
            return format_html('<span style="color: orange;">⚠️ Aucune invitation</span>')
        
        invitation = obj.invitation
        if invitation.used:
            return format_html(
                '<span style="color: green;">✅ Utilisée par {}</span>',
                invitation.user_created.email if invitation.user_created else "Utilisateur supprimé"
            )
        elif invitation.is_expired:
            return format_html('<span style="color: red;">❌ Expirée</span>')
        else:
            return format_html('<span style="color: blue;">📧 En attente</span>')
    
    invitation_status.short_description = _("Statut invitation")
    
    def get_queryset(self, request):
        """Seuls les super-admins peuvent gérer les établissements"""
        qs = super().get_queryset(request).select_related('invitation', 'invitation__user_created')
        if request.user.is_superuser:
            return qs
        # Les non-superusers n'ont aucun accès
        return qs.none()
    
    def has_add_permission(self, request):
        """Seuls les superusers peuvent ajouter des établissements"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Seuls les superusers peuvent modifier les établissements"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Seuls les superusers peuvent supprimer des établissements"""
        return request.user.is_superuser
    
    def send_invitation(self, request, queryset):
        """Action pour envoyer les invitations"""
        count = 0
        for etablissement in queryset:
            try:
                # Créer ou récupérer l'invitation
                invitation, created = EtablissementInvitation.objects.get_or_create(
                    etablissement=etablissement,
                    defaults={
                        'email': etablissement.email or 'admin@example.com',  # Email par défaut
                        'created_by': request.user
                    }
                )
                
                if invitation.is_valid or created:
                    # Envoyer l'email d'invitation
                    invitation.send_invitation_email(request)
                    count += 1
                else:
                    messages.warning(
                        request,
                        f"L'invitation pour {etablissement.nom} a déjà été utilisée ou a expiré."
                    )
                    
            except Exception as e:
                messages.error(
                    request,
                    f"Erreur lors de l'envoi de l'invitation pour {etablissement.nom}: {str(e)}"
                )
        
        if count > 0:
            messages.success(
                request,
                f"{count} invitation(s) envoyée(s) avec succès."
            )
    
    send_invitation.short_description = _("Envoyer l'invitation par email")
    
    def activate_etablissement(self, request, queryset):
        """Action pour activer les établissements"""
        count = queryset.update(is_active=True)
        messages.success(request, f"{count} établissement(s) activé(s).")
    
    activate_etablissement.short_description = _("Activer les établissements sélectionnés")
    
    def deactivate_etablissement(self, request, queryset):
        """Action pour désactiver les établissements"""
        count = queryset.update(is_active=False)
        messages.warning(request, f"{count} établissement(s) désactivé(s).")
    
    deactivate_etablissement.short_description = _("Désactiver les établissements sélectionnés")


@admin.register(EtablissementInvitation)
class EtablissementInvitationAdmin(admin.ModelAdmin):
    """
    Interface admin pour gérer les invitations séparément.
    """
    list_display = ['etablissement', 'email', 'used', 'is_expired', 'created_at', 'expires_at']
    list_filter = ['used', 'created_at', 'expires_at']
    search_fields = ['etablissement__nom', 'etablissement__code', 'email']
    readonly_fields = ['token', 'created_at', 'used_at', 'is_expired', 'is_valid']
    
    fieldsets = (
        (_("Invitation"), {
            'fields': ('etablissement', 'email', 'expires_at')
        }),
        (_("Statut"), {
            'fields': ('used', 'used_at', 'user_created', 'is_expired', 'is_valid'),
            'classes': ('collapse',)
        }),
        (_("Technique"), {
            'fields': ('token', 'created_at', 'created_by'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Seuls les super-admins peuvent voir les invitations"""
        qs = super().get_queryset(request).select_related('etablissement', 'user_created', 'created_by')
        if request.user.is_superuser:
            return qs
        return qs.none()
    
    def has_add_permission(self, request):
        """Seuls les superusers peuvent ajouter des invitations"""
        return request.user.is_superuser
    
    def has_change_permission(self, request, obj=None):
        """Seuls les superusers peuvent modifier les invitations"""
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        """Seuls les superusers peuvent supprimer les invitations"""
        return request.user.is_superuser
