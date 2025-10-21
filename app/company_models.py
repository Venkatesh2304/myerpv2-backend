#Create a Group and Company django model
from django.db import models

class Group(models.Model):
    name = models.CharField(max_length=20,primary_key=True)

class Company(models.Model):
    name = models.CharField(max_length=100,primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)