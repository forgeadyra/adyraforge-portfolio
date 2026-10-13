from django.conf import settings
from django.contrib import admin
from django.urls import path
from django_otp.admin import OTPAdminSite

from apps.accounts.views import MeView
from apps.core.views import CsrfView, HealthView

# Staff must pass TOTP (or a static backup token) to use the admin (rule 7).
admin.site.__class__ = OTPAdminSite

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    path("healthz/", HealthView.as_view(), name="healthz"),
    path("api/auth/csrf/", CsrfView.as_view(), name="auth-csrf"),
    path("api/auth/me/", MeView.as_view(), name="auth-me"),
]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
