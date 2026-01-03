from django.urls import path
from . import views

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('transactions/', views.transactions, name='transactions'),
    path('transaction_detail/<int:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transaction_add/', views.transaction_add, name='transaction_add'),
    path('transaction_edit/<int:transaction_id>/', views.transaction_edit, name='transaction_edit'),
    path('transaction_delete/<int:transaction_id>/', views.transaction_delete, name='transaction_delete'),
    path('accounts/', views.accounts, name='accounts'),
    path('account_detail/<int:account_id>/', views.account_detail, name='account_detail'),
    path('categories/', views.categories, name='categories'),
    path('charts/', views.charts, name='charts'),
    path('charts/balance_over_time/', views.chart_balance_over_time, name='chart_balance_over_time'),
    path('charts/sankey/', views.chart_sankey, name='chart_sankey'),
    path('devview/', views.devview, name='devview'),

]