from django.contrib import admin
from .models import Transaction, Account, Category, Refund

# Register your models here.

class TransactionAdmin(admin.ModelAdmin):
  list_display = ('id', 'sender', 'receiver', 'amount', 'timestamp', 'description', 'category', 'is_refund')

admin.site.register(Transaction, TransactionAdmin)



class AccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'iban', 'is_mine', 'start_balance')
    
admin.site.register(Account, AccountAdmin)

class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_category', 'icon')
    
admin.site.register(Category, CategoryAdmin)

class RefundAdmin(admin.ModelAdmin):
    list_display = ('original_transaction', 'refund_transaction')
    
admin.site.register(Refund, RefundAdmin)