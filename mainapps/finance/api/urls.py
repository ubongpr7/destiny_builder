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

router = DefaultRouter()
router.register(r'financial-institutions', FinancialInstitutionViewSet)
router.register(r'bank-accounts', BankAccountViewSet)
router.register(r'exchange-rates', ExchangeRateViewSet)
router.register(r'donation-campaigns', DonationCampaignViewSet)
router.register(r'donations', DonationViewSet)
router.register(r'recurring-donations', RecurringDonationViewSet)
router.register(r'in-kind-donations', InKindDonationViewSet)
router.register(r'grants', GrantViewSet)
router.register(r'grant-reports', GrantReportViewSet)
router.register(r'funding-sources', FundingSourceViewSet)
router.register(r'budgets', BudgetViewSet)
router.register(r'budget-items', BudgetItemViewSet)
router.register(r'organizational-expenses', OrganizationalExpenseViewSet)
router.register(r'account-transactions', AccountTransactionViewSet)
router.register(r'fund-allocations', FundAllocationViewSet)
router.register(r'dashboard', DashboardViewSet, basename='finance-dashboard')

urlpatterns = [
    path('', include(router.urls)),
]
