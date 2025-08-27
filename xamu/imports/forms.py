from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError

from .models import ImportSession


class ImportSessionForm(forms.ModelForm):
    """
    Formulaire pour créer une session d'import.
    """
    
    class Meta:
        model = ImportSession
        fields = ['type_import', 'nom_session', 'fichier_csv']
        widgets = {
            'type_import': forms.Select(
                attrs={
                    'class': 'form-select',
                    'id': 'id_type_import'
                }
            ),
            'nom_session': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': _('Ex: Rentrée 2024, Personnel Septembre...'),
                    'maxlength': 100
                }
            ),
            'fichier_csv': forms.FileInput(
                attrs={
                    'class': 'form-control',
                    'accept': '.csv',
                    'id': 'id_fichier_csv'
                }
            )
        }
        help_texts = {
            'type_import': _('Choisissez le type de données à importer'),
            'nom_session': _('Nom descriptif pour identifier cette session d\'import'),
            'fichier_csv': _('Fichier CSV avec séparateur point-virgule (;)')
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Utiliser tous les types définis dans le modèle
        self.fields['type_import'].choices = [('', _('-- Choisir un type --'))] + ImportSession.TYPE_IMPORT_CHOICES
        
        # Rendre les champs obligatoires plus explicites
        self.fields['type_import'].required = True
        self.fields['nom_session'].required = True
        self.fields['fichier_csv'].required = True
        
        # Ajouter des classes CSS
        for field_name, field in self.fields.items():
            if field.required:
                field.widget.attrs['required'] = 'required'
    
    def clean_fichier_csv(self):
        """Validation du fichier CSV."""
        fichier = self.cleaned_data.get('fichier_csv')
        
        if not fichier:
            return fichier
        
        # Vérifier l\'extension
        if not fichier.name.lower().endswith('.csv'):
            raise ValidationError(
                _('Le fichier doit avoir l\'extension .csv')
            )
        
        # Vérifier la taille (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if fichier.size > max_size:
            raise ValidationError(
                _('Le fichier ne peut pas dépasser 10 MB (taille actuelle: {:.1f} MB)').format(
                    fichier.size / (1024 * 1024)
                )
            )
        
        # Vérifier que le fichier n\'est pas vide
        if fichier.size == 0:
            raise ValidationError(_('Le fichier CSV ne peut pas être vide'))
        
        return fichier
    
    def clean_nom_session(self):
        """Validation du nom de session."""
        nom = self.cleaned_data.get('nom_session', '').strip()
        
        if not nom:
            raise ValidationError(_('Le nom de session est obligatoire'))
        
        if len(nom) < 3:
            raise ValidationError(
                _('Le nom de session doit faire au moins 3 caractères')
            )
        
        return nom
    
    def clean(self):
        """Validation globale du formulaire."""
        cleaned_data = super().clean()
        type_import = cleaned_data.get('type_import')
        
        # Vérifier que le type d\'import est supporté
        supported_types = [choice[0] for choice in ImportSession.TYPE_IMPORT_CHOICES]
        if type_import and type_import not in supported_types:
            raise ValidationError({
                'type_import': _('Type d\'import non supporté')
            })
        
        return cleaned_data


class ImportValidationForm(forms.Form):
    """
    Formulaire pour confirmer l\'exécution d\'un import après validation.
    """
    
    confirmer_import = forms.BooleanField(
        label=_("Je confirme vouloir exécuter cet import"),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    commentaire = forms.CharField(
        label=_("Commentaire (optionnel)"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Notes ou observations sur cet import...')
        })
    )


class ImportCancelForm(forms.Form):
    """
    Formulaire pour annuler une session d\'import.
    """
    
    raison = forms.CharField(
        label=_("Raison de l\'annulation"),
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': _('Expliquez pourquoi vous annulez cet import...')
        })
    )
    
    confirmer_annulation = forms.BooleanField(
        label=_("Je confirme vouloir annuler cette session d\'import"),
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )