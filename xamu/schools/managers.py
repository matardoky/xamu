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
        """
        Override clone pour préserver l'état du tenant filtering
        """
        clone = super()._clone()
        clone.tenant_filtering_disabled = self.tenant_filtering_disabled
        return clone
    
    def _apply_tenant_filter(self, clone, negate):
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant:
                tenant_filter = {self.model._tenant_field: tenant}
                if negate:
                    clone = clone.exclude(**tenant_filter)
                else:
                    clone = clone.filter(**tenant_filter)
        return clone

    def _filter_or_exclude(self, negate, *args, **kwargs):
        """
        Override pour appliquer le filtrage tenant automatiquement
        """
        # Si le filtrage tenant est désactivé, utiliser directement la méthode parent
        if getattr(self, 'tenant_filtering_disabled', False):
            return super()._filter_or_exclude(negate, *args, **kwargs)
        
        # Appliquer les filtres normaux en désactivant temporairement le tenant filtering
        self.tenant_filtering_disabled = True
        clone = super()._filter_or_exclude(negate, *args, **kwargs)
        self.tenant_filtering_disabled = False
        
        return clone
    
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
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant:
                # Désactiver temporairement le filtrage pour éviter la récursion
                queryset.tenant_filtering_disabled = True
                queryset = queryset.filter(**{self.model._tenant_field: tenant})
                queryset.tenant_filtering_disabled = False
        
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
    
    def _inject_tenant_to_kwargs(self, kwargs):
        if hasattr(self.model, '_tenant_field'):
            tenant = get_current_tenant()
            if tenant and self.model._tenant_field not in kwargs:
                kwargs[self.model._tenant_field] = tenant
            elif not tenant and self.model._tenant_field not in kwargs:
                raise ImproperlyConfigured(
                    f"Impossible de créer {self.model.__name__} sans tenant actuel. "
                    f"Utilisez set_current_tenant() ou passez '{self.model._tenant_field}' explicitement."
                )
        return kwargs

    def create(self, **kwargs):
        """
        Override create pour injecter automatiquement le tenant.
        """
        kwargs = self._inject_tenant_to_kwargs(kwargs)
        return super().create(**kwargs)
    
    def get_or_create(self, defaults=None, **kwargs):
        """
        Override get_or_create pour injecter automatiquement le tenant.
        """
        kwargs = self._inject_tenant_to_kwargs(kwargs)
        return super().get_or_create(defaults, **kwargs)
    
    def update_or_create(self, defaults=None, **kwargs):
        """
        Override update_or_create pour injecter automatiquement le tenant.
        """
        kwargs = self._inject_tenant_to_kwargs(kwargs)
        return super().update_or_create(defaults, **kwargs)