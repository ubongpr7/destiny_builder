import io
from django.core.management.base import BaseCommand
from cities_light.models import Country, Region, SubRegion
import requests
import csv

class Command(BaseCommand):
    help = 'Import subregions from Geonames'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Starting subregion import process"))
        
        # Download admin2 codes
        url = "https://download.geonames.org/export/dump/admin2Codes.txt"
        self.stdout.write(f"Downloading data from: {url}")
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to download data: {str(e)}"))
            return

        self.stdout.write(self.style.SUCCESS(f"Downloaded {len(response.content)} bytes"))
        
        # Create mapping of country_code + region_code to Region objects
        regions = {}
        for region in Region.objects.select_related('country').all():
            key = f"{region.country.code2}.{region.geoname_code}"
            regions[key] = region
            if len(regions) % 1000 == 0:
                self.stdout.write(f"Loaded {len(regions)} regions into memory map")

        self.stdout.write(self.style.SUCCESS(f"Created region map with {len(regions)} entries"))
        
        processed = 0
        created = 0
        errors = 0
        reader = csv.reader(io.TextIOWrapper(io.BytesIO(response.content)), delimiter='\t')
        start_processing = False
        
        for row in reader:
            processed += 1
            if processed % 1000 == 0:
                self.stdout.write(f"Processed {processed} rows, created {created} subregions, {errors} errors")
            
            if len(row) < 4:
                errors += 1
                self.stdout.write(self.style.WARNING(f"Row {processed}: Insufficient columns"))
                continue

            try:
                composite_code = row[0]
                name = row[1]
                geoname_id = row[3]
                
                
                self.stdout.write(f"Processing: {composite_code} - {name}", ending='\r')

                country_code, region_code, subregion_code = composite_code.split('.')
                lookup_key = f"{country_code}.{region_code}"

                if country_code == 'NG':
                    start_processing = True
                elif not start_processing:
                    self.stdout.write('Skipping')
                    continue

                # region = regions.get(lookup_key)
                country=Country.objects.get(code2=country_code)
                region= Region.objects.get(
                            country=country,
                            geoname_code=region_code,
                            
                        )

                if not region:
                    errors += 1
                    self.stdout.write(self.style.WARNING(
                        f"\nRow {processed}: No region found for {lookup_key} (Subregion: {subregion_code})"
                    ))
                    continue
                
                subregion, created_flag = SubRegion.objects.update_or_create(
                    geoname_id=geoname_id,
                    defaults={
                        'name': name,
                        'region': region,
                        'geoname_code': subregion_code,
                        'country': country
                    }
                )
                
                if created_flag:
                    created += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"\nCreated subregion: {name} ({subregion_code}) in {region.country.name} > {region.name}"
                    ))

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(
                    f"\nRow {processed}: Error processing row - {str(e)}"
                ))
                if processed < 5:  # Show sample row for first few errors
                    self.stdout.write(self.style.ERROR(f"Problematic row: {row}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nImport complete! Processed {processed} rows, created {created} subregions, {errors} errors"
        ))