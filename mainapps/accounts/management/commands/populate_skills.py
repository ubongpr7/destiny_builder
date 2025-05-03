from django.core.management.base import BaseCommand
from ...models import Skill

class Command(BaseCommand):
    help = 'Populates the database with common skills'

    def handle(self, *args, **options):
        skills = [
            {
                "name": "Public Speaking",
                "description": "Ability to effectively communicate ideas to an audience"
            },
            {
                "name": "Grant Writing",
                "description": "Experience in writing successful grant proposals"
            },
            {
                "name": "Community Organizing",
                "description": "Skills in mobilizing communities around shared goals"
            },
            {
                "name": "Financial Analysis",
                "description": "Ability to analyze financial data and make recommendations"
            },
            {
                "name": "Strategic Planning",
                "description": "Experience in developing long-term organizational strategies"
            },
            {
                "name": "Project Management",
                "description": "Skills in planning, executing, and closing projects"
            },
            {
                "name": "Fundraising",
                "description": "Experience in raising funds for organizations or causes"
            },
            {
                "name": "Social Media Management",
                "description": "Skills in managing organizational social media presence"
            },
            {
                "name": "Volunteer Coordination",
                "description": "Experience in recruiting, training, and managing volunteers"
            },
            {
                "name": "Event Planning",
                "description": "Skills in organizing and executing successful events"
            },
            {
                "name": "Curriculum Development",
                "description": "Experience in creating educational materials and programs"
            },
            {
                "name": "Mentoring",
                "description": "Skills in providing guidance and support to others"
            },
            {
                "name": "Advocacy",
                "description": "Experience in advocating for policy changes or social issues"
            },
            {
                "name": "Data Analysis",
                "description": "Skills in analyzing and interpreting data"
            },
            {
                "name": "Web Development",
                "description": "Experience in building and maintaining websites"
            },
            {
                "name": "Graphic Design",
                "description": "Skills in creating visual content and materials"
            },
            {
                "name": "Video Production",
                "description": "Experience in creating video content"
            },
            {
                "name": "Leadership",
                "description": "Skills in guiding and inspiring teams"
            },
            {
                "name": "Conflict Resolution",
                "description": "Experience in mediating and resolving conflicts"
            },
            {
                "name": "Cross-cultural Communication",
                "description": "Skills in communicating effectively across different cultures"
            },
        ]

        created_count = 0
        existing_count = 0

        for skill_data in skills:
            skill, created = Skill.objects.get_or_create(
                name=skill_data["name"],
                defaults={"description": skill_data["description"]}
            )
            if created:
                created_count += 1
            else:
                existing_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully added {created_count} skills. {existing_count} already existed.'
            )
        )
