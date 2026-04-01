from django.db import models
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from PIL import Image, ImageOps  # Wichtig für Bildbearbeitung
from django.core.files.base import ContentFile
import os
from django.core.validators import FileExtensionValidator
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from collections import defaultdict

class Transaction(models.Model):
    sender = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='sent_transactions', null=False, blank=False, db_index=True)
    receiver = models.ForeignKey('Account', on_delete=models.CASCADE, related_name='received_transactions', null=False, blank=False, db_index=True)
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

    @property
    def is_fully_refunded(self):
        return self.remainder_after_refunds == 0
    
    @property
    def type(self):
        if self.sender.is_mine and self.receiver.is_mine:
            return 'TRANSFER' 
        elif self.sender.is_mine and not self.receiver.is_mine:
            return 'EXPENSE'
        elif not self.sender.is_mine and self.receiver.is_mine:
            return 'INCOME'
        return 'EXTERNAL'

    # Helper functions for categories
    @property
    def assigned_amount(self):
        """Sum of all category splits"""
        return self.splits.aggregate(sum=models.Sum('amount'))['sum'] or Decimal(0)

    @property
    def unassigned_amount(self):
        """How much of the amount is not yet assigned to a category?"""
        remainder = self.amount - self.assigned_amount
        return max(Decimal(0), remainder)

    @property
    def is_fully_categorized(self):
        """Checks if the sum of the splits exactly matches the transaction amount"""
        return self.amount == self.assigned_amount
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = _("Transaction")
        verbose_name_plural = _("Transactions")

class TransactionSplit(models.Model):
    transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='splits')
    category = models.ForeignKey('Category', on_delete=models.PROTECT, related_name='transaction_splits')
    amount = models.DecimalField(decimal_places=2, max_digits=10)
    
    class Meta:
        unique_together = ('transaction', 'category')
        verbose_name = _("Transaction Split")
        verbose_name_plural = _("Transaction Splits")

    def __str__(self):
        return f"{self.transaction.id} - {self.category.name}: {self.amount} €"

class Refund(models.Model):
    original_transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='original_transaction_refunds')
    refund_transaction = models.ForeignKey('Transaction', on_delete=models.CASCADE, related_name='refund_transaction_refunds')
    
    class Meta:
        verbose_name = _("Refund")
        verbose_name_plural = _("Refunds")

    def __str__(self):
        return f"Refund of {self.original_transaction.id} by {self.refund_transaction.id}"
    

class Account(models.Model):
    name = models.CharField(max_length=100)
    account_nr = models.CharField(max_length=34, unique=True, null=True, blank=True)
    start_balance = models.DecimalField(decimal_places=2, max_digits=10, default=0)
    is_mine = models.BooleanField(default=False)
    is_closed = models.BooleanField(default=False)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    icon = models.FileField(
        upload_to='account_icons/', 
        null=True, 
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'webp', 'svg'])]
    )
    
    def get_current_balance(self):
        transactions_in = Transaction.objects.filter(receiver=self)
        transactions_out = Transaction.objects.filter(sender=self)
        
        if not self.user.settings.future_transactions_in_balance:
            transactions_in = transactions_in.filter(timestamp__lte=models.functions.Now())
            transactions_out = transactions_out.filter(timestamp__lte=models.functions.Now())
        
        incoming = transactions_in.aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
        outgoing = transactions_out.aggregate(models.Sum('amount'))['amount__sum'] or Decimal(0)
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
                    print(f"Error during image processing: {e}")

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}"
    
    class Meta:
        ordering = ['name']
        verbose_name = _("Account")
        verbose_name_plural = _("Accounts")
    
class Category(models.Model):
    name = models.CharField(max_length=100)
    parent_category = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    icon = models.CharField(max_length=50, default='bi bi-tags')
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")
    
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
    
class UserSettings(models.Model):
    THEME_CHOICES = [
        ('auto', _('System Default')),
        ('light', _('Light')),
        ('dark', _('Dark')),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')

    language = models.CharField(
        max_length=10, 
        choices=settings.LANGUAGES, 
        default=settings.LANGUAGE_CODE
    )
    
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='auto')
    
    future_transactions_in_balance = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("User Setting")
        verbose_name_plural = _("User Settings")

    def __str__(self):
        return f"Settings for {self.user.username}"

@receiver(post_save, sender=User)
def create_user_settings(sender, instance, created, **kwargs):
    if created:
        UserSettings.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_settings(sender, instance, **kwargs):
    instance.settings.save()

@receiver(post_save, sender=Refund)
def trigger_refund_calc_on_save(sender, instance, **kwargs):
    """Wird aufgerufen, wenn ein Refund erstellt/geändert wird."""
    affected_ids = {instance.original_transaction_id, instance.refund_transaction_id}
    user = instance.original_transaction.user 
    recalculate_refund_clusters(user, affected_ids)

@receiver(post_delete, sender=Refund)
def trigger_refund_calc_on_delete(sender, instance, **kwargs):
    affected_ids = {instance.original_transaction_id, instance.refund_transaction_id}
    try:
        user = instance.original_transaction.user
    except Transaction.DoesNotExist:
        try:
            user = instance.refund_transaction.user
        except Transaction.DoesNotExist:
            return
            
    recalculate_refund_clusters(user, affected_ids)

@receiver(post_save, sender=Transaction)
def trigger_refund_calc_on_transaction_save(sender, instance, created, **kwargs):
    """
    Wird aufgerufen, wenn eine Transaktion bearbeitet wird.
    Falls sie Teil eines Refund-Clusters ist, muss neu berechnet werden.
    """
    if not created:
        is_involved = Refund.objects.filter(
            models.Q(original_transaction=instance) | 
            models.Q(refund_transaction=instance)
        ).exists()

        if is_involved:
            recalculate_refund_clusters(instance.user, {instance.id})

@receiver(post_delete, sender=Transaction)
def trigger_refund_calc_on_transaction_delete(sender, instance, **kwargs):
    """
    Falls eine Transaktion gelöscht wird, die Teil eines Clusters war,
    müssen die verbleibenden Transaktionen im Cluster informiert werden.
    """
    affected_ids = set()
    links = Refund.objects.filter(
        models.Q(original_transaction=instance) | 
        models.Q(refund_transaction=instance)
    )
    
    for link in links:
        affected_ids.add(link.original_transaction_id)
        affected_ids.add(link.refund_transaction_id)
    
    affected_ids.discard(instance.id)
    
    if affected_ids:
        recalculate_refund_clusters(instance.user, affected_ids)

def recalculate_refund_clusters(user, affected_transaction_ids):
    """
    Berechnet die Refund-Werte für die Netzwerke/Bäume neu, 
    in denen sich die affected_transaction_ids befinden.
    """
    if not affected_transaction_ids:
        return

    all_links = list(Refund.objects.filter(original_transaction__user=user).values_list('refund_transaction_id', 'original_transaction_id'))
    
    refund_to_originals = defaultdict(list)
    original_to_refunds = defaultdict(list)
    
    for r_id, o_id in all_links:
        refund_to_originals[r_id].append(o_id)
        original_to_refunds[o_id].append(r_id)
        
    visited_r_ids = set()
    visited_o_ids = set()
    
    def get_cluster(start_id):
        queue = [start_id]
        comp_r = set()
        comp_o = set()
        
        while queue:
            curr = queue.pop(0)
            
            if curr in refund_to_originals and curr not in visited_r_ids:
                visited_r_ids.add(curr)
                comp_r.add(curr)
                for o_id in refund_to_originals[curr]:
                    if o_id not in visited_o_ids:
                        queue.append(o_id)
                        
            if curr in original_to_refunds and curr not in visited_o_ids:
                visited_o_ids.add(curr)
                comp_o.add(curr)
                for r_id in original_to_refunds[curr]:
                    if r_id not in visited_r_ids:
                        queue.append(r_id)
                        
        return comp_r, comp_o

    transactions_to_update = {}

    for t_id in affected_transaction_ids:
        if t_id in visited_r_ids or t_id in visited_o_ids:
            continue
            
        comp_r, comp_o = get_cluster(t_id)
        
        if not comp_r and not comp_o:
            try:
                t = Transaction.objects.get(id=t_id)
                t.remainder_after_refunds = t.amount
                t.remainder_of_refund = 0
                transactions_to_update[t.id] = t
            except Transaction.DoesNotExist:
                pass
            continue

        cluster_refunds = list(Transaction.objects.filter(id__in=comp_r).order_by('timestamp'))
        cluster_originals = {t.id: t for t in Transaction.objects.filter(id__in=comp_o)}
        
        for r_tx in cluster_refunds:
            r_tx.remainder_of_refund = r_tx.amount
            r_tx.remainder_after_refunds = 0
            
        for o_tx in cluster_originals.values():
            o_tx.remainder_after_refunds = o_tx.amount
            o_tx.remainder_of_refund = 0
            
        for r_tx in cluster_refunds:
            for o_id in refund_to_originals[r_tx.id]:
                o_tx = cluster_originals[o_id]
                
                if o_tx.remainder_after_refunds >= r_tx.remainder_of_refund:
                    o_tx.remainder_after_refunds -= r_tx.remainder_of_refund
                    r_tx.remainder_of_refund = 0
                    break
                else:
                    r_tx.remainder_of_refund -= o_tx.remainder_after_refunds
                    o_tx.remainder_after_refunds = 0
                    
        for r_tx in cluster_refunds:
            transactions_to_update[r_tx.id] = r_tx
        for o_tx in cluster_originals.values():
            transactions_to_update[o_tx.id] = o_tx

    if transactions_to_update:
        Transaction.objects.bulk_update(
            transactions_to_update.values(), 
            ['remainder_of_refund', 'remainder_after_refunds']
        )
