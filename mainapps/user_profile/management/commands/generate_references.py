# users/management/commands/backfill_references.py
from django.core.management.base import BaseCommand
from django.db import transaction
from mainapps.accounts.models import UserProfile
from mainapps.user_profile.api.utils import (
    ReferenceGenerator, 
    generate_certificate_pdf,
    send_certificate_email
)

class Command(BaseCommand):
    help = 'Generate references and send certificates for existing approved profiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--resend',
            action='store_true',
            help='Resend certificates even if reference exists'
        )

    def handle(self, *args, **options):
        base_query = UserProfile.objects.filter(is_kyc_verified=True)
        
        if not options['resend']:
            base_query = base_query.filter(reference__isnull=True)

        profiles = base_query.select_related('address', 'user').prefetch_related('address__country', 'address__region')

        total = profiles.count()
        success = 0
        errors = []

        self.stdout.write(f"Processing {total} profiles...")

        for index, profile in enumerate(profiles, 1):
            try:
                with transaction.atomic():
                    # Generate reference if missing or resend requested
                    if not profile.reference or options['resend']:
                        profile.reference = ReferenceGenerator.generate_reference(profile)
                        profile.save()

                    # Generate and send certificate
                    pdf_content = generate_certificate_pdf(profile)
                    send_certificate_email(profile, pdf_content)
                    
                    success += 1
                    self.stdout.write(f"Processed {index}/{total}: {profile.user.email}")

            except Exception as e:
                errors.append(f"Profile {profile.id}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"Error processing {profile.id}: {str(e)}"))

        summary = [
            f"\nSummary:",
            f"Total profiles: {total}",
            f"Successfully processed: {success}",
            f"Errors: {len(errors)}"
        ]

        self.stdout.write(self.style.SUCCESS('\n'.join(summary)))
        
        if errors:
            self.stdout.write(self.style.ERROR("\nError details:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(error))