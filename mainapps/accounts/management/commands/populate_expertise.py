from django.core.management.base import BaseCommand
from ...models import Expertise

class Command(BaseCommand):
    help = 'Populates the database with common areas of expertise'

    def handle(self, *args, **options):
        expertise_areas = [
            "Leadership",
            "Strategic Planning",
            "Project Management",
            "Financial Management",
            "Marketing",
            "Sales",
            "Human Resources",
            "Operations Management",
            "Supply Chain Management",
            "Information Technology",
            "Software Development",
            "Data Analysis",
            "Research",
            "Product Development",
            "Customer Service",
            "Public Relations",
            "Legal Affairs",
            "Regulatory Compliance",
            "Risk Management",
            "Quality Assurance",
            "Training & Development",
            "Community Outreach",
            "Fundraising",
            "Grant Writing",
            "Volunteer Management",
            "Event Planning",
            "Digital Marketing",
            "Social Media Management",
            "Content Creation",
            "Graphic Design",
            "Web Development",
            "Mobile App Development",
            "Entrepreneurship",
            "Innovation",
            "Sustainability",
            "Environmental Management",
            "Agriculture & Farming",
            "Healthcare Administration",
            "Education & Teaching",
            "Counseling & Mentoring",
        ]

        created_count = 0
        existing_count = 0

        for expertise_name in expertise_areas:
            expertise, created = Expertise.objects.get_or_create(name=expertise_name)
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} expertise areas. {existing_count} already existed.'
            )
        )
