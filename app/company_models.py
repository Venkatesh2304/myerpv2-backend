# Create a Group and Company django model
from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from requests.cookies import RequestsCookieJar
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    id = None
    username = models.CharField(max_length=150, unique=True, primary_key=True)

class Company(models.Model):
    name = models.CharField(max_length=100, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="companies")
    gst_types = models.JSONField(default=list,null=False,blank=False)

class UserSession(models.Model):
    user = models.CharField(max_length=50)
    key = models.CharField(max_length=50)
    pk = models.CompositePrimaryKey("user", "key")
    username = models.CharField(max_length=20)
    password = models.CharField(max_length=50)
    cookies = models.JSONField(
        default=list, null=True, blank=True
    )
    config = models.JSONField(default=dict,null=True, blank=True)

    def update_cookies(self, cookies: RequestsCookieJar):
        cookies_list = []
        for cookie in cookies:
            cookies_list.append(
                {
                    "name": cookie.name,
                    "value": cookie.value,
                    "domain": cookie.domain,
                    "path": cookie.path,
                }
            )
        self.cookies = cookies_list
        self.save()
