from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import UserManager as DjangoUserManager


class UserManager(DjangoUserManager["User"]):
    """Custom manager for the User model."""

    def _create_user(self, email: str, password: str | None, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            msg = "The given email must be set"
            raise ValueError(msg)
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.password = make_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)
    
    def create_etablissement_user(self, email: str, password: str | None = None, 
                                 etablissement=None, role: str = "professeur", **extra_fields):
        """
        Create a user associated with an establishment.
        For non-superusers, etablissement and role are required.
        """
        if not etablissement:
            raise ValueError("Establishment users must have an etablissement.")
        
        if not role:
            raise ValueError("Establishment users must have a role.")
            
        extra_fields['etablissement'] = etablissement
        extra_fields['role'] = role
        
        return self.create_user(email, password, **extra_fields)
    
    def create_chef_etablissement(self, email: str, password: str | None = None, 
                                 etablissement=None, **extra_fields):
        """
        Create a chef d'établissement user.
        Used specifically for invitation acceptance.
        """
        if not etablissement:
            raise ValueError("Chef d'établissement must have an etablissement.")
        
        extra_fields['etablissement'] = etablissement
        extra_fields['role'] = "chef_etablissement"
        
        return self.create_user(email, password, **extra_fields)

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):  # type: ignore[override]
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            msg = "Superuser must have is_staff=True."
            raise ValueError(msg)
        if extra_fields.get("is_superuser") is not True:
            msg = "Superuser must have is_superuser=True."
            raise ValueError(msg)

        # Les superusers n'ont pas d'établissement par défaut
        extra_fields.setdefault("etablissement", None)
        extra_fields.setdefault("role", "")  # Pas de rôle pour les superusers

        return self._create_user(email, password, **extra_fields)
    
    def for_etablissement(self, etablissement):
        """Get all users for a specific establishment."""
        return self.filter(etablissement=etablissement)
    
    def chefs_etablissement(self):
        """Get all chef d'établissement users."""
        return self.filter(role='chef_etablissement')
    
    def by_role(self, role: str):
        """Get all users with a specific role."""
        return self.filter(role=role)
    
    def active_users(self):
        """Get all active (non-superuser) users with establishments."""
        return self.filter(
            is_active=True,
            is_superuser=False,
            etablissement__isnull=False
        )