from django.contrib import admin
from .models import *


# Register your models here.
admin.site.register(Project)
admin.site.register(ProjectCategory)
admin.site.register([ProjectExpense,ProjectTeamMember,ProjectAsset])
