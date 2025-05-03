from django.core.management.base import BaseCommand
from ...models import PartnershipType

class Command(BaseCommand):
    help = 'Populates the database with common partnership types'

    def handle(self, *args, **options):
        partnership_types = [
            {
                "name": "Corporate Partner",
                "description": "Businesses and corporations that provide financial support, in-kind donations, or employee volunteer time."
            },
            {
                "name": "Academic Partner",
                "description": "Educational institutions that collaborate on research, provide expertise, or offer educational resources."
            },
            {
                "name": "NGO Partner",
                "description": "Other non-profit organizations that collaborate on projects, share resources, or work together on advocacy."
            },
            {
                "name": "Government Partner",
                "description": "Government agencies or departments that provide funding, policy support, or regulatory assistance."
            },
            {
                "name": "Community Partner",
                "description": "Local community organizations, associations, or groups that help implement programs at the grassroots level."
            },
            {
                "name": "Technical Partner",
                "description": "Organizations that provide specialized technical expertise or services to support programs."
            },
            {
                "name": "Funding Partner",
                "description": "Organizations or individuals that primarily provide financial support for programs and operations."
            },
            {
                "name": "Implementation Partner",
                "description": "Organizations that help execute programs and projects on the ground."
            },
            {
                "name": "Strategic Partner",
                "description": "Organizations with aligned missions that collaborate on long-term strategic initiatives."
            },
            {
                "name": "Media Partner",
                "description": "Media organizations that help raise awareness and visibility for the organization's work."
            },
        ]

        created_count = 0
        existing_count = 0

        for partnership_data in partnership_types:
            partnership_type, created = PartnershipType.objects.get_or_create(
                name=partnership_data["name"],
                defaults={"description": partnership_data["description"]}
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} partnership types. {existing_count} already existed.'
            )
        )
