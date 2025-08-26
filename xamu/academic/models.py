from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone

from xamu.schools.mixins import TenantMixin


class Matiere(TenantMixin):
    """
    Modèle représentant une matière/discipline d'enseignement.
    """
    nom = models.CharField(
        _("Nom de la matière"),
        max_length=100,
        help_text=_("Ex: Mathématiques, Français, Histoire-Géographie")
    )
    
    code_court = models.CharField(
        _("Code court"),
        max_length=10,
        help_text=_("Abréviation pour l'affichage (ex: MATH, FR, HG)")
    )
    
    couleur = models.CharField(
        _("Couleur"),
        max_length=7,
        default="#007bff",
        help_text=_("Couleur en format HEX pour l'affichage dans l'interface")
    )
    
    actif = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Matière enseignée dans l'établissement")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Matière")
        verbose_name_plural = _("Matières")
        ordering = ['nom']
        constraints = [
            models.UniqueConstraint(
                fields=['code_court', 'etablissement'],
                name='unique_code_court_per_etablissement'
            ),
            models.UniqueConstraint(
                fields=['nom', 'etablissement'],
                name='unique_matiere_per_etablissement'
            )
        ]
    
    def __str__(self):
        return f"{self.nom} ({self.code_court})"
    
    def clean(self):
        if self.couleur and not self.couleur.startswith('#'):
            self.couleur = f"#{self.couleur}"


class Classe(TenantMixin):
    """
    Modèle représentant une classe d'élèves.
    """
    NIVEAU_CHOICES = [
        ('6e', _('Sixième')),
        ('5e', _('Cinquième')),
        ('4e', _('Quatrième')),
        ('3e', _('Troisième')),
        ('2nde', _('Seconde')),
        ('1ere', _('Première')),
        ('term', _('Terminale')),
        ('autre', _('Autre')),
    ]
    
    nom = models.CharField(
        _("Nom de la classe"),
        max_length=50,
        help_text=_("Ex: 6A, 5B, 2ndeC")
    )
    
    niveau = models.CharField(
        _("Niveau"),
        max_length=10,
        choices=NIVEAU_CHOICES,
        help_text=_("Niveau scolaire de la classe")
    )
    
    professeur_principal = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'professeur'},
        verbose_name=_("Professeur principal"),
        related_name='classes_principales'
    )
    
    annee_scolaire = models.CharField(
        _("Année scolaire"),
        max_length=9,
        help_text=_("Format: 2024-2025")
    )
    
    effectif_max = models.PositiveIntegerField(
        _("Effectif maximum"),
        default=35,
        help_text=_("Nombre maximum d'élèves dans cette classe")
    )
    
    actif = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Classe active dans l'établissement")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Classe")
        verbose_name_plural = _("Classes")
        ordering = ['niveau', 'nom']
        constraints = [
            models.UniqueConstraint(
                fields=['nom', 'annee_scolaire', 'etablissement'],
                name='unique_classe_per_year_etablissement'
            )
        ]
    
    def __str__(self):
        return f"{self.nom} - {self.annee_scolaire}"
    
    @property
    def effectif_actuel(self):
        """Retourne l'effectif actuel de la classe."""
        return self.eleves.filter(actif=True).count()
    
    @property
    def places_disponibles(self):
        """Retourne le nombre de places disponibles."""
        return max(0, self.effectif_max - self.effectif_actuel)
    
    def clean(self):
        # Validation de l'année scolaire
        import re
        if not re.match(r'^\d{4}-\d{4}$', self.annee_scolaire):
            raise ValidationError({
                'annee_scolaire': _('Le format doit être YYYY-YYYY (ex: 2024-2025)')
            })
        
        # Vérifier que le professeur principal appartient au même établissement
        if (self.professeur_principal and 
            hasattr(self.professeur_principal, 'etablissement') and
            self.professeur_principal.etablissement != self.etablissement):
            raise ValidationError({
                'professeur_principal': _('Le professeur principal doit appartenir au même établissement')
            })


class Eleve(TenantMixin):
    """
    Modèle représentant un élève de l'établissement.
    """
    nom = models.CharField(
        _("Nom de famille"),
        max_length=100
    )
    
    prenom = models.CharField(
        _("Prénom"),
        max_length=100
    )
    
    classe_actuelle = models.ForeignKey(
        Classe,
        on_delete=models.CASCADE,
        verbose_name=_("Classe actuelle"),
        related_name='eleves'
    )
    
    date_naissance = models.DateField(
        _("Date de naissance"),
        null=True,
        blank=True
    )
    
    numero_ine = models.CharField(
        _("Numéro INE"),
        max_length=11,
        blank=True,
        help_text=_("Identifiant National Élève (optionnel)")
    )
    
    actif = models.BooleanField(
        _("Actif"),
        default=True,
        help_text=_("Élève scolarisé dans l'établissement")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Élève")
        verbose_name_plural = _("Élèves")
        ordering = ['nom', 'prenom']
        constraints = [
            models.UniqueConstraint(
                fields=['nom', 'prenom', 'etablissement'],
                name='unique_eleve_per_etablissement'
            ),
            models.UniqueConstraint(
                fields=['numero_ine', 'etablissement'],
                condition=models.Q(numero_ine__isnull=False) & ~models.Q(numero_ine=''),
                name='unique_ine_per_etablissement'
            )
        ]
    
    def __str__(self):
        return f"{self.prenom} {self.nom} ({self.classe_actuelle.nom})"
    
    @property
    def nom_complet(self):
        """Retourne le nom complet de l'élève."""
        return f"{self.prenom} {self.nom}"
    
    def clean(self):
        # Vérifier que la classe appartient au même établissement
        if (self.classe_actuelle and 
            self.classe_actuelle.etablissement != self.etablissement):
            raise ValidationError({
                'classe_actuelle': _('La classe doit appartenir au même établissement')
            })


class RelationFamiliale(TenantMixin):
    """
    Modèle représentant la relation entre un élève et un parent/responsable légal.
    """
    TYPE_RELATION_CHOICES = [
        ('pere', _('Père')),
        ('mere', _('Mère')),
        ('tuteur_legal', _('Tuteur légal')),
        ('autre', _('Autre responsable')),
    ]
    
    eleve = models.ForeignKey(
        Eleve,
        on_delete=models.CASCADE,
        verbose_name=_("Élève"),
        related_name='relations_familiales'
    )
    
    parent = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'parent'},
        verbose_name=_("Parent/Responsable"),
        related_name='enfants'
    )
    
    type_relation = models.CharField(
        _("Type de relation"),
        max_length=20,
        choices=TYPE_RELATION_CHOICES,
        default='autre'
    )
    
    principal = models.BooleanField(
        _("Contact principal"),
        default=False,
        help_text=_("Contact prioritaire pour cet élève")
    )
    
    autorise_notifications = models.BooleanField(
        _("Autorise les notifications"),
        default=True,
        help_text=_("Ce parent peut recevoir les notifications concernant l'élève")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Relation familiale")
        verbose_name_plural = _("Relations familiales")
        constraints = [
            models.UniqueConstraint(
                fields=['eleve', 'parent'],
                name='unique_parent_eleve_relation'
            )
        ]
    
    def __str__(self):
        return f"{self.parent.name} ({self.get_type_relation_display()}) - {self.eleve.nom_complet}"
    
    def clean(self):
        # Vérifier que l'élève et le parent appartiennent au même établissement
        if (self.eleve and self.parent and 
            hasattr(self.parent, 'etablissement') and
            self.eleve.etablissement != self.parent.etablissement):
            raise ValidationError(
                _('L\'élève et le parent doivent appartenir au même établissement')
            )
