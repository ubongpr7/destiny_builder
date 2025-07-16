from django.db import models

# Create your models here.
# models.py
from django.db import models

class TeamMember(models.Model):
    name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, blank=True, null=True)
    image = models.ImageField(upload_to='team_members/')
    priority = models.IntegerField(
        default=0,
        help_text="Higher priority appears first"
    )
    social_facebook = models.URLField(blank=True, null=True)
    social_twitter = models.URLField(blank=True, null=True)
    social_instagram = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-priority', 'name']
        verbose_name = "Team Member"
        verbose_name_plural = "Team Members"

    def __str__(self):
        return self.name

