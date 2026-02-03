from django.db import models
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from PIL import Image, ImageOps  # Wichtig für Bildbearbeitung
from django.core.files.base import ContentFile
import os
from django.core.validators import FileExtensionValidator

class Transaction(models.Model):
    sender = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='sent_transactions', null=False, blank=False)
    receiver = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='received_transactions', null=False, blank=False)
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    timestamp = models.DateTimeField()
    description = models.TextField(blank=True, null=True)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    remainder_of_refund = models.DecimalField(decimal_places=2, max_digits=10, default=0) # After calculation of all refunds, how much of the refunded amount is left
    remainder_after_refunds = models.DecimalField(decimal_places=2, max_digits=10, default=0) # After calculation of all refunds, how much of the original amount is left

    categories = models.ManyToManyField(
        'Category', 
        through='TransactionSplit',
        related_name='transactions',
        blank=True
    )
    
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
    
    # @property
    # def remainder_of_refund(self):
    #     """Berechnet den Rest einer Rückerstattungstransaktion, der nach der Rückerstattung noch übrig ist"""
    #     amount = self.amount - sum(r.original_transaction.amount for r in self.refund_transaction_refunds.all())
    #     if amount < 0:
    #         return 0
    #     else:
    #         return amount

    # @property
    # def total_refunded_amount(self):
    #     """Berechnet die Summe aller Erstattungen für diese Transaktion"""
    #     return sum(r.refund_transaction.amount for r in self.original_transaction_refunds.all())

    # @property
    # def total_amount_after_refunds(self):
    #     amount = self.amount - self.total_refunded_amount
    #     if amount < 0:
    #         return 0
    #     else:
    #         return amount

    @property
    def is_fully_refunded(self):
        return self.remainder_after_refunds == 0

    
    # Helper functions for categories
    @property
    def assigned_amount(self):
        """Summe aller Kategorien-Splits"""
        return self.splits.aggregate(sum=models.Sum('amount'))['sum'] or Decimal(0)

    @property
    def unassigned_amount(self):
        """Wieviel vom Betrag ist noch keiner Kategorie zugeordnet?"""
        remainder = self.amount - self.assigned_amount
        return max(Decimal(0), remainder)

    @property
    def is_fully_categorized(self):
        """Prüft, ob die Summe der Splits exakt dem Transaktionsbetrag entspricht"""
        return self.amount == self.assigned_amount
    
    class Meta:
        ordering = ['-timestamp']

class TransactionSplit(models.Model):
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='splits')
    category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='transaction_splits')
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    
    class Meta:
        unique_together = ('transaction', 'category')
        verbose_name = "Transaction Split"
        verbose_name_plural = "Transaction Splits"

    def __str__(self):
        return f"{self.transaction.id} - {self.category.name}: {self.amount} €"

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
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    icon = models.FileField(
        upload_to='account_icons/', 
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'svg'])]
    )
    
    def get_current_balance(self):
        incoming = Transaction.objects.filter(receiver=self).aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
        outgoing = Transaction.objects.filter(sender=self).aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
        balance = self.start_balance + incoming - outgoing
        return Decimal(balance).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    def save(self, *args, **kwargs):
        if self.icon:
            is_svg = self.icon.name.lower().endswith('.svg')

            if not is_svg:
                try:
                    img = Image.open(self.icon)
                    if img.format != 'WEBP' or img.width > 128 or img.height > 128:
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGBA")
                        else:
                            img = img.convert("RGB")
                        img.thumbnail((128, 128), Image.Resampling.LANCZOS)
                        buffer = BytesIO()
                        img.save(buffer, format='WEBP', quality=90)
                        new_filename = os.path.splitext(self.icon.name)[0] + '.webp'
                        self.icon.save(new_filename, ContentFile(buffer.getvalue()), save=False)
                
                except Exception as e:
                    print(f"Fehler bei der Bildverarbeitung: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        ordering = ['name']
    
class Category(models.Model):
    name = models.CharField(max_length=100)
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    icon = models.CharField(max_length=50, default='bi bi-tags')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def get_all_subcategories_recursive(self):
        subcategories = []
        def fetch_subcategories(category):
            for subcat in category.subcategories.all():
                subcategories.append(subcat)
                fetch_subcategories(subcat)
        fetch_subcategories(self)
        return subcategories

    def __str__(self):
        return f"{self.name}"