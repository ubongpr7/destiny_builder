from django.contrib import admin
from .models import Task, TaskComment, TaskAttachment, TaskTimeLog, 


admin.site.register(Task)
admin.site.register(TaskComment)
admin.site.register(TaskAttachment)
admin.site.register(TaskTimeLog)

# Register your models here.
