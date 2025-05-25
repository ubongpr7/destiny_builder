from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

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
router.register(r'grants', GrantViewSet)

router.register(r'in-kind-donations', InKindDonationViewSet)
router.register(r'grant-reports', GrantReportViewSet)
router.register(r'funding-sources', FundingSourceViewSet)
router.register(r'budget-items', BudgetItemViewSet)
router.register(r'account-transactions', AccountTransactionViewSet)
router.register(r'fund-allocations', FundAllocationViewSet)

# Budgets & Expenses
router.register(r'budgets', BudgetViewSet)
router.register(r'organizational-expenses', OrganizationalExpenseViewSet)

# Transactions & Allocations

# Dashboard & Analytics
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

# URL patterns
urlpatterns = [
    # API routes
    path('', include(router.urls)),
    
    # Additional custom endpoints (if needed)
    path('api/finance/reports/', include([
        # Custom report endpoints can go here
    ])),
]

# Optional: Add API documentation endpoints
from rest_framework.documentation import include_docs_urls

urlpatterns += [
    path('api/finance/docs/', include_docs_urls(title='Finance API Documentation')),
]
