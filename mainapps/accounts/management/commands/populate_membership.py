from django.core.management.base import BaseCommand
from django.utils.text import slugify
from ...models import Membership  # Adjust the import path based on your app structure

class Command(BaseCommand):
    help = 'Populates the database with default membership types'

    def handle(self, *args, **options):
        membership_types = [
            {
                "name": "Standard Member",
                "description": "Basic membership with standard privileges"
            },
            {
                "name": "Executive",
                "description": "Membership for executive-level professionals"
            },
            {
                "name": "CEO",
                "description": "Membership for Chief Executive Officers"
            },
            {
                "name": "Country Director",
                "description": "Membership for Country Directors and regional leaders"
            },
            {
                "name": "Partnership Body",
                "description": "Membership for organizational partnerships"
            },
            {
                "name": "Sub-Head",
                "description": "Membership for departmental and divisional leaders"
            }
        ]

        created_count = 0
        existing_count = 0

        for membership_data in membership_types:
            # Create slug from name
            slug = slugify(membership_data["name"])
            
            # Check if membership already exists
            membership, created = Membership.objects.get_or_create(
                name=membership_data["name"],
                defaults={
                    "slug": slug,
                    "description": membership_data["description"],
                    "is_active": True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'Created membership: {membership.name}'))
            else:
                existing_count += 1
                self.stdout.write(self.style.WARNING(f'Membership already exists: {membership.name}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'Finished populating memberships. Created: {created_count}, Already existed: {existing_count}'
        ))