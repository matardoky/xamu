import csv
import io
from abc import ABC, abstractmethod
from django.db import transaction
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from django.utils.translation import gettext_lazy as _

from xamu.schools.models import Etablissement
from xamu.academic.models import Classe # Assuming this model exists
from xamu.users.models import User # Assuming this model exists
from ..models import ComptesGeneres

User = get_user_model()


class BaseImportService(ABC):
    def __init__(self, import_session):
        self.import_session = import_session
        self.etablissement = import_session.etablissement
        self.created_by = import_session.created_by
        self.results = {'success': True, 'message': '', 'stats': {}, 'errors': []}

    @abstractmethod
    def validate_csv(self, file_path):
        """
        Validates the CSV file structure and content.
        Returns (is_valid, errors_list).
        """
        pass

    @abstractmethod
    def process_import(self, file_path):
        """
        Processes the CSV data and creates/updates objects.
        Returns results dictionary.
        """
        pass

    def _read_csv_data(self, file_path):
        """Helper to read CSV content."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # Read a small chunk to detect delimiter
                sample = f.read(1024)
                dialect = csv.Sniffer().sniff(sample, delimiters=';,')
                f.seek(0) # Rewind after sniffing

                reader = csv.reader(f, dialect)
                header = [h.strip() for h in next(reader)]
                data = [row for row in reader if any(row)] # Filter out empty rows
            return header, data
        except Exception as e:
            self.results['success'] = False
            self.results['message'] = str(_("Erreur de lecture du fichier CSV: ")) + str(e)
            return None, None

    def _handle_exception(self, e, row_num=None, message_prefix=""):
        """Helper to handle exceptions during import processing."""
        self.results['success'] = False
        error_message = f"{message_prefix}: {str(e)}"
        if row_num:
            error_message = f"Ligne {row_num}: {error_message}"
        self.results['errors'].append(error_message)
        self.results['message'] = str(_("L'import a rencontré des erreurs inattendues."))
        self.import_session.statut = 'error'
        self.import_session.resultats = self.results
        self.import_session.save()