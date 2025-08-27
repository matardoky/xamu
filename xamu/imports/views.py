import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST # Import require_POST

from xamu.schools.utils import tenant_required
from .models import ImportSession, ComptesGeneres
from .forms import ImportSessionForm
from .services import PersonnelImportService, ClassesImportService, ElevesImportService # Import the services directly from the package

logger = logging.getLogger(__name__)


@method_decorator([login_required, tenant_required], name='dispatch')
class ImportDashboardView(TemplateView):
    template_name = 'imports/dashboard.html' # Simplified template name

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_chef_etablissement:
            raise PermissionDenied(_("Seul un chef d'établissement peut accéder aux imports"))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        etablissement = self.request.tenant
        sessions = ImportSession.objects.filter(etablissement=etablissement)

        context.update({
            'etablissement': etablissement,
            'sessions': sessions.order_by('-created_at'),
        })

        # Check if the created_by user's name is empty
        if not self.request.user.name:
            messages.warning(self.request, _(
                "Votre nom n'est pas renseigné dans votre profil. "
                "Veuillez mettre à jour votre profil pour afficher votre nom correctement."
            ))
        return context


@login_required
@tenant_required
def create_import_session(request, tenant_code):
    if not request.user.is_chef_etablissement:
        raise PermissionDenied(_("Seul un chef d'établissement peut créer des imports"))

    if request.method == 'POST':
        form = ImportSessionForm(request.POST, request.FILES)
        if form.is_valid():
            session = form.save(commit=False)
            session.etablissement = request.tenant
            session.created_by = request.user
            session.save() # Save the session first to ensure it exists in DB

            # Determine the service based on import type
            service = None
            if session.type_import == 'personnel':
                service = PersonnelImportService(session)
            elif session.type_import == 'classes':
                service = ClassesImportService(session)
            elif session.type_import == 'eleves':
                service = ElevesImportService(session)
            else:
                messages.error(request, _("Type d'import non supporté."))
                session.statut = 'error'
                session.resultats = {'error': str(_("Type d'import non supporté."))} # Ensure string conversion
                session.save()
                return redirect('imports:dashboard', tenant_code=tenant_code)

            if service:
                try:
                    # Process the import
                    results = service.process_import(session.fichier_csv.path)
                    if results['success']:
                        messages.success(request, _("Import terminé avec succès."))
                    else:
                        messages.error(request, _("L'import a rencontré des erreurs: ") + results.get('message', ''))
                        for error in results.get('errors', []):
                            messages.error(request, error)
                except Exception as e:
                    logger.error(f"Error during import processing: {e}", exc_info=True)
                    messages.error(request, _("Une erreur inattendue est survenue lors de l'import: ") + str(e))
                    session.statut = 'error'
                    session.resultats = {'error': str(e)}
                    session.save() # Save the session with error status

            return redirect('imports:detail', tenant_code=tenant_code, session_id=session.id)
    else:
        form = ImportSessionForm()

    context = {
        'form': form,
    }
    return render(request, 'imports/create_session.html', context)


@method_decorator([login_required, tenant_required], name='dispatch')
class ImportSessionDetailView(TemplateView):
    template_name = 'imports/session_detail.html' # Simplified template name

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session_id = self.kwargs['session_id']
        session = get_object_or_404(
            ImportSession,
            id=session_id,
            etablissement=self.request.tenant,
            created_by=self.request.user
        )
        context['session'] = session
        context['comptes_generes'] = ComptesGeneres.objects.filter(import_session=session)
        return context


@login_required
@tenant_required
@require_POST # Ensure only POST requests can delete
def delete_import_session(request, tenant_code, session_id):
    if not request.user.is_chef_etablissement:
        raise PermissionDenied(_("Seul un chef d'établissement peut supprimer des sessions d'import."))

    session = get_object_or_404(
        ImportSession,
        id=session_id,
        etablissement=request.tenant,
        created_by=request.user # Only allow the creator to delete
    )

    session.delete()
    messages.success(request, _("La session d'import a été supprimée avec succès."))
    return redirect('imports:dashboard', tenant_code=tenant_code)


@login_required
@tenant_required
def comptes_management(request, tenant_code):
    if not request.user.is_chef_etablissement:
        raise PermissionDenied(_("Accès restreint aux chefs d'établissement"))

    comptes = ComptesGeneres.objects.filter(import_session__etablissement=request.tenant).order_by('-import_session__created_at')

    context = {
        'comptes': comptes,
    }
    return render(request, 'imports/comptes_management.html', context)
