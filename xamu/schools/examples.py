"""
Exemples d'usage du système multi-tenant xamu.

Ce fichier présente comment utiliser le système multi-tenant dans différents contextes.
"""

from django.db import models
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse

from .models import Etablissement
from .mixins import TenantMixin, TenantAuditMixin
from .utils import tenant_required, tenant_url, TenantContext, get_current_tenant
from .middleware import set_current_tenant


# ==============================================================================
# EXEMPLE 1: CRÉATION D'UN MODÈLE AVEC TENANT
# ==============================================================================

class Student(TenantAuditMixin):
    """
    Exemple de modèle élève utilisant le système multi-tenant.
    Hérite de TenantAuditMixin pour avoir établissement + audit.
    """
    first_name = models.CharField("Prénom", max_length=100)
    last_name = models.CharField("Nom", max_length=100)
    date_of_birth = models.DateField("Date de naissance")
    student_number = models.CharField("Numéro étudiant", max_length=20)
    
    class Meta:
        app_label = 'schools'
        unique_together = [['student_number', 'etablissement']]  # Unique par tenant
        verbose_name = "Élève"
        verbose_name_plural = "Élèves"
    
    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_number})"


class Absence(TenantMixin):
    """
    Exemple de modèle absence avec isolation tenant.
    """
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField("Date d'absence")
    period = models.CharField("Période", max_length=20)
    reason = models.TextField("Motif", blank=True)
    is_justified = models.BooleanField("Justifiée", default=False)
    
    class Meta:
        app_label = 'schools'
        verbose_name = "Absence"
        verbose_name_plural = "Absences"
    
    def __str__(self):
        return f"Absence de {self.student} le {self.date}"


# ==============================================================================
# EXEMPLE 2: VUES AVEC SYSTÈME TENANT
# ==============================================================================

@tenant_required
@login_required
def dashboard_view(request):
    """
    Dashboard principal d'un établissement.
    Le décorateur @tenant_required garantit la présence du tenant.
    """
    # request.tenant est automatiquement disponible
    etablissement = request.tenant
    
    # Toutes les requêtes sont automatiquement filtrées par tenant
    total_students = Student.objects.count()
    recent_absences = Absence.objects.filter(date__gte='2024-01-01')[:10]
    
    context = {
        'etablissement': etablissement,
        'total_students': total_students,
        'recent_absences': recent_absences,
    }
    return render(request, 'schools/dashboard.html', context)


@tenant_required
def student_list_view(request):
    """
    Liste des élèves - automatiquement filtrée par tenant.
    """
    # Pas besoin de filtrer manuellement - le TenantManager s'en charge
    students = Student.objects.all().order_by('last_name', 'first_name')
    
    # Génération d'URLs tenant-aware
    create_url = tenant_url('student_create')
    
    return render(request, 'schools/student_list.html', {
        'students': students,
        'create_url': create_url,
    })


@tenant_required
def student_detail_view(request, student_id):
    """
    Détail d'un élève avec vérification automatique du tenant.
    """
    # get_object_or_404 utilise automatiquement le filtrage tenant
    student = get_object_or_404(Student, id=student_id)
    
    # L'élève appartient forcément au tenant actuel
    absences = Absence.objects.filter(student=student).order_by('-date')
    
    return render(request, 'schools/student_detail.html', {
        'student': student,
        'absences': absences,
    })


# ==============================================================================
# EXEMPLE 3: API AVEC TENANT
# ==============================================================================

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
@tenant_required
def api_student_stats(request):
    """
    API retournant les statistiques des élèves du tenant actuel.
    """
    etablissement = request.tenant
    
    stats = {
        'etablissement_code': etablissement.code,
        'etablissement_nom': etablissement.nom,
        'total_students': Student.objects.count(),
        'total_absences': Absence.objects.count(),
        'absences_not_justified': Absence.objects.filter(is_justified=False).count(),
    }
    
    return Response(stats)


# ==============================================================================
# EXEMPLE 4: TÂCHES CELERY AVEC TENANT
# ==============================================================================

from celery import shared_task

@shared_task
def send_absence_notifications(etablissement_id, absence_ids):
    """
    Tâche Celery pour envoyer les notifications d'absence.
    Utilise TenantContext pour définir le tenant.
    """
    try:
        etablissement = Etablissement.objects.get(id=etablissement_id)
        
        # Définir le contexte tenant pour toute la tâche
        with TenantContext(etablissement):
            absences = Absence.objects.filter(id__in=absence_ids)
            
            for absence in absences:
                # Logique d'envoi d'email
                send_email_to_parents(absence)
                
        return f"Notifications envoyées pour {len(absence_ids)} absences"
        
    except Etablissement.DoesNotExist:
        return f"Établissement {etablissement_id} non trouvé"


def send_email_to_parents(absence):
    """
    Envoie un email aux parents pour une absence.
    """
    # Implémentation de l'envoi d'email
    pass


# ==============================================================================
# EXEMPLE 5: MANAGEMENT COMMAND AVEC TENANT
# ==============================================================================

from django.core.management.base import BaseCommand

class Command(BaseCommand):
    """
    Exemple de management command qui traite tous les tenants.
    Usage: python manage.py process_all_tenants
    """
    help = 'Traite les données pour tous les établissements'
    
    def handle(self, *args, **options):
        etablissements = Etablissement.objects.filter(is_active=True)
        
        for etablissement in etablissements:
            self.stdout.write(f"Traitement de {etablissement.nom}...")
            
            with TenantContext(etablissement):
                # Toutes les opérations dans ce contexte sont isolées
                student_count = Student.objects.count()
                absence_count = Absence.objects.count()
                
                self.stdout.write(
                    f"  - {student_count} élèves, {absence_count} absences"
                )
        
        self.stdout.write(
            self.style.SUCCESS('Traitement terminé pour tous les établissements')
        )


# ==============================================================================
# EXEMPLE 6: TESTS AVEC SYSTÈME TENANT
# ==============================================================================

from django.test import TestCase
from django.contrib.sites.models import Site

class TenantTestCase(TestCase):
    """
    Classe de base pour les tests avec système tenant.
    """
    
    def setUp(self):
        # Créer des établissements de test
        self.site1 = Site.objects.create(domain='test1.example.com', name='Test1')
        self.site2 = Site.objects.create(domain='test2.example.com', name='Test2')
        
        self.etablissement1 = Etablissement.objects.create(
            code='test001',
            nom='École Test 1',
            site=self.site1
        )
        
        self.etablissement2 = Etablissement.objects.create(
            code='test002',
            nom='École Test 2',
            site=self.site2
        )
    
    def test_tenant_isolation(self):
        """Test que les données sont bien isolées par tenant."""
        
        # Créer un élève dans le premier tenant
        with TenantContext(self.etablissement1):
            student1 = Student.objects.create(
                first_name="Jean",
                last_name="Dupont",
                student_number="001",
                date_of_birth="2010-01-01"
            )
            count1 = Student.objects.count()
        
        # Créer un élève dans le second tenant
        with TenantContext(self.etablissement2):
            student2 = Student.objects.create(
                first_name="Marie",
                last_name="Martin",
                student_number="001",  # Même numéro, mais tenant différent
                date_of_birth="2010-02-01"
            )
            count2 = Student.objects.count()
        
        # Vérifier l'isolation
        self.assertEqual(count1, 1)
        self.assertEqual(count2, 1)
        
        # Vérifier que chaque élève appartient au bon tenant
        self.assertEqual(student1.etablissement, self.etablissement1)
        self.assertEqual(student2.etablissement, self.etablissement2)
    
    def test_cross_tenant_access_blocked(self):
        """Test qu'on ne peut pas accéder aux données d'un autre tenant."""
        
        # Créer un élève dans le premier tenant
        with TenantContext(self.etablissement1):
            student = Student.objects.create(
                first_name="Test",
                last_name="User",
                student_number="123",
                date_of_birth="2010-01-01"
            )
            student_id = student.id
        
        # Essayer d'accéder depuis le second tenant
        with TenantContext(self.etablissement2):
            with self.assertRaises(Student.DoesNotExist):
                Student.objects.get(id=student_id)
        
        # Mais on peut accéder avec all_tenants()
        with TenantContext(self.etablissement2):
            student_found = Student.objects.all_tenants().get(id=student_id)
            self.assertEqual(student_found.etablissement, self.etablissement1)


# ==============================================================================
# EXEMPLE 7: UTILITAIRES ET HELPERS
# ==============================================================================

def get_tenant_students_with_absences(tenant_code=None):
    """
    Fonction utilitaire pour récupérer les élèves avec leurs absences.
    """
    if tenant_code:
        tenant = Etablissement.get_by_code(tenant_code)
        if not tenant:
            return None
        
        with TenantContext(tenant):
            return _get_students_with_absences()
    else:
        # Utiliser le tenant actuel
        return _get_students_with_absences()


def _get_students_with_absences():
    """Helper interne pour récupérer les données."""
    students = Student.objects.prefetch_related('absence_set').all()
    
    results = []
    for student in students:
        results.append({
            'student': student,
            'absence_count': student.absence_set.count(),
            'unexcused_count': student.absence_set.filter(is_justified=False).count()
        })
    
    return results


def switch_to_tenant(tenant_code):
    """
    Fonction pour changer de tenant programmatiquement.
    Utilisée principalement pour les tests ou l'admin.
    """
    tenant = Etablissement.get_by_code(tenant_code)
    if tenant:
        set_current_tenant(tenant)
        return tenant
    return None


# ==============================================================================
# EXEMPLE 8: INTÉGRATION AVEC LES PERMISSIONS
# ==============================================================================

from django.contrib.auth.decorators import user_passes_test
from .utils import validate_tenant_access

def tenant_user_required(view_func):
    """
    Décorateur combiné pour vérifier tenant + permissions utilisateur.
    """
    @tenant_required
    @login_required
    def wrapper(request, *args, **kwargs):
        # Valider que l'utilisateur a accès au tenant actuel
        validate_tenant_access(request.user, request.tenant)
        return view_func(request, *args, **kwargs)
    
    return wrapper


@tenant_user_required
def admin_student_import(request):
    """
    Vue d'import CSV pour les élèves - nécessite tenant + permissions.
    """
    if request.method == 'POST':
        # Logique d'import avec tenant automatique
        csv_file = request.FILES['csv_file']
        imported_count = import_students_from_csv(csv_file)
        
        return JsonResponse({
            'success': True,
            'imported': imported_count,
            'tenant': request.tenant.code
        })
    
    return render(request, 'schools/import_students.html')


def import_students_from_csv(csv_file):
    """
    Import CSV avec tenant automatique.
    Le tenant est déjà défini par le middleware.
    """
    import csv
    import io
    
    count = 0
    csv_content = csv_file.read().decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in csv_reader:
        # Pas besoin de spécifier l'établissement - automatique via TenantMixin
        Student.objects.create(
            first_name=row['first_name'],
            last_name=row['last_name'],
            student_number=row['student_number'],
            date_of_birth=row['date_of_birth']
        )
        count += 1
    
    return count