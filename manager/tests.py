from django.test import TestCase, Client
from django.contrib.auth.models import User
from .models import Account, Transaction, Category, TransactionSplit, Refund, UserSettings
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from io import BytesIO
import json
from PIL import Image
from django.db.utils import IntegrityError
from .forms import (
    TransactionForm, 
    TransactionSplitForm, 
    TransactionSplitFormSet, 
    AccountForm, 
    CategoryForm
)

class UserSettingsModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")

    def test_user_settings_created_on_user_creation(self):
        """Prüft, ob durch das post_save Signal automatisch UserSettings generiert werden."""
        new_user = User.objects.create_user(username="newuser", password="pw")
        self.assertTrue(hasattr(new_user, 'settings'))
        self.assertEqual(new_user.settings.theme, 'auto')
        self.assertFalse(new_user.settings.future_transactions_in_balance)


class AccountModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")

        self.account_giro = Account.objects.create(
            name="Girokonto", start_balance=Decimal("1000.00"), is_mine=True, user=self.user_a
        )
        self.account_supermarkt = Account.objects.create(
            name="Supermarkt", start_balance=Decimal("0"), is_mine=False, user=self.user_a
        )

    def test_model_str_representations(self):
        self.assertEqual(str(self.account_giro), "Girokonto")

    def test_account_balance_calculation_standard(self):
        """Testet die normale Kontostandsberechnung."""
        Transaction.objects.create(
            sender=self.account_giro, receiver=self.account_supermarkt,
            amount=Decimal("50.00"), timestamp=timezone.now(), user=self.user_a
        )
        self.assertEqual(self.account_giro.get_current_balance(), Decimal("950.00"))
        self.assertEqual(self.account_supermarkt.get_current_balance(), Decimal("50.00"))

    def test_account_balance_with_future_transactions(self):
        """Testet, ob zukünftige Transaktionen korrekt basierend auf UserSettings behandelt werden."""
        # Transaktion in 5 Tagen
        future_date = timezone.now() + timedelta(days=5)
        Transaction.objects.create(
            sender=self.account_giro, receiver=self.account_supermarkt,
            amount=Decimal("100.00"), timestamp=future_date, user=self.user_a
        )

        # Standard: Zukünftige werden ignoriert
        self.assertEqual(self.account_giro.get_current_balance(), Decimal("1000.00"))

        # User ändert Einstellung
        self.user_a.settings.future_transactions_in_balance = True
        self.user_a.settings.save()

        # Jetzt sollten die 100€ abgezogen sein
        self.assertEqual(self.account_giro.get_current_balance(), Decimal("900.00"))

    def test_account_icon_image_processing(self):
        """Testet die Bildbearbeitung für Konto-Icons."""
        svg_file = SimpleUploadedFile("icon.svg", b"<svg></svg>", content_type="image/svg+xml")
        account_svg = Account.objects.create(name="SVG Konto", user=self.user_a, icon=svg_file)
        self.assertTrue(account_svg.icon.name.endswith('.svg'))

        image_io = BytesIO()
        dummy_img = Image.new('RGB', (500, 500), color='red')
        dummy_img.save(image_io, format='PNG')
        image_io.seek(0)
        
        png_file = SimpleUploadedFile("icon.png", image_io.read(), content_type="image/png")
        account_png = Account.objects.create(name="PNG Konto", user=self.user_a, icon=png_file)
        
        self.assertTrue(account_png.icon.name.endswith('.webp'))
        
        saved_img = Image.open(account_png.icon)
        self.assertEqual(saved_img.format, 'WEBP')
        self.assertEqual(saved_img.size, (128, 128))

        bad_file = SimpleUploadedFile("bad_icon.jpg", b"Das ist kein Bild", content_type="image/jpeg")
        account_bad = Account.objects.create(name="Bad Konto", user=self.user_a, icon=bad_file)
        self.assertTrue(account_bad.icon.name.endswith('.jpg'))


class TransactionModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")

        self.acc_mine_1 = Account.objects.create(name="Girokonto", is_mine=True, user=self.user_a)
        self.acc_mine_2 = Account.objects.create(name="Tagesgeld", is_mine=True, user=self.user_a)
        self.acc_ext_1 = Account.objects.create(name="Supermarkt", is_mine=False, user=self.user_a)
        self.acc_ext_2 = Account.objects.create(name="Arbeitgeber", is_mine=False, user=self.user_a)

    def test_transaction_types(self):
        """Testet, ob die Property 'type' basierend auf 'is_mine' korrekt evaluiert wird."""
        # EXPENSE: Mine -> Ext
        tx_expense = Transaction.objects.create(sender=self.acc_mine_1, receiver=self.acc_ext_1, amount=Decimal("10"), timestamp=timezone.now(), user=self.user_a)
        self.assertEqual(tx_expense.type, 'EXPENSE')

        # INCOME: Ext -> Mine
        tx_income = Transaction.objects.create(sender=self.acc_ext_2, receiver=self.acc_mine_1, amount=Decimal("10"), timestamp=timezone.now(), user=self.user_a)
        self.assertEqual(tx_income.type, 'INCOME')

        # TRANSFER: Mine -> Mine
        tx_transfer = Transaction.objects.create(sender=self.acc_mine_1, receiver=self.acc_mine_2, amount=Decimal("10"), timestamp=timezone.now(), user=self.user_a)
        self.assertEqual(tx_transfer.type, 'TRANSFER')

        # EXTERNAL: Ext -> Ext
        tx_external = Transaction.objects.create(sender=self.acc_ext_2, receiver=self.acc_ext_1, amount=Decimal("10"), timestamp=timezone.now(), user=self.user_a)
        self.assertEqual(tx_external.type, 'EXTERNAL')

    def test_transaction_split_properties(self):
        cat1 = Category.objects.create(name="Lebensmittel", user=self.user_a)
        cat2 = Category.objects.create(name="Drogerie", user=self.user_a)

        tx = Transaction.objects.create(sender=self.acc_mine_1, receiver=self.acc_ext_1, amount=Decimal("100.00"), timestamp=timezone.now(), user=self.user_a)

        self.assertEqual(tx.assigned_amount, Decimal("0"))
        self.assertEqual(tx.unassigned_amount, Decimal("100.00"))
        self.assertFalse(tx.is_fully_categorized)

        TransactionSplit.objects.create(transaction=tx, category=cat1, amount=Decimal("60.00"))
        self.assertEqual(tx.assigned_amount, Decimal("60.00"))
        self.assertEqual(tx.unassigned_amount, Decimal("40.00"))
        self.assertFalse(tx.is_fully_categorized)

        TransactionSplit.objects.create(transaction=tx, category=cat2, amount=Decimal("40.00"))
        self.assertEqual(tx.assigned_amount, Decimal("100.00"))
        self.assertEqual(tx.unassigned_amount, Decimal("0.00"))
        self.assertTrue(tx.is_fully_categorized)

    def test_transaction_split_unique_together(self):
        """Testet, dass dieselbe Kategorie nicht zweimal derselben Transaktion zugewiesen werden kann."""
        cat = Category.objects.create(name="Lebensmittel", user=self.user_a)
        tx = Transaction.objects.create(sender=self.acc_mine_1, receiver=self.acc_ext_1, amount=Decimal("100.00"), timestamp=timezone.now(), user=self.user_a)
        
        TransactionSplit.objects.create(transaction=tx, category=cat, amount=Decimal("50.00"))
        
        with self.assertRaises(IntegrityError):
            TransactionSplit.objects.create(transaction=tx, category=cat, amount=Decimal("50.00"))


class RefundClusterTests(TestCase):
    """Fokus auf die komplexe Signal-Logik für Refund-Cluster."""
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user = User.objects.create_user(username="usera", password="pw")
        self.acc_mine = Account.objects.create(name="Giro", is_mine=True, user=self.user)
        self.acc_ext = Account.objects.create(name="Shop", is_mine=False, user=self.user)

    def test_refund_creation_updates_remainders(self):
        """Testet, ob die Erstellung eines Refunds die Remainder korrekt berechnet."""
        # 1. Ausgabe: 100€
        tx_out = Transaction.objects.create(sender=self.acc_mine, receiver=self.acc_ext, amount=Decimal("100"), timestamp=timezone.now(), user=self.user)
        # 2. Rückerstattung: 40€
        tx_in = Transaction.objects.create(sender=self.acc_ext, receiver=self.acc_mine, amount=Decimal("40"), timestamp=timezone.now(), user=self.user)

        # Verknüpfen (Triggert post_save Signal am Refund)
        Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)

        # Neu aus der DB laden
        tx_out.refresh_from_db()
        tx_in.refresh_from_db()

        self.assertEqual(tx_out.remainder_after_refunds, Decimal("60"))
        self.assertEqual(tx_in.remainder_of_refund, Decimal("0"))
        self.assertFalse(tx_out.is_fully_refunded)

    def test_refund_deletion_restores_remainders(self):
        """Testet, ob das Löschen eines Refunds die Beträge wiederherstellt."""
        tx_out = Transaction.objects.create(sender=self.acc_mine, receiver=self.acc_ext, amount=Decimal("100"), timestamp=timezone.now(), user=self.user)
        tx_in = Transaction.objects.create(sender=self.acc_ext, receiver=self.acc_mine, amount=Decimal("100"), timestamp=timezone.now(), user=self.user)
        
        ref = Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)
        
        tx_out.refresh_from_db()
        self.assertEqual(tx_out.remainder_after_refunds, Decimal("0"))
        self.assertTrue(tx_out.is_fully_refunded)

        # Refund löschen (Triggert post_delete Signal am Refund)
        ref.delete()

        tx_out.refresh_from_db()
        tx_in.refresh_from_db()
        
        self.assertEqual(tx_out.remainder_after_refunds, Decimal("100"))
        self.assertEqual(tx_in.remainder_of_refund, Decimal("0"))
        self.assertFalse(tx_out.is_fully_refunded)

    def test_transaction_amount_update_triggers_recalculation(self):
        """Testet, ob die Änderung des Betrags einer Transaktion das Cluster neu berechnet."""
        tx_out = Transaction.objects.create(sender=self.acc_mine, receiver=self.acc_ext, amount=Decimal("100"), timestamp=timezone.now(), user=self.user)
        tx_in = Transaction.objects.create(sender=self.acc_ext, receiver=self.acc_mine, amount=Decimal("60"), timestamp=timezone.now(), user=self.user)
        Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)

        # Ausgabe war statt 100€ eigentlich nur 50€
        tx_out.amount = Decimal("50")
        tx_out.save() # Triggert post_save Signal an Transaction

        tx_out.refresh_from_db()
        tx_in.refresh_from_db()

        # Jetzt sollte tx_out komplett erstattet sein (0 Rest)
        self.assertEqual(tx_out.remainder_after_refunds, Decimal("0"))
        # Und die Erstattung hat noch 10€ "übrig", da sie 60€ war, aber nur 50€ verrechnet wurden
        self.assertEqual(tx_in.remainder_of_refund, Decimal("10"))
    
    def test_transaction_deletion_triggers_recalculation(self):
        """Testet, ob das Löschen einer Transaktion das Cluster für die verbleibenden anpasst."""
        tx_out = Transaction.objects.create(sender=self.acc_mine, receiver=self.acc_ext, amount=Decimal("100"), timestamp=timezone.now(), user=self.user)
        tx_in = Transaction.objects.create(sender=self.acc_ext, receiver=self.acc_mine, amount=Decimal("40"), timestamp=timezone.now(), user=self.user)
        Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)

        tx_out.refresh_from_db()
        self.assertEqual(tx_out.remainder_after_refunds, Decimal("60"))

        tx_in.delete()

        tx_out.refresh_from_db()
        self.assertEqual(tx_out.remainder_after_refunds, Decimal("100"))
        self.assertFalse(tx_out.is_fully_refunded)


class CategoryModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")
    
    def test_model_str_representations(self):
        cat = Category.objects.create(name="TestCat", user=self.user_a)
        self.assertEqual(str(cat), "TestCat")

    def test_category_recursion(self):
        parent = Category.objects.create(name="Wohnen", user=self.user_a)
        child = Category.objects.create(name="Strom", parent_category=parent, user=self.user_a)
        grandchild = Category.objects.create(name="Nachzahlung", parent_category=child, user=self.user_a)

        subcats = parent.get_all_subcategories_recursive()

        self.assertEqual(len(subcats), 2)
        self.assertIn(child, subcats)
        self.assertIn(grandchild, subcats)

class GeneralViewTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username='admin', password='pw', email='')
        self.user = User.objects.create_user(username='usera', password='pw')
        
    def test_homepage_loads_correctly(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('homepage'))
        self.assertEqual(response.status_code, 200)
    
    def test_login_required_redirects(self):
        """Tests that all protected views redirect to the login page when accessed by an anonymous user."""
        protected_urls = [
            'accounts', 'account_add', 'transactions', 'transaction_add',
            'categories', 'category_add', 'charts', 'chart_balance_over_time', 'chart_sankey'
        ]
        
        for url_name in protected_urls:
            url = reverse(url_name)
            with self.subTest(url_name=url_name):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue('/users/login' in response.url)
                
class TransactionFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")
        
        self.acc_mine = Account.objects.create(name="Giro", is_mine=True, user=self.user)
        self.acc_ext = Account.objects.create(name="Shop", is_mine=False, user=self.user)
        
        self.timestamp_str = timezone.now().strftime('%Y-%m-%dT%H:%M')

    def test_valid_transaction_form(self):
        """Testet ein komplett valides Standard-Transaktions-Formular."""
        data = {
            'sender': self.acc_mine.id,
            'receiver': self.acc_ext.id,
            'amount': '50.00',
            'timestamp': self.timestamp_str,
            'description': 'Einkauf',
            'is_refund': False
        }
        form = TransactionForm(data=data, user=self.user)
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_identical_sender_and_receiver(self):
        """Testet die custom clean() Methode: Sender und Empfänger dürfen nicht gleich sein."""
        data = {
            'sender': self.acc_mine.id,
            'receiver': self.acc_mine.id, # Identisch!
            'amount': '50.00',
            'timestamp': self.timestamp_str,
        }
        form = TransactionForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors) # Fehler taucht in non_field_errors auf
        self.assertIn("Sender and receiver cannot be identical.", form.errors['__all__'][0])

    def test_invalid_negative_amount(self):
        """Testet, dass der Betrag nicht negativ sein darf."""
        data = {
            'sender': self.acc_mine.id,
            'receiver': self.acc_ext.id,
            'amount': '-10.00', # Negativ!
            'timestamp': self.timestamp_str,
        }
        form = TransactionForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)
        self.assertIn("The amount cannot be negative.", form.errors['__all__'][0])

    def test_refund_validation(self):
        """Testet, dass bei is_refund=True zwingend refund_links übergeben werden müssen."""
        # Setup einer Original-Transaktion, die wir referenzieren könnten
        orig_tx = Transaction.objects.create(
            sender=self.acc_mine, receiver=self.acc_ext, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user
        )

        # Fall 1: is_refund ist True, aber keine Links ausgewählt -> Fehler
        data_invalid = {
            'sender': self.acc_ext.id,
            'receiver': self.acc_mine.id,
            'amount': '50.00',
            'timestamp': self.timestamp_str,
            'is_refund': True,
            # refund_links fehlt
        }
        form_invalid = TransactionForm(data=data_invalid, user=self.user)
        self.assertFalse(form_invalid.is_valid())
        self.assertIn('refund_links', form_invalid.errors)
        self.assertIn("Please select at least one original transaction.", form_invalid.errors['refund_links'][0])

        # Fall 2: is_refund ist True UND Links sind übergeben -> Valide
        data_valid = data_invalid.copy()
        data_valid['refund_links'] = [orig_tx.id]
        
        form_valid = TransactionForm(data=data_valid, user=self.user)
        self.assertTrue(form_valid.is_valid(), form_valid.errors)

    def test_form_queryset_isolation(self):
        """Testet die __init__ Methode: Ein User darf nur seine eigenen Konten sehen."""
        acc_other_user = Account.objects.create(name="Fremdes Konto", is_mine=True, user=self.user_b)
        
        form = TransactionForm(user=self.user)
        choices = str(form.fields['sender'].choices)
        
        self.assertIn(self.acc_mine.name, choices)
        self.assertNotIn(acc_other_user.name, choices)


class TransactionSplitFormSetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="usera", password="pw")
        self.cat1 = Category.objects.create(name="Lebensmittel", user=self.user)
        self.cat2 = Category.objects.create(name="Drogerie", user=self.user)
        
        self.acc_mine = Account.objects.create(name="Giro", is_mine=True, user=self.user)
        self.acc_ext = Account.objects.create(name="Shop", is_mine=False, user=self.user)
        
        # Eine Dummy-Transaktion mit Betrag 100€
        self.tx = Transaction.objects.create(
            sender=self.acc_mine, receiver=self.acc_ext, 
            amount=Decimal('100.00'), timestamp=timezone.now(), user=self.user
        )

    def get_formset_data(self, splits_data):
        """Hilfsfunktion, um das lästige Django Management Form Data zu generieren."""
        data = {
            'splits-TOTAL_FORMS': str(len(splits_data)),
            'splits-INITIAL_FORMS': '0',
            'splits-MIN_NUM_FORMS': '0',
            'splits-MAX_NUM_FORMS': '1000',
        }
        for i, split in enumerate(splits_data):
            data[f'splits-{i}-category'] = split.get('category')
            data[f'splits-{i}-amount'] = split.get('amount')
            if 'DELETE' in split:
                data[f'splits-{i}-DELETE'] = split.get('DELETE')
        return data

    def test_formset_valid_amounts(self):
        """Die Summe der Splits (40+60=100) ist genau gleich dem Transaktionsbetrag (100). -> Valide"""
        splits = [
            {'category': self.cat1.id, 'amount': '40.00'},
            {'category': self.cat2.id, 'amount': '60.00'},
        ]
        data = self.get_formset_data(splits)
        
        formset = TransactionSplitFormSet(data=data, instance=self.tx, form_kwargs={'user': self.user})
        self.assertTrue(formset.is_valid(), formset.errors)

    def test_formset_invalid_exceeding_amount(self):
        """Die Summe der Splits (60+50=110) ist größer als der Transaktionsbetrag (100). -> Invalide"""
        splits = [
            {'category': self.cat1.id, 'amount': '60.00'},
            {'category': self.cat2.id, 'amount': '50.00'},
        ]
        data = self.get_formset_data(splits)
        
        formset = TransactionSplitFormSet(data=data, instance=self.tx, form_kwargs={'user': self.user})
        self.assertFalse(formset.is_valid())
        # FormSet non-form errors werden in non_form_errors() gespeichert
        self.assertTrue(any("cannot exceed the total amount" in error for error in formset.non_form_errors()))


class AccountAndCategoryFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")

    def test_account_form_valid(self):
        data = {
            'name': 'Neues Girokonto',
            'start_balance': '500.00',
            'is_mine': True,
            'is_closed': False,
            'account_nr': 'DE123456789'
        }
        form = AccountForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_category_form_queryset_isolation(self):
        """Stellt sicher, dass bei parent_category nur die eigenen Kategorien auswählbar sind."""
        cat_mine = Category.objects.create(name="Meine Kategorie", user=self.user)
        cat_other = Category.objects.create(name="Fremde Kategorie", user=self.user_b)
        
        form = CategoryForm(user=self.user)
        choices = [choice[1] for choice in form.fields['parent_category'].choices]
        
        # '---------' ist der Standard-Leer-Eintrag (Index 0), danach kommen die Querysets
        self.assertIn(cat_mine.name, choices)
        self.assertNotIn(cat_other.name, choices)
        
        
class BaseViewTestSetup(TestCase):
    """Basis-Setup, das von allen View-Tests geerbt wird, um Code zu sparen."""
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        
        self.user_a = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")

        self.acc_mine_a = Account.objects.create(name="Giro A", is_mine=True, user=self.user_a, start_balance=Decimal("1000.00"))
        self.acc_ext_a = Account.objects.create(name="Shop A", is_mine=False, user=self.user_a)
        self.cat_a = Category.objects.create(name="Lebensmittel", user=self.user_a)
        
        self.tx_a = Transaction.objects.create(
            sender=self.acc_mine_a, receiver=self.acc_ext_a, amount=Decimal("50.00"), 
            timestamp=timezone.now(), user=self.user_a, description="Test Einkauf"
        )
        
        self.client_a = Client()
        self.client_a.force_login(self.user_a)

        self.client_b = Client()
        self.client_b.force_login(self.user_b)


class SecurityViewTests(BaseViewTestSetup):
    """Stellt sicher, dass User streng voneinander isoliert sind."""
    
    def test_user_cannot_view_others_transaction_detail(self):
        response = self.client_b.get(reverse('transaction_detail', args=[self.tx_a.id]))
        self.assertEqual(response.status_code, 404)

    def test_user_cannot_edit_others_transaction(self):
        response_post = self.client_b.post(reverse('transaction_edit', args=[self.tx_a.id]), {
            'amount': '999.00',
        })
        self.assertEqual(response_post.status_code, 404)
        self.tx_a.refresh_from_db()
        self.assertEqual(self.tx_a.amount, Decimal("50.00"))

    def test_user_cannot_delete_others_data(self):
        response_tx = self.client_b.post(reverse('transaction_delete', args=[self.tx_a.id]))
        self.assertEqual(response_tx.status_code, 404)
        
        response_acc = self.client_b.post(reverse('account_delete', args=[self.acc_mine_a.id]))
        self.assertEqual(response_acc.status_code, 404)
        
        response_cat = self.client_b.post(reverse('category_delete', args=[self.cat_a.id]))
        self.assertEqual(response_cat.status_code, 404)


class TransactionViewTests(BaseViewTestSetup):
    """Tests für die Transaktions-Logik und HTMX/AJAX Endpunkte."""

    def test_transaction_list_htmx_partial(self):
        """Testet, ob bei einem HTMX-Request nur das Partial-Template gerendert wird."""
        response = self.client_a.get(reverse('transactions'), HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'transactions/_transaction_list_partial.html')
        self.assertTemplateNotUsed(response, 'transactions/index.html')

    def test_transaction_search_ajax(self):
        """Testet den JSON Endpoint für Select2."""
        response = self.client_a.get(reverse('transaction_search_ajax'), {'q': 'Einkauf'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('results', data)
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], self.tx_a.id)

    def test_quicksearch_length_limit(self):
        """Testet die Logik, dass bei < 2 Zeichen keine DB-Abfrage gemacht wird."""
        response = self.client_a.get(reverse('quicksearch'), {'q': 'E'})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_empty'])
        self.assertFalse(response.context.get('has_results'))

        response_valid = self.client_a.get(reverse('quicksearch'), {'q': 'Einkauf'})
        self.assertTrue(response_valid.context['has_results'])


class CategoryViewTests(BaseViewTestSetup):
    """Tests speziell für Kategorien (inkl. ProtectedError Edge Case)."""

    def test_category_protected_error_on_delete(self):
        """Testet, dass eine Kategorie mit verknüpfter Transaktion NICHT gelöscht wird und eine Fehlermeldung ausgibt."""
        TransactionSplit.objects.create(transaction=self.tx_a, category=self.cat_a, amount=Decimal("50.00"))

        response = self.client_a.post(reverse('category_delete', args=[self.cat_a.id]))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('error', response.context)
        self.assertTrue(Category.objects.filter(id=self.cat_a.id).exists())

    def test_category_successful_delete(self):
        """Testet, dass eine freie Kategorie gelöscht werden kann."""
        free_cat = Category.objects.create(name="Frei", user=self.user_a)
        response = self.client_a.post(reverse('category_delete', args=[free_cat.id]))
        self.assertEqual(response.status_code, 302) # Redirect nach Erfolg
        self.assertFalse(Category.objects.filter(id=free_cat.id).exists())


class ToolAndViewTests(BaseViewTestSetup):
    """Tests für Backup, Einstellungen, Setup und Charts."""

    def test_first_run_setup_creates_superuser(self):
        """Sicherstellen, dass der First Run einen Superuser anlegt, wenn noch keiner da ist."""
        User.objects.all().delete() 
        
        client = Client()
        response = client.post(reverse('first_run_setup'), {
            'username': 'newadmin',
            'password': 'securepassword'
        })
        
        self.assertEqual(response.status_code, 302) # Redirect zum Login
        self.assertTrue(User.objects.filter(username='newadmin', is_superuser=True).exists())

    def test_user_settings_post(self):
        """Testet das Ändern der User Settings."""
        response = self.client_a.post(reverse('user_settings'), {
            'theme': 'dark',
            'language': 'en',
            'future_transactions_in_balance': 'on'
        })
        self.assertEqual(response.status_code, 302)
        
        settings = UserSettings.objects.get(user=self.user_a)
        self.assertEqual(settings.theme, 'dark')
        self.assertEqual(settings.language, 'en')
        self.assertTrue(settings.future_transactions_in_balance)

    def test_backup_export_format(self):
        """Prüft, ob der Export-View ein korrekt formatiertes JSON-Attachment liefert."""
        response = self.client_a.get(reverse('backup_export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertIn('attachment; filename="opencent_backup.json"', response['Content-Disposition'])
        
        data = json.loads(response.content)
        self.assertIn('accounts', data)
        self.assertIn('transactions', data)
        self.assertEqual(data['accounts'][0]['name'], 'Giro A')

    def test_backup_import_process(self):
        """Prüft, ob ein hochgeladenes JSON-File erfolgreich importiert wird."""
        backup_data = {
            'accounts': [{'id': 99, 'name': 'Importiertes Konto', 'start_balance': '0.00', 'is_mine': True, 'is_closed': False}],
            'categories': [], 'transactions': [], 'splits': [], 'refunds': []
        }
        
        json_file = SimpleUploadedFile("backup.json", json.dumps(backup_data).encode('utf-8'), content_type="application/json")
        
        response = self.client_a.post(reverse('backup_import'), {'backup_file': json_file})
        self.assertEqual(response.status_code, 302)
        
        self.assertFalse(Account.objects.filter(name="Giro A").exists())
        self.assertTrue(Account.objects.filter(name="Importiertes Konto", user=self.user_a).exists())

    def test_chart_views_render(self):
        """Testet grob, ob die Chart-Views bei GET und POST (Zeitraum) nicht crashen."""
        views_to_test = ['charts', 'chart_balance_over_time', 'chart_sankey']
        for view_name in views_to_test:
            resp_get = self.client_a.get(reverse(view_name))
            self.assertEqual(resp_get.status_code, 200)
            
            if view_name != 'charts':
                resp_post = self.client_a.post(reverse(view_name), {
                    'time': 'custom',
                    'start_date': '2020-01-01T00:00',
                    'end_date': '2030-01-01T00:00',
                    'account': 'all'
                })
                self.assertEqual(resp_post.status_code, 200)