from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django_otp.admin import OTPAdminSite
from rest_framework.routers import SimpleRouter

from apps.accounts import views as auth
from apps.clients.admin_api import AdminClientViewSet
from apps.clients.downloads import SignedDownloadView
from apps.clients.views import (
    ClientProjectViewSet,
    InvoiceViewSet,
    MessageViewSet,
    ProjectFileViewSet,
)
from apps.core.views import CsrfView, HealthView
from apps.leads.admin_api import AdminLeadViewSet
from apps.leads.views import ContactView, PlannerView

# Staff must pass TOTP (or a static backup token) to use the admin (rule 7).
admin.site.__class__ = OTPAdminSite

portal = SimpleRouter()
portal.register("projects", ClientProjectViewSet, basename="portal-project")
portal.register("messages", MessageViewSet, basename="portal-message")
portal.register("files", ProjectFileViewSet, basename="portal-file")
portal.register("invoices", InvoiceViewSet, basename="portal-invoice")

admin_api = SimpleRouter()
admin_api.register("leads", AdminLeadViewSet, basename="admin-lead")
admin_api.register("clients", AdminClientViewSet, basename="admin-client")

auth_urls = [
    path("csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("login/", auth.LoginView.as_view(), name="auth-login"),
    path("logout/", auth.LogoutView.as_view(), name="auth-logout"),
    path("logout-all/", auth.LogoutAllView.as_view(), name="auth-logout-all"),
    path("me/", auth.MeView.as_view(), name="auth-me"),
    path("password/change/", auth.PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/reset/", auth.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "password/reset/confirm/",
        auth.PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("invite/accept/", auth.InviteAcceptView.as_view(), name="auth-invite-accept"),
]

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("healthz/", HealthView.as_view(), name="healthz"),
    path("api/auth/", include(auth_urls)),
    path("api/portal/", include(portal.urls)),
    path("api/files/<str:token>/", SignedDownloadView.as_view(), name="signed-download"),
    path("api/admin/", include(admin_api.urls)),
    path("api/leads/contact/", ContactView.as_view(), name="leads-contact"),
    path("api/leads/planner/", PlannerView.as_view(), name="leads-planner"),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
