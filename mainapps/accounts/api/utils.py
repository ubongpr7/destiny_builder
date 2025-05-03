from django.db.models import Prefetch, Count, Q
from ..models import  Industry, Expertise, PartnershipType, PartnershipLevel, Skill

def get_reference_data_counts():
    """Get counts of all reference data for dashboard display"""
    return {
        'industries': Industry.objects.count(),
        'expertise': Expertise.objects.count(),
        'skills': Skill.objects.count(),
        'partnership_types': PartnershipType.objects.count(),
        'partnership_levels': PartnershipLevel.objects.count(),

    }

def search_reference_data(query):
    """Search across all reference data models"""
    if not query:
        return {}
        
    return {
        'industries': Industry.objects.filter(name__icontains=query),
        'expertise': Expertise.objects.filter(name__icontains=query),
        'skills': Skill.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ),
        'partnership_types': PartnershipType.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ),
        'partnership_levels': PartnershipLevel.objects.filter(
            Q(name__icontains=query) | Q(description__icontains=query)
        ),
    }
