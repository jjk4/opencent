from django.test import TestCase
from django.contrib.auth.models import User
from .models import Account, Transaction
from decimal import Decimal
from django.utils import timezone

class TransactionModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username='admin', password='pw', email='')
        self.user_a = User.objects.create_user(username='usera', password='pw')
        self.user_b = User.objects.create_user(username='userb', password='pw')
        
        self.account_giro = Account.objects.create(
            name="Girokonto", start_balance=Decimal('1000.00'), is_mine=True, user=self.user_a
        )
        self.account_supermarkt = Account.objects.create(
            name="Supermarkt", start_balance=Decimal('0'), is_mine=False, user=self.user_a
        )

    def test_account_balance_calculation(self):
        """Tests whether the account balance is correctly calculated after a transaction."""
        Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal('50.00'),
            timestamp=timezone.now(),
            user=self.user_a
        )
        
        self.assertEqual(self.account_giro.get_current_balance(), Decimal('950.00'))
        self.assertEqual(self.account_supermarkt.get_current_balance(), Decimal('50.00'))

    def test_security_user_cannot_access_others_transaction(self):
        """Tests that a user cannot access a transaction that belongs to another user."""
        tx = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal('10.00'),
            timestamp=timezone.now(),
            user=self.user_a # Gehört User A!
        )
        
        self.client.login(username='userb', password='pw')
        
        response = self.client.get(f'/transactions/{tx.id}/')
        
        self.assertEqual(response.status_code, 404)