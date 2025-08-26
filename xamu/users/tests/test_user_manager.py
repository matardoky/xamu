"""
Tests pour le UserManager personnalisé.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site

from ..managers import UserManager
from xamu.schools.models import Etablissement

User = get_user_model()


class UserManagerTest(TestCase):
    """Tests pour les méthodes du UserManager personnalisé"""
    
    def setUp(self):
        """Configuration initiale"""
        # Créer un site
        self.site = Site.objects.create(
            domain='test.example.com',
            name='Test Site'
        )
        
        # Créer un établissement
        self.etablissement = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            site=self.site
        )
    
    def test_create_user_basic(self):
        """Test de création d'utilisateur basique"""
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
        
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test User')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('testpass123'))
        self.assertIsNone(user.etablissement)
        self.assertEqual(user.role, '')  # Pas de rôle par défaut
    
    def test_create_superuser(self):
        """Test de création de superuser"""
        user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        self.assertEqual(user.email, 'admin@example.com')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password('adminpass123'))
        self.assertIsNone(user.etablissement)  # Superuser n'a pas d'établissement
    
    def test_create_etablissement_user(self):
        """Test de création d'utilisateur d'établissement"""
        user = User.objects.create_etablissement_user(
            email='prof@ecole.fr',
            password='profpass123',
            name='Professeur Test',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        self.assertEqual(user.email, 'prof@ecole.fr')
        self.assertEqual(user.name, 'Professeur Test')
        self.assertEqual(user.etablissement, self.etablissement)
        self.assertEqual(user.role, 'professeur')
        self.assertFalse(user.is_superuser)
    
    def test_create_etablissement_user_without_etablissement_fails(self):
        """Test que créer un utilisateur d'établissement sans établissement échoue"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_etablissement_user(
                email='prof@ecole.fr',
                password='profpass123',
                role='professeur'
            )
        
        self.assertIn("Establishment users must have an etablissement", str(context.exception))
    
    def test_create_etablissement_user_without_role_fails(self):
        """Test que créer un utilisateur d'établissement sans rôle échoue"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_etablissement_user(
                email='prof@ecole.fr',
                password='profpass123',
                etablissement=self.etablissement
            )
        
        self.assertIn("Establishment users must have a role", str(context.exception))
    
    def test_create_chef_etablissement(self):
        """Test de création de chef d'établissement"""
        user = User.objects.create_chef_etablissement(
            email='chef@ecole.fr',
            password='chefpass123',
            name='Chef Test',
            etablissement=self.etablissement
        )
        
        self.assertEqual(user.email, 'chef@ecole.fr')
        self.assertEqual(user.name, 'Chef Test')
        self.assertEqual(user.etablissement, self.etablissement)
        self.assertEqual(user.role, 'chef_etablissement')
        self.assertTrue(user.is_chef_etablissement)
        self.assertTrue(user.can_manage_etablissement)
    
    def test_create_chef_etablissement_without_etablissement_fails(self):
        """Test que créer un chef sans établissement échoue"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_chef_etablissement(
                email='chef@ecole.fr',
                password='chefpass123'
            )
        
        self.assertIn("Establishment users must have an etablissement", str(context.exception))
    
    def test_for_etablissement_query(self):
        """Test de requête par établissement"""
        # Créer plusieurs utilisateurs
        User.objects.create_chef_etablissement(
            email='chef1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement
        )
        
        User.objects.create_etablissement_user(
            email='prof1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        # Créer un autre établissement et utilisateur
        other_site = Site.objects.create(domain='other.com', name='Other')
        other_etablissement = Etablissement.objects.create(
            code='etb002',
            nom='Autre École',
            site=other_site
        )
        User.objects.create_chef_etablissement(
            email='chef2@autre.fr',
            password='pass123',
            etablissement=other_etablissement
        )
        
        # Tester la requête
        users = User.objects.for_etablissement(self.etablissement)
        self.assertEqual(users.count(), 2)
        
        emails = set(user.email for user in users)
        self.assertEqual(emails, {'chef1@ecole.fr', 'prof1@ecole.fr'})
    
    def test_chefs_etablissement_query(self):
        """Test de requête des chefs d'établissement"""
        # Créer différents types d'utilisateurs
        User.objects.create_chef_etablissement(
            email='chef1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement
        )
        
        User.objects.create_etablissement_user(
            email='prof1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        User.objects.create_etablissement_user(
            email='cpe1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='cpe'
        )
        
        # Tester la requête
        chefs = User.objects.chefs_etablissement()
        self.assertEqual(chefs.count(), 1)
        self.assertEqual(chefs.first().email, 'chef1@ecole.fr')
    
    def test_by_role_query(self):
        """Test de requête par rôle"""
        # Créer des utilisateurs avec différents rôles
        User.objects.create_etablissement_user(
            email='prof1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        User.objects.create_etablissement_user(
            email='prof2@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        User.objects.create_etablissement_user(
            email='cpe1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='cpe'
        )
        
        # Tester la requête
        professeurs = User.objects.by_role('professeur')
        self.assertEqual(professeurs.count(), 2)
        
        cpes = User.objects.by_role('cpe')
        self.assertEqual(cpes.count(), 1)
    
    def test_active_users_query(self):
        """Test de requête des utilisateurs actifs"""
        # Créer différents types d'utilisateurs
        User.objects.create_etablissement_user(
            email='prof1@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        
        # Utilisateur inactif
        inactive_user = User.objects.create_etablissement_user(
            email='prof2@ecole.fr',
            password='pass123',
            etablissement=self.etablissement,
            role='professeur'
        )
        inactive_user.is_active = False
        inactive_user.save()
        
        # Superuser (ne doit pas être inclus)
        User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123'
        )
        
        # Utilisateur sans établissement
        User.objects.create_user(
            email='orphan@example.com',
            password='pass123'
        )
        
        # Tester la requête
        active_users = User.objects.active_users()
        self.assertEqual(active_users.count(), 1)
        self.assertEqual(active_users.first().email, 'prof1@ecole.fr')
    
    def test_create_user_validates_email_required(self):
        """Test que l'email est requis"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_user(email='', password='pass123')
        
        self.assertIn("The given email must be set", str(context.exception))
    
    def test_create_superuser_validates_staff_required(self):
        """Test que is_staff est requis pour les superusers"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                password='pass123',
                is_staff=False
            )
        
        self.assertIn("Superuser must have is_staff=True", str(context.exception))
    
    def test_create_superuser_validates_superuser_required(self):
        """Test que is_superuser est requis pour les superusers"""
        with self.assertRaises(ValueError) as context:
            User.objects.create_superuser(
                email='admin@example.com',
                password='pass123',
                is_superuser=False
            )
        
        self.assertIn("Superuser must have is_superuser=True", str(context.exception))