from django.contrib import admin
from .models import Task, TaskComment, TaskAttachment, TaskTimeLog, TaskStatus, TaskPriority, TaskType


admin.site.register(Task)
admin.site.register(TaskComment)
admin.site.register(TaskAttachment)
admin.site.register(TaskTimeLog)
admin.site.register(TaskStatus)
admin.site.register(TaskPriority)
admin.site.register(TaskType)

# Register your models here.
