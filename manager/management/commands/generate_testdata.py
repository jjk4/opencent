from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Sum
import random

from manager.models import Account, Category, Transaction, TransactionSplit, Refund

class Command(BaseCommand):
    help = 'Generates financial test data from Jan 1st of the previous year until today.'

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
        now = timezone.now()
        
        # --- STARTDATUM: 1. Januar des Vorjahres ---
        start_date = timezone.make_aware(datetime(now.year - 1, 1, 1, 0, 0))
        
        self.stdout.write(f"Starting test data generation (Language: {lang.upper()})...")
        self.stdout.write(f"Range: {start_date.date()} to {now.date()}")

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
                'desc_online': 'Online-Bestellung', 'desc_mixed': 'Wocheneinkauf: Lebensmittel & Drogerie',
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
                'desc_online': 'Online Order', 'desc_mixed': 'Weekly Haul: Groceries & Drugstore',
                'desc_clothes_buy': 'Clothes (Original Purchase)', 'desc_clothes_ret': 'Clothes Return',
                'desc_cc_bill': 'Credit Card Settlement'
            }
        }[lang]

        # 1. Test-User erstellen
        user, created = User.objects.get_or_create(username='testuser')
        if created:
            user.set_password('testpass123')
            user.save()
            self.stdout.write(self.style.SUCCESS("User 'testuser' created."))

        # Alte Daten löschen
        Account.objects.filter(user=user).delete()
        Category.objects.filter(user=user).delete()

        # 2. Konten erstellen
        girokonto = Account.objects.create(name=t['acc_giro'], start_balance=2500.00, is_mine=True, user=user)
        kreditkarte = Account.objects.create(name=t['acc_cc'], start_balance=0.00, is_mine=True, user=user)
        bargeld = Account.objects.create(name=t['acc_cash'], start_balance=50.00, is_mine=True, user=user)
        
        ext_employer = Account.objects.create(name=t['acc_employer'], is_mine=False, user=user)
        ext_landlord = Account.objects.create(name=t['acc_landlord'], is_mine=False, user=user)
        ext_supermarket = Account.objects.create(name=t['acc_supermarket'], is_mine=False, user=user)
        ext_online = Account.objects.create(name=t['acc_online'], is_mine=False, user=user)
        ext_gas = Account.objects.create(name=t['acc_gas'], is_mine=False, user=user)
        ext_cafe = Account.objects.create(name=t['acc_cafe'], is_mine=False, user=user)

        # 3. Kategorien erstellen (mit Icons)
        cat_inc = Category.objects.create(name=t['cat_income'], icon='bi bi-cash-stack', user=user)
        cat_sal = Category.objects.create(name=t['cat_salary'], icon='bi bi-building', parent_category=cat_inc, user=user)
        cat_hou = Category.objects.create(name=t['cat_housing'], icon='bi bi-house', user=user)
        cat_rnt = Category.objects.create(name=t['cat_rent'], icon='bi bi-house-door', parent_category=cat_hou, user=user)
        cat_liv = Category.objects.create(name=t['cat_living'], icon='bi bi-basket', user=user)
        cat_grc = Category.objects.create(name=t['cat_groceries'], icon='bi bi-cart', parent_category=cat_liv, user=user)
        cat_drg = Category.objects.create(name=t['cat_drugstore'], icon='bi bi-bandaid', parent_category=cat_liv, user=user)
        cat_din = Category.objects.create(name=t['cat_dining'], icon='bi bi-cup-hot', parent_category=cat_liv, user=user)
        cat_mob = Category.objects.create(name=t['cat_mobility'], icon='bi bi-car-front', user=user)
        cat_fue = Category.objects.create(name=t['cat_gas'], icon='bi bi-fuel-pump', parent_category=cat_mob, user=user)
        cat_shp = Category.objects.create(name=t['cat_shopping'], icon='bi bi-bag', user=user)

        # --- ZEIT-LOOP: Von start_date bis heute, Monat für Monat ---
        current_processing_date = start_date
        month_index = 1
        
        while current_processing_date <= now:
            year = current_processing_date.year
            month = current_processing_date.month
            
            # Gehalt (1. des Monats)
            salary_date = current_processing_date.replace(day=1, hour=8, minute=0)
            if salary_date <= now:
                t_sal = Transaction.objects.create(sender=ext_employer, receiver=girokonto, amount=Decimal('2850.00'), timestamp=salary_date, description=f"{t['desc_salary']} {month}/{year}", user=user)
                TransactionSplit.objects.create(transaction=t_sal, category=cat_sal, amount=t_sal.amount)

            # Miete (3. des Monats)
            rent_date = current_processing_date.replace(day=3, hour=10, minute=0)
            if rent_date <= now:
                t_rnt = Transaction.objects.create(sender=girokonto, receiver=ext_landlord, amount=Decimal('950.00'), timestamp=rent_date, description=t['desc_rent'], user=user)
                TransactionSplit.objects.create(transaction=t_rnt, category=cat_rnt, amount=t_rnt.amount)

            # ATM Abhebung
            atm_date = current_processing_date.replace(day=random.randint(2, 10), hour=14, minute=30)
            if atm_date <= now:
                Transaction.objects.create(sender=girokonto, receiver=bargeld, amount=Decimal('100.00'), timestamp=atm_date, description=t['desc_atm'], user=user)

            # Bargeld Ausgaben
            for _ in range(random.randint(2, 4)):
                day = random.randint(1, 28)
                c_date = current_processing_date.replace(day=day, hour=random.randint(8, 16))
                if c_date <= now:
                    amt = Decimal(random.uniform(3.50, 20.00)).quantize(Decimal('0.01'))
                    t_c = Transaction.objects.create(sender=bargeld, receiver=ext_cafe, amount=amt, timestamp=c_date, description=t['desc_snack'], user=user)
                    TransactionSplit.objects.create(transaction=t_c, category=cat_din, amount=amt)

            # Supermarkt (4-6x)
            for _ in range(random.randint(4, 6)):
                day = random.randint(1, 28)
                s_date = current_processing_date.replace(day=day, hour=random.randint(9, 19))
                if s_date <= now:
                    amt = Decimal(random.uniform(20.0, 130.0)).quantize(Decimal('0.01'))
                    t_s = Transaction.objects.create(sender=girokonto, receiver=ext_supermarket, amount=amt, timestamp=s_date, description=t['desc_groc'], user=user)
                    TransactionSplit.objects.create(transaction=t_s, category=cat_grc, amount=amt)

            # Online Shopping auf Kreditkarte (Zufällige Beträge)
            for _ in range(random.randint(1, 3)):
                day = random.randint(1, 28)
                o_date = current_processing_date.replace(day=day, hour=20)
                if o_date <= now:
                    amt = Decimal(random.uniform(15.0, 300.0)).quantize(Decimal('0.01'))
                    t_o = Transaction.objects.create(sender=kreditkarte, receiver=ext_online, amount=amt, timestamp=o_date, description=t['desc_online'], user=user)
                    # Teilweise Kategorisierung (ca. 70% zugewiesen)
                    TransactionSplit.objects.create(transaction=t_o, category=cat_shp, amount=(amt * Decimal('0.7')).quantize(Decimal('0.01')))

            # --- SPEZIALFÄLLE ---
            # Split-Transaktion im Juni des Vorjahres
            if month == 6 and year == now.year - 1:
                sp_date = current_processing_date.replace(day=20, hour=18)
                t_sp = Transaction.objects.create(sender=girokonto, receiver=ext_supermarket, amount=Decimal('115.75'), timestamp=sp_date, description=t['desc_mixed'], user=user)
                TransactionSplit.objects.create(transaction=t_sp, category=cat_grc, amount=Decimal('80.00'))
                TransactionSplit.objects.create(transaction=t_sp, category=cat_drg, amount=Decimal('35.75'))

            # Refund im November des Vorjahres
            if month == 11 and year == now.year - 1:
                b_date = current_processing_date.replace(day=10)
                t_orig = Transaction.objects.create(sender=kreditkarte, receiver=ext_online, amount=Decimal('200.00'), timestamp=b_date, description=t['desc_clothes_buy'], user=user)
                TransactionSplit.objects.create(transaction=t_orig, category=cat_shp, amount=t_orig.amount)
                
                r_date = current_processing_date.replace(day=15)
                t_ref = Transaction.objects.create(sender=ext_online, receiver=kreditkarte, amount=Decimal('80.00'), timestamp=r_date, description=t['desc_clothes_ret'], user=user)
                Refund.objects.create(original_transaction=t_orig, refund_transaction=t_ref)

            # --- KREDITKARTEN-ABRECHNUNG ---
            # Ausgleich alle 3 Monate (März, Juni, Sept), aber NICHT im letzten Quartal des aktuellen Jahres
            if month in [3, 6, 9]:
                # Wir gleichen nur aus, wenn es nicht der absolut letzte Monat im Datensatz ist
                cc_bill_date = current_processing_date.replace(day=28, hour=23, minute=50)
                if cc_bill_date < now - timedelta(days=30):
                    spent = Transaction.objects.filter(sender=kreditkarte, timestamp__lte=cc_bill_date).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                    paid = Transaction.objects.filter(receiver=kreditkarte, timestamp__lte=cc_bill_date).aggregate(Sum('amount'))['amount__sum'] or Decimal('0')
                    balance = paid - spent
                    if balance < 0:
                        Transaction.objects.create(sender=girokonto, receiver=kreditkarte, amount=abs(balance), timestamp=cc_bill_date, description=t['desc_cc_bill'], user=user)

            # Nächster Monat
            if month == 12:
                current_processing_date = current_processing_date.replace(year=year + 1, month=1)
            else:
                current_processing_date = current_processing_date.replace(month=month + 1)
            month_index += 1

        self.stdout.write(self.style.SUCCESS("Test data generated successfully!"))