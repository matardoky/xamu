import csv
import io
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from xamu.schools.models import Etablissement
from xamu.academic.models import Classe # Assuming this model exists
from xamu.users.models import User # Assuming this model exists
from ..models import ComptesGeneres
from .base_service import BaseImportService

User = get_user_model()


class ClassesImportService(BaseImportService):
    REQUIRED_HEADERS = ['nom_classe', 'niveau', 'annee_scolaire']

    def validate_csv(self, file_path):
        header, data = self._read_csv_data(file_path)
        errors = []

        if header is None:
            errors.append(self.results['message'])
            return False, errors

        for rh in self.REQUIRED_HEADERS:
            if rh not in header:
                errors.append(str(_(f"En-tête manquant: '{rh}'")))

        if errors:
            return False, errors

        for i, row in enumerate(data):
            row_num = i + 2
            row_dict = dict(zip(header, row))

            if not all(row_dict.get(h) for h in self.REQUIRED_HEADERS):
                errors.append(str(_(f"Ligne {row_num}: Données manquantes dans les colonnes requises.")))

        return not bool(errors), errors

    def process_import(self, file_path):
        is_valid, errors = self.validate_csv(file_path)
        if not is_valid:
            self.results['success'] = False
            self.results['message'] = str(_("Validation du fichier CSV échouée."))
            self.results['errors'] = errors
            return self.results

        header, data = self._read_csv_data(file_path)
        created_count = 0

        with transaction.atomic():
            for i, row in enumerate(data):
                row_num = i + 2
                row_dict = dict(zip(header, row))

                try:
                    classe, created = Classe.objects.get_or_create(
                        nom=row_dict['nom_classe'],
                        etablissement=self.etablissement,
                        defaults={
                            'niveau': row_dict.get('niveau', ''),
                            'annee_scolaire': row_dict.get('annee_scolaire', ''),
                        }
                    )
                    if created:
                        created_count += 1
                    else:
                        self.results['errors'].append(str(_(f"Ligne {row_num}: Classe '{row_dict['nom_classe']}' existe déjà. Ignoré.")))

                except Exception as e:
                    self._handle_exception(e, row_num=row_num, message_prefix="Erreur lors de la création de la classe")

        self.results['stats']['classes_creees'] = created_count
        self.import_session.nb_comptes_crees = created_count # Re-using for classes count
        self.import_session.statut = 'completed' if self.results['success'] else 'error'
        self.import_session.resultats = self.results
        self.import_session.save()
        return self.results
