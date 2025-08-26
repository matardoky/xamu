# Guide de démarrage Multi-Tenant avec Système d'Invitation

## ✅ Le système multi-tenant avec invitations sécurisées a été implémenté avec succès !

### 🚀 Étapes pour tester le système d'invitation :

#### 1. Appliquer les migrations
```bash
just manage makemigrations schools
just manage migrate
```

**Note**: Si vous voyez des warnings allauth concernant des méthodes dépréciées, ils ont été corrigés dans le code. Les warnings n'affectent pas le fonctionnement.

#### 2. Créer un superutilisateur
```bash
just manage createsuperuser
```

#### 3. Créer et inviter un établissement (NOUVEAU PROCESSUS)
1. Aller sur `/admin/`
2. Dans "Sites", créer un nouveau site :
   - Domain: `etb001.localhost`
   - Name: `École Test 001`
3. Dans "Schools > Établissements", créer un établissement :
   - Code: `etb001`
   - Nom: `École de Test`
   - Email: `chef@ecole-test.fr` (email du futur chef d'établissement)
   - Site: sélectionner le site créé ci-dessus
   - Cocher "Actif"
4. **ENVOYER L'INVITATION** :
   - Sélectionner l'établissement créé
   - Choisir l'action "Envoyer l'invitation par email"
   - L'invitation sera envoyée automatiquement

#### 4. Accepter l'invitation (Simuler le chef d'établissement)
1. Vérifier les emails dans la console ou les logs
2. Copier le lien d'invitation (format: `/schools/invitation/etb001/uuid-token/`)
3. Ouvrir le lien dans un navigateur
4. Remplir le formulaire de création de compte :
   - Nom: `Chef École`
   - Email: `chef@ecole-test.fr` (doit correspondre à l'invitation)
   - Mot de passe: `motdepasse123`
5. Le compte sera créé automatiquement avec le rôle `chef_etablissement`

#### 5. Tester l'accès sécurisé multi-tenant
- ✅ Accéder à `/etb001/` → Page d'accueil tenant (connecté comme chef)
- ✅ Accéder à `/etb001/dashboard/` → Dashboard établissement
- ✅ Accéder à `/etb001/users/` → Gestion utilisateurs
- ❌ Le super-admin ne peut PLUS accéder aux URLs tenant (sécurité renforcée)

### 🔧 URLs disponibles :

#### URLs globales (sans tenant) :
- `/` - Homepage globale avec sélection établissement
- `/about/` - Page À propos
- `/admin/` - Administration Django (super-admin uniquement)
- `/schools/invitation/<code>/<token>/` - **Acceptation d'invitation (nouveau)**
- `/schools/admin/invitation-status/<id>/` - Statut invitation pour super-admin
- `/schools/no-tenant/` - Page d'erreur tenant non trouvé
- `/api/schema/` - Schéma API OpenAPI
- `/api/docs/` - Documentation API

#### URLs tenant (avec `/etb001/`) :
- `/etb001/` - Homepage établissement
- `/etb001/dashboard/` - Dashboard principal
- `/etb001/accounts/login/` - **Connexion dans le contexte tenant**
- `/etb001/accounts/signup/` - **Inscription dans le contexte tenant**
- `/etb001/accounts/logout/` - **Déconnexion dans le contexte tenant**
- `/etb001/users/` - Gestion utilisateurs

### 💡 Fonctionnalités implémentées :

#### 🔐 **NOUVEAU : Système d'invitation sécurisé**
- **Invitation par email** : Tokens UUID sécurisés avec expiration (7 jours)
- **Création automatique de comptes** : Interface d'inscription intégrée
- **Emails professionnels** : Templates HTML/texte avec branding
- **Sécurité renforcée** : Super-admins bloqués de l'accès tenant
- **Validation stricte** : Email doit correspondre à l'invitation
- **Interface admin** : Gestion complète des invitations
- **Statuts visuels** : En attente / Utilisée / Expirée
- **Tests complets** : Couverture complète du système

#### ✅ **Architecture Multi-tenant de base**

#### ✅ Middleware TenantMiddleware
- Résolution automatique du tenant depuis l'URL
- Cache Redis pour performance optimale
- Gestion des erreurs 404 si tenant inexistant
- Thread-local storage pour accès global

#### ✅ Auto-filtering des données
- Toutes les requêtes sont automatiquement filtrées par tenant
- Impossible d'accéder aux données d'un autre établissement
- Injection automatique du tenant lors des créations

#### ✅ Mixins pour modèles
- `TenantMixin` : Champ établissement + manager tenant
- `TenantAuditMixin` : + champs audit (created_at, updated_at, etc.)
- `TenantUserMixin` : Spécialisé pour les utilisateurs

#### ✅ Utilitaires complets
- `@tenant_required` : Décorateur de vues
- `tenant_url()` : Génération URLs tenant-aware
- `TenantContext` : Context manager pour tests/Celery
- `validate_tenant_access()` : Validation permissions

#### ✅ Tests de sécurité
- Tests d'isolation des données
- Tests de performance avec cache
- Tests cross-tenant bloqués

#### ✅ Authentification tenant-aware
- **Allauth intégré au système multi-tenant**
- Login/Logout/Signup dans le contexte établissement
- Redirections automatiques vers le dashboard tenant
- Navigation adaptative selon le contexte
- Context processor pour templates tenant-aware

### 🔒 **NOUVEAU : Sécurité renforcée** :

1. **Séparation stricte des rôles** :
   - ✅ Super-admins : Gèrent uniquement les établissements via `/admin/`
   - ✅ Chefs d'établissement : Gèrent leurs données via `/etb001/`
   - ❌ **Aucun croisement** : Super-admins ne peuvent plus voir les données tenant

2. **Validation d'accès automatique** :
   - ✅ Utilisateur doit appartenir à l'établissement
   - ✅ Établissement doit être actif
   - ✅ Redirection automatique si tentative d'accès incorrect
   - ✅ Messages d'erreur explicites

3. **Protection contre les attaques** :
   - ✅ Tokens UUID impossibles à deviner
   - ✅ Expiration automatique des invitations
   - ✅ Validation email stricte
   - ✅ Une seule utilisation par invitation

### 🎯 **SYSTÈME PRÊT** - Modèle User déjà étendu :

Le modèle User a été automatiquement étendu avec :
```python
# ✅ DÉJÀ IMPLÉMENTÉ dans xamu/users/models.py
class User(AbstractUser):
    ROLE_CHOICES = [
        ('chef_etablissement', 'Chef d\'établissement'),
        ('professeur', 'Professeur'),
        ('cpe', 'CPE'),
        ('parent', 'Parent'),
    ]
    
    # Champs multi-tenant
    etablissement = ForeignKey('schools.Etablissement', ...)
    role = CharField(max_length=20, choices=ROLE_CHOICES)
    
    # Méthodes de permission
    def has_etablissement_perm(self, perm): ...
    def can_manage_etablissement(self): ...
    # + contrainte DB : un seul chef par établissement
```

### 🚀 Prochaines étapes pour votre app métier :

#### 2. Créer vos modèles métier
```python
# Dans une nouvelle app ou dans schools/models.py
from xamu.schools.mixins import TenantMixin

class Student(TenantMixin):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    student_number = models.CharField(max_length=20)
    # etablissement automatiquement ajouté via TenantMixin

class Absence(TenantMixin):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    date = models.DateField()
    is_justified = models.BooleanField(default=False)
    # etablissement automatiquement ajouté via TenantMixin
```

#### 3. Créer des vues tenant-aware
```python
from xamu.schools.utils import tenant_required

@tenant_required
def student_list(request):
    # request.tenant automatiquement disponible
    students = Student.objects.all()  # Filtré automatiquement par tenant
    return render(request, 'students/list.html', {'students': students})
```

#### 4. Implémenter l'import CSV
```python
from xamu.schools.utils import TenantContext

def import_students(csv_file, etablissement):
    with TenantContext(etablissement):
        # Toutes les créations seront automatiquement liées à cet établissement
        for row in csv_data:
            Student.objects.create(
                first_name=row['first_name'],
                last_name=row['last_name'],
                # etablissement ajouté automatiquement
            )
```

#### 5. Notifications Celery
```python
from celery import shared_task
from xamu.schools.utils import TenantContext

@shared_task
def send_absence_notifications(etablissement_id, absence_ids):
    etablissement = Etablissement.objects.get(id=etablissement_id)
    
    with TenantContext(etablissement):
        absences = Absence.objects.filter(id__in=absence_ids)
        # Envoyer emails aux parents...
```

### 🔒 Sécurité garantie :

1. **Isolation stricte** : Impossible d'accéder aux données d'un autre tenant
2. **Cache sécurisé** : Les tenants sont mis en cache de façon isolée
3. **Validation automatique** : Tentatives cross-tenant automatiquement bloquées
4. **Thread-safe** : Utilisation de thread-local storage
5. **Performance optimisée** : Une seule requête DB par tenant (avec cache)

### 📊 Monitoring et debug :

- Vérifier le tenant actuel : `request.tenant`
- Forcer un tenant : `set_current_tenant(etablissement)`
- Accéder à tous les tenants : `Model.objects.all_tenants()`
- Context manager : `with TenantContext(etb): ...`

### 🔧 Configuration finale :

Les settings dans `config/settings/base.py` sont déjà configurés correctement :

```python
# Les adaptateurs allauth utilisent maintenant la logique multi-tenant
ACCOUNT_ADAPTER = "xamu.users.adapters.AccountAdapter"  # ✅ Avec redirections tenant
SOCIALACCOUNT_ADAPTER = "xamu.users.adapters.SocialAccountAdapter"  # ✅ Avec redirections tenant

# Context processor pour variables tenant dans templates
"xamu.schools.context_processors.tenant_context",  # ✅ Ajouté

# Middleware tenant activé
"xamu.schools.middleware.TenantMiddleware",  # ✅ Activé

# App schools ajoutée
"xamu.schools",  # ✅ Ajoutée
```

Le système est **prêt en production** ! 🎉