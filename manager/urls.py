from django.urls import path, include
from .views import core, accounts, transactions, categories, charts
from django.views.generic import TemplateView
from django.http import JsonResponse

def chrome_devtools_json(request):
    return JsonResponse({})

urlpatterns = [
    # --- CORE ---
    path('', core.homepage, name='homepage'),
    path('first_run_setup/', core.first_run_setup, name='first_run_setup'),
    path('search/', core.search, name='search'),
    path('quicksearch/', core.quicksearch, name='quicksearch'),
    path('user_settings/', core.user_settings, name='user_settings'),
    path('settings/export/', core.backup_export, name='backup_export'),
    path('settings/import/', core.backup_import, name='backup_import'),
    path('devview/', core.devview, name='devview'),
    
    # --- PWA & Service Workers ---
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='service_worker'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('.well-known/appspecific/com.chrome.devtools.json', chrome_devtools_json), 

    # --- TRANSACTIONS ---
    path('transactions/', transactions.transactions, name='transactions'),
    path('transactions/search/', transactions.transaction_search_ajax, name='transaction_search_ajax'),
    path('transaction_detail/<int:transaction_id>/', transactions.transaction_detail, name='transaction_detail'),
    path('transaction_add/', transactions.transaction_add, name='transaction_add'),
    path('transaction_add/<int:copy_id>/', transactions.transaction_add, name='transaction_add'),
    path('transaction_edit/<int:transaction_id>/', transactions.transaction_edit, name='transaction_edit'),
    path('transaction_delete/<int:transaction_id>/', transactions.transaction_delete, name='transaction_delete'),

    # --- ACCOUNTS ---
    path('accounts/', accounts.accounts, name='accounts'),
    path('account_detail/<int:account_id>/', accounts.account_detail, name='account_detail'),
    path('account_add/', accounts.account_add, name='account_add'),
    path('account_edit/<int:account_id>/', accounts.account_edit, name='account_edit'),
    path('account_delete/<int:account_id>/', accounts.account_delete, name='account_delete'),

    # --- CATEGORIES ---
    path('categories/', categories.categories, name='categories'),
    path('category_detail/<int:category_id>/', categories.category_detail, name='category_detail'),
    path('category_add/', categories.category_add, name='category_add'),
    path('category_edit/<int:category_id>/', categories.category_edit, name='category_edit'),
    path('category_delete/<int:category_id>/', categories.category_delete, name='category_delete'),

    # --- CHARTS ---
    path('charts/', charts.charts, name='charts'),
    path('charts/balance_over_time/', charts.chart_balance_over_time, name='chart_balance_over_time'),
    path('charts/sankey/', charts.chart_sankey, name='chart_sankey'),

    # --- INTERNATIONALIZATION ---
    path('i18n/', include('django.conf.urls.i18n')),
]