from django.db import models
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
import re


class Etablissement(models.Model):
    """
    Modèle représentant un établissement scolaire pour le multi-tenant.
    Chaque établissement correspond à un tenant isolé.
    """
    code = models.CharField(
        _("Code établissement"),
        max_length=10,
        unique=True,
        help_text=_("Code unique de l'établissement (ex: etb001)")
    )
    nom = models.CharField(_("Nom"), max_length=200)
    adresse = models.TextField(_("Adresse"), blank=True)
    telephone = models.CharField(_("Téléphone"), max_length=20, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    
    # Configuration multi-tenant
    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name='etablissement',
        help_text=_("Site Django associé pour le multi-tenant")
    )
    
    is_active = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Décochez pour désactiver temporairement l'établissement")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Établissement")
        verbose_name_plural = _("Établissements")
        ordering = ['nom']
        
    def __str__(self):
        return f"{self.nom} ({self.code})"
    
    def clean(self):
        """Validation du code établissement"""
        if not re.match(r'^[a-zA-Z0-9_]+$', self.code):
            raise ValidationError({
                'code': _("Le code ne peut contenir que des lettres, chiffres et underscores")
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalider le cache
        self.invalidate_cache()
    
    def delete(self, *args, **kwargs):
        self.invalidate_cache()
        super().delete(*args, **kwargs)
    
    @classmethod
    def get_by_code(cls, code):
        """
        Récupère un établissement par son code avec mise en cache.
        Performance optimisée pour le middleware.
        """
        cache_key = f"etablissement:{code}"
        etablissement = cache.get(cache_key)
        
        if etablissement is None:
            try:
                etablissement = cls.objects.select_related('site').get(
                    code=code, 
                    is_active=True
                )
                # Cache pendant 1 heure
                cache.set(cache_key, etablissement, 3600)
            except cls.DoesNotExist:
                # Cache les résultats négatifs pendant 5 minutes
                cache.set(cache_key, False, 300)
                return None
        
        return etablissement if etablissement else None
    
    def invalidate_cache(self):
        """Invalide le cache de cet établissement"""
        cache_key = f"etablissement:{self.code}"
        cache.delete(cache_key)
    
    @property
    def base_url(self):
        """URL de base pour cet établissement"""
        return f"/{self.code}/"
