from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ...models import Department  

class Command(BaseCommand):
    help = 'Populates the database with organizational departments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force recreation of departments (will delete existing ones)',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing departments instead of skipping them',
        )
        parser.add_argument(
            '--prefix',
            type=str,
            default='',
            help='Add a prefix to department codes to avoid conflicts',
        )

    def handle(self, *args, **options):
        force = options['force']
        update = options['update']
        prefix = options['prefix']
        
        if force and update:
            raise CommandError("Cannot use both --force and --update together")
        
        if force:
            self.stdout.write(self.style.WARNING('Force mode enabled. Deleting all existing departments...'))
            try:
                # Delete all departments (use with caution!)
                Department.objects.all().delete()
                self.stdout.write(self.style.SUCCESS('All existing departments deleted.'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error deleting departments: {str(e)}'))
                return
        
        self.stdout.write('Creating departments...')
        
        # Define administrative levels
        admin_levels = [
            {'name': 'National Administration', 'code': 'NAT', 'description': 'National level administration'},
            {'name': 'Regional Administration', 'code': 'REG', 'description': 'Regional level administration'},
            {'name': 'State Administration', 'code': 'STATE', 'description': 'State level administration'},
            {'name': 'LGA Administration', 'code': 'LGA', 'description': 'Local Government Area administration'},
            {'name': 'Ward Administration', 'code': 'WARD', 'description': 'Ward level administration'},
            {'name': 'Village/Clan Administration', 'code': 'VILL', 'description': 'Village/Clan level administration'},
        ]
        
        # Define core directorates that exist at multiple levels
        core_directorates = [
            {'name': 'Agriculture and Natural Resources', 'code': 'AGR', 'description': 'Oversees agricultural activities and natural resources management'},
            {'name': 'Auditing and Fintech', 'code': 'AUD', 'description': 'Handles auditing and financial technology'},
            {'name': 'Budget and Economic Planning', 'code': 'BEP', 'description': 'Responsible for budgeting and economic planning'},
            {'name': 'Commerce and Industry', 'code': 'COM', 'description': 'Manages commercial and industrial activities'},
            {'name': 'Corporate Governance and Administration', 'code': 'CGA', 'description': 'Handles corporate governance and administrative functions'},
            {'name': 'Corporate Social Responsibility/Community Relations', 'code': 'CSR', 'description': 'Manages CSR initiatives and community relations'},
            {'name': 'Culture and Tourism', 'code': 'CUL', 'description': 'Promotes cultural heritage and tourism'},
            {'name': 'Education', 'code': 'EDU', 'description': 'Oversees educational programs and institutions'},
            {'name': 'Emergency and Disaster Response Management', 'code': 'EDR', 'description': 'Manages emergency and disaster response'},
            {'name': 'Employment Generation and Empowerment', 'code': 'EGE', 'description': 'Creates employment opportunities and empowerment programs'},
            {'name': 'Energy and Power', 'code': 'ENP', 'description': 'Manages energy and power resources'},
            {'name': 'Environmental Development / Climate Change', 'code': 'ENV', 'description': 'Handles environmental issues and climate change initiatives'},
            {'name': 'Finance and Accounts', 'code': 'FIN', 'description': 'Manages financial operations and accounting'},
            {'name': 'Health and Social Services', 'code': 'HSS', 'description': 'Provides health and social services'},
            {'name': 'Human Resource Development', 'code': 'HRD', 'description': 'Manages human resource development'},
            {'name': 'Humanitarian Services and Donor Agencies', 'code': 'HUM', 'description': 'Coordinates humanitarian services and donor relations'},
            {'name': 'ICT (Digital Economy)', 'code': 'ICT', 'description': 'Manages information and communication technology'},
            {'name': 'Internal and Foreign Affairs', 'code': 'IFA', 'description': 'Handles internal and foreign affairs'},
            {'name': 'Legal Services and Social Justice', 'code': 'LEG', 'description': 'Provides legal services and promotes social justice'},
            {'name': 'Maintenance & Asset Management', 'code': 'MAM', 'description': 'Manages maintenance and assets'},
            {'name': 'Media and Publicity', 'code': 'MED', 'description': 'Handles media relations and publicity'},
            {'name': 'Monitoring and Evaluation (M/E)', 'code': 'MOE', 'description': 'Conducts monitoring and evaluation of programs'},
            {'name': 'National Orientation/ Enlightenment, Contacts and Social Mobilization', 'code': 'NOR', 'description': 'Manages national orientation and social mobilization'},
            {'name': 'Peace and Conflict Resolution Management', 'code': 'PCR', 'description': 'Handles peace and conflict resolution'},
            {'name': 'Procurement Services / Contracts', 'code': 'PRO', 'description': 'Manages procurement and contracts'},
            {'name': 'Religious Affairs (Christian)', 'code': 'RAC', 'description': 'Handles Christian religious affairs'},
            {'name': 'Religious Affairs (Islam)', 'code': 'RAI', 'description': 'Handles Islamic religious affairs'},
            {'name': 'Research, Policy and Development', 'code': 'RPD', 'description': 'Conducts research and develops policies'},
            {'name': 'Safety and Security', 'code': 'SEC', 'description': 'Manages safety and security'},
            {'name': 'Science and Technology', 'code': 'SCI', 'description': 'Promotes science and technology'},
            {'name': 'Social Welfare and Rehabilitation', 'code': 'SWR', 'description': 'Provides social welfare and rehabilitation services'},
            {'name': 'Special Duties', 'code': 'SPD', 'description': 'Handles special duties and assignments'},
            {'name': 'Special Needs / Persons with Disabilities (PWDS)', 'code': 'PWD', 'description': 'Supports persons with disabilities'},
            {'name': 'Sports and Entertainments', 'code': 'SPE', 'description': 'Promotes sports and entertainment'},
            {'name': 'Sustainable Development Goals (SDGS) and Inter-Governmental Agencies', 'code': 'SDG', 'description': 'Coordinates SDG initiatives and inter-governmental relations'},
            {'name': 'Traditional Institutions / Community Leaders', 'code': 'TRA', 'description': 'Liaises with traditional institutions and community leaders'},
            {'name': 'Transport and Logistics', 'code': 'TRL', 'description': 'Manages transportation and logistics'},
            {'name': 'Urban Community and Rural Development', 'code': 'URD', 'description': 'Promotes urban and rural development'},
            {'name': 'Water Resources', 'code': 'WAT', 'description': 'Manages water resources'},
            {'name': 'Women Affairs and Development', 'code': 'WAD', 'description': 'Promotes women affairs and development'},
            {'name': 'Works / Infrastructural Development and Lands', 'code': 'INF', 'description': 'Manages infrastructure development and lands'},
            {'name': 'Youth and Social Development', 'code': 'YSD', 'description': 'Promotes youth and social development'},
            {'name': 'Programs and Projects', 'code': 'PPM', 'description': 'Manages programs and projects'},
            {'name': 'Materials Handling and Stores', 'code': 'MHS', 'description': 'Manages materials and stores'},
        ]
        
        # Define leadership positions
        leadership_positions = [
            {'name': 'Office of the Coordinator', 'code': 'COORD', 'description': 'Office of the Coordinator'},
            {'name': 'Office of the Secretary', 'code': 'SECR', 'description': 'Office of the Secretary'},  # Changed from SEC to SECR to avoid conflicts
            {'name': 'Office of the Deputy Coordinator', 'code': 'DCOORD', 'description': 'Office of the Deputy Coordinator'},
        ]
        
        # Define sub-departments for each directorate
        sub_departments = [
            {'name': 'Planning and Strategy', 'code': 'PS', 'description': 'Handles planning and strategic initiatives'},
            {'name': 'Operations', 'code': 'OPS', 'description': 'Manages day-to-day operations'},
            {'name': 'Administration', 'code': 'ADM', 'description': 'Handles administrative functions'},
            {'name': 'Research and Development', 'code': 'RD', 'description': 'Conducts research and development activities'},
        ]
        
        # Track created and skipped departments
        created_count = 0
        updated_count = 0
        skipped_count = 0
        error_count = 0
        
        try:
            # Create admin level departments
            admin_depts = {}
            
            for level in admin_levels:
                code = f"{prefix}{level['code']}"
                try:
                    # Check if department already exists
                    dept, created = self._get_or_create_department(
                        name=level['name'],
                        code=code,
                        description=level['description'],
                        update=update
                    )
                    
                    admin_depts[level['code']] = dept
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created admin level: {dept}")
                    elif update:
                        updated_count += 1
                        self.stdout.write(f"Updated admin level: {dept}")
                    else:
                        skipped_count += 1
                        self.stdout.write(f"Skipped existing admin level: {dept}")
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Error creating admin level {level['name']}: {str(e)}"))
            
            # Create hierarchical relationship between admin levels
            try:
                if 'REG' in admin_depts and 'NAT' in admin_depts:
                    admin_depts['REG'].parent_department = admin_depts['NAT']
                    admin_depts['REG'].save()
                
                if 'STATE' in admin_depts and 'REG' in admin_depts:
                    admin_depts['STATE'].parent_department = admin_depts['REG']
                    admin_depts['STATE'].save()
                
                if 'LGA' in admin_depts and 'STATE' in admin_depts:
                    admin_depts['LGA'].parent_department = admin_depts['STATE']
                    admin_depts['LGA'].save()
                
                if 'WARD' in admin_depts and 'LGA' in admin_depts:
                    admin_depts['WARD'].parent_department = admin_depts['LGA']
                    admin_depts['WARD'].save()
                
                if 'VILL' in admin_depts and 'WARD' in admin_depts:
                    admin_depts['VILL'].parent_department = admin_depts['WARD']
                    admin_depts['VILL'].save()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error setting up hierarchy: {str(e)}"))
            
            # Create leadership positions at each admin level
            for level_code, level_dept in admin_depts.items():
                for position in leadership_positions:
                    position_name = f"{position['name']} ({level_dept.name})"
                    position_code = f"{prefix}{position['code']}_{level_code}"
                    
                    try:
                        dept, created = self._get_or_create_department(
                            name=position_name,
                            code=position_code,
                            description=f"{position['description']} for {level_dept.name}",
                            parent_department=level_dept,
                            update=update
                        )
                        
                        if created:
                            created_count += 1
                            self.stdout.write(f"Created leadership position: {dept}")
                        elif update:
                            updated_count += 1
                            self.stdout.write(f"Updated leadership position: {dept}")
                        else:
                            skipped_count += 1
                            self.stdout.write(f"Skipped existing leadership position: {dept}")
                            
                    except Exception as e:
                        error_count += 1
                        self.stdout.write(self.style.ERROR(f"Error creating leadership position {position_name}: {str(e)}"))
            
            # Create directorates at each admin level (except Village/Clan and Ward)
            for level_code, level_dept in admin_depts.items():
                if level_code in ['NAT', 'REG', 'STATE', 'LGA']:  # Skip Ward and Village levels
                    for directorate in core_directorates:
                        directorate_name = f"{directorate['name']} ({level_dept.name})"
                        directorate_code = f"{prefix}{directorate['code']}_{level_code}"
                        
                        try:
                            dir_dept, created = self._get_or_create_department(
                                name=directorate_name,
                                code=directorate_code,
                                description=f"{directorate['description']} for {level_dept.name}",
                                parent_department=level_dept,
                                update=update
                            )
                            
                            if created:
                                created_count += 1
                                self.stdout.write(f"Created directorate: {dir_dept}")
                            elif update:
                                updated_count += 1
                                self.stdout.write(f"Updated directorate: {dir_dept}")
                            else:
                                skipped_count += 1
                                self.stdout.write(f"Skipped existing directorate: {dir_dept}")
                            
                            # Create sub-departments for each directorate
                            for i, sub_dept in enumerate(sub_departments, 1):
                                sub_name = f"{sub_dept['name']} - {directorate['name']} ({level_dept.name})"
                                sub_code = f"{prefix}{directorate['code']}_{sub_dept['code']}_{level_code}"
                                
                                try:
                                    sub_department, sub_created = self._get_or_create_department(
                                        name=sub_name,
                                        code=sub_code,
                                        description=f"{sub_dept['description']} for {directorate_name}",
                                        parent_department=dir_dept,
                                        update=update
                                    )
                                    
                                    if sub_created:
                                        created_count += 1
                                        self.stdout.write(f"Created sub-department: {sub_department}")
                                    elif update:
                                        updated_count += 1
                                        self.stdout.write(f"Updated sub-department: {sub_department}")
                                    else:
                                        skipped_count += 1
                                        self.stdout.write(f"Skipped existing sub-department: {sub_department}")
                                        
                                except Exception as e:
                                    error_count += 1
                                    self.stdout.write(self.style.ERROR(f"Error creating sub-department {sub_name}: {str(e)}"))
                                    
                        except Exception as e:
                            error_count += 1
                            self.stdout.write(self.style.ERROR(f"Error creating directorate {directorate_name}: {str(e)}"))
            
            # Create Ward Representative departments
            if 'WARD' in admin_depts:
                try:
                    ward_rep_dept, created = self._get_or_create_department(
                        name="Ward Representatives",
                        code=f"{prefix}WREP",
                        description="Ward level representatives",
                        parent_department=admin_depts['WARD'],
                        update=update
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created department: {ward_rep_dept}")
                    elif update:
                        updated_count += 1
                        self.stdout.write(f"Updated department: {ward_rep_dept}")
                    else:
                        skipped_count += 1
                        self.stdout.write(f"Skipped existing department: {ward_rep_dept}")
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Error creating Ward Representatives department: {str(e)}"))
            
            # Create Village/Clan Representative departments
            if 'VILL' in admin_depts:
                try:
                    village_rep_dept, created = self._get_or_create_department(
                        name="Village/Clan Representatives",
                        code=f"{prefix}VREP",
                        description="Village/Clan level representatives",
                        parent_department=admin_depts['VILL'],
                        update=update
                    )
                    
                    if created:
                        created_count += 1
                        self.stdout.write(f"Created department: {village_rep_dept}")
                    elif update:
                        updated_count += 1
                        self.stdout.write(f"Updated department: {village_rep_dept}")
                    else:
                        skipped_count += 1
                        self.stdout.write(f"Skipped existing department: {village_rep_dept}")
                        
                except Exception as e:
                    error_count += 1
                    self.stdout.write(self.style.ERROR(f"Error creating Village/Clan Representatives department: {str(e)}"))
            
            # Summary
            self.stdout.write(self.style.SUCCESS(f"""
Department creation summary:
- Created: {created_count}
- Updated: {updated_count}
- Skipped: {skipped_count}
- Errors: {error_count}
            """))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error creating departments: {str(e)}'))
    
    def _get_or_create_department(self, name, code, description, parent_department=None, update=False):
        """
        Helper method to get or create a department with error handling
        Returns (department, created) tuple
        """
        try:
            # Try to get existing department by code
            dept = Department.objects.filter(code=code).first()
            
            if dept:
                if update:
                    # Update existing department
                    dept.name = name
                    dept.description = description
                    dept.parent_department = parent_department
                    dept.save()
                    return dept, False
                else:
                    # Return existing department without updating
                    return dept, False
            else:
                # Create new department
                with transaction.atomic():
                    dept = Department.objects.create(
                        name=name,
                        code=code,
                        description=description,
                        parent_department=parent_department
                    )
                    return dept, True
                    
        except Exception as e:
            raise CommandError(f"Error creating/updating department {name} ({code}): {str(e)}")