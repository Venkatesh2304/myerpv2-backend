from django.urls import path
import app.api as api
from .auth_api import login as auth_login, logout as auth_logout, me as auth_me

urlpatterns = [
    path("einvoice/damage/stats", api.einvoice_damage_stats, name="einvoice-damage-stats"),
    path("einvoice/damage/file", api.einvoice_damage_file, name="einvoice-damage-file"),
    path("einvoice/damage/excel", api.einvoice_damage_excel, name="einvoice-damage-excel"),
    path("einvoice/damage/pdf", api.einvoice_damage_pdf, name="einvoice-damage-pdf"),
    path("gst/generate", api.generate_gst_return, name="generate-gst-return"),
    path("gst/summary", api.gst_summary, name="gst-summary"),
    path("gst/json", api.gst_json, name="gst-json"),
    path("custom/captcha", api.get_captcha, name="captcha"),
    path("custom/login", api.captcha_login, name="login"),  # captcha-login (kept as-is)
    # Auth (session) endpoints
    path("login", auth_login, name="auth-login"),
    path("logout", auth_logout, name="auth-logout"),
    path("me", auth_me, name="auth-me"),
]
