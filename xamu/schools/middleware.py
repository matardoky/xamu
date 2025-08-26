from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse, resolve
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _
from django.contrib import messages
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
        r'^/api/',
        r'^/static/',
        r'^/media/',
        r'^/favicon\.ico$',
        r'^/$',  # Homepage sans tenant (landing page)
        r'^/about/$',  # Page about globale
        r'^/schools/',  # URLs d'invitation (accessibles globalement)
        r'^/accounts/', # Allauth URLs are public
        r'^/users/', # User management URLs are public
    ]
    
    def __init__(self, get_response=None):
        super().__init__(get_response)
        self.tenant_exempt_regex = re.compile('|'.join(self.TENANT_EXEMPT_PATHS))
    
    def process_request(self, request):
        """
        Extrait et résout le tenant depuis l'URL path, la session ou l'utilisateur connecté.
        """
        path = request.path_info
        
        # Vérifier si l'URL est exemptée du tenant
        if self.tenant_exempt_regex.match(path):
            request.tenant = None
            _thread_local.tenant = None
            return None
        
        # Extraire le tenant code depuis l'URL
        tenant_match = re.match(r'^/([a-zA-Z0-9_]+)/', path)
        tenant_code = None
        if tenant_match:
            tenant_code = tenant_match.group(1)
        elif request.user.is_authenticated and hasattr(request.user, 'etablissement') and request.user.etablissement:
            tenant_code = request.user.etablissement.code
        else:
            # If not in URL or user, check session (for allauth pages)
            tenant_code = request.session.get('tenant_code')

        if not tenant_code:
            return redirect('home')
        
        # Résoudre l'établissement (avec cache)
        etablissement = Etablissement.get_by_code(tenant_code)
        
        if not etablissement:
            raise Http404(_("Établissement '{0}' non trouvé ou inactif.").format(tenant_code))
        
        # Attacher le tenant à la requête
        request.tenant = etablissement
        request.tenant_code = tenant_code
        
        # Stocker dans thread-local pour accès global
        _thread_local.tenant = etablissement
        
        # Validation des permissions strictes
        permission_response = self._validate_tenant_permissions(request, path)
        if permission_response:
            return permission_response
        
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
    
    def _validate_tenant_permissions(self, request, path):
        """
        Valide les permissions strictes pour l'accès au tenant.
        
        Règles de sécurité:
        1. L'utilisateur doit être authentifié (sauf pour les URLs d'auth)
        2. L'utilisateur doit appartenir à l'établissement du tenant
        3. Les super-admins n'ont PAS accès aux données tenant
        """
        # Si l'utilisateur n'est pas authentifié
        if not request.user.is_authenticated:
            messages.info(request, _("Veuillez vous connecter pour accéder à cette page."))
            return redirect('account_login')
        
        # SÉCURITÉ CRITIQUE: Les super-admins ne doivent PAS accéder aux données tenant
        if request.user.is_superuser:
            messages.error(request, _(
                "Les super-administrateurs ne peuvent pas accéder aux données "
                "des établissements. Utilisez l'interface d'administration Django."
            ))
            return redirect('/admin/')
        
        # L'utilisateur doit appartenir à l'établissement
        if not hasattr(request.user, 'etablissement') or not request.user.etablissement:
            messages.error(request, _(
                "Votre compte n'est associé à aucun établissement. "
                "Contactez un administrateur."
            ))
            return redirect('home')
        
        # L'utilisateur doit appartenir au BON établissement
        if request.user.etablissement != request.tenant:
            messages.error(request, _(
                "Vous n'avez pas accès à l'établissement {}. "
                "Vous ne pouvez accéder qu'à votre établissement : {}."
            ).format(request.tenant.nom, request.user.etablissement.nom))
            return redirect('tenant:home', tenant_code=request.user.etablissement.code)
        
        # Vérifier que l'établissement est actif
        if not request.tenant.is_active:
            messages.error(request, _(
                "L'établissement {} est actuellement désactivé. "
                "Contactez un administrateur."
            ).format(request.tenant.nom))
            return redirect('home')
        
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