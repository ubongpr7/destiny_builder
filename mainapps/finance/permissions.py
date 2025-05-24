from rest_framework import permissions
from django.contrib.auth.models import Group

class IsFinanceManager(permissions.BasePermission):
    """
    Custom permission to only allow finance managers to edit financial data.
    """
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        return (
            request.user.is_authenticated and 
            (request.user.is_staff or 
             request.user.groups.filter(name='Finance Managers').exists())
        )

class IsAccountantOrFinanceManager(permissions.BasePermission):
    """
    Custom permission for accountants and finance managers.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return (
            request.user.is_staff or
            request.user.groups.filter(
                name__in=['Finance Managers', 'Accountants']
            ).exists()
        )

class IsDonationManager(permissions.BasePermission):
    """
    Custom permission for donation management.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return (
            request.user.is_staff or
            request.user.groups.filter(
                name__in=['Finance Managers', 'Donation Managers']
            ).exists()
        )

class IsGrantManager(permissions.BasePermission):
    """
    Custom permission for grant management.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
            
        if request.method in permissions.SAFE_METHODS:
            return True
            
        return (
            request.user.is_staff or
            request.user.groups.filter(
                name__in=['Finance Managers', 'Grant Managers']
            ).exists()
        )
