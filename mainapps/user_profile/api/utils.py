# users/utils.py
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.template.loader import render_to_string
from weasyprint import HTML
from io import BytesIO
from django.core.mail import EmailMessage
from mainapps.accounts.models import ReferenceCounter

class ReferenceGenerator:
    ROLE_HIERARCHY = [
        ('is_DB_executive', 'DBEX'),
        ('is_executive', 'EXEC'),
        ('is_ceo', 'CEO'),
        ('is_DB_admin', 'ADMI'),
        ('is_project_manager', 'PMGR'),
        ('is_DB_staff', 'STAF'),
        ('is_donor', 'DONR'),
        ('is_partner', 'PRTN'),
        ('is_volunteer', 'VOLU'),
        ('is_standard_member', 'MEMB'),
    ]

    @classmethod
    def get_role_code(cls, profile):
        for field, code in cls.ROLE_HIERARCHY:
            if getattr(profile, field, False):
                return code
        return 'USER'

    @staticmethod
    def get_location_codes(address):
        country_code = address.country.code2 if address.country else 'XX'
        region_code = (address.region.code[:3] if address.region else 'XX').upper()
        return country_code, region_code

    @classmethod
    @transaction.atomic
    def generate_reference(cls, profile):

        if profile.reference:
            return profile.reference
            
        if not profile.address:
            raise ValueError("User has no address information")
            
        role_code = cls.get_role_code(profile)
        country_code, region_code = cls.get_location_codes(profile.address)
        
        counter, created = ReferenceCounter.objects.select_for_update().get_or_create(
            role_code=role_code,
            country_code=country_code,
            region_code=region_code,
            defaults={'last_number': 0}
        )
        
        counter.last_number += 1
        counter.save()
        
        return f"DBEF-{role_code}-{country_code}-{region_code}-{counter.last_number:09d}"

def generate_certificate_pdf(profile):
    verification_url = f"https://www.destinybuilders.africa/verify/{profile.reference}"
    
    context = {
        'profile': profile,
        'reference': profile.reference,
        'verification_date': profile.kyc_verification_date or timezone.now(),
        'current_date': timezone.now(),
         'verification_url': verification_url,
        'verification_qr_url': reverse('verification-qr', args=[profile.reference]),
        'role': get_highest_role_display(profile),
    }
    
    html = render_to_string('users/certificate.html', context)
    pdf_file = HTML(string=html).write_pdf()
    return pdf_file

def send_certificate_email(profile, pdf_content):
    email = EmailMessage(
        subject='Your KYC Verification Certificate',
        body=f'Dear {profile.user.get_full_name()},\n\nAttached is your verification certificate.',
        from_email='noreply@example.com',
        to=[profile.user.email]
    )
    email.attach(f'certificate_{profile.reference}.pdf', pdf_content, 'application/pdf')
    email.send()

def get_highest_role_display(profile):
    for field, _ in ReferenceGenerator.ROLE_HIERARCHY:
        if getattr(profile, field, False):
            return field.replace('is_', '').replace('_', ' ').title()
    return "Verified Member"