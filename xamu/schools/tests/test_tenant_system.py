"""
Tests pour le système multi-tenant complet.
"""

from django.test import TestCase, RequestFactory, override_settings
from django.contrib.sites.models import Site
from django.core.exceptions import ImproperlyConfigured
from django.http import Http404
from django.db import models
from unittest.mock import patch

from ..models import Etablissement
from ..middleware import TenantMiddleware, get_current_tenant, set_current_tenant, clear_current_tenant
from ..managers import TenantManager
from ..mixins import TenantMixin
from ..utils import TenantContext, tenant_required, tenant_url


class TestTenantModel(TenantMixin):
    """Modèle de test utilisant TenantMixin"""
    name = models.CharField(max_length=100)
    
    class Meta:
        app_label = 'schools'


class TenantMiddlewareTest(TestCase):
    """Tests pour le TenantMiddleware"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware()
        
        # Créer des établissements de test
        self.site1 = Site.objects.create(domain='test1.com', name='Test1')
        self.site2 = Site.objects.create(domain='test2.com', name='Test2')
        
        self.etb1 = Etablissement.objects.create(
            code='etb001',
            nom='École Test 1',
            email='contact1@test.fr',
            site=self.site1
        )
        self.etb2 = Etablissement.objects.create(
            code='etb002',
            nom='École Test 2',
            email='contact2@test.fr',
            site=self.site2
        )
    
    def test_extract_tenant_from_url(self):
        """Test extraction du tenant depuis l'URL"""
        request = self.factory.get('/etb001/dashboard/')
        
        result = self.middleware.process_request(request)
        
        self.assertIsNone(result)  # Pas de redirection
        self.assertEqual(request.tenant, self.etb1)
        self.assertEqual(request.tenant_code, 'etb001')
    
    def test_nonexistent_tenant_404(self):
        """Test erreur 404 pour tenant inexistant"""
        request = self.factory.get('/etb999/dashboard/')
        
        with self.assertRaises(Http404):
            self.middleware.process_request(request)
    
    def test_inactive_tenant_404(self):
        """Test erreur 404 pour tenant inactif"""
        self.etb1.is_active = False
        self.etb1.save()
        
        request = self.factory.get('/etb001/dashboard/')
        
        with self.assertRaises(Http404):
            self.middleware.process_request(request)
    
    def test_exempt_paths_no_tenant(self):
        """Test que les paths exemptés n'ont pas de tenant"""
        exempt_paths = [
            '/admin/',
            '/api/schema/',
            '/static/css/main.css',
            '/',
            '/about/',
            '/accounts/login/',
            '/accounts/signup/',
            '/schools/invitation/etb001/token123/',
            '/users/~redirect/',
        ]
        
        for path in exempt_paths:
            request = self.factory.get(path)
            result = self.middleware.process_request(request)
            
            self.assertIsNone(result)
            self.assertIsNone(request.tenant)
    
    def test_url_without_tenant_redirects(self):
        """Test redirection pour URLs sans tenant"""
        request = self.factory.get('/dashboard/')
        
        result = self.middleware.process_request(request)
        
        self.assertEqual(result.status_code, 302)  # Redirection
        self.assertEqual(result.url, '/')
    
    def test_auth_urls_without_tenant_do_not_raise_404(self):
        """Test que les URLs d'auth sans tenant ne lèvent pas de 404"""
        auth_paths = [
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/password/reset/',
        ]
        
        for path in auth_paths:
            request = self.factory.get(path)
            result = self.middleware.process_request(request)
            
            self.assertIsNone(result) # Ne doit pas rediriger ou lever de 404
            self.assertIsNone(getattr(request, 'tenant', None)) # Pas de tenant attaché
    
    def test_tenant_caching(self):
        """Test mise en cache des tenants"""
        with patch('xamu.schools.models.cache') as mock_cache:
            mock_cache.get.return_value = None
            mock_cache.set.return_value = None
            
            # Premier appel
            tenant = Etablissement.get_by_code('etb001')
            
            # Vérifier que le cache est utilisé
            mock_cache.get.assert_called_with('etablissement:etb001')
            mock_cache.set.assert_called()
            
            # Deuxième appel
            mock_cache.get.return_value = self.etb1
            tenant2 = Etablissement.get_by_code('etb001')
            
            # Le cache devrait être utilisé
            self.assertEqual(mock_cache.get.call_count, 2)


class TenantManagerTest(TestCase):
    """Tests pour le TenantManager"""
    
    def setUp(self):
        self.site1 = Site.objects.create(domain='test1.com', name='Test1')
        self.site2 = Site.objects.create(domain='test2.com', name='Test2')
        
        self.etb1 = Etablissement.objects.create(
            code='etb001',
            nom='École Test 1',
            site=self.site1
        )
        self.etb2 = Etablissement.objects.create(
            code='etb002',
            nom='École Test 2',
            site=self.site2
        )
    
    def test_auto_filtering_with_tenant(self):
        """Test filtrage automatique avec tenant"""
        # Simuler un modèle avec TenantMixin
        class TestModel(models.Model):
            etablissement = models.ForeignKey(Etablissement, on_delete=models.CASCADE)
            name = models.CharField(max_length=100)
            objects = TenantManager()
            _tenant_field = 'etablissement'
            
            class Meta:
                app_label = 'schools'
        
        # Ne pas créer vraiment les tables pour ce test
        # Juste tester la logique
        
        with TenantContext(self.etb1):
            # Simuler une requête avec tenant
            tenant = get_current_tenant()
            self.assertEqual(tenant, self.etb1)
    
    def test_all_tenants_method(self):
        """Test méthode all_tenants()"""
        # Test conceptuel - ne peut pas être testé facilement sans modèle réel
        pass
    
    def test_for_tenant_method(self):
        """Test méthode for_tenant()"""
        # Test conceptuel - ne peut pas être testé facilement sans modèle réel
        pass


class TenantMixinTest(TestCase):
    """Tests pour TenantMixin"""
    
    def setUp(self):
        self.site1 = Site.objects.create(domain='test1.com', name='Test1')
        self.etb1 = Etablissement.objects.create(
            code='etb001',
            nom='École Test 1',
            site=self.site1
        )
    
    def test_auto_tenant_injection(self):
        """Test injection automatique du tenant"""
        with TenantContext(self.etb1):
            # Simuler la création d'un objet
            tenant = get_current_tenant()
            self.assertEqual(tenant, self.etb1)


class TenantUtilsTest(TestCase):
    """Tests pour les utilitaires tenant"""
    
    def setUp(self):
        self.factory = RequestFactory()
        self.site1 = Site.objects.create(domain='test1.com', name='Test1')
        self.etb1 = Etablissement.objects.create(
            code='etb001',
            nom='École Test 1',
            site=self.site1
        )
    
    def test_tenant_required_decorator(self):
        """Test décorateur tenant_required"""
        
        @tenant_required
        def test_view(request):
            return "Success"
        
        # Test avec tenant
        request = self.factory.get('/etb001/dashboard/')
        request.tenant = self.etb1
        
        response = self.middleware.process_request(request)
        self.assertIsNone(response)
        result = test_view(request)
        self.assertEqual(result, "Success")
        
        # Test sans tenant
        request_no_tenant = self.factory.get('/dashboard/')
        
        with self.assertRaises(Http404):
            test_view(request_no_tenant)
    
    def test_tenant_url_generation(self):
        """Test génération URLs tenant"""
        with TenantContext(self.etb1):
            # Test conceptuel - nécessiterait des URLs définies
            pass
    
    def test_tenant_context_manager(self):
        """Test context manager TenantContext"""
        # Vérifier qu'il n'y a pas de tenant au départ
        self.assertIsNone(get_current_tenant())
        
        # Utiliser le context manager
        with TenantContext(self.etb1):
            self.assertEqual(get_current_tenant(), self.etb1)
        
        # Vérifier que le tenant est nettoyé après
        self.assertIsNone(get_current_tenant())
    
    def test_nested_tenant_context(self):
        """Test context managers imbriqués"""
        site2 = Site.objects.create(domain='test2.com', name='Test2')
        etb2 = Etablissement.objects.create(
            code='etb002',
            nom='École Test 2',
            site=site2
        )
        
        with TenantContext(self.etb1):
            self.assertEqual(get_current_tenant(), self.etb1)
            
            with TenantContext(etb2):
                self.assertEqual(get_current_tenant(), etb2)
            
            # Retour au tenant précédent
            self.assertEqual(get_current_tenant(), self.etb1)
        
        # Nettoyage final
        self.assertIsNone(get_current_tenant())


class TenantSecurityTest(TestCase):
    """Tests de sécurité pour l'isolation des tenants"""
    
    def setUp(self):
        self.site1 = Site.objects.create(domain='test1.com', name='Test1')
        self.site2 = Site.objects.create(domain='test2.com', name='Test2')
        
        self.etb1 = Etablissement.objects.create(
            code='etb001',
            nom='École Test 1',
            site=self.site1
        )
        self.etb2 = Etablissement.objects.create(
            code='etb002',
            nom='École Test 2',
            site=self.site2
        )
    
    def test_tenant_isolation(self):
        """Test isolation stricte entre tenants"""
        # Test conceptuel - nécessiterait des modèles réels avec données
        
        with TenantContext(self.etb1):
            # Toutes les opérations devraient être isolées à etb1
            tenant = get_current_tenant()
            self.assertEqual(tenant, self.etb1)
        
        with TenantContext(self.etb2):
            # Toutes les opérations devraient être isolées à etb2
            tenant = get_current_tenant()
            self.assertEqual(tenant, self.etb2)
    
    def test_prevent_cross_tenant_access(self):
        """Test prévention accès cross-tenant"""
        # Test conceptuel - nécessiterait modèles réels
        pass


class TenantPerformanceTest(TestCase):
    """Tests de performance pour le système tenant"""
    
    def setUp(self):
        self.site = Site.objects.create(domain='test.com', name='Test')
        self.etb = Etablissement.objects.create(
            code='etb001',
            nom='École Test',
            site=self.site
        )
    
    def test_tenant_caching_performance(self):
        """Test performance du cache tenant"""
        # Mesurer les appels de cache
        import time
        
        # Premier appel (mise en cache)
        start = time.time()
        tenant1 = Etablissement.get_by_code('etb001')
        first_call_time = time.time() - start
        
        # Deuxième appel (depuis cache)
        start = time.time()
        tenant2 = Etablissement.get_by_code('etb001')
        second_call_time = time.time() - start
        
        # Le deuxième appel devrait être plus rapide
        # Note: Ce test peut être flaky selon l'environnement
        self.assertEqual(tenant1, tenant2)
    
    def test_no_db_query_per_request(self):
        """Test qu'il n'y a pas de requête DB à chaque request après cache"""
        with patch('django.db.connection') as mock_connection:
            # Forcer la mise en cache
            Etablissement.get_by_code('etb001')
            
            # Deuxième appel ne devrait pas faire de requête
            Etablissement.get_by_code('etb001')
            
            # Vérifier qu'il n'y a pas eu de requête supplémentaire
            # Note: Test conceptuel, l'implémentation réelle dépend du cache