from django.db import models
from decimal import Decimal, ROUND_HALF_UP

class Transaction(models.Model):
    sender = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='sent_transactions', null=False, blank=False)
    receiver = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='received_transactions', null=False, blank=False)
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    timestamp = models.DateTimeField()
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.sender.name} -> {self.receiver.name}: {self.amount} €"
    
    @property
    def refunds(self):
        return Refund.objects.filter(original_transaction=self)
    
    @property
    def is_refund_of(self):
        return Refund.objects.filter(refund_transaction=self)
        
    @property
    def is_refund(self):
        return self.refund_transaction_refunds.exists()
    
    @property
    def has_refunds(self):
        return self.original_transaction_refunds.exists()
    
    @property
    def remainder_of_refund(self):
        """Berechnet den Rest einer Rückerstattungstransaktion, der nach der Rückerstattung noch übrig ist"""
        amount = self.amount - sum(r.original_transaction.amount for r in self.refund_transaction_refunds.all())
        if amount < 0:
            return 0
        else:
            return amount

    @property
    def total_refunded_amount(self):
        """Berechnet die Summe aller Erstattungen für diese Transaktion"""
        return sum(r.refund_transaction.amount for r in self.original_transaction_refunds.all())

    @property
    def total_amount_after_refunds(self):
        amount = self.amount - self.total_refunded_amount
        if amount < 0:
            return 0
        else:
            return amount

    @property
    def is_fully_refunded(self):
        """Prüft, ob der erstattete Betrag >= dem ursprünglichen Betrag ist"""
        return self.total_refunded_amount >= self.amount
    
    class Meta:
        ordering = ['-timestamp']
        
class Refund(models.Model):
    original_transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='original_transaction_refunds')
    refund_transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='refund_transaction_refunds')
    
    def __str__(self):
        return f"Refund of {self.original_transaction.id} by {self.refund_transaction.id}"
    

class Account(models.Model):
    name = models.CharField(max_length=100)
    iban = models.CharField(max_length=34, unique=True, null=True, blank=True)
    start_balance = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    is_mine = models.BooleanField(default=False)
    
    def get_current_balance(self):
        incoming = Transaction.objects.filter(receiver=self).aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
        outgoing = Transaction.objects.filter(sender=self).aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
        balance = self.start_balance + incoming - outgoing
        return Decimal(balance).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        ordering = ['name']
    
class Category(models.Model):
    name = models.CharField(max_length=100)
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    icon = models.CharField(max_length=50, default='bi bi-tags')
    
    class Meta:
        verbose_name_plural = "Categories"
        
    def __str__(self):
        return f"{self.name}"