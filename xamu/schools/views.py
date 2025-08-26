from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.urls import reverse
from django.http import Http404
from django.views.generic import View, TemplateView, DetailView
from django.utils.decorators import method_decorator
import logging

from .models import Etablissement, EtablissementInvitation

logger = logging.getLogger(__name__)


class TenantRequiredMixin:
    """
    Mixin pour les vues nécessitant un tenant dans la requête.
    Redirige vers la page d'erreur si aucun tenant n'est trouvé.
    """
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request, 'tenant') or not request.tenant:
            messages.error(request, _("Établissement non trouvé."))
            return render(request, 'schools/no_tenant.html', status=404)
        return super().dispatch(request, *args, **kwargs)


class HomeView(TenantRequiredMixin, TemplateView):
    template_name = 'schools/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['etablissement'] = self.request.tenant
        return context


class DashboardView(TenantRequiredMixin, TemplateView):
    template_name = 'schools/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['etablissement'] = self.request.tenant
        context['user_role'] = self.request.user.role if self.request.user.is_authenticated else 'guest'
        context['permissions'] = {
            'can_manage_etablissement': self.request.user.can_manage_etablissement if self.request.user.is_authenticated else False,
            'can_manage_students': self.request.user.can_manage_students if self.request.user.is_authenticated else False,
        }
        return context


class AcceptInvitationView(View):
    @method_decorator(never_cache)
    def get(self, request, tenant_code, token):
        etablissement = get_object_or_404(Etablissement, code=tenant_code)
        invitation = get_object_or_404(EtablissementInvitation, etablissement=etablissement, token=token)

        if not invitation.is_valid:
            return render(request, 'schools/invitation_invalid.html', {'invitation': invitation, 'etablissement': etablissement})

        # Store invitation details in session for allauth signup
        request.session['invitation_token'] = str(invitation.token)
        request.session['tenant_code'] = tenant_code
        
        signup_url = reverse('account_signup')
        return redirect(f'{signup_url}?email={invitation.email}')




class InvitationStatusView(DetailView):
    model = Etablissement
    template_name = 'schools/invitation_status.html'
    pk_url_kwarg = 'etablissement_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.get_object()
        try:
            invitation = etablissement.invitation
        except EtablissementInvitation.DoesNotExist:
            invitation = None
        context['etablissement'] = etablissement
        context['invitation'] = invitation
        return context


class NoTenantView(TemplateView):
    template_name = 'schools/no_tenant.html'
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, status=404)