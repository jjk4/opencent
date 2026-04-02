from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import datetime
from django.db.models import Sum
import random

# WICHTIG: Passe den App-Namen ('manager' oder wie deine App heißt) hier an!
from manager.models import Account, Category, Transaction, TransactionSplit, Refund

class Command(BaseCommand):
    help = 'Generates realistic financial test data for a full year. Supports multiple languages and includes icons.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--lang',
            type=str,
            default='en',
            choices=['de', 'en'],
            help='Language for generated test data (de or en)',
        )

    def handle(self, *args, **kwargs):
        lang = kwargs['lang']
        self.stdout.write(f"Starting test data generation (Language: {lang.upper()})...")

        # --- ÜBERSETZUNGS-DICTIONARY ---
        t = {
            'de': {
                'acc_giro': 'Girokonto', 'acc_cc': 'Kreditkarte', 'acc_cash': 'Bargeld (Portemonnaie)',
                'acc_employer': 'Arbeitgeber', 'acc_landlord': 'Hausverwaltung', 'acc_supermarket': 'Supermarkt',
                'acc_online': 'Online-Shop', 'acc_gas': 'Tankstelle', 'acc_cafe': 'Bäckerei / Café',
                'cat_income': 'Einnahmen', 'cat_salary': 'Gehalt',
                'cat_housing': 'Wohnen', 'cat_rent': 'Miete',
                'cat_living': 'Lebenshaltung', 'cat_groceries': 'Supermarkt', 'cat_drugstore': 'Drogerie', 'cat_dining': 'Auswärts Essen',
                'cat_mobility': 'Mobilität', 'cat_gas': 'Tanken',
                'cat_shopping': 'Shopping',
                'desc_salary': 'Gehalt', 'desc_rent': 'Miete Warm', 'desc_atm': 'Bargeldabhebung Geldautomat',
                'desc_snack': 'Snack / Kaffee', 'desc_groc': 'Einkauf Supermarkt', 'desc_gas': 'Tanken',
                'desc_online': 'Online-Bestellung (Teilweise zugewiesen)', 'desc_mixed': 'Wocheneinkauf: Lebensmittel & Drogerie',
                'desc_clothes_buy': 'Klamotten (Originalkauf)', 'desc_clothes_ret': 'Retoure Klamotten',
                'desc_cc_bill': 'Kreditkartenabrechnung Ausgleich'
            },
            'en': {
                'acc_giro': 'Checking Account', 'acc_cc': 'Credit Card', 'acc_cash': 'Cash (Wallet)',
                'acc_employer': 'Employer', 'acc_landlord': 'Property Management', 'acc_supermarket': 'Supermarket',
                'acc_online': 'Online Store', 'acc_gas': 'Gas Station', 'acc_cafe': 'Bakery / Cafe',
                'cat_income': 'Income', 'cat_salary': 'Salary',
                'cat_housing': 'Housing', 'cat_rent': 'Rent',
                'cat_living': 'Living', 'cat_groceries': 'Groceries', 'cat_drugstore': 'Drugstore', 'cat_dining': 'Dining Out',
                'cat_mobility': 'Mobility', 'cat_gas': 'Gas',
                'cat_shopping': 'Shopping',
                'desc_salary': 'Salary', 'desc_rent': 'Rent (Warm)', 'desc_atm': 'ATM Cash Withdrawal',
                'desc_snack': 'Snack / Coffee', 'desc_groc': 'Grocery Shopping', 'desc_gas': 'Gas Station',
                'desc_online': 'Online Order (Partially assigned)', 'desc_mixed': 'Weekly Haul: Groceries & Drugstore',
                'desc_clothes_buy': 'Clothes (Original Purchase)', 'desc_clothes_ret': 'Clothes Return',
                'desc_cc_bill': 'Credit Card Settlement'
            }
        }[lang]

        # 1. Test-User erstellen
        user, created = User.objects.get_or_create(username='testuser')
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(self.style.SUCCESS("User 'testuser' created (Password: testpass123)."))

        # Lösche alte Daten des Testusers
        Account.objects.filter(user=user).delete()
        Category.objects.filter(user=user).delete()

        # 2. Konten erstellen
        girokonto = Account.objects.create(name=t['acc_giro'], start_balance=2500.00, is_mine=True, user=user)
        kreditkarte = Account.objects.create(name=t['acc_cc'], start_balance=0.00, is_mine=True, user=user)
        bargeld = Account.objects.create(name=t['acc_cash'], start_balance=50.00, is_mine=True, user=user)
        
        arbeitgeber = Account.objects.create(name=t['acc_employer'], is_mine=False, user=user)
        vermieter = Account.objects.create(name=t['acc_landlord'], is_mine=False, user=user)
        supermarkt_konto = Account.objects.create(name=t['acc_supermarket'], is_mine=False, user=user)
        online_shop_konto = Account.objects.create(name=t['acc_online'], is_mine=False, user=user)
        tankstelle_konto = Account.objects.create(name=t['acc_gas'], is_mine=False, user=user)
        baecker_konto = Account.objects.create(name=t['acc_cafe'], is_mine=False, user=user)

        # 3. Kategorien erstellen (Hierarchisch & MIT ICONS)
        cat_income = Category.objects.create(name=t['cat_income'], icon='bi bi-cash-stack', user=user)
        cat_salary = Category.objects.create(name=t['cat_salary'], icon='bi bi-building', parent_category=cat_income, user=user)

        cat_housing = Category.objects.create(name=t['cat_housing'], icon='bi bi-house', user=user)
        cat_rent = Category.objects.create(name=t['cat_rent'], icon='bi bi-house-door', parent_category=cat_housing, user=user)

        cat_living = Category.objects.create(name=t['cat_living'], icon='bi bi-basket', user=user)
        cat_groceries = Category.objects.create(name=t['cat_groceries'], icon='bi bi-cart', parent_category=cat_living, user=user)
        cat_drugstore = Category.objects.create(name=t['cat_drugstore'], icon='bi bi-bandaid', parent_category=cat_living, user=user)
        cat_cafe = Category.objects.create(name=t['cat_dining'], icon='bi bi-cup-hot', parent_category=cat_living, user=user)

        cat_mobility = Category.objects.create(name=t['cat_mobility'], icon='bi bi-car-front', user=user)
        cat_gas = Category.objects.create(name=t['cat_gas'], icon='bi bi-fuel-pump', parent_category=cat_mobility, user=user)

        cat_shopping = Category.objects.create(name=t['cat_shopping'], icon='bi bi-bag', user=user)

        # 4. Transaktionen generieren
        year = 2025
        self.stdout.write(f"Generating transactions for the year {year}...")

        for month in range(1, 13):
            # Gehalt
            salary_date = timezone.make_aware(datetime(year, month, 1, 8, 0))
            t_salary = Transaction.objects.create(
                sender=arbeitgeber, receiver=girokonto, amount=Decimal('2850.00'),
                timestamp=salary_date, description=f"{t['desc_salary']} {month}/{year}", user=user
            )
            TransactionSplit.objects.create(transaction=t_salary, category=cat_salary, amount=t_salary.amount)

            # Miete
            rent_date = timezone.make_aware(datetime(year, month, 3, 10, 0))
            t_rent = Transaction.objects.create(
                sender=girokonto, receiver=vermieter, amount=Decimal('950.00'),
                timestamp=rent_date, description=t['desc_rent'], user=user
            )
            TransactionSplit.objects.create(transaction=t_rent, category=cat_rent, amount=t_rent.amount)

            # Umbuchung: Bargeld abheben
            atm_date = timezone.make_aware(datetime(year, month, random.randint(2, 10), 14, 30))
            Transaction.objects.create(
                sender=girokonto, receiver=bargeld, amount=Decimal('100.00'),
                timestamp=atm_date, description=t['desc_atm'], user=user
            )

            # Bargeld-Ausgaben
            for _ in range(random.randint(2, 4)):
                day = random.randint(1, 28)
                cash_date = timezone.make_aware(datetime(year, month, day, random.randint(8, 16), random.randint(0, 59)))
                amount = Decimal(random.uniform(3.50, 18.00)).quantize(Decimal('0.01'))
                
                t_cash = Transaction.objects.create(
                    sender=bargeld, receiver=baecker_konto, amount=amount,
                    timestamp=cash_date, description=t['desc_snack'], user=user
                )
                TransactionSplit.objects.create(transaction=t_cash, category=cat_cafe, amount=amount)

            # Lebensmitteleinkäufe
            for _ in range(random.randint(4, 6)):
                day = random.randint(4, 28)
                groc_date = timezone.make_aware(datetime(year, month, day, random.randint(9, 19), random.randint(0, 59)))
                amount = Decimal(random.uniform(25.0, 120.0)).quantize(Decimal('0.01'))
                
                t_groc = Transaction.objects.create(
                    sender=girokonto, receiver=supermarkt_konto, amount=amount,
                    timestamp=groc_date, description=t['desc_groc'], user=user
                )
                TransactionSplit.objects.create(transaction=t_groc, category=cat_groceries, amount=amount)

            # Tanken
            for _ in range(random.randint(1, 2)):
                day = random.randint(1, 28)
                gas_date = timezone.make_aware(datetime(year, month, day, random.randint(7, 20), 0))
                amount = Decimal(random.uniform(50.0, 80.0)).quantize(Decimal('0.01'))
                
                t_gas = Transaction.objects.create(
                    sender=girokonto, receiver=tankstelle_konto, amount=amount,
                    timestamp=gas_date, description=t['desc_gas'], user=user
                )
                TransactionSplit.objects.create(transaction=t_gas, category=cat_gas, amount=amount)

            # Einkaufen online (teilweise kategorisiert, ZUFÄLLIGER BETRAG)
            if month % 2 == 0:
                partial_date = timezone.make_aware(datetime(year, month, 15, 20, 0))
                
                # Gesamtbetrag zwischen 60 und 250
                online_amount = Decimal(random.uniform(60.0, 250.0)).quantize(Decimal('0.01'))
                # Der kategorisierte Betrag ist ein zufälliger Anteil davon
                assigned_amount = Decimal(random.uniform(20.0, float(online_amount) - 10.0)).quantize(Decimal('0.01'))
                
                t_online = Transaction.objects.create(
                    sender=kreditkarte, receiver=online_shop_konto, amount=online_amount,
                    timestamp=partial_date, description=t['desc_online'], user=user
                )
                TransactionSplit.objects.create(transaction=t_online, category=cat_shopping, amount=assigned_amount)

            # --- SONDERFALL JUNI: Split-Transaktion ---
            if month == 6:
                split_tx_date = timezone.make_aware(datetime(year, 6, 20, 18, 45))
                t_mixed_shopping = Transaction.objects.create(
                    sender=girokonto, receiver=supermarkt_konto, amount=Decimal('115.75'),
                    timestamp=split_tx_date, description=t['desc_mixed'], user=user
                )
                TransactionSplit.objects.create(transaction=t_mixed_shopping, category=cat_groceries, amount=Decimal('80.00'))
                TransactionSplit.objects.create(transaction=t_mixed_shopping, category=cat_drugstore, amount=Decimal('35.75'))

            # --- SONDERFALL NOVEMBER: Refund-Szenario ---
            if month == 11:
                buy_date = timezone.make_aware(datetime(year, 11, 10, 14, 0))
                t_original = Transaction.objects.create(
                    sender=kreditkarte, receiver=online_shop_konto, amount=Decimal('200.00'),
                    timestamp=buy_date, description=t['desc_clothes_buy'], user=user
                )
                TransactionSplit.objects.create(transaction=t_original, category=cat_shopping, amount=t_original.amount)

                refund_date = timezone.make_aware(datetime(year, 11, 15, 10, 0))
                t_refund = Transaction.objects.create(
                    sender=online_shop_konto, receiver=kreditkarte, amount=Decimal('80.00'),
                    timestamp=refund_date, description=t['desc_clothes_ret'], user=user
                )
                Refund.objects.create(original_transaction=t_original, refund_transaction=t_refund)

            # --- KREDITKARTENABRECHNUNG (Nur März, Juni, September) ---
            if month % 3 == 0 and month != 12:
                cc_bill_date = timezone.make_aware(datetime(year, month, 28, 23, 50))
                
                cc_spent = Transaction.objects.filter(sender=kreditkarte, timestamp__lte=cc_bill_date).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                cc_paid = Transaction.objects.filter(receiver=kreditkarte, timestamp__lte=cc_bill_date).aggregate(Sum('amount'))['amount__sum'] or Decimal('0.00')
                
                cc_balance = cc_paid - cc_spent 
                
                if cc_balance < 0:
                    transfer_amount = abs(cc_balance)
                    Transaction.objects.create(
                        sender=girokonto, receiver=kreditkarte, amount=transfer_amount,
                        timestamp=cc_bill_date, description=t['desc_cc_bill'], user=user
                    )

        self.stdout.write(self.style.SUCCESS("Test data generated successfully!"))