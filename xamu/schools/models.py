from django.db import models
from django.contrib.sites.models import Site
from django.core.cache import cache
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from uuid import uuid4
import re
import logging

logger = logging.getLogger(__name__)


from django.urls import reverse

class Etablissement(models.Model):
    """
    Modèle représentant un établissement scolaire pour le multi-tenant.
    Chaque établissement correspond à un tenant isolé.
    """
    code = models.CharField(
        _("Code établissement"),
        max_length=10,
        unique=True,
        help_text=_("Code unique de l'établissement (ex: etb001)")
    )
    nom = models.CharField(_("Nom"), max_length=200)
    adresse = models.TextField(_("Adresse"), blank=True)
    telephone = models.CharField(_("Téléphone"), max_length=20, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    
    # Configuration multi-tenant
    site = models.OneToOneField(
        Site,
        on_delete=models.CASCADE,
        related_name='etablissement',
        help_text=_("Site Django associé pour le multi-tenant")
    )
    
    is_active = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Décochez pour désactiver temporairement l'établissement")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Établissement")
        verbose_name_plural = _("Établissements")
        ordering = ['nom']
        
    def __str__(self):
        return f"{self.nom} ({self.code})"
    
    def clean(self):
        """Validation du code établissement"""
        if not re.match(r'^[a-zA-Z0-9_]+$', self.code):
            raise ValidationError({
                'code': _("Le code ne peut contenir que des lettres, chiffres et underscores")
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
        # Invalider le cache
        self.invalidate_cache()
    
    def delete(self, *args, **kwargs):
        self.invalidate_cache()
        super().delete(*args, **kwargs)
    
    @classmethod
    def get_by_code(cls, code):
        """
        Récupère un établissement par son code avec mise en cache.
        Performance optimisée pour le middleware.
        """
        cache_key = f"etablissement:{code}"
        etablissement = cache.get(cache_key)
        
        if etablissement is None:
            try:
                etablissement = cls.objects.select_related('site').get(
                    code=code, 
                    is_active=True
                )
                # Cache pendant 1 heure
                cache.set(cache_key, etablissement, 3600)
            except cls.DoesNotExist:
                # Cache les résultats négatifs pendant 5 minutes
                cache.set(cache_key, False, 300)
                return None
        
        return etablissement if etablissement else None
    
    def invalidate_cache(self):
        """Invalide le cache de cet établissement"""
        cache_key = f"etablissement:{self.code}"
        cache.delete(cache_key)
    
    @property
    def base_url(self):
        """URL de base pour cet établissement"""
        return f"/{self.code}/"


class EtablissementInvitation(models.Model):
    """
    Modèle pour gérer les invitations d'établissements.
    Permet au super-admin d'inviter un chef d'établissement de manière sécurisée.
    """
    
    etablissement = models.OneToOneField(
        Etablissement,
        on_delete=models.CASCADE,
        related_name='invitation',
        verbose_name=_("Établissement")
    )
    
    email = models.EmailField(
        _("Email du chef d'établissement"),
        help_text=_("Email de la personne qui gérera cet établissement")
    )
    
    token = models.UUIDField(
        _("Token d'invitation"),
        default=uuid4,
        unique=True,
        editable=False
    )
    
    used = models.BooleanField(
        _("Invitation utilisée"),
        default=False
    )
    
    user_created = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Utilisateur créé"),
        help_text=_("Utilisateur qui a accepté l'invitation")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créée le"), auto_now_add=True)
    used_at = models.DateTimeField(_("Utilisée le"), null=True, blank=True)
    expires_at = models.DateTimeField(_("Expire le"))
    
    # Audit
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='invitations_created',
        verbose_name=_("Créée par")
    )
    
    class Meta:
        verbose_name = _("Invitation d'établissement")
        verbose_name_plural = _("Invitations d'établissements")
        ordering = ['-created_at']
    
    def __str__(self):
        status = _("Utilisée") if self.used else _("En attente")
        return f"Invitation {self.etablissement.nom} ({self.email}) - {status}"
    
    def save(self, *args, **kwargs):
        # Définir la date d'expiration si pas déjà définie
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        """Vérifie si l'invitation a expiré"""
        return timezone.now() > self.expires_at
    
    @property
    def is_valid(self):
        """Vérifie si l'invitation est encore valide"""
        return not self.used and not self.is_expired
    
    def use_invitation(self, user):
        """
        Marque l'invitation comme utilisée et associe l'utilisateur.
        """
        if not self.is_valid:
            if self.used:
                raise ValidationError(_("Cette invitation a déjà été utilisée."))
            if self.is_expired:
                raise ValidationError(_("Cette invitation a expiré."))
        
        self.used = True
        self.used_at = timezone.now()
        self.user_created = user
        self.save()
        
        # Associer l'utilisateur à l'établissement avec le rôle de chef d'établissement
        user.etablissement = self.etablissement
        user.role = 'chef_etablissement'
        user.save()
        
        return user
    
    def get_invitation_url(self, request=None):
        """
        Génère l'URL d'invitation complète.
        """
        url = reverse("schools:accept_invitation", kwargs={"tenant_code": self.etablissement.code, "token": self.token})
        
        if request:
            return request.build_absolute_uri(url)
        
        return url
    
    def send_invitation_email(self, request=None):
        """
        Envoie l'email d'invitation au chef d'établissement.
        """
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings
        
        logger.info(f"Début envoi email invitation à {self.email} pour {self.etablissement.nom}")
        logger.debug(f"DEFAULT_FROM_EMAIL = {getattr(settings, 'DEFAULT_FROM_EMAIL', 'NON DÉFINI')}")
        
        # Générer l'URL d'invitation
        invitation_url = self.get_invitation_url(request)
        logger.debug(f"URL invitation générée: {invitation_url}")
        
        # Contexte pour le template
        context = {
            'etablissement': self.etablissement,
            'invitation': self,
            'invitation_url': invitation_url,
            'expires_at': self.expires_at,
        }
        
        # Rendu du template email
        subject = f"Invitation - Gestion de l'établissement {self.etablissement.nom}"
        logger.debug(f"Subject: {subject}")
        
        try:
            html_content = render_to_string('schools/emails/invitation.html', context)
            text_content = render_to_string('schools/emails/invitation.txt', context)
            logger.debug("Templates email rendus avec succès")
        except Exception as e:
            logger.error(f"Erreur lors du rendu des templates email: {e}")
            raise
        
        # Envoi de l'email
        try:
            result = send_mail(
                subject=subject,
                message=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[self.email],
                html_message=html_content,
                fail_silently=False,
            )
            logger.info(f"Email envoyé avec succès. send_mail returned: {result}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de l'email: {e}")
            raise
        
        return True