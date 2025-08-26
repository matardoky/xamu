"""
Context processors pour le système multi-tenant.
"""

from .middleware import get_current_tenant


def tenant_context(request):
    """
    Context processor qui ajoute les informations tenant à tous les templates.
    
    Variables ajoutées:
    - tenant: L'établissement actuel (ou None)
    - tenant_code: Le code de l'établissement actuel (ou None)
    - is_tenant_context: Boolean indiquant si on est dans un contexte tenant
    - tenant_urls: Fonction helper pour générer des URLs tenant-aware
    """
    tenant = getattr(request, 'tenant', None)
    
    def tenant_url_helper(url_name, *args, **kwargs):
        """Helper pour générer des URLs tenant dans les templates"""
        if tenant:
            # Construire l'URL avec le préfixe tenant
            from django.urls import reverse
            from django.urls.exceptions import NoReverseMatch
            
            try:
                # Essayer avec le namespace tenant
                return reverse(f'tenant:{url_name}', args=[tenant.code] + list(args), kwargs=kwargs)
            except NoReverseMatch:
                try:
                    # Fallback: construire manuellement
                    base_url = reverse(url_name, args=args, kwargs=kwargs)
                    return f'/{tenant.code}{base_url}'
                except:
                    return f'/{tenant.code}/'
        return '/'
    
    return {
        'tenant': tenant,
        'tenant_code': tenant.code if tenant else None,
        'is_tenant_context': tenant is not None,
        'tenant_url': tenant_url_helper,
    }