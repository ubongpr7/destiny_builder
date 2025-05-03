from django.contrib import admin
from .models import *

admin.site.register(User)
admin.site.register(Membership)
admin.site.register(PartnershipLevel)
admin.site.register(PartnershipType)
admin.site.register(Expertise)
admin.site.register(VerificationCode)
