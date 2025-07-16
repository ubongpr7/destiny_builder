from django.contrib import admin

from mainapps.user_profile.models import TeamMember

@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'position', 'priority', 'created_at', 'updated_at')
    list_filter = ('priority',)
    search_fields = ('name', 'position')
    ordering = ('priority', 'name')
    readonly_fields = ('created_at', 'updated_at')