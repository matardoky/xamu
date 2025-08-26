from django.apps import AppConfig


class SchoolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'xamu.schools'
    
    def ready(self):
        """Importer les signaux quand l'app est prête."""
        import xamu.schools.signals
