# types/serializers.py
from rest_framework import serializers
from mainapps.common.models import Currency, TypeOf, Unit,Address
from rest_framework import serializers
from cities_light.models import Country, Region, SubRegion, City
from django.core.exceptions import ValidationError

class TypeOfSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeOf
        fields = '__all__'
        depth = 1  # To show nested parent/children relationships
class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = '__all__'



class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ['id', 'name']
class UnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unit
        fields = ['id', 'name']

class RegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ['id', 'name', 'country']

class SubRegionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubRegion
        fields = ['id', 'name', 'region']

class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ['id', 'name', 'subregion']






class AddressSerializer(serializers.ModelSerializer):
    country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), allow_null=True
    )
    region = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.all(), allow_null=True
    )
    subregion = serializers.PrimaryKeyRelatedField(
        queryset=SubRegion.objects.all(), allow_null=True
    )
    city = serializers.PrimaryKeyRelatedField(
        queryset=City.objects.all(), allow_null=True
    )

    class Meta:
        model = Address
        fields = '__all__'

    def create(self, validated_data):
        # Create instance but don't save yet
        instance = Address(**validated_data)
        try:
            instance.full_clean()  # Validate model fields
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        # Update instance attributes
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()  # Validate updated instance
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)
        instance.save()
        return instance