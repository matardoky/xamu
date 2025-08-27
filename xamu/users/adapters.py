from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter # Import this
from django.conf import settings
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib import messages # Import messages

class AccountAdapter(DefaultAccountAdapter):
    def get_email_confirmation_redirect_url(self, request):
        # ... (existing code)
        # Fix for RecursionError: maximum recursion depth exceeded in comparison
        # when trying to redirect after email confirmation.
        # This happens because get_email_verification_redirect_url calls
        # get_email_confirmation_redirect_url in a loop.
        # We need to ensure that the redirect URL is tenant-aware.
        if request.user.is_authenticated and hasattr(request.user, 'etablissement') and request.user.etablissement:
            return reverse('tenant:home', kwargs={'tenant_code': request.user.etablissement.code})
        return settings.LOGIN_REDIRECT_URL

    def get_email_verification_redirect_url(self, email_address):
        # This method is called by allauth after email verification.
        # It should return a URL that is not tenant-aware, as the user might not be logged in yet,
        # or their tenant might not be resolved.
        # We redirect to a generic login page or a page that handles tenant resolution.
        return reverse('account_login') # Or a specific page that handles post-verification login

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        # Ensure the 'name' field is populated from the form
        user.name = form.cleaned_data.get('name') # Add this line
        user.save()
        return user

    def is_open_for_signup(self, request):
        # Allow signup only if there's an invitation or if it's a superuser creating accounts
        # For now, we'll keep it open for simplicity during development
        return True

    def get_login_redirect_url(self, request):
        # Custom login redirect to handle tenant-aware URLs
        # Check if it's the first login and redirect to password change
        if request.user.is_authenticated and request.user.premiere_connexion:
            # Set premiere_connexion to False after redirection
            request.user.premiere_connexion = False
            request.user.save()
            messages.info(request, _("Veuillez changer votre mot de passe pour votre première connexion."))
            return reverse('account_change_password') # allauth's password change URL

        if request.user.is_authenticated and hasattr(request.user, 'etablissement') and request.user.etablissement:
            return reverse('tenant:home', kwargs={'tenant_code': request.user.etablissement.code})
        return settings.LOGIN_REDIRECT_URL

    def clean_email(self, email):
        # Custom email cleaning if needed
        return email

    def add_message(self, request, level, message_template,
                    message_context=None, extra_tags=''):
        # Custom message handling if needed
        messages.add_message(request, level, message_template, extra_tags=extra_tags)


class SocialAccountAdapter(DefaultSocialAccountAdapter): # Add this class
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Ensure the 'name' field is populated for social accounts
        if form and 'name' in form.cleaned_data:
            user.name = form.cleaned_data['name']
            user.save()
        return user