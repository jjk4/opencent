from django.db import migrations

def copy_categories_to_splits(apps, schema_editor):
    Transaction = apps.get_model('manager', 'Transaction')
    TransactionSplit = apps.get_model('manager', 'TransactionSplit')

    splits_to_create = []

    for trans in Transaction.objects.exclude(category=None):
        split = TransactionSplit(
            transaction=trans,
            category=trans.category,
            amount=trans.amount
        )
        splits_to_create.append(split)

    if splits_to_create:
        TransactionSplit.objects.bulk_create(splits_to_create)

class Migration(migrations.Migration):

    dependencies = [
        ('manager', '0023_transactionsplit_transaction_categories'),
    ]

    operations = [
        migrations.RunPython(copy_categories_to_splits),
    ]
