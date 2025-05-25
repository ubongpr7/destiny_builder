from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    FinancialInstitutionViewSet, BankAccountViewSet, ExchangeRateViewSet,
    DonationCampaignViewSet, DonationViewSet, RecurringDonationViewSet,
    InKindDonationViewSet, GrantViewSet, GrantReportViewSet,
    FundingSourceViewSet, BudgetViewSet, BudgetItemViewSet,
    OrganizationalExpenseViewSet, AccountTransactionViewSet,
    FundAllocationViewSet, DashboardViewSet
)

# Create router and register viewsets
router = DefaultRouter()

# Financial Infrastructure
router.register(r'financial-institutions', FinancialInstitutionViewSet)
router.register(r'bank-accounts', BankAccountViewSet)
router.register(r'exchange-rates', ExchangeRateViewSet)

# Donations & Campaigns
router.register(r'donation-campaigns', DonationCampaignViewSet)
router.register(r'donations', DonationViewSet)
router.register(r'recurring-donations', RecurringDonationViewSet)
router.register(r'in-kind-donations', InKindDonationViewSet)

# Grants & Reports
router.register(r'grants', GrantViewSet)
router.register(r'grant-reports', GrantReportViewSet)

# Budgets & Expenses
router.register(r'funding-sources', FundingSourceViewSet)
router.register(r'budgets', BudgetViewSet)
router.register(r'budget-items', BudgetItemViewSet)
router.register(r'organizational-expenses', OrganizationalExpenseViewSet)

# Transactions & Allocations
router.register(r'account-transactions', AccountTransactionViewSet)
router.register(r'fund-allocations', FundAllocationViewSet)

# Dashboard & Analytics
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

# URL patterns
urlpatterns = [
    # API routes
    path('api/finance/', include(router.urls)),
    
    # Additional custom endpoints (if needed)
    path('api/finance/reports/', include([
        # Custom report endpoints can go here
    ])),
]

