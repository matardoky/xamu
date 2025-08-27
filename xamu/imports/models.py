from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

from xamu.schools.models import Etablissement


class ImportSession(models.Model):
    """Session d'import pour traçabilité"""
    TYPE_IMPORT_CHOICES = [ # Re-added this
        ('personnel', _('Personnel')),
        ('classes', _('Classes')),
        ('eleves', _('Élèves')),
    ]

    etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
    type_import = models.CharField(
        max_length=20,
        choices=TYPE_IMPORT_CHOICES # Using the re-added choices
    )
    nom_session = models.CharField(max_length=100)  # "Rentrée 2024"
    fichier_csv = models.FileField(upload_to='imports/%Y/%m/')
    statut = models.CharField(
        max_length=20,
        choices=[
            ('uploaded', 'Fichier uploadé'),
            ('validated', 'Données validées'),
            ('processing', 'Import en cours'),
            ('completed', 'Terminé'),
            ('error', 'Erreur')
        ],
        default='uploaded'
    )
    resultats = models.JSONField(default=dict)  # Stats + erreurs détaillés
    nb_comptes_crees = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE
    )  # Chef établissement
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom_session} ({self.get_type_import_display()})"


class ComptesGeneres(models.Model):
    """Traçabilité des comptes générés pour impression fiches"""
    import_session = models.ForeignKey(ImportSession, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    mot_de_passe_temporaire = models.CharField(max_length=50)  # Stockage temporaire pour impression
    fiche_imprimee = models.BooleanField(default=False)
    distribue = models.BooleanField(default=False)
    date_distribution = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Compte pour {self.user} (session: {self.import_session.id})"