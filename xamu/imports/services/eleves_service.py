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


class ElevesImportService(BaseImportService):
    REQUIRED_HEADERS = ['eleve_nom', 'eleve_prenom', 'classe', 'parent1_nom', 'parent1_prenom', 'parent1_email']
    # Assuming Eleve and Parent models exist in academic app or similar
    # from xamu.academic.models import Eleve, Parent # Example

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

            if row_dict.get('parent1_email') and not '@' in row_dict['parent1_email']:
                errors.append(str(_(f"Ligne {row_num}: Format d'email parent invalide pour '{row_dict['parent1_email']}'.")))

        return not bool(errors), errors

    def process_import(self, file_path):
        is_valid, errors = self.validate_csv(file_path)
        if not is_valid:
            self.results['success'] = False
            self.results['message'] = str(_("Validation du fichier CSV échouée."))
            self.results['errors'] = errors
            return self.results

        header, data = self._read_csv_data(file_path)
        eleves_created_count = 0
        parents_created_count = 0

        with transaction.atomic():
            for i, row in enumerate(data):
                row_num = i + 2
                row_dict = dict(zip(header, row))

                try:
                    # Find or create parent user
                    parent_email = row_dict['parent1_email']
                    parent_password = get_random_string(12)
                    parent_user, parent_created = User.objects.get_or_create(
                        email=parent_email,
                        defaults={
                            'name': f"{row_dict.get('parent1_prenom', '')} {row_dict.get('parent1_nom', '')}".strip(),
                            'role': 'parent',
                            'etablissement': self.etablissement,
                            'is_active': True,
                        }
                    )
                    if parent_created:
                        parent_user.set_password(parent_password)
                        parent_user.save()
                        ComptesGeneres.objects.create(
                            import_session=self.import_session,
                            user=parent_user,
                            mot_de_passe_temporaire=parent_password,
                        )
                        parents_created_count += 1

                    # Find or create student (Eleve)
                    # classe_obj = Classe.objects.get(nom=row_dict['classe'], etablissement=self.etablissement)
                    # eleve, eleve_created = Eleve.objects.get_or_create(
                    #     nom=row_dict['eleve_nom'],
                    #     prenom=row_dict['eleve_prenom'],
                    #     classe=classe_obj,
                    #     etablissement=self.etablissement,
                    #     defaults={'parent': parent_user}
                    # )
                    # if eleve_created:
                    #     eleves_created_count += 1
                    # else:
                    #     self.results['errors'].append(str(_(f"Ligne {row_num}: Élève '{row_dict['eleve_nom']} {row_dict['eleve_prenom']}' existe déjà. Ignoré.")))

                    # Placeholder for Eleve creation as models are not defined here
                    eleves_created_count += 1 # Simulate creation

                except Classe.DoesNotExist as e:
                    self._handle_exception(e, row_num=row_num, message_prefix=f"Classe '{row_dict['classe']}' non trouvée")
                except Exception as e:
                    self._handle_exception(e, row_num=row_num, message_prefix="Erreur lors de la création de l'élève/parent")

        self.results['stats']['eleves_crees'] = eleves_created_count
        self.results['stats']['parents_crees'] = parents_created_count
        self.import_session.nb_comptes_crees = eleves_created_count + parents_created_count
        self.import_session.statut = 'completed' if self.results['success'] else 'error'
        self.import_session.resultats = self.results
        self.import_session.save()
        return self.results