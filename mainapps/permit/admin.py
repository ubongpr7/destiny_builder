from django.contrib import admin

# Register your models here.
from .models import PermissionCategory,CustomUserPermission,ActivityLog

admin.site.register(PermissionCategory)
admin.site.register(CustomUserPermission)
admin.site.register(ActivityLog)