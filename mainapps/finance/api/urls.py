from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DonationCampaignViewSet,
    DonationViewSet,
    RecurringDonationViewSet,
    InKindDonationViewSet,
    GrantViewSet,
    GrantReportViewSet,
    BudgetViewSet,
    BudgetItemViewSet,
    OrganizationalExpenseViewSet,
    FinanceDashboardViewSet,
    create_public_donation,
)

router = DefaultRouter()
router.register(r'campaigns', DonationCampaignViewSet, basename='donationcampaign')
router.register(r'donations', DonationViewSet, basename='donation')
router.register(r'recurring-donations', RecurringDonationViewSet, basename='recurringdonation')
router.register(r'in-kind-donations', InKindDonationViewSet, basename='inkinddonation')
router.register(r'grants', GrantViewSet, basename='grant')
router.register(r'grant-reports', GrantReportViewSet, basename='grantreport')
router.register(r'budgets', BudgetViewSet, basename='budget')
router.register(r'budget-items', BudgetItemViewSet, basename='budgetitem')
router.register(r'organizational-expenses', OrganizationalExpenseViewSet, basename='organizationalexpense')
router.register(r'dashboard', FinanceDashboardViewSet, basename='finance-dashboard')

urlpatterns = [
    path('', include(router.urls)),
    path('donations/public/', create_public_donation, name='create_public_donation'),
]
