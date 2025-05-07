from mainapps.accounts.models import Disability, Membership, Industry, Expertise, PartnershipType, PartnershipLevel, Skill, UserProfile
from rest_framework import serializers

from mainapps.common.api.serializers import CitySerializer, CountrySerializer, RegionSerializer, SubRegionSerializer
from mainapps.common.models import Address


class IndustrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Industry
        fields = ['id', 'name']

class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ['id', 'name']


class ExpertiseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Expertise
        fields = ['id', 'name']


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ['id', 'name', 'description']


class PartnershipTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnershipType
        fields = ['id', 'name', 'description']
class DisabilityTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Disability
        fields = ['id', 'name', 'description']


class PartnershipLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnershipLevel
        fields = ['id', 'name', 'description', 'benefits']


class ProfileSerialIzer(serializers.ModelSerializer):
    class Meta:
        model=UserProfile
        fields="__all__"
        depth=1


class ProfileSerialIzerAttachment(serializers.ModelSerializer):
    class Meta:
        depth=1
        model = UserProfile
        fields = '__all__'
        
    def update(self, instance, validated_data):
        # Handle file fields explicitly
        file_fields = ['id_document_image_front', 'id_document_image_back', 'selfie_image', 'profile_image']
        
        for field in file_fields:
            if field in validated_data:
                setattr(instance, field, validated_data.pop(field))
        
        # Update the rest of the fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
            
        instance.save()
        return instance

class CAddressSerializer(serializers.ModelSerializer):
    country_details = CountrySerializer(source='country', read_only=True)
    region_details = RegionSerializer(source='region', read_only=True)
    subregion_details = SubRegionSerializer(source='subregion', read_only=True)
    city_details = CitySerializer(source='city', read_only=True)
    
    class Meta:
        model = Address
        fields = [
            'id', 'country', 'region', 'subregion', 'city', 
            'apt_number', 'street_number', 'street', 'postal_code',
            'country_details', 'region_details', 'subregion_details', 'city_details'
        ]
        read_only_fields = ['id']