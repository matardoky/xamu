from __future__ import annotations

import typing

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.urls import reverse

from xamu.schools.models import Etablissement, EtablissementInvitation

if typing.TYPE_CHECKING:
    from allauth.socialaccount.models import SocialLogin
    from django.http import HttpRequest

    from xamu.users.models import User


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request: HttpRequest) -> bool:
        invitation_token = request.session.get('invitation_token')
        if invitation_token:
            try:
                invitation = EtablissementInvitation.objects.get(token=invitation_token)
                if invitation.is_valid:
                    return True
            except EtablissementInvitation.DoesNotExist:
                pass
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)

        invitation_token = request.session.get('invitation_token')
        tenant_code = request.session.get('tenant_code')

        if invitation_token and tenant_code:
            etablissement = get_object_or_404(Etablissement, code=tenant_code)
            invitation = get_object_or_404(EtablissementInvitation, token=invitation_token, etablissement=etablissement)

            if invitation.is_valid and invitation.email == user.email:
                user.etablissement = etablissement
                user.role = 'chef_etablissement'
                if commit:
                    user.save()
                invitation.use_invitation(user)
                del request.session['invitation_token']
                del request.session['tenant_code']

        if commit:
            user.save()
        return user

    def get_login_redirect_url(self, request: HttpRequest) -> str:
        """
        Redirige vers le dashboard du tenant après connexion.
        """
        # Import ici pour éviter les imports circulaires
        from xamu.schools.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        if tenant:
            return reverse("tenant:dashboard", kwargs={"tenant_code": tenant.code})
        
        # Fallback vers le comportement par défaut
        return super().get_login_redirect_url(request)
    
    def get_logout_redirect_url(self, request: HttpRequest) -> str:
        """
        Redirige vers la page d'accueil du tenant après déconnexion.
        """
        from xamu.schools.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        if tenant:
            return f"/{tenant.code}/"
        
        # Fallback vers la homepage globale
        return "/"
    
    def get_email_confirmation_redirect_url(self, request: HttpRequest) -> str:
        """
        Redirige vers la page de connexion après vérification email.
        """
        return reverse("account_login")
    
    def get_signup_redirect_url(self, request: HttpRequest) -> str:
        """
        Redirige vers le dashboard du tenant après inscription.
        """
        from xamu.schools.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        if tenant:
            return f"/{tenant.code}/dashboard/"
        
        return super().get_signup_redirect_url(request)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def is_open_for_signup(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
    ) -> bool:
        """
        Désactive l'inscription sociale dans le contexte tenant.
        L'inscription se fait uniquement par invitation.
        """
        from xamu.schools.middleware import get_current_tenant
        
        # Si nous sommes dans un contexte tenant, pas d'inscription sociale
        tenant = get_current_tenant()
        if tenant:
            return False
        
        # En dehors du contexte tenant, utiliser le setting
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", True)

    def populate_user(
        self,
        request: HttpRequest,
        sociallogin: SocialLogin,
        data: dict[str, typing.Any],
    ) -> User:
        """
        Populates user information from social provider info.

        See: https://docs.allauth.org/en/latest/socialaccount/advanced.html#creating-and-populating-user-instances
        """
        user = super().populate_user(request, sociallogin, data)
        if not user.name:
            if name := data.get("name"):
                user.name = name
            elif first_name := data.get("first_name"):
                user.name = first_name
                if last_name := data.get("last_name"):
                    user.name += f" {last_name}"
        
        # Associer au tenant actuel si possible
        from xamu.schools.middleware import get_current_tenant
        tenant = get_current_tenant()
        if tenant and hasattr(user, 'etablissement'):
            user.etablissement = tenant
        
        return user
    
    def get_connect_redirect_url(
        self,
        request: HttpRequest,
        socialaccount,
    ) -> str:
        """
        Redirige vers le dashboard du tenant après connexion sociale.
        """
        from xamu.schools.middleware import get_current_tenant
        
        tenant = get_current_tenant()
        if tenant:
            return f"/{tenant.code}/dashboard/"
        
        return super().get_connect_redirect_url(request, socialaccount)