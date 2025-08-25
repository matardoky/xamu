from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _
import re
import threading

from .models import Etablissement

# Thread-local storage pour stocker le tenant actuel
_thread_local = threading.local()


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware pour la gestion multi-tenant par URL path.
    
    Résout le tenant à partir de l'URL (ex: /etb001/dashboard/)
    et l'attache à request.tenant pour toute la requête.
    """
    
    # URLs exemptées du tenant (admin, api globale, etc.)
    TENANT_EXEMPT_PATHS = [
        r'^/admin/',
        r'^/api/schema/',
        r'^/api/docs/',
        r'^/static/',
        r'^/media/',
        r'^/favicon\.ico$',
        r'^/$',  # Homepage sans tenant
        r'^/about/$',  # Page about globale
    ]
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.tenant_exempt_regex = re.compile('|'.join(self.TENANT_EXEMPT_PATHS))
    
    def process_request(self, request):
        """
        Extrait et résout le tenant depuis l'URL path.
        """
        path = request.path_info
        
        # Vérifier si l'URL est exemptée du tenant
        if self.tenant_exempt_regex.match(path):
            request.tenant = None
            _thread_local.tenant = None
            return None
        
        # Extraire le tenant code depuis l'URL
        tenant_match = re.match(r'^/([a-zA-Z0-9_]+)/', path)
        
        if not tenant_match:
            # URLs sans tenant -> rediriger vers homepage ou erreur
            if path.startswith('/accounts/'):
                # URLs d'authentification sans tenant -> erreur
                raise Http404(_("Accès non autorisé. Veuillez accéder via un établissement."))
            # Autres URLs sans tenant -> rediriger vers homepage
            return redirect('home')
        
        tenant_code = tenant_match.group(1)
        
        # Résoudre l'établissement (avec cache)
        etablissement = Etablissement.get_by_code(tenant_code)
        
        if not etablissement:
            raise Http404(_("Établissement '{0}' non trouvé ou inactif.").format(tenant_code))
        
        # Attacher le tenant à la requête
        request.tenant = etablissement
        request.tenant_code = tenant_code
        
        # Stocker dans thread-local pour accès global
        _thread_local.tenant = etablissement
        
        return None
    
    def process_response(self, request, response):
        """
        Nettoie le thread-local après la requête.
        """
        if hasattr(_thread_local, 'tenant'):
            del _thread_local.tenant
        return response
    
    def process_exception(self, request, exception):
        """
        Nettoie le thread-local en cas d'exception.
        """
        if hasattr(_thread_local, 'tenant'):
            del _thread_local.tenant
        return None


def get_current_tenant():
    """
    Fonction utilitaire pour récupérer le tenant actuel depuis n'importe où.
    
    Returns:
        Etablissement: L'établissement actuel ou None
    """
    return getattr(_thread_local, 'tenant', None)


def set_current_tenant(tenant):
    """
    Fonction utilitaire pour définir manuellement le tenant actuel.
    Utile pour les tests ou les tâches en arrière-plan.
    
    Args:
        tenant (Etablissement): L'établissement à définir
    """
    _thread_local.tenant = tenant


def clear_current_tenant():
    """
    Fonction utilitaire pour effacer le tenant actuel.
    """
    if hasattr(_thread_local, 'tenant'):
        del _thread_local.tenant