"""
Tests pour les permissions strictes du middleware multi-tenant.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sites.models import Site
from django.http import Http404
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.urls import reverse

from ..middleware import TenantMiddleware
from ..models import Etablissement

User = get_user_model()


class TenantMiddlewarePermissionsTest(TestCase):
    """Tests pour les permissions strictes du middleware tenant"""

    def setUp(self):
        """Configuration initiale pour les tests"""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(lambda r: None)

        # Créer des sites pour les établissements
        self.site1 = Site.objects.create(
            domain="etb001.example.com",
            name="École 1 Site",
        )
        self.site2 = Site.objects.create(
            domain="etb002.example.com",
            name="Test Site",
        )

        # Créer des établissements
        self.etablissement1 = Etablissement.objects.create(
            code="etb001",
            nom="École Test 1",
            email="contact1@test.fr",
            site=self.site1,
            is_active=True,
        )

        self.etablissement2 = Etablissement.objects.create(
            code="etb002",
            nom="École Test 2",
            email="contact2@test.fr",
            site=self.site2,
            is_active=True,
        )

        # Créer des utilisateurs
        self.superuser = User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
        )

        self.user_etb1 = User.objects.create_user(
            email="chef1@test.fr",
            password="testpass123",
            name="Chef 1",
            etablissement=self.etablissement1,
            role="chef_etablissement",
        )

        self.user_etb2 = User.objects.create_user(
            email="chef2@test.fr",
            password="testpass123",
            name="Chef 2",
            etablissement=self.etablissement2,
            role="chef_etablissement",
        )

        self.user_no_etb = User.objects.create_user(
            email="orphan@test.fr",
            password="testpass123",
            name="Orphan User",
        )

    def _add_middleware(self, request, user=None):
        """Ajoute les middlewares nécessaires à la request"""
        # Session middleware
        session_middleware = SessionMiddleware(lambda r: None)
        session_middleware.process_request(request)
        request.session.save()

        # Auth middleware
        auth_middleware = AuthenticationMiddleware(lambda r: None)
        auth_middleware.process_request(request)

        # Message middleware
        message_middleware = MessageMiddleware(lambda r: None)
        message_middleware.process_request(request)

        # Définir l'utilisateur
        if user:
            request.user = user
        else:
            from django.contrib.auth.models import AnonymousUser
            request.user = AnonymousUser()

        return request

    def test_exempt_paths_no_tenant_required(self):
        """Test que les URLs exemptées n'ont pas besoin de tenant"""
        exempt_paths = [
            "/admin/",
            "/api/schema/",
            "/static/css/style.css",
            "/media/uploads/file.pdf",
            "/favicon.ico$",
            "/$",  # Homepage sans tenant (landing page)
            "/about/$",  # Page about globale
            "/schools/",
            "/accounts/",
            "/users/~redirect/",
        ]

        for path in exempt_paths:
            request = self.factory.get(path)
            request = self._add_middleware(request)

            response = self.middleware.process_request(request)

            # Ces URLs ne doivent pas être redirigées
            self.assertIsNone(response, f"Path {path} should be exempt")
            self.assertIsNone(getattr(request, "tenant", None))

    def test_tenant_path_resolves_correctly(self):
        """Test de résolution correcte du tenant"""
        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request, self.user_etb1)

        response = self.middleware.process_request(request)

        self.assertIsNone(response)  # Pas de redirection
        self.assertEqual(request.tenant, self.etablissement1)
        self.assertEqual(request.tenant_code, "etb001")

    def test_invalid_tenant_code_raises_404(self):
        """Test qu'un code tenant invalide lève une 404"""
        request = self.factory.get("/invalid/dashboard/")
        request = self._add_middleware(request)

        with self.assertRaises(Http404):
            self.middleware.process_request(request)

    def test_anonymous_user_redirected_to_login(self):
        """Test que les utilisateurs anonymes sont redirigés vers la connexion"""
        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request)  # Utilisateur anonyme

        response = self.middleware.process_request(request)

        # Doit être redirigé vers la page de connexion
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("account_login"))

    def test_superuser_blocked_from_tenant_access(self):
        """Test que les super-admins ne peuvent pas accéder aux données tenant"""
        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request, self.superuser)

        response = self.middleware.process_request(request)

        # Super-admin doit être redirigé vers l'admin
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)

    def test_user_without_etablissement_blocked(self):
        """Test qu'un utilisateur sans établissement est bloqué"""
        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request, self.user_no_etb)

        response = self.middleware.process_request(request)

        # Utilisateur sans établissement doit être redirigé
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)

    def test_user_accessing_wrong_etablissement_blocked(self):
        """Test qu'un utilisateur ne peut pas accéder à un autre établissement"""
        request = self.factory.get("/etb002/dashboard/")  # user_etb1 essaie d'accéder à etb002
        request = self._add_middleware(request, self.user_etb1)

        response = self.middleware.process_request(request)

        # Utilisateur doit être redirigé vers son propre établissement
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)

    def test_user_accessing_correct_etablissement_allowed(self):
        """Test qu'un utilisateur peut accéder à son propre établissement"""
        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request, self.user_etb1)

        response = self.middleware.process_request(request)

        # Accès autorisé
        self.assertIsNone(response)
        self.assertEqual(request.tenant, self.etablissement1)

    def test_auth_exempt_paths_allow_anonymous(self):
        """Test que les URLs d'auth permettent l'accès anonyme"""
        auth_paths = [
            "/etb001/accounts/login/",
            "/etb001/accounts/signup/",
            "/etb001/accounts/password/reset/",
        ]

        for path in auth_paths:
            request = self.factory.get(path)
            request = self._add_middleware(request)  # Utilisateur anonyme

            response = self.middleware.process_request(request)

            # Ces URLs ne doivent pas rediriger les utilisateurs anonymes
            self.assertIsNone(response, f"Auth path {path} should allow anonymous access")

    def test_inactive_etablissement_blocks_access(self):
        """Test qu'un établissement inactif bloque l'accès"""
        # Désactiver l'établissement
        self.etablissement1.is_active = False
        self.etablissement1.save()

        request = self.factory.get("/etb001/dashboard/")
        request = self._add_middleware(request, self.user_etb1)

        response = self.middleware.process_request(request)

        # Accès doit être bloqué pour établissement inactif
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 302)


class TenantMiddlewareIntegrationTest(TestCase):
    """Tests d'intégration du middleware avec les vues réelles"""

    def setUp(self):
        """Configuration initiale"""
        # Créer un site
        self.site = Site.objects.create(
            domain="test.example.com",
            name="Test Site",
        )

        # Créer un établissement
        self.etablissement = Etablissement.objects.create(
            code="etb001",
            nom="École Test",
            site=self.site,
            is_active=True,
        )

        # Créer un utilisateur
        self.user = User.objects.create_user(
            email="chef@test.fr",
            password="testpass123",
            name="Chef Test",
            etablissement=self.etablissement,
            role="chef_etablissement",
        )

        self.client = Client()

    def test_tenant_dashboard_requires_correct_user(self):
        """Test que le dashboard nécessite le bon utilisateur"""
        # Tenter d'accéder sans connexion
        url = reverse("tenant:dashboard", kwargs={"tenant_code": "etb001"})
        response = self.client.get(url)

        # Doit être redirigé vers la connexion
        self.assertEqual(response.status_code, 302)

        # Se connecter avec le bon utilisateur
        self.client.force_login(self.user)
        response = self.client.get(url)

        # Maintenant l'accès doit être autorisé
        self.assertEqual(response.status_code, 200)

    def test_superuser_cannot_access_tenant_dashboard(self):
        """Test que les super-admins ne peuvent pas accéder au dashboard tenant"""
        superuser = User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
        )

        self.client.force_login(superuser)

        url = reverse("tenant:dashboard", kwargs={"tenant_code": "etb001"})
        response = self.client.get(url)

        # Super-admin doit être redirigé
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, "/admin/")

    def test_user_with_different_etablissement_redirected(self):
        """Test qu'un utilisateur d'un autre établissement est redirigé"""
        # Créer un autre établissement et utilisateur
        other_site = Site.objects.create(
            domain="other.example.com",
            name="Other Site",
        )
        other_etablissement = Etablissement.objects.create(
            code="etb002",
            nom="Autre École",
            site=other_site,
        )
        other_user = User.objects.create_user(
            email="chef2@test.fr",
            password="testpass123",
            etablissement=other_etablissement,
            role="chef_etablissement",
        )

        self.client.force_login(other_user)

        # Tenter d'accéder au dashboard de etb001
        url = reverse("tenant:dashboard", kwargs={"tenant_code": "etb001"})
        response = self.client.get(url)

        # Doit être redirigé vers son propre établissement
        self.assertEqual(response.status_code, 302)
        expected_url = reverse("tenant:home", kwargs={"tenant_code": "etb002"})
        self.assertRedirects(response, expected_url)
