from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from app import models
from app.company_models import UserSession

@admin.register(models.User)
class UserAdmin(DjangoUserAdmin):
    pass

@admin.register(models.Company)
class CompanyAdmin(admin.ModelAdmin):
    pass


