"""
Tests pour le système d'invitation des établissements.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.utils import timezone
from uuid import uuid4
import datetime

from ..models import Etablissement, EtablissementInvitation
from ...users.adapters import AccountAdapter

User = get_user_model()


class EtablissementInvitationModelTest(TestCase):
    """Tests pour le modèle EtablissementInvitation"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        # Créer un site pour l'établissement
        self.site = Site.objects.create(
            domain='test.example.com',
            name='Test Site'
        )
        
        # Créer un établissement
        self.etablissement = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            email='contact@ecole-test.fr',
            site=self.site
        )
        
        # Créer un super-admin
        self.superuser = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
    
    def test_create_invitation(self):
        """Test de création d'invitation"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        self.assertEqual(invitation.etablissement, self.etablissement)
        self.assertEqual(invitation.email, 'chef@ecole-test.fr')
        self.assertFalse(invitation.used)
        self.assertTrue(invitation.is_valid)
        self.assertFalse(invitation.is_expired)
        self.assertIsNotNone(invitation.token)
        self.assertIsNotNone(invitation.expires_at)
    
    def test_invitation_expires_at_auto_set(self):
        """Test que expires_at est défini automatiquement"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        expected_expires = timezone.now() + datetime.timedelta(days=7)
        self.assertAlmostEqual(
            invitation.expires_at, 
            expected_expires, 
            delta=datetime.timedelta(seconds=10)
        )
    
    def test_invitation_is_expired(self):
        """Test de détection d'invitation expirée"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser,
            expires_at=timezone.now() - datetime.timedelta(hours=1)
        )
        
        self.assertTrue(invitation.is_expired)
        self.assertFalse(invitation.is_valid)
    
    def test_invitation_is_used(self):
        """Test d'invitation utilisée"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        # Créer un utilisateur et utiliser l'invitation
        user = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123',
            name='Chef Test'
        )
        
        invitation.use_invitation(user)
        
        self.assertTrue(invitation.used)
        self.assertFalse(invitation.is_valid)
        self.assertEqual(invitation.user_created, user)
        self.assertIsNotNone(invitation.used_at)
        self.assertEqual(user.etablissement, self.etablissement)
    
    def test_use_expired_invitation(self):
        """Test d'utilisation d'invitation expirée"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser,
            expires_at=timezone.now() - datetime.timedelta(hours=1)
        )
        
        user = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123'
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            invitation.use_invitation(user)
    
    def test_use_already_used_invitation(self):
        """Test d'utilisation d'invitation déjà utilisée"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        # Premier utilisateur
        user1 = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123'
        )
        invitation.use_invitation(user1)
        
        # Deuxième utilisateur
        user2 = User.objects.create_user(
            email='autre@test.fr',
            password='testpass123'
        )
        
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            invitation.use_invitation(user2)
    
    def test_get_invitation_url(self):
        """Test de génération d'URL d'invitation"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        url = invitation.get_invitation_url()
        expected_url = reverse('schools:accept_invitation', kwargs={
            'tenant_code': self.etablissement.code,
            'token': str(invitation.token)
        })
        
        self.assertEqual(url, expected_url)
    
    def test_send_invitation_email(self):
        """Test d'envoi d'email d'invitation"""
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        # Vider la boîte mail
        mail.outbox = []
        
        # Envoyer l'invitation
        result = invitation.send_invitation_email()
        
        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        
        email = mail.outbox[0]
        self.assertIn(self.etablissement.nom, email.subject)
        self.assertIn(invitation.get_invitation_url(), email.body)


class AcceptInvitationViewTest(TestCase):
    """Tests pour la vue d'acceptation d'invitation"""
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        self.client = Client()
        
        # Créer un site pour l'établissement
        self.site = Site.objects.create(
            domain='test.example.com',
            name='Test Site'
        )
        
        # Créer un établissement
        self.etablissement = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            email='contact@ecole-test.fr',
            site=self.site
        )
        
        # Créer un super-admin
        self.superuser = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
        
        # Créer une invitation valide
        self.invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
    
    def test_get_accept_invitation_page(self):
        """Test d'affichage de la page d'acceptation"""
        url = reverse('schools:accept_invitation', kwargs={
            'tenant_code': self.etablissement.code,
            'token': str(self.invitation.token)
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('account_signup')}?email={self.invitation.email}")
    
    def test_accept_invitation_invalid_etablissement(self):
        """Test avec code établissement invalide"""
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': 'invalid',
            'token': str(self.invitation.token)
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_accept_invitation_invalid_token(self):
        """Test avec token invalide"""
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': self.etablissement.code,
            'token': str(uuid4())
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_accept_invitation_expired(self):
        """Test avec invitation expirée"""
        # Expirer l'invitation
        self.invitation.expires_at = timezone.now() - datetime.timedelta(hours=1)
        self.invitation.save()
        
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': self.etablissement.code,
            'token': str(self.invitation.token)
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invitation a expiré')
    
    def test_accept_invitation_already_used(self):
        """Test avec invitation déjà utilisée"""
        # Marquer l'invitation comme utilisée
        user = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123'
        )
        self.invitation.use_invitation(user)
        
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': self.etablissement.code,
            'token': str(self.invitation.token)
        })
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invitation a déjà été utilisée')
    
    
    
    def test_accept_invitation_logged_in_user(self):
        """Test d'acceptation avec utilisateur connecté"""
        # Créer un utilisateur et le connecter
        user = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123',
            name='Chef Test'
        )
        self.client.force_login(user)
        
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': self.etablissement.code,
            'token': str(self.invitation.token)
        })
        
        # GET pour accepter l'invitation (devrait rediriger si déjà connecté et email correspond)
        response = self.client.get(url)
        
        # Vérifier la redirection vers le dashboard
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('tenant:dashboard', kwargs={'tenant_code': self.etablissement.code}))
        
        # Vérifier que l'utilisateur a été associé
        user.refresh_from_db()
        self.assertEqual(user.etablissement, self.etablissement)
        self.assertEqual(user.role, 'chef_etablissement')
    
    def test_accept_invitation_user_already_has_etablissement(self):
        """Test avec utilisateur déjà associé à un établissement"""
        # Créer un autre établissement
        other_site = Site.objects.create(
            domain='other.example.com',
            name='Other Site'
        )
        other_etablissement = Etablissement.objects.create(
            code='etb002',
            nom='Autre École',
            site=other_site
        )
        
        # Créer un utilisateur déjà associé
        user = User.objects.create_user(
            email='chef@ecole-test.fr',
            password='testpass123',
            etablissement=other_etablissement,
            role='chef_etablissement'
        )
        self.client.force_login(user)
        
        url = reverse('schools:accept_invitation', kwargs={
            'etablissement_code': self.etablissement.code,
            'token': str(self.invitation.token)
        })
        
        response = self.client.post(url)
        
        # L'utilisateur doit être redirigé vers son propre établissement
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response, 
            reverse('tenant:dashboard', kwargs={'tenant_code': other_etablissement.code})
        )


class AccountAdapterTest(TestCase):
    """Tests pour l'AccountAdapter personnalisé"""
    
    def setUp(self):
        self.client = Client()
        self.site = Site.objects.create(
            domain='test.example.com',
            name='Test Site'
        )
        self.etablissement = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            email='contact@ecole-test.fr',
            site=self.site
        )
        self.superuser = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
        self.invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='test@example.com',
            created_by=self.superuser
        )
        self.adapter = AccountAdapter()
        
    def test_save_user_with_invitation(self):
        # Simuler une requête avec le token d'invitation en session
        session = self.client.session
        session['invitation_token'] = str(self.invitation.token)
        session['tenant_code'] = self.etablissement.code
        session.save()
        
        request = self.client.request().wsgi_request
        request.session = session
        
        # Créer un utilisateur (simuler le formulaire allauth)
        user = User(
            email='test@example.com',
            name='Test User'
        )
        user.set_password('password123')
        
        # Appeler save_user
        self.adapter.save_user(request, user, form=None)
        
        # Vérifier que l'utilisateur est associé à l'établissement
        user.refresh_from_db()
        self.assertEqual(user.etablissement, self.etablissement)
        self.assertEqual(user.role, 'chef_etablissement')
        
        # Vérifier que l'invitation a été utilisée
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.used)
        self.assertEqual(self.invitation.user_created, user)
        
        # Vérifier que les tokens ont été retirés de la session
        self.assertNotIn('invitation_token', request.session)
        self.assertNotIn('tenant_code', request.session)
        
    def test_save_user_without_invitation(self):
        # Simuler une requête sans token d'invitation
        request = self.client.request().wsgi_request
        request.session = self.client.session
        
        # Créer un utilisateur
        user = User(
            email='noinvitation@example.com',
            name='No Invitation User'
        )
        user.set_password('password123')
        
        # Appeler save_user
        self.adapter.save_user(request, user, form=None)
        
        # Vérifier que l'utilisateur n'est pas associé à un établissement
        user.refresh_from_db()
        self.assertIsNone(user.etablissement)
        self.assertIsNone(user.role)


class InvitationSystemAdminTest(TestCase):
    """
    Tests pour l'interface admin du système d'invitation
    """
    
    def setUp(self):
        """Configuration initiale pour les tests"""
        self.client = Client()
        
        # Créer un site pour l'établissement
        self.site = Site.objects.create(
            domain='test.example.com',
            name='Test Site'
        )
        
        # Créer un établissement
        self.etablissement = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            email='contact@ecole-test.fr',
            site=self.site
        )
        
        # Créer un super-admin et se connecter
        self.superuser = User.objects.create_superuser(
            email='admin@test.com',
            password='testpass123'
        )
        self.client.force_login(self.superuser)
    
    def test_etablissement_admin_shows_invitation_status(self):
        """Test que l'admin affiche le statut d'invitation"""
        # Créer une invitation
        invitation = EtablissementInvitation.objects.create(
            etablissement=self.etablissement,
            email='chef@ecole-test.fr',
            created_by=self.superuser
        )
        
        url = reverse('admin:schools_etablissement_changelist')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'En attente')  # Statut d'invitation
    
    def test_send_invitation_action(self):
        """Test de l'action d'envoi d'invitation"""
        # Vider la boîte mail
        mail.outbox = []
        
        url = reverse('admin:schools_etablissement_changelist')
        
        # Exécuter l'action d'envoi d'invitation
        response = self.client.post(url, {
            'action': 'send_invitation',
            '_selected_action': [self.etablissement.pk]
        })
        
        self.assertEqual(response.status_code, 302)  # Redirection après action
        
        # Vérifier qu'une invitation a été créée
        invitation = EtablissementInvitation.objects.get(
            etablissement=self.etablissement
        )
        self.assertIsNotNone(invitation)
        
        # Vérifier qu'un email a été envoyé
        self.assertEqual(len(mail.outbox), 1)
    
    def test_invitation_inline_admin(self):
        """Test de l'inline d'invitation dans l'admin établissement"""
        url = reverse('admin:schools_etablissement_change', args=[self.etablissement.pk])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'invitation')  # Formulaire inline
    
    def test_non_superuser_cannot_access_admin(self):
        """Test que les non-superusers n'ont pas accès à l'admin"""
        # Créer un utilisateur normal
        user = User.objects.create_user(
            email='user@test.com',
            password='testpass123'
        )
        self.client.force_login(user)
        
        url = reverse('admin:schools_etablissement_changelist')
        response = self.client.get(url)
        
        # L'utilisateur ne doit pas voir d'établissements
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, self.etablissement.nom)