from django.contrib import admin
from .models import Transaction, Account, Category, Refund, TransactionSplit, UserSettings

class TransactionSplitInline(admin.TabularInline):
    model = TransactionSplit
    extra = 1
    autocomplete_fields = ['category']

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'sender', 'receiver', 'amount', 'timestamp', 
        'is_refund', 'is_fully_categorized', 
        'remainder_after_refunds', 'remainder_of_refund'
    )
    list_filter = ('user', 'timestamp') 
    
    search_fields = ('description', 'sender__name', 'receiver__name')
    
    readonly_fields = ('remainder_of_refund', 'remainder_after_refunds')
    
    inlines = [TransactionSplitInline]
    
    autocomplete_fields = ['sender', 'receiver', 'user'] 

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_nr', 'is_mine', 'start_balance', 'user')
    list_filter = ('is_mine', 'is_closed', 'user')
    search_fields = ('name', 'account_nr')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'icon', 'user')
    list_filter = ('user',)
    search_fields = ('name',) 

@admin.register(Refund)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('id', 'original_transaction', 'refund_transaction')
    autocomplete_fields = ['original_transaction', 'refund_transaction']

@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'language', 'theme', 'future_transactions_in_balance')
    search_fields = ('user__username',)