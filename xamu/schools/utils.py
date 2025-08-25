from functools import wraps
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _
from django.conf import settings

from .middleware import get_current_tenant


def tenant_required(view_func=None, *, redirect_to_home=False):
    """
    Décorateur pour s'assurer qu'un tenant est présent dans la requête.
    
    Args:
        view_func: La vue à décorer
        redirect_to_home (bool): Si True, redirige vers la home en cas d'absence de tenant.
                                 Si False (défaut), lève Http404.
    
    Example:
        @tenant_required
        def my_view(request):
            # request.tenant est garanti d'exister
            pass
            
        @tenant_required(redirect_to_home=True)
        def my_view(request):
            # Redirige vers home si pas de tenant
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'tenant') or not request.tenant:
                if redirect_to_home:
                    return redirect('home')
                else:
                    raise Http404(_("Accès refusé. Aucun établissement sélectionné."))
            return view_func(request, *args, **kwargs)
        return wrapper
    
    if view_func is None:
        return decorator
    else:
        return decorator(view_func)


def tenant_url(url_name, tenant_code=None, *args, **kwargs):
    """
    Génère une URL avec le préfixe tenant.
    
    Args:
        url_name (str): Nom de l'URL Django
        tenant_code (str, optional): Code du tenant. Si None, utilise le tenant actuel.
        *args, **kwargs: Arguments pour reverse()
    
    Returns:
        str: URL complète avec préfixe tenant
    
    Example:
        # Avec tenant actuel
        url = tenant_url('dashboard')  # /etb001/dashboard/
        
        # Avec tenant spécifique
        url = tenant_url('dashboard', 'etb002')  # /etb002/dashboard/
    """
    if tenant_code is None:
        tenant = get_current_tenant()
        if not tenant:
            raise ValueError("Aucun tenant actuel et tenant_code non fourni")
        tenant_code = tenant.code
    
    try:
        # Essayer d'abord avec le pattern tenant
        url = reverse(f'tenant:{url_name}', args=[tenant_code] + list(args), kwargs=kwargs)
    except:
        # Fallback : construire manuellement
        base_url = reverse(url_name, args=args, kwargs=kwargs)
        url = f'/{tenant_code}{base_url}'
    
    return url


def get_tenant_from_request(request):
    """
    Récupère le tenant depuis la requête de manière sécurisée.
    
    Args:
        request: Objet request Django
    
    Returns:
        Etablissement or None: Le tenant ou None si pas trouvé
    """
    return getattr(request, 'tenant', None)


def require_tenant_permission(permission, tenant_field='etablissement'):
    """
    Décorateur pour vérifier les permissions dans le contexte d'un tenant.
    
    Args:
        permission (str): Permission Django à vérifier
        tenant_field (str): Nom du champ tenant sur l'utilisateur
    
    Example:
        @require_tenant_permission('schools.add_student')
        def add_student_view(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied(_("Authentification requise."))
            
            # Vérifier la permission globale
            if not request.user.has_perm(permission):
                raise PermissionDenied(_("Permission insuffisante."))
            
            # Vérifier que l'utilisateur appartient au tenant actuel
            tenant = get_current_tenant()
            if tenant and hasattr(request.user, tenant_field):
                user_tenant = getattr(request.user, tenant_field)
                if user_tenant != tenant:
                    raise PermissionDenied(
                        _("Vous n'avez pas accès à cet établissement.")
                    )
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class TenantContext:
    """
    Context manager pour forcer temporairement un tenant.
    Utile pour les tests, tâches Celery, etc.
    
    Example:
        with TenantContext(etablissement):
            # Toutes les opérations dans ce bloc utilisent ce tenant
            Student.objects.create(name="Test")
    """
    
    def __init__(self, tenant):
        self.tenant = tenant
        self.previous_tenant = None
    
    def __enter__(self):
        from .middleware import set_current_tenant
        self.previous_tenant = get_current_tenant()
        set_current_tenant(self.tenant)
        return self.tenant
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        from .middleware import set_current_tenant, clear_current_tenant
        if self.previous_tenant:
            set_current_tenant(self.previous_tenant)
        else:
            clear_current_tenant()


def get_tenant_url_patterns():
    """
    Génère les patterns d'URL pour les tenants.
    À utiliser dans urls.py principal.
    
    Returns:
        list: Liste des patterns URL avec préfixe tenant
    """
    from django.urls import path, include
    
    return [
        path('<str:tenant_code>/', include('xamu.schools.tenant_urls', namespace='tenant')),
    ]


def validate_tenant_access(user, tenant):
    """
    Valide qu'un utilisateur a accès à un tenant spécifique.
    
    Args:
        user: Utilisateur Django
        tenant: Instance d'Etablissement
    
    Returns:
        bool: True si l'accès est autorisé
        
    Raises:
        PermissionDenied: Si l'accès n'est pas autorisé
    """
    if not user.is_authenticated:
        raise PermissionDenied(_("Authentification requise."))
    
    # Super-admin a accès à tous les tenants
    if user.is_superuser:
        return True
    
    # Vérifier l'appartenance au tenant
    if hasattr(user, 'etablissement') and user.etablissement == tenant:
        return True
    
    # Vérifier via les relations Many-to-Many si applicables
    if hasattr(user, 'etablissements'):
        if tenant in user.etablissements.all():
            return True
    
    raise PermissionDenied(
        _("Vous n'avez pas accès à l'établissement '{0}'.").format(tenant.nom)
    )


def get_user_tenants(user):
    """
    Récupère tous les tenants auxquels un utilisateur a accès.
    
    Args:
        user: Utilisateur Django
    
    Returns:
        QuerySet: QuerySet d'établissements accessibles
    """
    from .models import Etablissement
    
    if not user.is_authenticated:
        return Etablissement.objects.none()
    
    if user.is_superuser:
        return Etablissement.objects.filter(is_active=True)
    
    # Logique spécifique selon votre modèle utilisateur
    if hasattr(user, 'etablissement'):
        return Etablissement.objects.filter(id=user.etablissement.id, is_active=True)
    
    if hasattr(user, 'etablissements'):
        return user.etablissements.filter(is_active=True)
    
    return Etablissement.objects.none()


def switch_tenant_url(tenant_code, current_path=None):
    """
    Génère l'URL pour switcher vers un autre tenant en gardant le même path.
    
    Args:
        tenant_code (str): Code du nouveau tenant
        current_path (str): Path actuel (sans le préfixe tenant)
    
    Returns:
        str: URL pour le nouveau tenant
    
    Example:
        # Si on est sur /etb001/dashboard/students/
        url = switch_tenant_url('etb002', '/dashboard/students/')
        # Retourne: /etb002/dashboard/students/
    """
    if current_path is None:
        current_path = '/dashboard/'
    
    # Nettoyer le path des préfixes tenant existants
    import re
    clean_path = re.sub(r'^/[a-zA-Z0-9_]+', '', current_path)
    if not clean_path.startswith('/'):
        clean_path = '/' + clean_path
    
    return f'/{tenant_code}{clean_path}'