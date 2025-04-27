from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class MembershipTier(models.Model):
    """Membership tiers available to users"""
    name = models.CharField(max_length=100)
    description = models.TextField()
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    annual_price = models.DecimalField(max_digits=10, decimal_places=2)
    benefits = models.JSONField(default=list)  # List of benefits as JSON
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UserProfile(models.Model):
    """Extended user profile information"""
    VERIFICATION_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('submitted', 'Submitted'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(blank=True)
    
    # Membership related fields
    membership_tier = models.ForeignKey(MembershipTier, on_delete=models.SET_NULL, null=True, blank=True)
    membership_start_date = models.DateField(null=True, blank=True)
    membership_end_date = models.DateField(null=True, blank=True)
    is_membership_active = models.BooleanField(default=False)
    
    # KYC verification fields
    verification_status = models.CharField(
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default='pending'
    )
    id_document_type = models.CharField(max_length=50, blank=True)
    id_document_number = models.CharField(max_length=100, blank=True)
    id_document_front = models.ImageField(upload_to='kyc_documents/', null=True, blank=True)
    id_document_back = models.ImageField(upload_to='kyc_documents/', null=True, blank=True)
    selfie_with_id = models.ImageField(upload_to='kyc_documents/', null=True, blank=True)
    address_proof = models.ImageField(upload_to='kyc_documents/', null=True, blank=True)
    verification_submitted_at = models.DateTimeField(null=True, blank=True)
    verification_processed_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    
    # Additional fields
    is_volunteer = models.BooleanField(default=False)
    is_partner = models.BooleanField(default=False)
    skills = models.JSONField(default=list, blank=True)  # List of skills as JSON
    interests = models.JSONField(default=list, blank=True)  # List of interests as JSON
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"


class AssetCategory(models.Model):
    """Categories for inventory assets"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Asset Categories"

    def __str__(self):
        return self.name


class Asset(models.Model):
    """Inventory assets"""
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
    ]
    
    asset_id = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(AssetCategory, on_delete=models.SET_NULL, null=True, related_name='assets')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='new')
    
    # Acquisition details
    acquisition_date = models.DateField(null=True, blank=True)
    acquisition_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    supplier = models.CharField(max_length=255, blank=True)
    
    # Physical attributes
    location = models.CharField(max_length=255, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    manufacturer = models.CharField(max_length=100, blank=True)
    
    # Warranty and maintenance
    warranty_expiry = models.DateField(null=True, blank=True)
    maintenance_schedule = models.JSONField(default=list, blank=True)  # List of maintenance dates as JSON
    last_maintenance = models.DateField(null=True, blank=True)
    next_maintenance = models.DateField(null=True, blank=True)
    
    # Usage tracking
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_assets')
    checked_out = models.BooleanField(default=False)
    checkout_date = models.DateTimeField(null=True, blank=True)
    expected_return_date = models.DateTimeField(null=True, blank=True)
    
    # Media
    image = models.ImageField(upload_to='asset_images/', null=True, blank=True)
    documents = models.JSONField(default=list, blank=True)  # List of document URLs as JSON
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)  # List of tags as JSON
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_assets')

    def __str__(self):
        return f"{self.asset_id} - {self.name}"


class AssetActivity(models.Model):
    """Activity log for assets"""
    ACTIVITY_TYPES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('checked_out', 'Checked Out'),
        ('checked_in', 'Checked In'),
        ('maintenance', 'Maintenance'),
        ('retired', 'Retired'),
        ('transferred', 'Transferred'),
    ]
    
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='asset_activities')
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.JSONField(default=dict)  # Details of the activity as JSON
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Asset Activities"

    def __str__(self):
        return f"{self.activity_type} - {self.asset.name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class Project(models.Model):
    """Projects managed by the organization"""
    STATUS_CHOICES = [
        ('planning', 'Planning'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
        ('cancelled', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expenses = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    location = models.CharField(max_length=255, blank=True)
    
    # Media
    featured_image = models.ImageField(upload_to='project_images/', null=True, blank=True)
    gallery = models.JSONField(default=list, blank=True)  # List of image URLs as JSON
    
    # Relationships
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='managed_projects')
    team_members = models.ManyToManyField(User, related_name='projects', blank=True)
    assets = models.ManyToManyField(Asset, related_name='projects', blank=True)
    
    # Metadata
    tags = models.JSONField(default=list, blank=True)  # List of tags as JSON
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_projects')

    def __str__(self):
        return self.title


class Donation(models.Model):
    """Donations made to the organization"""
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('other', 'Other'),
    ]
    
    DONATION_TYPE_CHOICES = [
        ('one_time', 'One Time'),
        ('recurring', 'Recurring'),
        ('in_kind', 'In Kind'),
    ]
    
    donor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    donation_type = models.CharField(max_length=20, choices=DONATION_TYPE_CHOICES, default='one_time')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=255, blank=True)
    date = models.DateTimeField(default=timezone.now)
    
    # For in-kind donations
    item_description = models.TextField(blank=True)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    
    # For recurring donations
    recurring_frequency = models.CharField(max_length=20, blank=True)  # monthly, quarterly, etc.
    recurring_start = models.DateField(null=True, blank=True)
    recurring_end = models.DateField(null=True, blank=True)
    
    # Additional information
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='donations')
    is_anonymous = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    receipt_sent = models.BooleanField(default=False)
    thank_you_sent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.donor and not self.is_anonymous:
            return f"Donation by {self.donor.get_full_name() or self.donor.username} - {self.date.strftime('%Y-%m-%d')}"
        return f"Anonymous Donation - {self.date.strftime('%Y-%m-%d')}"


class Event(models.Model):
    """Events organized by the foundation"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    location = models.CharField(max_length=255)
    location_details = models.TextField(blank=True)
    is_virtual = models.BooleanField(default=False)
    virtual_meeting_link = models.URLField(blank=True)
    
    # Registration
    registration_required = models.BooleanField(default=False)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    max_attendees = models.PositiveIntegerField(null=True, blank=True)
    
    # Media
    featured_image = models.ImageField(upload_to='event_images/', null=True, blank=True)
    
    # Relationships
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='organized_events')
    attendees = models.ManyToManyField(User, related_name='events', blank=True, through='EventAttendee')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    
    # Metadata
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_events')

    def __str__(self):
        return self.title


class EventAttendee(models.Model):
    """Many-to-many relationship between events and attendees with additional data"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    registration_date = models.DateTimeField(auto_now_add=True)
    attended = models.BooleanField(default=False)
    check_in_time = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('event', 'user')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.event.title}"


class VolunteerOpportunity(models.Model):
    """Volunteer opportunities offered by the organization"""
    title = models.CharField(max_length=255)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    location = models.CharField(max_length=255)
    is_remote = models.BooleanField(default=False)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    hours_per_week = models.PositiveIntegerField(null=True, blank=True)
    skills_needed = models.JSONField(default=list, blank=True)  # List of required skills as JSON
    
    # Status
    is_active = models.BooleanField(default=True)
    positions_available = models.PositiveIntegerField(default=1)
    
    # Relationships
    coordinator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='coordinated_opportunities')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True, related_name='volunteer_opportunities')
    volunteers = models.ManyToManyField(User, related_name='volunteer_opportunities', blank=True, through='VolunteerApplication')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_opportunities')

    class Meta:
        verbose_name_plural = "Volunteer Opportunities"

    def __str__(self):
        return self.title


class VolunteerApplication(models.Model):
    """Applications for volunteer opportunities"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]
    
    opportunity = models.ForeignKey(VolunteerOpportunity, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    message = models.TextField(blank=True)
    resume = models.FileField(upload_to='volunteer_resumes/', null=True, blank=True)
    availability = models.JSONField(default=dict, blank=True)  # Availability details as JSON
    
    # Tracking
    applied_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_applications')
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('opportunity', 'user')

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.opportunity.title}"


class Partnership(models.Model):
    """Partnerships with other organizations"""
    PARTNERSHIP_TYPE_CHOICES = [
        ('sponsor', 'Sponsor'),
        ('collaborator', 'Collaborator'),
        ('service_provider', 'Service Provider'),
        ('donor', 'Donor Organization'),
        ('community', 'Community Partner'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('expired', 'Expired'),
        ('terminated', 'Terminated'),
    ]
    
    organization_name = models.CharField(max_length=255)
    partnership_type = models.CharField(max_length=20, choices=PARTNERSHIP_TYPE_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Contact information
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    
    # Agreement details
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    agreement_document = models.FileField(upload_to='partnership_agreements/', null=True, blank=True)
    
    # Financial details (for sponsors)
    contribution_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contribution_frequency = models.CharField(max_length=50, blank=True)
    
    # Media
    logo = models.ImageField(upload_to='partner_logos/', null=True, blank=True)
    website = models.URLField(blank=True)
    
    # Relationships
    projects = models.ManyToManyField(Project, related_name='partnerships', blank=True)
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_partnerships')

    def __str__(self):
        return f"{self.organization_name} - {self.get_partnership_type_display()}"


class BlogPost(models.Model):
    """Blog posts for the website"""
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    excerpt = models.TextField(blank=True)
    featured_image = models.ImageField(upload_to='blog_images/', null=True, blank=True)
    
    # Publishing
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    
    # Categories and tags
    categories = models.JSONField(default=list, blank=True)  # List of categories as JSON
    tags = models.JSONField(default=list, blank=True)  # List of tags as JSON
    
    # Relationships
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='blog_posts')
    related_projects = models.ManyToManyField(Project, related_name='blog_posts', blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class FAQ(models.Model):
    """Frequently Asked Questions"""
    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=100, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['order', 'created_at']

    def __str__(self):
        return self.question


class ContactMessage(models.Model):
    """Messages from the contact form"""
    name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    subject = models.CharField(max_length=255)
    message = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    is_replied = models.BooleanField(default=False)
    replied_at = models.DateTimeField(null=True, blank=True)
    replied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='replied_messages')
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - {self.subject} - {self.created_at.strftime('%Y-%m-%d')}"


class Notification(models.Model):
    """User notifications"""
    TYPE_CHOICES = [
        ('system', 'System'),
        ('project', 'Project'),
        ('membership', 'Membership'),
        ('donation', 'Donation'),
        ('event', 'Event'),
        ('volunteer', 'Volunteer'),
        ('asset', 'Asset'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='system')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Optional related objects
    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.notification_type} - {self.title} - {self.user.username}"