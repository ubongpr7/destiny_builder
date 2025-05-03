from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Populates all reference data tables in the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Starting to populate all reference data...'))
        
        # Call each populate command in sequence
        call_command('populate_industries')
        call_command('populate_expertise')
        call_command('populate_partnership_types')
        call_command('populate_partnership_levels')
        call_command('populate_skills')
        
        self.stdout.write(self.style.SUCCESS('Successfully populated all reference data!'))
