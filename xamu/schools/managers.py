from django.db import models
from django.db.models.query import QuerySet
from django.core.exceptions import ImproperlyConfigured

from .middleware import get_current_tenant


class TenantQuerySet(QuerySet):
    """
    QuerySet personnalisé qui filtre automatiquement par tenant.
    """
    
    def __init__(self, *args, **kwargs):
        self.tenant_filtering_disabled = False
        super().__init__(*args, **kwargs)
    
    def _clone(self):
        """Override clone pour préserver l'état du tenant filtering"""
        clone = super()._clone()
        clone.tenant_filtering_disabled = self.tenant_filtering_disabled
        return clone
    
    def _filter_or_exclude(self, negate, *args, **kwargs):
        """Override pour appliquer le filtrage tenant automatiquement"""
        clone = self._clone()
        
        # Appliquer le filtrage tenant si activé
        if not clone.tenant_filtering_disabled and hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant:
                tenant_filter = {self.model._tenant_field: tenant}
                if negate:
                    clone = clone.exclude(**tenant_filter)
                else:
                    clone = clone.filter(**tenant_filter)
        
        # Appliquer les autres filtres normalement
        return super(TenantQuerySet, clone)._filter_or_exclude(negate, *args, **kwargs)
    
    def all_tenants(self):
        """
        Désactive le filtrage tenant pour cette requête.
        Utilisé pour accéder aux données de tous les tenants.
        """
        clone = self._clone()
        clone.tenant_filtering_disabled = True
        return clone
    
    def for_tenant(self, tenant):
        """
        Force le filtrage pour un tenant spécifique.
        
        Args:
            tenant (Etablissement): L'établissement pour lequel filtrer
        
        Returns:
            QuerySet: QuerySet filtré pour ce tenant
        """
        if not hasattr(self.model, '_tenant_field'):
            return self._clone()
        
        clone = self._clone()
        clone.tenant_filtering_disabled = True
        return clone.filter(**{self.model._tenant_field: tenant})


class TenantManager(models.Manager):
    """
    Manager personnalisé qui applique automatiquement le filtrage par tenant.
    """
    
    def get_queryset(self):
        """
        Retourne le QuerySet de base avec filtrage tenant.
        """
        queryset = TenantQuerySet(self.model, using=self._db)
        
        # Appliquer le filtrage tenant par défaut
        if (hasattr(self.model, '_tenant_field') and 
            not getattr(queryset, 'tenant_filtering_disabled', False)):
            
            tenant = get_current_tenant()
            if tenant:
                tenant_filter = {self.model._tenant_field: tenant}
                queryset = queryset.filter(**tenant_filter)
        
        return queryset
    
    def all_tenants(self):
        """
        Retourne tous les objets sans filtrage tenant.
        À utiliser avec précaution !
        """
        return self.get_queryset().all_tenants()
    
    def for_tenant(self, tenant):
        """
        Retourne les objets pour un tenant spécifique.
        
        Args:
            tenant (Etablissement): L'établissement pour lequel filtrer
        
        Returns:
            QuerySet: QuerySet filtré pour ce tenant
        """
        return self.get_queryset().for_tenant(tenant)
    
    def create(self, **kwargs):
        """
        Override create pour injecter automatiquement le tenant.
        """
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant and self.model._tenant_field not in kwargs:
                kwargs[self.model._tenant_field] = tenant
            elif not tenant and self.model._tenant_field not in kwargs:
                raise ImproperlyConfigured(
                    f"Impossible de créer {self.model.__name__} sans tenant actuel. "
                    f"Utilisez set_current_tenant() ou passez '{self.model._tenant_field}' explicitement."
                )
        
        return super().create(**kwargs)
    
    def get_or_create(self, defaults=None, **kwargs):
        """
        Override get_or_create pour injecter automatiquement le tenant.
        """
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant and self.model._tenant_field not in kwargs:
                kwargs[self.model._tenant_field] = tenant
            elif not tenant and self.model._tenant_field not in kwargs:
                raise ImproperlyConfigured(
                    f"Impossible de get_or_create {self.model.__name__} sans tenant actuel. "
                    f"Utilisez set_current_tenant() ou passez '{self.model._tenant_field}' explicitement."
                )
        
        return super().get_or_create(defaults, **kwargs)
    
    def update_or_create(self, defaults=None, **kwargs):
        """
        Override update_or_create pour injecter automatiquement le tenant.
        """
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant and self.model._tenant_field not in kwargs:
                kwargs[self.model._tenant_field] = tenant
            elif not tenant and self.model._tenant_field not in kwargs:
                raise ImproperlyConfigured(
                    f"Impossible de update_or_create {self.model.__name__} sans tenant actuel. "
                    f"Utilisez set_current_tenant() ou passez '{self.model._tenant_field}' explicitement."
                )
        
        return super().update_or_create(defaults, **kwargs)