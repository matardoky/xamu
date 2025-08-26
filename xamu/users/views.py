from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db.models import QuerySet
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView
from django.views.generic import RedirectView
from django.views.generic import UpdateView

from xamu.users.models import User


class UserDetailView(LoginRequiredMixin, DetailView):
    model = User
    slug_field = "id"
    slug_url_kwarg = "id"


class UserUpdateView(LoginRequiredMixin, SuccessMessageMixin, UpdateView):
    model = User
    fields = ["name"]
    success_message = _("Information successfully updated")

    def get_success_url(self) -> str:
        assert self.request.user.is_authenticated  # type guard
        return self.request.user.get_absolute_url()

    def get_object(self, queryset: QuerySet | None=None) -> User:
        return self.request.user


class UserRedirectView(LoginRequiredMixin, RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs) -> str:
        if self.request.user.is_authenticated:
            if hasattr(self.request, 'tenant') and self.request.tenant:
                return reverse(
                    "tenant:dashboard",
                    kwargs={"tenant_code": self.request.tenant.code},
                )
            if hasattr(self.request.user, 'etablissement') and self.request.user.etablissement:
                return reverse(
                    "tenant:dashboard",
                    kwargs={"tenant_code": self.request.user.etablissement.code},
                )
            return reverse("home")
        return reverse("account_login")
