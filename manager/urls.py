from django.urls import path, include
from . import views
from django.views.generic import TemplateView
from django.http import JsonResponse

def chrome_devtools_json(request):
    return JsonResponse({})

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('first_run_setup/', views.first_run_setup, name='first_run_setup'),
    path('transactions/', views.transactions, name='transactions'),
    path('transaction_detail/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transaction_add/', views.transaction_add, name='transaction_add'),
    path('transaction_add/<int:copy_id>/', views.transaction_add, name='transaction_add'),
    path('transaction_edit/<int:transaction_id>/', views.transaction_edit, name='transaction_edit'),
    path('transaction_delete/<int:transaction_id>/', views.transaction_delete, name='transaction_delete'),
    path('transactions/search/', views.transaction_search_ajax, name='transaction_search_ajax'),
    path('accounts/', views.accounts, name='accounts'),
    path('account_detail/<int:account_id>/', views.account_detail, name='account_detail'),
    path('account_add/', views.account_add, name='account_add'),
    path('account_edit/<int:account_id>/', views.account_edit, name='account_edit'),
    path('account_delete/<int:account_id>/', views.account_delete, name='account_delete'),
    path('categories/', views.categories, name='categories'),
    path('category_detail/<int:category_id>/', views.category_detail, name='category_detail'),
    path('category_add/', views.category_add, name='category_add'),
    path('category_edit/<int:category_id>/', views.category_edit, name='category_edit'),
    path('category_delete/<int:category_id>/', views.category_delete, name='category_delete'),
    path('search/', views.search, name='search'),
    path('quicksearch/', views.quicksearch, name='quicksearch'),
    path('user_settings/', views.user_settings, name='user_settings'),
    path('settings/export/', views.backup_export, name='backup_export'),
    path('settings/import/', views.backup_import, name='backup_import'),
    path('i18n/', include('django.conf.urls.i18n')),
    path('charts/', views.charts, name='charts'),
    path('charts/balance_over_time/', views.chart_balance_over_time, name='chart_balance_over_time'),
    path('charts/sankey/', views.chart_sankey, name='chart_sankey'),
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json'), name='manifest'),
    path('sw.js', TemplateView.as_view(template_name='sw.js', content_type='application/javascript'), name='service_worker'),
    path('offline/', TemplateView.as_view(template_name='offline.html'), name='offline'),
    path('.well-known/appspecific/com.chrome.devtools.json', chrome_devtools_json),
    path('devview/', views.devview, name='devview'),
]