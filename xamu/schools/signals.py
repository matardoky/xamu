"""
Signaux pour le système d'invitation allauth.
"""

import logging

from allauth.account.signals import email_confirmed
from allauth.account.signals import user_signed_up
from django.contrib import messages
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from .models import EtablissementInvitation

logger = logging.getLogger(__name__)


@receiver(user_signed_up)
def handle_invitation_signup(sender, request, user, **kwargs):
    """
    Signal déclenché après qu'un utilisateur se soit inscrit via allauth.
    Vérifie si c'est dans le cadre d'une invitation.
    """
    logger.info(f"Signal user_signed_up reçu pour {user.email}")

    # Vérifier si il y a un token d'invitation en session
    invitation_token = request.session.get("invitation_token")
    if invitation_token:
        logger.info(f"Token d'invitation trouvé en session: {invitation_token}")

        try:
            invitation = EtablissementInvitation.objects.get(token=invitation_token)

            if invitation.is_valid and invitation.email == user.email:
                # Associer l'utilisateur à l'établissement
                user.etablissement = invitation.etablissement
                user.role = "chef_etablissement"
                user.save()

                # Marquer l'invitation comme utilisée
                invitation.use_invitation(user)

                logger.info(f"Utilisateur {user.email} associé à l'établissement {invitation.etablissement.nom}")

                # Nettoyer la session
                del request.session["invitation_token"]

                messages.success(request, _(
                    "Félicitations ! Vous êtes maintenant chef de l'établissement {}.",
                ).format(invitation.etablissement.nom))

            else:
                logger.warning("Invitation invalide ou email non correspondant")

        except EtablissementInvitation.DoesNotExist:
            logger.warning(f"Invitation avec token {invitation_token} non trouvée")


@receiver(email_confirmed)
def handle_email_confirmed(sender, request, email_address, **kwargs):
    """
    Signal déclenché après confirmation d'email.
    Redirige vers le dashboard du tenant si l'utilisateur a un établissement.
    """
    user = email_address.user
    logger.info(f"Signal email_confirmed reçu pour {user.email}")

    if user.etablissement:
        logger.info(f"Utilisateur {user.email} a un établissement: {user.etablissement.nom}")
        # La redirection sera gérée par l'AccountAdapter
    else:
        logger.info(f"Utilisateur {user.email} n'a pas d'établissement")


@receiver(user_signed_up)
def link_import_invitations(sender, request, user, **kwargs):
    """
    Signal pour lier automatiquement les ImportInvitation lors de l'inscription.
    Mis à jour le statut des invitations d'import correspondantes.
    """
    from xamu.imports.models import ImportInvitation
    
    logger.info(f"Recherche d'ImportInvitation pour {user.email}")
    
    # Chercher toutes les ImportInvitation en attente pour cet email
    import_invitations = ImportInvitation.objects.filter(
        email=user.email,
        statut__in=['pending', 'sent']
    )
    
    if user.etablissement:
        # Filtrer par établissement si l'utilisateur en a un
        import_invitations = import_invitations.filter(
            etablissement=user.etablissement
        )
    
    for import_invitation in import_invitations:
        try:
            import_invitation.marquer_comme_acceptee(user)
            logger.info(f"ImportInvitation {import_invitation.id} liée à l'utilisateur {user.email}")
        except Exception as e:
            logger.error(f"Erreur lors de la liaison ImportInvitation {import_invitation.id}: {e}")
