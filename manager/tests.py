from django.test import TestCase
from django.contrib.auth.models import User
from .models import Account, Transaction, Category, TransactionSplit, Refund
from decimal import Decimal
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from io import BytesIO
from PIL import Image
from .views import calculate_refund_clusters

class AccountModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")

        self.account_giro = Account.objects.create(
            name="Girokonto",
            start_balance=Decimal("1000.00"),
            is_mine=True,
            user=self.user_a,
        )
        self.account_supermarkt = Account.objects.create(
            name="Supermarkt",
            start_balance=Decimal("0"),
            is_mine=False,
            user=self.user_a,
        )
    def test_model_str_representations(self):
        """Tests the string representations of the models for better readability in the admin interface and elsewhere."""
        self.assertEqual(str(self.account_giro), "Girokonto")
        self.assertEqual(str(self.account_supermarkt), "Supermarkt")

    def test_account_balance_calculation(self):
        """Tests whether the account balance is correctly calculated after a transaction."""
        Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("50.00"),
            timestamp=timezone.now(),
            user=self.user_a,
        )

        self.assertEqual(self.account_giro.get_current_balance(), Decimal("950.00"))
        self.assertEqual(
            self.account_supermarkt.get_current_balance(), Decimal("50.00")
        )
    def test_account_icon_image_processing(self):
        """Tests the image processing logic for account icons, including handling of SVGs, resizing of large PNGs, and exception handling for invalid images."""
        
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

        account_svg.icon.delete()
        account_png.icon.delete()
        account_bad.icon.delete()

class TransactionModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")

        self.account_giro = Account.objects.create(
            name="Girokonto",
            start_balance=Decimal("1000.00"),
            is_mine=True,
            user=self.user_a,
        )
        self.account_supermarkt = Account.objects.create(
            name="Supermarkt",
            start_balance=Decimal("0"),
            is_mine=False,
            user=self.user_a,
        )


    def test_security_user_cannot_access_others_transaction(self):
        """Tests that a user cannot access a transaction that belongs to another user."""
        tx = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("10.00"),
            timestamp=timezone.now(),
            user=self.user_a,  # Gehört User A!
        )

        self.client.login(username="userb", password="pw")

        response = self.client.get(f"/transactions/{tx.id}/")

        self.assertEqual(response.status_code, 404)

    def test_transaction_split_properties(self):
        """Tests the properties related to TransactionSplits, such as assigned_amount, unassigned_amount and is_fully_categorized."""
        cat1 = Category.objects.create(name="Lebensmittel", user=self.user_a)
        cat2 = Category.objects.create(name="Drogerie", user=self.user_a)

        tx = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("100.00"),
            timestamp=timezone.now(),
            user=self.user_a,
        )

        # Phase 1: No Splits
        self.assertEqual(tx.assigned_amount, Decimal("0"))
        self.assertEqual(tx.unassigned_amount, Decimal("100.00"))
        self.assertFalse(tx.is_fully_categorized)

        # Phase 2: Partly categorized (60€ assigned)
        TransactionSplit.objects.create(
            transaction=tx, category=cat1, amount=Decimal("60.00")
        )
        self.assertEqual(tx.assigned_amount, Decimal("60.00"))
        self.assertEqual(tx.unassigned_amount, Decimal("40.00"))
        self.assertFalse(tx.is_fully_categorized)

        # Phase 3: fully categorized (additional 40€ assigned)
        TransactionSplit.objects.create(
            transaction=tx, category=cat2, amount=Decimal("40.00")
        )
        self.assertEqual(tx.assigned_amount, Decimal("100.00"))
        self.assertEqual(tx.unassigned_amount, Decimal("0.00"))
        self.assertTrue(tx.is_fully_categorized)

    def test_model_str_representations(self):
        """Tests the string representations of the models for better readability in the admin interface and elsewhere."""

        tx = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("15.50"),
            timestamp=timezone.now(),
            user=self.user_a,
        )
        self.assertEqual(str(tx), "Girokonto -> Supermarkt: 15.50 €")

    def test_transaction_types_and_ui_classes(self):
        """Tests the transaction type determination and corresponding UI classes based on sender and receiver accounts."""
        acc_mine = self.account_giro
        acc_ext = self.account_supermarkt
        acc_ext2 = Account.objects.create(name="Anderer Supermarkt", is_mine=False, user=self.user_a)

        # 1. TRANSFER
        tx_transfer = Transaction.objects.create(
            sender=acc_mine, receiver=acc_mine, amount=Decimal('10.00'), timestamp=timezone.now(), user=self.user_a
        )
        self.assertEqual(tx_transfer.type, 'TRANSFER')
        self.assertEqual(tx_transfer.ui_color_class, 'list-group-item-secondary')

        # 2. EXPENSE
        tx_expense = Transaction.objects.create(
            sender=acc_mine, receiver=acc_ext, amount=Decimal('10.00'), timestamp=timezone.now(), user=self.user_a
        )
        self.assertEqual(tx_expense.type, 'EXPENSE')
        self.assertEqual(tx_expense.ui_color_class, 'list-group-item-danger')

        # 3. INCOME
        tx_income = Transaction.objects.create(
            sender=acc_ext, receiver=acc_mine, amount=Decimal('10.00'), timestamp=timezone.now(), user=self.user_a
        )
        self.assertEqual(tx_income.type, 'INCOME')
        self.assertEqual(tx_income.ui_color_class, 'list-group-item-success')

        # 4. EXTERNAL
        tx_external = Transaction.objects.create(
            sender=acc_ext, receiver=acc_ext2, amount=Decimal('10.00'), timestamp=timezone.now(), user=self.user_a
        )
        self.assertEqual(tx_external.type, 'EXTERNAL')
        self.assertEqual(tx_external.ui_color_class, 'list-group-item-secondary')

    def test_transaction_refund_queries_and_ui(self):
        """Tests refund queries"""
        tx_orig = Transaction.objects.create(
            sender=self.account_giro, receiver=self.account_supermarkt, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user_a, remainder_after_refunds=Decimal('100.00')
        )
        tx_ref = Transaction.objects.create(
            sender=self.account_supermarkt, receiver=self.account_giro, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user_a, remainder_of_refund=Decimal('100.00')
        )
        refund_link = Refund.objects.create(original_transaction=tx_orig, refund_transaction=tx_ref)

        self.assertIn(refund_link, tx_orig.refunds)
        self.assertIn(refund_link, tx_ref.is_refund_of)

        self.assertEqual(tx_orig.ui_color_class, 'list-group-item-danger')
        tx_orig.remainder_after_refunds = Decimal('0')
        self.assertEqual(tx_orig.ui_color_class, 'list-group-item-secondary text-decoration-line-through opacity-75')

        self.assertEqual(tx_ref.ui_color_class, 'list-group-item-success')
        tx_ref.remainder_of_refund = Decimal('0')
        self.assertEqual(tx_ref.ui_color_class, 'list-group-item-secondary text-decoration-line-through opacity-75')

    def test_transaction_split_str(self):
        """Tests the string representation of the TransactionSplit model"""
        tx = Transaction.objects.create(
            sender=self.account_giro, receiver=self.account_supermarkt, amount=Decimal('50.00'), timestamp=timezone.now(), user=self.user_a
        )
        cat = Category.objects.create(name="TestKategorie", user=self.user_a)
        split = TransactionSplit.objects.create(transaction=tx, category=cat, amount=Decimal('25.50'))
        
        expected_str = f"{tx.id} - TestKategorie: 25.50 €"
        self.assertEqual(str(split), expected_str)

class RefundModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")
        self.user_b = User.objects.create_user(username="userb", password="pw")

        self.account_giro = Account.objects.create(
            name="Girokonto",
            start_balance=Decimal("1000.00"),
            is_mine=True,
            user=self.user_a,
        )
        self.account_supermarkt = Account.objects.create(
            name="Supermarkt",
            start_balance=Decimal("0"),
            is_mine=False,
            user=self.user_a,
        )
    def test_model_str_representations(self):
        """Tests the string representations of the models for better readability in the admin interface and elsewhere."""
        tx_original = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("50.00"),
            timestamp=timezone.now(),
            user=self.user_a,
            remainder_after_refunds=Decimal("50.00"),
        )

        tx_refund = Transaction.objects.create(
            sender=self.account_supermarkt,
            receiver=self.account_giro,
            amount=Decimal("50.00"),
            timestamp=timezone.now(),
            user=self.user_a,
        )

        refund = Refund.objects.create(
            original_transaction=tx_original, refund_transaction=tx_refund
        )

        self.assertEqual(
            str(refund),
            f"Refund of {tx_original.id} by {tx_refund.id}",
        )

    def test_refund_properties(self):
        """Tests the properties related to refunds, such as has_refunds, is_refund and is_fully_refunded."""
        tx_original = Transaction.objects.create(
            sender=self.account_giro,
            receiver=self.account_supermarkt,
            amount=Decimal("50.00"),
            timestamp=timezone.now(),
            user=self.user_a,
            remainder_after_refunds=Decimal("50.00"),
        )

        tx_refund = Transaction.objects.create(
            sender=self.account_supermarkt,
            receiver=self.account_giro,
            amount=Decimal("50.00"),
            timestamp=timezone.now(),
            user=self.user_a,
        )

        # before linking
        self.assertFalse(tx_original.has_refunds)
        self.assertFalse(tx_original.is_refund)
        self.assertFalse(tx_refund.has_refunds)
        self.assertFalse(tx_refund.is_refund)

        Refund.objects.create(
            original_transaction=tx_original, refund_transaction=tx_refund
        )

        self.assertTrue(tx_original.has_refunds)
        self.assertFalse(tx_original.is_refund)
        self.assertTrue(tx_refund.is_refund)
        self.assertFalse(tx_refund.has_refunds)
        self.assertFalse(
            tx_original.is_fully_refunded
        )

        tx_original.remainder_after_refunds = Decimal("0.00")
        tx_original.save()
        self.assertTrue(tx_original.is_fully_refunded)
        
class CategoryModelTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username="admin", password="pw", email="")
        self.user_a = User.objects.create_user(username="usera", password="pw")
    
    def test_model_str_representations(self):
        """Tests the string representations of the models for better readability in the admin interface and elsewhere."""
        cat = Category.objects.create(name="TestCat", user=self.user_a)
        self.assertEqual(str(cat), "TestCat")

    def test_category_recursion(self):
        """Tests the recursive retrieval of subcategories in the Category model."""
        parent = Category.objects.create(name="Wohnen", user=self.user_a)
        child = Category.objects.create(
            name="Strom", parent_category=parent, user=self.user_a
        )
        grandchild = Category.objects.create(
            name="Nachzahlung", parent_category=child, user=self.user_a
        )

        subcats = parent.get_all_subcategories_recursive()

        self.assertEqual(len(subcats), 2)
        self.assertIn(child, subcats)
        self.assertIn(grandchild, subcats)


class RefundClusterLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='usera', password='pw')
        self.acc_giro = Account.objects.create(name="Giro", start_balance=0, is_mine=True, user=self.user)
        self.acc_shop = Account.objects.create(name="Shop", start_balance=0, is_mine=False, user=self.user)

    def test_simple_full_refund_calculation(self):
        """Tests a simple case where a 100€ transaction is fully refunded with another 100€ transaction, and checks if the remainders are correctly set to 0."""
        tx_out = Transaction.objects.create(
            sender=self.acc_giro, receiver=self.acc_shop, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user, remainder_after_refunds=Decimal('100.00')
        )
        tx_in = Transaction.objects.create(
            sender=self.acc_shop, receiver=self.acc_giro, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user, remainder_of_refund=Decimal('100.00')
        )
        
        Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)

        calculate_refund_clusters(self.user, {tx_out.id, tx_in.id})

        tx_out.refresh_from_db()
        tx_in.refresh_from_db()

        self.assertEqual(tx_out.remainder_after_refunds, Decimal('0.00'))
        self.assertEqual(tx_in.remainder_of_refund, Decimal('0.00'))

    def test_partial_refund_calculation(self):
        """Tests a case where a 100€ transaction is partially refunded with a 40€ transaction, and checks if the remainders are correctly updated to reflect the partial refund."""
        tx_out = Transaction.objects.create(
            sender=self.acc_giro, receiver=self.acc_shop, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user, remainder_after_refunds=Decimal('100.00')
        )
        tx_in = Transaction.objects.create(
            sender=self.acc_shop, receiver=self.acc_giro, amount=Decimal('40.00'), 
            timestamp=timezone.now(), user=self.user, remainder_of_refund=Decimal('40.00')
        )
        
        Refund.objects.create(original_transaction=tx_out, refund_transaction=tx_in)
        calculate_refund_clusters(self.user, {tx_out.id})

        tx_out.refresh_from_db()
        tx_in.refresh_from_db()

        self.assertEqual(tx_out.remainder_after_refunds, Decimal('60.00'))
        self.assertEqual(tx_in.remainder_of_refund, Decimal('0.00'))

    def test_orphaned_transaction_reset(self):
        """Tests whether the amounts are reset when a cluster is dissolved, i.e., when there are no more refunds linked to an original transaction, the remainder should be reset to the full amount."""
        tx_out = Transaction.objects.create(
            sender=self.acc_giro, receiver=self.acc_shop, amount=Decimal('100.00'), 
            timestamp=timezone.now(), user=self.user, remainder_after_refunds=Decimal('0.00')
        )
        
        calculate_refund_clusters(self.user, {tx_out.id})
        
        tx_out.refresh_from_db()
        self.assertEqual(tx_out.remainder_after_refunds, Decimal('100.00'))
        
class GeneralViewTests(TestCase):
    def setUp(self):
        User.objects.create_superuser(username='admin', password='pw', email='')
        self.user = User.objects.create_user(username='usera', password='pw')
        
    def test_homepage_loads_correctly(self):
        """Prüft, ob die Startseite für eingeloggte User korrekt mit dem richtigen Template lädt."""
        self.client.force_login(self.user)
        
        response = self.client.get(reverse('homepage'))
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'index.html')
        self.assertTemplateUsed(response, 'master.html')
        
        self.assertContains(response, "Gesamtvermögen")
        self.assertContains(response, "Meine Konten")
    
    def test_login_required_redirects(self):
        """Tests that all protected views redirect to the login page when accessed by an anonymous user."""
        
        protected_urls = [
            ''
            'accounts',
            'account_add',
            'transactions',
            'transaction_add',
            'categories',
            'category_add',
            'charts',
            'chart_balance_over_time',
            'chart_sankey',
            ('transaction_detail', [999]),
            ('transaction_edit', [999]),
            ('transaction_delete', [999]),
            ('account_detail', [999]),
            ('account_edit', [999]),
            ('account_delete', [999]),
            ('category_detail', [999]),
            ('category_edit', [999]),
            ('category_delete', [999]),
        ]

        
        for item in protected_urls:
            if isinstance(item, tuple):
                url_name, args = item
                url = reverse(url_name, args=args)
            else:
                url_name = item
                url = reverse(url_name)

            with self.subTest(url_name=url_name):
                response = self.client.get(url)
                
                self.assertEqual(
                    response.status_code, 
                    302, 
                    f"ERROR: The URL '{url}' is not protected! (Status: {response.status_code})"
                )
                
                self.assertTrue(
                    '/users/login' in response.url, 
                    f"ERROR: The URL '{url}' redirects to the wrong location: {response.url}"
                )