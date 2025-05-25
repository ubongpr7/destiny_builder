from django.core.management.base import BaseCommand
from django.db import transaction
from mainapps.finance.models import FinancialInstitution


class Command(BaseCommand):
    help = 'Populate database with standard commercial banks and digital financial institutions'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing financial institutions before populating',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing financial institutions...')
            FinancialInstitution.objects.all().delete()

        african_banks = [
            # Nigeria
            {'name': 'Guaranty Trust Bank (GTBank)', 'code': 'GTBINGLA'},
            {'name': 'Access Bank', 'code': 'ABNGNGLA'},
            {'name': 'Zenith Bank', 'code': 'ZEIBNGLA'},
            {'name': 'First Bank of Nigeria', 'code': 'FBNINGLA'},
            {'name': 'United Bank for Africa (UBA)', 'code': 'UNAFNGLA'},
            {'name': 'Fidelity Bank Nigeria', 'code': 'FIDELNGN'},
            {'name': 'Stanbic IBTC Bank', 'code': 'SBICNGLA'},
            {'name': 'Sterling Bank', 'code': 'STERLNGN'},
            
            # South Africa
            {'name': 'Standard Bank of South Africa', 'code': 'SBZAZAJJ'},
            {'name': 'FirstRand Bank (FNB)', 'code': 'FIRNZAJJ'},
            {'name': 'ABSA Bank', 'code': 'ABSAZAJJ'},
            {'name': 'Nedbank', 'code': 'NEDSZAJJ'},
            {'name': 'Capitec Bank', 'code': 'CABLZAJJ'},
            {'name': 'Investec Bank', 'code': 'IVESZAJJ'},
            
            # Kenya
            {'name': 'Kenya Commercial Bank (KCB)', 'code': 'KCBLKENX'},
            {'name': 'Equity Bank Kenya', 'code': 'EQBLKENX'},
            {'name': 'Cooperative Bank of Kenya', 'code': 'COOPKENX'},
            {'name': 'Standard Chartered Kenya', 'code': 'SCBLKENX'},
            {'name': 'Barclays Bank Kenya', 'code': 'BARCKENX'},
            {'name': 'NCBA Bank Kenya', 'code': 'CBAFKENX'},
            
            # Ghana
            {'name': 'Ghana Commercial Bank', 'code': 'GHCBGHAC'},
            {'name': 'Ecobank Ghana', 'code': 'ECOCZGHC'},
            {'name': 'Standard Chartered Ghana', 'code': 'SCBLGHAC'},
            {'name': 'Zenith Bank Ghana', 'code': 'ZEIBGHAC'},
            {'name': 'Fidelity Bank Ghana', 'code': 'FIDELGHC'},
            
            # Egypt
            {'name': 'National Bank of Egypt', 'code': 'NBEGEGCX'},
            {'name': 'Banque Misr', 'code': 'BMISEGCX'},
            {'name': 'Commercial International Bank (CIB)', 'code': 'CIBEEGCX'},
            {'name': 'HSBC Bank Egypt', 'code': 'HBMKEGCX'},
            
            # Morocco
            {'name': 'Attijariwafa Bank', 'code': 'BCMAMAMC'},
            {'name': 'Banque Populaire du Maroc', 'code': 'BMCEMAMC'},
            {'name': 'BMCE Bank of Africa', 'code': 'BMCEMAMC'},
            
            # Ethiopia
            {'name': 'Commercial Bank of Ethiopia', 'code': 'CBETETAA'},
            {'name': 'Dashen Bank', 'code': 'DASHETAA'},
            {'name': 'Bank of Abyssinia', 'code': 'ABYSETAA'},
            
            # Tanzania
            {'name': 'CRDB Bank', 'code': 'CORUTZTZ'},
            {'name': 'National Microfinance Bank (NMB)', 'code': 'NMBZTZTZ'},
            {'name': 'Stanbic Bank Tanzania', 'code': 'SBICTZTZ'},
            
            # Uganda
            {'name': 'Stanbic Bank Uganda', 'code': 'SBICUGKX'},
            {'name': 'Centenary Bank', 'code': 'CENTUUGX'},
            {'name': 'DFCU Bank', 'code': 'DFCUUGKX'},
            
            # Rwanda
            {'name': 'Bank of Kigali', 'code': 'BKIGRWRW'},
            {'name': 'Equity Bank Rwanda', 'code': 'EQBLRWRW'},
            
            # Other African Countries
            {'name': 'Ecobank Transnational', 'code': 'ECOCTGBJ'},  # Togo (HQ)
            {'name': 'United Bank for Africa', 'code': 'UNAFNGLA'},  # Pan-African
            {'name': 'Standard Bank Group', 'code': 'SBZAZAJJ'},  # Pan-African
        ]

        # Top Digital Financial Organizations
        digital_financial_orgs = [
            {'name': 'PayPal', 'code': 'PAYPAL'},
            {'name': 'Stripe', 'code': 'STRIPE'},
            {'name': 'Square (Block)', 'code': 'SQUARE'},
            {'name': 'Wise (formerly TransferWise)', 'code': 'WISE'},
            {'name': 'Revolut', 'code': 'REVOLUT'},
            {'name': 'Klarna', 'code': 'KLARNA'},
            {'name': 'Adyen', 'code': 'ADYEN'},
            {'name': 'Remitly', 'code': 'REMITLY'},
            {'name': 'WorldRemit', 'code': 'WORLDREMIT'},
            {'name': 'Western Union Digital', 'code': 'WUDIGITAL'},
            {'name': 'MoneyGram', 'code': 'MONEYGRAM'},
            {'name': 'Flutterwave', 'code': 'FLUTTERWAVE'},
            {'name': 'Paystack', 'code': 'PAYSTACK'},
            {'name': 'M-Pesa', 'code': 'MPESA'},
            {'name': 'Chipper Cash', 'code': 'CHIPPERCASH'},
        ]

        # Combine all institutions
        all_institutions = african_banks + digital_financial_orgs

        # Remove duplicates based on code
        unique_institutions = {}
        for institution in all_institutions:
            code = institution['code']
            if code not in unique_institutions:
                unique_institutions[code] = institution

        self.stdout.write(f'Creating {len(unique_institutions)} financial institutions...')

        created_count = 0
        updated_count = 0

        with transaction.atomic():
            for institution_data in unique_institutions.values():
                institution, created = FinancialInstitution.objects.get_or_create(
                    code=institution_data['code'],
                    defaults={
                        'name': institution_data['name'],
                        'is_active': True,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Created: {institution.name} ({institution.code})')
                    )
                else:
                    # Update name if it's different
                    if institution.name != institution_data['name']:
                        institution.name = institution_data['name']
                        institution.save()
                        updated_count += 1
                        self.stdout.write(
                            self.style.WARNING(f'Updated: {institution.name} ({institution.code})')
                        )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nCompleted! Created {created_count} new institutions, '
                f'updated {updated_count} existing institutions.'
            )
        )

        # Display summary by category
        self.stdout.write('\n--- Summary ---')
        self.stdout.write(f'African Banks: {len(african_banks)} institutions')
        self.stdout.write(f'Digital Financial Organizations: {len(digital_financial_orgs)} institutions')
        self.stdout.write(f'Total Unique Institutions: {len(unique_institutions)}')
        
        # Show some statistics
        total_institutions = FinancialInstitution.objects.count()
        active_institutions = FinancialInstitution.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\nDatabase Statistics:')
        self.stdout.write(f'Total institutions in database: {total_institutions}')
        self.stdout.write(f'Active institutions: {active_institutions}')
