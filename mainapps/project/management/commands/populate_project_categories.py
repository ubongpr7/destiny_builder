from django.core.management.base import BaseCommand
from django.db import transaction
from ...models import ProjectCategory
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Populates the database with project categories'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of categories even if they already exist',
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        
        # Check if categories already exist
        if ProjectCategory.objects.exists() and not force:
            self.stdout.write(self.style.WARNING(
                'Project categories already exist. Use --force to recreate them.'
            ))
            return
        
        # If --force is used, delete existing categories
        if force:
            self.stdout.write('Deleting existing project categories...')
            ProjectCategory.objects.all().delete()
        
        self.stdout.write('Creating project categories...')
        
        try:
            with transaction.atomic():
                # Create main categories
                categories = self._create_categories()
                
                # Create subcategories
                self._create_subcategories(categories)
                
            self.stdout.write(self.style.SUCCESS(
                f'Successfully created {ProjectCategory.objects.count()} project categories'
            ))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating categories: {str(e)}'))
            logger.exception("Error in populate_project_categories command")
    
    def _create_categories(self):
        """Create main top-level categories"""
        categories = {}
        
        main_categories = [
            {
                'name': 'Infrastructure',
                'description': 'Projects focused on building or improving physical structures and facilities.'
            },
            {
                'name': 'Education',
                'description': 'Projects aimed at improving access to quality education and learning opportunities.'
            },
            {
                'name': 'Healthcare',
                'description': 'Projects focused on improving health services, facilities, and outcomes.'
            },
            {
                'name': 'Agriculture',
                'description': 'Projects related to farming, food production, and agricultural development.'
            },
            {
                'name': 'Environment',
                'description': 'Projects focused on environmental conservation, sustainability, and climate action.'
            },
            {
                'name': 'Technology',
                'description': 'Projects leveraging technology for development and innovation.'
            },
            {
                'name': 'Community Development',
                'description': 'Projects aimed at strengthening communities and improving quality of life.'
            },
            {
                'name': 'Economic Development',
                'description': 'Projects focused on economic growth, job creation, and poverty reduction.'
            },
            {
                'name': 'Water & Sanitation',
                'description': 'Projects improving access to clean water and sanitation facilities.'
            },
            {
                'name': 'Energy',
                'description': 'Projects related to energy access, renewable energy, and energy efficiency.'
            },
        ]
        
        for category_data in main_categories:
            category = ProjectCategory.objects.create(
                name=category_data['name'],
                description=category_data['description'],
                parent=None
            )
            categories[category_data['name']] = category
            self.stdout.write(f"Created category: {category.name}")
        
        return categories
    
    def _create_subcategories(self, categories):
        """Create subcategories for each main category"""
        
        # Infrastructure subcategories
        infrastructure_subcategories = [
            {
                'name': 'Roads & Bridges',
                'description': 'Construction and maintenance of roads, bridges, and related infrastructure.'
            },
            {
                'name': 'Buildings',
                'description': 'Construction of schools, hospitals, community centers, and other buildings.'
            },
            {
                'name': 'Water Infrastructure',
                'description': 'Dams, irrigation systems, water treatment facilities, and distribution networks.'
            },
            {
                'name': 'Housing',
                'description': 'Affordable housing projects and housing improvement initiatives.'
            },
            {
                'name': 'Public Spaces',
                'description': 'Parks, playgrounds, and other public recreational facilities.'
            },
        ]
        
        # Education subcategories
        education_subcategories = [
            {
                'name': 'Primary Education',
                'description': 'Projects focused on primary school education and early childhood development.'
            },
            {
                'name': 'Secondary Education',
                'description': 'Projects focused on secondary school education and adolescent development.'
            },
            {
                'name': 'Higher Education',
                'description': 'University, college, and vocational training initiatives.'
            },
            {
                'name': 'Teacher Training',
                'description': 'Programs to improve teacher skills and teaching methodologies.'
            },
            {
                'name': 'Educational Materials',
                'description': 'Development and distribution of textbooks, learning aids, and educational resources.'
            },
            {
                'name': 'Digital Learning',
                'description': 'E-learning platforms, digital literacy, and technology in education.'
            },
        ]
        
        # Healthcare subcategories
        healthcare_subcategories = [
            {
                'name': 'Primary Healthcare',
                'description': 'Basic health services, clinics, and preventive care.'
            },
            {
                'name': 'Maternal & Child Health',
                'description': 'Programs focused on the health of mothers, infants, and children.'
            },
            {
                'name': 'Disease Prevention',
                'description': 'Vaccination campaigns, disease awareness, and prevention programs.'
            },
            {
                'name': 'Medical Facilities',
                'description': 'Hospitals, clinics, and specialized medical centers.'
            },
            {
                'name': 'Mental Health',
                'description': 'Mental health services, counseling, and awareness programs.'
            },
            {
                'name': 'Nutrition',
                'description': 'Nutrition programs, food supplementation, and dietary improvement initiatives.'
            },
        ]
        
        # Agriculture subcategories
        agriculture_subcategories = [
            {
                'name': 'Crop Production',
                'description': 'Improving farming techniques, crop yields, and agricultural productivity.'
            },
            {
                'name': 'Livestock',
                'description': 'Animal husbandry, veterinary services, and livestock development.'
            },
            {
                'name': 'Irrigation',
                'description': 'Irrigation systems, water management for agriculture.'
            },
            {
                'name': 'Sustainable Farming',
                'description': 'Organic farming, agroforestry, and sustainable agricultural practices.'
            },
            {
                'name': 'Agricultural Training',
                'description': 'Farmer education, agricultural extension services, and skills development.'
            },
            {
                'name': 'Food Security',
                'description': 'Programs ensuring consistent access to sufficient, safe, and nutritious food.'
            },
        ]
        
        # Environment subcategories
        environment_subcategories = [
            {
                'name': 'Conservation',
                'description': 'Protection of natural habitats, biodiversity, and ecosystems.'
            },
            {
                'name': 'Reforestation',
                'description': 'Tree planting, forest restoration, and afforestation projects.'
            },
            {
                'name': 'Waste Management',
                'description': 'Recycling, waste reduction, and sustainable waste disposal.'
            },
            {
                'name': 'Climate Change Adaptation',
                'description': 'Helping communities adapt to the impacts of climate change.'
            },
            {
                'name': 'Pollution Control',
                'description': 'Reducing air, water, and soil pollution.'
            },
            {
                'name': 'Environmental Education',
                'description': 'Raising awareness about environmental issues and sustainable practices.'
            },
        ]
        
        # Technology subcategories
        technology_subcategories = [
            {
                'name': 'Digital Inclusion',
                'description': 'Expanding access to digital technologies and the internet.'
            },
            {
                'name': 'Tech Education',
                'description': 'Teaching coding, digital skills, and technology literacy.'
            },
            {
                'name': 'Innovation Hubs',
                'description': 'Creating spaces for technological innovation and entrepreneurship.'
            },
            {
                'name': 'Mobile Solutions',
                'description': 'Mobile applications and services for development challenges.'
            },
            {
                'name': 'Data Systems',
                'description': 'Information management systems, data collection, and analysis.'
            },
        ]
        
        # Community Development subcategories
        community_development_subcategories = [
            {
                'name': 'Youth Programs',
                'description': 'Initiatives focused on youth empowerment, skills, and leadership.'
            },
            {
                'name': 'Women\'s Empowerment',
                'description': 'Programs supporting women\'s rights, leadership, and economic participation.'
            },
            {
                'name': 'Cultural Preservation',
                'description': 'Preserving cultural heritage, traditions, and indigenous knowledge.'
            },
            {
                'name': 'Community Centers',
                'description': 'Facilities for community gatherings, activities, and services.'
            },
            {
                'name': 'Social Inclusion',
                'description': 'Programs supporting marginalized groups and promoting inclusivity.'
            },
            {
                'name': 'Capacity Building',
                'description': 'Strengthening community organizations and local leadership.'
            },
        ]
        
        # Economic Development subcategories
        economic_development_subcategories = [
            {
                'name': 'Microfinance',
                'description': 'Small loans and financial services for entrepreneurs and small businesses.'
            },
            {
                'name': 'Vocational Training',
                'description': 'Skills training for employment and livelihood improvement.'
            },
            {
                'name': 'Small Business Support',
                'description': 'Assistance for small and medium enterprises and business development.'
            },
            {
                'name': 'Market Access',
                'description': 'Helping producers access markets and improve value chains.'
            },
            {
                'name': 'Cooperative Development',
                'description': 'Supporting the formation and growth of cooperatives and producer groups.'
            },
        ]
        
        # Water & Sanitation subcategories
        water_sanitation_subcategories = [
            {
                'name': 'Clean Water Access',
                'description': 'Wells, boreholes, and water supply systems for clean drinking water.'
            },
            {
                'name': 'Sanitation Facilities',
                'description': 'Toilets, latrines, and waste disposal systems.'
            },
            {
                'name': 'Hygiene Promotion',
                'description': 'Education and awareness about hygiene practices.'
            },
            {
                'name': 'Water Treatment',
                'description': 'Systems and technologies for purifying and treating water.'
            },
            {
                'name': 'Watershed Management',
                'description': 'Protection and management of water sources and watersheds.'
            },
        ]
        
        # Energy subcategories
        energy_subcategories = [
            {
                'name': 'Solar Energy',
                'description': 'Solar power systems, solar home systems, and solar applications.'
            },
            {
                'name': 'Wind Energy',
                'description': 'Wind turbines and wind power generation.'
            },
            {
                'name': 'Hydropower',
                'description': 'Small-scale hydroelectric power generation.'
            },
            {
                'name': 'Biomass Energy',
                'description': 'Biogas, biofuels, and other biomass energy solutions.'
            },
            {
                'name': 'Energy Efficiency',
                'description': 'Improving energy use efficiency and reducing energy consumption.'
            },
            {
                'name': 'Rural Electrification',
                'description': 'Extending electricity access to rural and underserved areas.'
            },
        ]
        
        # Map subcategories to main categories
        subcategories_map = {
            'Infrastructure': infrastructure_subcategories,
            'Education': education_subcategories,
            'Healthcare': healthcare_subcategories,
            'Agriculture': agriculture_subcategories,
            'Environment': environment_subcategories,
            'Technology': technology_subcategories,
            'Community Development': community_development_subcategories,
            'Economic Development': economic_development_subcategories,
            'Water & Sanitation': water_sanitation_subcategories,
            'Energy': energy_subcategories,
        }
        
        # Create all subcategories
        for main_category_name, subcategory_list in subcategories_map.items():
            parent_category = categories.get(main_category_name)
            if parent_category:
                for subcategory_data in subcategory_list:
                    subcategory = ProjectCategory.objects.create(
                        name=subcategory_data['name'],
                        description=subcategory_data['description'],
                        parent=parent_category
                    )
                    self.stdout.write(f"Created subcategory: {subcategory.name} (under {parent_category.name})")