from django.urls import path

from xamu.schools.views import AcceptInvitationView
from xamu.schools.views import InvitationStatusView

app_name = "schools"

urlpatterns = [
    path("invitation/<str:tenant_code>/<uuid:token>/", AcceptInvitationView.as_view(), name="accept_invitation"),
    path("invitation-status/<int:etablissement_id>/", InvitationStatusView.as_view(), name="invitation_status"),
]
