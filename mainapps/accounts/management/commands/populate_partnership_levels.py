from django.core.management.base import BaseCommand
from ...models import PartnershipLevel

class Command(BaseCommand):
    help = 'Populates the database with common partnership levels'

    def handle(self, *args, **options):
        partnership_levels = [
            {
                "name": "Platinum",
                "description": "Our highest level of partnership, offering maximum visibility and impact.",
                "benefits": "• Logo placement on homepage and all major publications\n• Featured in annual report\n• Speaking opportunities at major events\n• Quarterly strategy meetings with leadership\n• Priority access to all programs and events\n• Custom impact reports"
            },
            {
                "name": "Gold",
                "description": "A premium partnership level with significant visibility and engagement opportunities.",
                "benefits": "• Logo placement on website and select publications\n• Mentioned in annual report\n• Invitation to speak at select events\n• Bi-annual meetings with leadership\n• Early access to programs and events\n• Semi-annual impact reports"
            },
            {
                "name": "Silver",
                "description": "A mid-tier partnership with good visibility and regular engagement.",
                "benefits": "• Logo placement on website\n• Listed in annual report\n• Invitation to all major events\n• Annual meeting with leadership\n• Regular program updates\n• Annual impact report"
            },
            {
                "name": "Bronze",
                "description": "An entry-level partnership with basic visibility and engagement.",
                "benefits": "• Name listed on website\n• Listed in annual report\n• Invitation to select events\n• Regular program updates\n• Annual impact summary"
            },
            {
                "name": "Community",
                "description": "A grassroots level partnership focused on local impact.",
                "benefits": "• Name listed on website\n• Invitation to community events\n• Quarterly newsletters\n• Participation in local initiatives"
            },
        ]

        created_count = 0
        existing_count = 0

        for level_data in partnership_levels:
            level, created = PartnershipLevel.objects.get_or_create(
                name=level_data["name"],
                defaults={
                    "description": level_data["description"],
                    "benefits": level_data["benefits"]
                }
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} partnership levels. {existing_count} already existed.'
            )
        )
