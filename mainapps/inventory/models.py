
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from mptt.models import MPTTModel, TreeForeignKey
User = get_user_model()

class AssetCategory(MPTTModel):
    """Categories for assets"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    icon = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Asset Categories"
    
    def __str__(self):
        return self.name

class AssetLocation(models.Model):
    """Locations where assets can be stored"""
    name = models.CharField(max_length=100)
    address = models.ForeignKey('common.Address', on_delete=models.SET_NULL, null=True, blank=True)
    contact_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_locations')
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Supplier(models.Model):
    """Suppliers of assets"""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.ForeignKey('common.Address', on_delete=models.SET_NULL, null=True, blank=True)
    website = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Asset(models.Model):
    """Physical assets owned by the organization"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('in_use', 'In Use'),
        ('maintenance', 'Under Maintenance'),
        ('retired', 'Retired'),
        ('lost', 'Lost/Stolen'),
    ]
    
    CONDITION_CHOICES = [
        ('new', 'New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
    ]
    
    name = models.CharField(max_length=200)
    asset_id = models.CharField(max_length=50, unique=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.CASCADE, related_name='assets')
    description = models.TextField(blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)
    model_number = models.CharField(max_length=100, blank=True, null=True)
    manufacturer = models.CharField(max_length=100, blank=True, null=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='supplied_assets')
    purchase_date = models.DateField(blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    warranty_expiry_date = models.DateField(blank=True, null=True)
    location = models.ForeignKey(AssetLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='assets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_assets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='new')
    notes = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='asset_images/', blank=True, null=True)
    barcode = models.CharField(max_length=100, blank=True, null=True)
    qr_code = models.CharField(max_length=100, blank=True, null=True)
    last_maintenance_date = models.DateField(blank=True, null=True)
    next_maintenance_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.asset_id} - {self.name}"

class AssetMaintenance(models.Model):
    """Maintenance records for assets"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='maintenance_records')
    maintenance_type = models.CharField(max_length=100)
    description = models.TextField()
    scheduled_date = models.DateField()
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='performed_maintenance')
    actual_date = models.DateField(blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.asset.name} - {self.maintenance_type}"

class AssetCheckout(models.Model):
    """Records of asset checkouts"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='checkouts')
    checked_out_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='asset_checkouts')
    checked_out_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_assets')
    checkout_date = models.DateTimeField()
    expected_return_date = models.DateTimeField()
    actual_return_date = models.DateTimeField(blank=True, null=True)
    checkout_condition = models.CharField(max_length=20)
    return_condition = models.CharField(max_length=20, blank=True, null=True)
    checkout_notes = models.TextField(blank=True, null=True)
    return_notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.asset.name} - {self.checked_out_to.username}"

class AssetAttachment(models.Model):
    """Attachments related to assets"""
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='attachments')
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    file = models.FileField(upload_to='asset_attachments/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='asset_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"{self.asset.name} - {self.title}"

class InventoryAudit(models.Model):
    """Records of inventory audits"""
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    conducted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='conducted_audits')
    location = models.ForeignKey(AssetLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='audits')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    findings = models.TextField(blank=True, null=True)
    recommendations = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class AuditAsset(models.Model):
    """Assets included in an audit"""
    STATUS_CHOICES = [
        ('found', 'Found'),
        ('missing', 'Missing'),
        ('damaged', 'Damaged'),
        ('wrong_location', 'Wrong Location'),
    ]
    
    audit = models.ForeignKey(InventoryAudit, on_delete=models.CASCADE, related_name='audit_assets')
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='audit_records')
    expected_location = models.ForeignKey(AssetLocation, on_delete=models.SET_NULL, null=True, related_name='expected_assets')
    actual_location = models.ForeignKey(AssetLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name='actual_assets')
    expected_condition = models.CharField(max_length=20)
    actual_condition = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.audit.title} - {self.asset.name}"
    

registerable_models=[AssetCategory, AssetLocation, Supplier, Asset, AssetMaintenance, AssetCheckout, AssetAttachment, InventoryAudit, AuditAsset]