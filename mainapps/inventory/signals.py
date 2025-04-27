from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Inventory
from mainapps.inventory.api.views import InventoryListAPIView

@receiver(post_save, sender=Inventory)
def invalidate_cache_on_inventory_change(sender, instance, **kwargs):
    """
    Signal to invalidate the cache when an Inventory object is saved.
    """
    
    user = instance.profile.owner 
    InventoryListAPIView.invalidate_cache_for_user(user)

@receiver(post_delete, sender=Inventory)
def invalidate_cache_on_inventory_delete(sender, instance, **kwargs):
    """
    Signal to invalidate the cache when an Inventory object is deleted.
    """
    # Assuming `profile` is the field linking Inventory to the user/company
    user = instance.profile.owner  # Adjust based on your model relationships
    InventoryListAPIView.invalidate_cache_for_user(user)