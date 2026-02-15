from django.contrib import admin
from .models import Transaction, Account, Category, Refund, TransactionSplit

class TransactionSplitInline(admin.TabularInline):
    model = TransactionSplit
    extra = 1
    autocomplete_fields = ['category']

# Register your models here.

class TransactionAdmin(admin.ModelAdmin):
  list_display = ('id', 'sender', 'receiver', 'amount', 'timestamp', 'description', 'is_refund', 'user','is_fully_categorized', 'remainder_of_refund', 'remainder_after_refunds')
  inlines = [TransactionSplitInline]

admin.site.register(Transaction, TransactionAdmin)



class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_nr', 'is_mine', 'start_balance', 'user')
    
admin.site.register(Account, AccountAdmin)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'icon', 'user')
    search_fields = (['name'])
    
admin.site.register(Category, CategoryAdmin)

class RefundAdmin(admin.ModelAdmin):
    list_display = ('original_transaction', 'refund_transaction')
    
admin.site.register(Refund, RefundAdmin)