from typing import ClassVar

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField, ForeignKey, CASCADE, Q
from django.db.models import EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .managers import UserManager


# Permissions par rôle (définies une seule fois)
ROLE_PERMISSIONS = {
    'chef_etablissement': [
        'manage_users', 'manage_students', 'manage_classes', 
        'view_absences', 'manage_absences', 'view_statistics'
    ],
    'cpe': [
        'manage_students', 'view_absences', 'manage_absences', 
        'view_statistics'
    ],
    'professeur': [
        'view_students', 'view_absences', 'add_absences'
    ],
    'parent': [
        'view_own_children', 'view_own_absences'
    ]
}


class User(AbstractUser):
    """
    Custom user model for xamu with multi-tenant support.
    Users are associated with establishments through roles.
    """
    
    # Rôles dans l'établissement scolaire
    ROLE_CHOICES = [
        ('chef_etablissement', _('Chef d\'établissement')),
        ('professeur', _('Professeur')),
        ('cpe', _('CPE (Conseiller Principal d\'Éducation)')),
        ('parent', _('Parent')),
    ]

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore[assignment]
    
    # Champs multi-tenant
    etablissement = ForeignKey(
        'schools.Etablissement',
        on_delete=CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Établissement"),
        help_text=_("Établissement auquel appartient cet utilisateur")
    )
    
    role = CharField(
        _("Rôle"),
        max_length=20,
        choices=ROLE_CHOICES,
        blank=True,
        help_text=_("Rôle de l'utilisateur dans l'établissement")
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects: ClassVar[UserManager] = UserManager()

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view in tenant context."""
        if self.etablissement:
            return reverse("tenant:users:detail", kwargs={"tenant_code": self.etablissement.code, "pk": self.pk})
        return reverse("users:detail", kwargs={"pk": self.id})
    
    def has_role(self, role_name: str) -> bool:
        """
        Vérifie si l'utilisateur a un rôle spécifique.
        """
        return self.role == role_name
    
    @property
    def is_chef_etablissement(self) -> bool:
        """Vérifie si l'utilisateur est chef d'établissement."""
        return self.has_role('chef_etablissement')
    
    @property 
    def is_professeur(self) -> bool:
        """Vérifie si l'utilisateur est professeur."""
        return self.has_role('professeur')
    
    @property
    def is_cpe(self) -> bool:
        """Vérifie si l'utilisateur est CPE."""
        return self.has_role('cpe')
    
    @property
    def is_parent(self) -> bool:
        """Vérifie si l'utilisateur est parent."""
        return self.has_role('parent')
    
    @property
    def can_manage_etablissement(self) -> bool:
        """Vérifie si l'utilisateur peut gérer l'établissement."""
        return self.is_chef_etablissement or self.is_cpe
    
    @property
    def can_manage_students(self) -> bool:
        """Vérifie si l'utilisateur peut gérer les élèves."""
        return self.role in ['chef_etablissement', 'cpe', 'professeur']
    
    def has_etablissement_perm(self, perm: str) -> bool:
        """
        Vérifie les permissions dans le contexte de l'établissement.
        """
        if self.is_superuser:
            return True
            
        if not self.etablissement:
            return False
        
        return perm in ROLE_PERMISSIONS.get(self.role, [])
    
    class Meta:
        verbose_name = _("Utilisateur")
        verbose_name_plural = _("Utilisateurs")
        constraints = [
            # Un chef d'établissement par établissement
            models.UniqueConstraint(
                fields=['etablissement'],
                condition=models.Q(role='chef_etablissement'),
                name='unique_chef_per_etablissement'
            )
        ]