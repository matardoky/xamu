from django.db import models
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.utils.translation import gettext_lazy as _

from .managers import TenantManager
from .middleware import get_current_tenant


class TenantMixin(models.Model):
    """
    Mixin pour les modèles qui doivent être isolés par tenant.
    
    Ajoute automatiquement :
    - Le champ etablissement_id
    - Le manager avec filtrage tenant
    - Les contraintes d'intégrité
    """
    
    etablissement = models.ForeignKey(
        'schools.Etablissement',
        on_delete=models.CASCADE,
        verbose_name=_("Établissement"),
        help_text=_("Établissement auquel appartient cet enregistrement")
    )
    
    objects = TenantManager()
    
    # Définir le champ tenant pour le manager
    _tenant_field = 'etablissement'
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """
        Override save pour injecter automatiquement le tenant si manquant.
        """
        if not self.etablissement_id:
            tenant = get_current_tenant()
            if tenant:
                self.etablissement = tenant
            else:
                raise ImproperlyConfigured(
                    f"Impossible de sauvegarder {self.__class__.__name__} sans tenant. "
                    "Utilisez set_current_tenant() ou définissez 'etablissement' explicitement."
                )
        
        # Validation de sécurité : vérifier que l'établissement n'a pas changé
        if self.pk:
            try:
                existing = self.__class__.objects.all_tenants().get(pk=self.pk)
                if existing.etablissement_id != self.etablissement_id:
                    raise ImproperlyConfigured(
                        f"Impossible de changer l'établissement de {self.__class__.__name__}. "
                        "Créez un nouvel enregistrement si nécessaire."
                    )
            except self.__class__.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        """
        Override delete pour s'assurer qu'on supprime dans le bon tenant.
        """
        tenant = get_current_tenant()
        if tenant and self.etablissement_id != tenant.id:
            raise ImproperlyConfigured(
                f"Impossible de supprimer {self.__class__.__name__} d'un autre établissement."
            )
        super().delete(*args, **kwargs)


class TenantUserMixin(TenantMixin):
    """
    Mixin spécialisé pour les modèles liés aux utilisateurs dans un contexte tenant.
    Étend TenantMixin avec des fonctionnalités user-specific.
    """
    
    class Meta:
        abstract = True
    
    def clean(self):
        """
        Validation supplémentaire pour s'assurer que l'utilisateur
        appartient au bon établissement.
        """
        super().clean()
        
        # Vérifier que l'utilisateur lié appartient au même établissement
        if (hasattr(self, 'user') and self.user and 
            hasattr(self.user, 'etablissement') and 
            self.user.etablissement != self.etablissement):
            
            raise ValidationError({
                'user': _("L'utilisateur doit appartenir au même établissement.")
            })


class TenantAuditMixin(TenantMixin):
    """
    Mixin qui combine TenantMixin avec des fonctionnalités d'audit.
    """
    
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_%(class)s_set',
        verbose_name=_("Créé par")
    )
    updated_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_%(class)s_set',
        verbose_name=_("Modifié par")
    )
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """
        Override save pour capturer automatiquement created_by/updated_by.
        """
        # Note: La logique pour capturer l'utilisateur actuel pourrait être ajoutée ici
        # via un middleware similaire au tenant middleware
        
        super().save(*args, **kwargs)