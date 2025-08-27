import csv
import io
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _
import logging # Import logging

from xamu.schools.models import Etablissement
from xamu.academic.models import Classe # Assuming this model exists
from xamu.users.models import User # Assuming this model exists
from ..models import ComptesGeneres
from .base_service import BaseImportService

User = get_user_model()
logger = logging.getLogger(__name__) # Initialize logger


class PersonnelImportService(BaseImportService):
    REQUIRED_HEADERS = ['nom', 'prenom', 'role', 'email']
    ALLOWED_ROLES = ['professeur', 'cpe', 'chef_etablissement'] # Add other roles as needed

    def validate_csv(self, file_path):
        header, data = self._read_csv_data(file_path)
        errors = []

        if header is None:
            errors.append(self.results['message']) # Add CSV read error
            return False, errors

        # Check required headers
        for rh in self.REQUIRED_HEADERS:
            if rh not in header:
                errors.append(str(_(f"En-tête manquant: '{rh}'")))

        if errors:
            return False, errors

        # Validate content
        for i, row in enumerate(data):
            row_num = i + 2 # +1 for 0-index, +1 for header row
            row_dict = dict(zip(header, row))

            if not all(row_dict.get(h) for h in self.REQUIRED_HEADERS):
                errors.append(str(_(f"Ligne {row_num}: Données manquantes dans les colonnes requises.")))

            if row_dict.get('email') and not '@' in row_dict['email']:
                errors.append(str(_(f"Ligne {row_num}: Format d'email invalide pour '{row_dict['email']}'.")))

            if row_dict.get('role') and row_dict['role'] not in self.ALLOWED_ROLES:
                errors.append(str(_(f"Ligne {row_num}: Rôle non autorisé '{row_dict['role']}'. Rôles autorisés: {', '.join(self.ALLOWED_ROLES)}.")))

        return not bool(errors), errors

    def process_import(self, file_path):
        logger.info(f"Starting PersonnelImportService.process_import for session {self.import_session.id}")
        is_valid, errors = self.validate_csv(file_path)
        if not is_valid:
            self.results['success'] = False
            self.results['message'] = str(_("Validation du fichier CSV échouée."))
            self.results['errors'] = errors
            logger.warning(f"CSV validation failed for session {self.import_session.id}: {errors}")
            return self.results

        header, data = self._read_csv_data(file_path)
        created_count = 0

        with transaction.atomic():
            for i, row in enumerate(data):
                row_num = i + 2
                row_dict = dict(zip(header, row))
                logger.info(f"Processing row {row_num}: {row_dict}")

                try:
                    email = row_dict['email']
                    logger.info(f"Attempting to get_or_create user with email: {email}") # Added logging
                    password = get_random_string(12) # Generate random password

                    user, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            'name': f"{row_dict.get('prenom', '')} {row_dict.get('nom', '')}".strip(),
                            'role': row_dict.get('role', 'professeur'), # Default role
                            'etablissement': self.etablissement,
                            'is_active': True,
                        }
                    )
                    logger.info(f"User {email} created: {created}")
                    if created:
                        user.set_password(password)
                        user.save()
                        ComptesGeneres.objects.create(
                            import_session=self.import_session,
                            user=user,
                            mot_de_passe_temporaire=password,
                        )
                        created_count += 1
                        logger.info(f"ComptesGeneres created for {email}")
                    else:
                        self.results['errors'].append(str(_(f"Ligne {row_num}: Utilisateur avec l\'email '{email}' existe déjà. Ignoré.")))
                        logger.info(f"User {email} already exists. Ignored.")

                except Exception as e:
                    self._handle_exception(e, row_num=row_num, message_prefix=r"Erreur lors de la création de l'utilisateur")
                    logger.error(f"Exception processing row {row_num}: {e}", exc_info=True)
                    # Do not re-raise here, _handle_exception already updates results and session status

        self.results['stats']['comptes_crees'] = created_count
        self.import_session.nb_comptes_crees = created_count
        self.import_session.statut = 'completed' if self.results['success'] else 'error'
        self.import_session.resultats = self.results
        self.import_session.save()
        logger.info(f"Finished PersonnelImportService.process_import for session {self.import_session.id}. Created: {created_count}")
        return self.results