from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('reports/financial-summary/', views.financial_summary_report, name='financial_summary'),
    path('reports/ledger/', views.ledger_report, name='ledger'),
    path('reports/ledger/<int:account_id>/', views.ledger_report, name='ledger_for_account'),
    path('reports/invoices/', views.invoice_list_report, name='invoice_list'),
    path('reports/revenue/', views.revenue_report, name='revenue'),
    path('reports/statement/<int:account_id>/', views.account_statement, name='account_statement'),
]
