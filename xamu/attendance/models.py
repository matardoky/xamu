from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import time, timedelta

from xamu.schools.mixins import TenantMixin


class Cours(TenantMixin):
    """
    Modèle représentant un cours programmé.
    """
    TYPE_COURS_CHOICES = [
        ('cours', _('Cours magistral')),
        ('td', _('Travaux dirigés')),
        ('tp', _('Travaux pratiques')),
        ('controle', _('Contrôle/Évaluation')),
        ('autre', _('Autre')),
    ]
    
    date_heure_debut = models.DateTimeField(
        _("Date et heure de début"),
        help_text=_("Début du cours")
    )
    
    date_heure_fin = models.DateTimeField(
        _("Date et heure de fin"),
        help_text=_("Fin du cours")
    )
    
    matiere = models.ForeignKey(
        'academic.Matiere',
        on_delete=models.CASCADE,
        verbose_name=_("Matière"),
        related_name='cours'
    )
    
    classe = models.ForeignKey(
        'academic.Classe',
        on_delete=models.CASCADE,
        verbose_name=_("Classe"),
        related_name='cours'
    )
    
    professeur = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        limit_choices_to={'role': 'professeur'},
        verbose_name=_("Professeur"),
        related_name='cours_enseignes'
    )
    
    salle = models.CharField(
        _("Salle"),
        max_length=50,
        blank=True,
        help_text=_("Salle de cours (optionnel)")
    )
    
    type_cours = models.CharField(
        _("Type de cours"),
        max_length=20,
        choices=TYPE_COURS_CHOICES,
        default='cours'
    )
    
    annule = models.BooleanField(
        _("Cours annulé"),
        default=False,
        help_text=_("Ce cours a été annulé")
    )
    
    motif_annulation = models.TextField(
        _("Motif d'annulation"),
        blank=True,
        help_text=_("Raison de l'annulation du cours")
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cours_crees',
        verbose_name=_("Créé par")
    )
    
    class Meta:
        verbose_name = _("Cours")
        verbose_name_plural = _("Cours")
        ordering = ['date_heure_debut']
    
    def __str__(self):
        date_str = self.date_heure_debut.strftime('%d/%m/%Y %H:%M')
        return f"{self.matiere.code_court} - {self.classe.nom} - {date_str}"
    
    @property
    def duree(self):
        """Retourne la durée du cours en minutes."""
        if self.date_heure_fin and self.date_heure_debut:
            delta = self.date_heure_fin - self.date_heure_debut
            return int(delta.total_seconds() / 60)
        return 0
    
    @property
    def est_en_cours(self):
        """Vérifie si le cours est actuellement en cours."""
        maintenant = timezone.now()
        return (self.date_heure_debut <= maintenant <= self.date_heure_fin 
                and not self.annule)
    
    @property
    def est_termine(self):
        """Vérifie si le cours est terminé."""
        return timezone.now() > self.date_heure_fin
    
    @property
    def nombre_absences(self):
        """Retourne le nombre d'absences pour ce cours."""
        return self.absences.filter(type_absence='absence').count()
    
    @property
    def nombre_retards(self):
        """Retourne le nombre de retards pour ce cours."""
        return self.absences.filter(type_absence='retard').count()
    
    def clean(self):
        # Vérifier que la fin est après le début
        if self.date_heure_fin and self.date_heure_debut:
            if self.date_heure_fin <= self.date_heure_debut:
                raise ValidationError({
                    'date_heure_fin': _('La fin du cours doit être après le début')
                })
            
            # Vérifier que le cours ne dépasse pas une journée
            if (self.date_heure_fin - self.date_heure_debut).days >= 1:
                raise ValidationError({
                    'date_heure_fin': _('Un cours ne peut pas dépasser une journée')
                })
        
        # Vérifier que tous les éléments appartiennent au même établissement
        if (self.matiere and self.classe and 
            self.matiere.etablissement != self.classe.etablissement):
            raise ValidationError(
                _('La matière et la classe doivent appartenir au même établissement')
            )
        
        if (self.professeur and hasattr(self.professeur, 'etablissement') and
            self.etablissement != self.professeur.etablissement):
            raise ValidationError({
                'professeur': _('Le professeur doit appartenir au même établissement')
            })


class Absence(TenantMixin):
    """
    Modèle représentant une absence, un retard ou un départ anticipé d'un élève.
    """
    TYPE_ABSENCE_CHOICES = [
        ('absence', _('Absence')),
        ('retard', _('Retard')),
        ('depart_anticipe', _('Départ anticipé')),
    ]
    
    eleve = models.ForeignKey(
        'academic.Eleve',
        on_delete=models.CASCADE,
        verbose_name=_("Élève"),
        related_name='absences'
    )
    
    cours = models.ForeignKey(
        Cours,
        on_delete=models.CASCADE,
        verbose_name=_("Cours"),
        related_name='absences'
    )
    
    type_absence = models.CharField(
        _("Type d'absence"),
        max_length=20,
        choices=TYPE_ABSENCE_CHOICES,
        default='absence'
    )
    
    heure_constat = models.TimeField(
        _("Heure de constat"),
        help_text=_("Heure à laquelle l'absence/retard a été constaté")
    )
    
    justifiee = models.BooleanField(
        _("Justifiée"),
        default=False,
        help_text=_("L'absence a été justifiée par un responsable")
    )
    
    motif_justification = models.TextField(
        _("Motif de justification"),
        blank=True,
        help_text=_("Raison donnée pour justifier l'absence")
    )
    
    date_justification = models.DateTimeField(
        _("Date de justification"),
        null=True,
        blank=True,
        help_text=_("Quand l'absence a été justifiée")
    )
    
    justifiee_par = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role__in': ['cpe', 'chef_etablissement']},
        verbose_name=_("Justifiée par"),
        related_name='justifications_validees'
    )
    
    commentaire_prof = models.TextField(
        _("Commentaire du professeur"),
        blank=True,
        help_text=_("Observations du professeur")
    )
    
    notification_envoyee = models.BooleanField(
        _("Notification envoyée"),
        default=False,
        help_text=_("Une notification a été envoyée aux parents")
    )
    
    date_notification = models.DateTimeField(
        _("Date de notification"),
        null=True,
        blank=True
    )
    
    # Métadonnées
    created_at = models.DateTimeField(_("Créé le"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Modifié le"), auto_now=True)
    created_by = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        verbose_name=_("Créé par"),
        related_name='absences_saisies',
        help_text=_("Professeur qui a saisi l'absence")
    )
    
    class Meta:
        verbose_name = _("Absence")
        verbose_name_plural = _("Absences")
        ordering = ['-cours__date_heure_debut']
        constraints = [
            models.UniqueConstraint(
                fields=['eleve', 'cours'],
                name='unique_absence_per_eleve_cours'
            )
        ]
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.get_type_absence_display()} - {self.cours}"
    
    @property
    def duree_retard(self):
        """
        Calcule la durée du retard en minutes.
        Applicable uniquement pour les retards.
        """
        if self.type_absence != 'retard':
            return 0
            
        if self.heure_constat and self.cours.date_heure_debut:
            # Convertir l'heure de début du cours en time
            heure_debut = self.cours.date_heure_debut.time()
            
            # Calculer la différence
            debut_minutes = heure_debut.hour * 60 + heure_debut.minute
            constat_minutes = self.heure_constat.hour * 60 + self.heure_constat.minute
            
            return max(0, constat_minutes - debut_minutes)
        return 0
    
    def marquer_comme_justifiee(self, motif, user):
        """
        Marque l'absence comme justifiée.
        
        Args:
            motif (str): Motif de la justification
            user (User): Utilisateur qui valide la justification
        """
        self.justifiee = True
        self.motif_justification = motif
        self.date_justification = timezone.now()
        self.justifiee_par = user
        self.save()
    
    def envoyer_notification(self):
        """
        Marque que la notification a été envoyée.
        La logique d'envoi réelle sera dans l'app notifications.
        """
        self.notification_envoyee = True
        self.date_notification = timezone.now()
        self.save()
    
    def clean(self):
        # Vérifier que l'élève appartient à la classe du cours
        if (self.eleve and self.cours and 
            self.eleve.classe_actuelle != self.cours.classe):
            raise ValidationError({
                'eleve': _('L\'élève doit appartenir à la classe du cours')
            })
        
        # Vérifier que l'heure de constat est cohérente avec le type d'absence
        if self.cours and self.heure_constat:
            heure_debut = self.cours.date_heure_debut.time()
            heure_fin = self.cours.date_heure_fin.time()
            
            if self.type_absence == 'retard':
                # Pour un retard, l'heure de constat doit être après le début
                if self.heure_constat <= heure_debut:
                    raise ValidationError({
                        'heure_constat': _('Pour un retard, l\'heure doit être après le début du cours')
                    })
            
            elif self.type_absence == 'depart_anticipe':
                # Pour un départ anticipé, l'heure doit être avant la fin
                if self.heure_constat >= heure_fin:
                    raise ValidationError({
                        'heure_constat': _('Pour un départ anticipé, l\'heure doit être avant la fin du cours')
                    })
        
        # Vérifier que tous les éléments appartiennent au même établissement
        if (self.eleve and self.cours and 
            self.eleve.etablissement != self.cours.etablissement):
            raise ValidationError(
                _('L\'élève et le cours doivent appartenir au même établissement')
            )


class StatistiquesAbsences(models.Model):
    """
    Modèle pour stocker des statistiques pré-calculées d'absences.
    Permet d'optimiser les requêtes pour les tableaux de bord.
    """
    eleve = models.ForeignKey(
        'academic.Eleve',
        on_delete=models.CASCADE,
        verbose_name=_("Élève"),
        related_name='statistiques'
    )
    
    periode_debut = models.DateField(
        _("Début de période"),
        help_text=_("Date de début de la période de calcul")
    )
    
    periode_fin = models.DateField(
        _("Fin de période"),
        help_text=_("Date de fin de la période de calcul")
    )
    
    total_absences = models.PositiveIntegerField(
        _("Total absences"),
        default=0
    )
    
    total_retards = models.PositiveIntegerField(
        _("Total retards"),
        default=0
    )
    
    total_departs_anticipes = models.PositiveIntegerField(
        _("Total départs anticipés"),
        default=0
    )
    
    absences_justifiees = models.PositiveIntegerField(
        _("Absences justifiées"),
        default=0
    )
    
    absences_non_justifiees = models.PositiveIntegerField(
        _("Absences non justifiées"),
        default=0
    )
    
    heures_cours_manquees = models.PositiveIntegerField(
        _("Heures de cours manquées"),
        default=0,
        help_text=_("Nombre d'heures de cours manquées (absences seulement)")
    )
    
    # Métadonnées
    calculee_le = models.DateTimeField(_("Calculée le"), auto_now=True)
    
    class Meta:
        verbose_name = _("Statistiques d'absences")
        verbose_name_plural = _("Statistiques d'absences")
        constraints = [
            models.UniqueConstraint(
                fields=['eleve', 'periode_debut', 'periode_fin'],
                name='unique_stats_per_eleve_periode'
            )
        ]
    
    def __str__(self):
        return f"Stats {self.eleve.nom_complet} ({self.periode_debut} - {self.periode_fin})"
