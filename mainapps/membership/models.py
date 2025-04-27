from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

class MembershipTier(models.Model):
    """Different membership levels with benefits"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2)
    benefits = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class Membership(models.Model):
    """User membership information"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Pending'),
    ]
    
    PAYMENT_FREQUENCY_CHOICES = [
        ('monthly', 'Monthly'),
        ('annually', 'Annually'),
        ('one_time', 'One Time'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    tier = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, related_name='memberships')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_frequency = models.CharField(max_length=20, choices=PAYMENT_FREQUENCY_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    auto_renew = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.tier.name}"

class MembershipPayment(models.Model):
    """Payment records for memberships"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField()
    payment_method = models.CharField(max_length=100)
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.membership.user.username} - {self.amount}"

class MembershipBenefit(models.Model):
    """Specific benefits for membership tiers"""
    tier = models.ForeignKey(MembershipTier, on_delete=models.CASCADE, related_name='specific_benefits')
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, blank=True, null=True)
    
    def __str__(self):
        return f"{self.tier.name} - {self.name}"

class VolunteerOpportunity(models.Model):
    """Volunteer opportunities for members"""
    title = models.CharField(max_length=200)
    description = models.TextField()
    requirements = models.TextField()
    location = models.CharField(max_length=200)
    is_remote = models.BooleanField(default=False)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    hours_required = models.PositiveIntegerField(blank=True, null=True)
    max_volunteers = models.PositiveIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class VolunteerApplication(models.Model):
    """Applications for volunteer opportunities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='volunteer_applications')
    opportunity = models.ForeignKey(VolunteerOpportunity, on_delete=models.CASCADE, related_name='applications')
    motivation = models.TextField()
    availability = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    hours_completed = models.PositiveIntegerField(default=0)
    feedback = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.opportunity.title}"

class Partnership(models.Model):
    """Partnerships with other organizations"""
    PARTNERSHIP_TYPE_CHOICES = [
        ('corporate', 'Corporate'),
        ('nonprofit', 'Non-Profit'),
        ('government', 'Government'),
        ('educational', 'Educational'),
        ('community', 'Community'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]
    
    organization_name = models.CharField(max_length=200)
    organization_type = models.CharField(max_length=20, choices=PARTNERSHIP_TYPE_CHOICES)
    contact_person = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='partnerships')
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=20)
    website = models.URLField(blank=True, null=True)
    description = models.TextField()
    benefits = models.TextField()
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    logo = models.ImageField(upload_to='partnership_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.organization_name