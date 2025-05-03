from django.core.management.base import BaseCommand
from ...models import Industry

class Command(BaseCommand):
    help = 'Populates the database with common industries'

    def handle(self, *args, **options):
        industries = [
            "Agriculture",
            "Banking & Finance",
            "Construction",
            "Education",
            "Energy",
            "Entertainment",
            "Food & Beverage",
            "Government",
            "Healthcare",
            "Hospitality & Tourism",
            "Information Technology",
            "Legal Services",
            "Manufacturing",
            "Media & Communications",
            "Mining",
            "Non-profit & NGO",
            "Oil & Gas",
            "Real Estate",
            "Retail",
            "Telecommunications",
            "Transportation & Logistics",
            "Utilities",
        ]

        created_count = 0
        existing_count = 0

        for industry_name in industries:
            industry, created = Industry.objects.get_or_create(name=industry_name)
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} industries. {existing_count} already existed.'
            )
        )
