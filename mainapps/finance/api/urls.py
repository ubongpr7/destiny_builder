from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    BudgetFundingViewSet, FinancialInstitutionViewSet, BankAccountViewSet, ExchangeRateViewSet,
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
router.register(r'budget-funding', BudgetFundingViewSet)
router.register(r'budgets', BudgetViewSet)
router.register(r'budget-items', BudgetItemViewSet)
router.register(r'organizational-expenses', OrganizationalExpenseViewSet)

# Transactions & Allocations
router.register(r'account-transactions', AccountTransactionViewSet)
router.register(r'fund-allocations', FundAllocationViewSet)

router.register(r'dashboard', DashboardViewSet, basename='dashboard')

urlpatterns = [
    # API routes
    path('', include(router.urls)),
    
    path('api/finance/reports/', include([
    ])),
]

