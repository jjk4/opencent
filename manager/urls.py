from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('first_run_setup/', views.first_run_setup, name='first_run_setup'),
    path('transactions/', views.transactions, name='transactions'),
    path('transaction_detail/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transaction_add/', views.transaction_add, name='transaction_add'),
    path('transaction_add/<int:copy_id>/', views.transaction_add, name='transaction_add'),
    path('transaction_edit/<int:transaction_id>/', views.transaction_edit, name='transaction_edit'),
    path('transaction_delete/<int:transaction_id>/', views.transaction_delete, name='transaction_delete'),
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
    path('charts/', views.charts, name='charts'),
    path('charts/balance_over_time/', views.chart_balance_over_time, name='chart_balance_over_time'),
    path('charts/sankey/', views.chart_sankey, name='chart_sankey'),
    path('devview/', views.devview, name='devview'),

]