
from django.contrib import admin
from .models import UserProfile, Industry, Expertise, PartnershipType, PartnershipLevel, Disability,User

class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('get_user_email', 'get_user_name', 'is_kyc_verified', 'kyc_submission_date', 'kyc_verification_date')
    list_filter = ('is_kyc_verified', 'is_executive', 'is_ceo', 'is_project_manager', 'is_donor', 
                  'is_volunteer', 'is_partner', 'is_DB_staff', 'is_standard_member', 
                  'is_DB_executive', 'is_DB_admin', 'is_country_director', 'is_regional_head')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'organization', 'position')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_user_email(self, obj):
        return obj.user.email if obj.user else "No User"
    get_user_email.short_description = 'Email'
    
    def get_user_name(self, obj):
        if obj.user:
            return f"{obj.user.first_name} {obj.user.last_name}"
        return "No User"
    get_user_name.short_description = 'Name'

admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Industry)
admin.site.register(Expertise)
admin.site.register(PartnershipType)
admin.site.register(PartnershipLevel)
admin.site.register(Disability)
admin.site.register(User)
