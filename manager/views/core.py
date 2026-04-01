from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.core.files.base import ContentFile
import json
import base64
import os
from django.conf import settings as django_settings

from ..models import Account, Transaction, Category, UserSettings, Refund, TransactionSplit
from ..utils import get_balance_history

def first_run_setup(request):
    superuser = User.objects.filter(is_superuser=True).first()
    superuser_exists = superuser is not None
    if request.method == 'POST':
        if not superuser_exists:
            username = request.POST.get('username')
            password = request.POST.get('password')
            User.objects.create_superuser(username=username, password=password, email='')
            return redirect('/users/login')

    context = {
        'header_data': {
            'title': _('Setup Assistant'),
            'selected_tab': 'home',
        },
        'superuser_exists': superuser_exists,
    }
    
    return render(request, 'first_run_setup.html', context)

@login_required
def homepage(request):
    all_accounts = Account.objects.filter(is_mine=True, user=request.user)
    account_list = all_accounts.filter(is_closed=False)
    
    total_balance = sum(acc.get_current_balance() for acc in all_accounts)

    today_last_year = timezone.now() - timedelta(days=365)
    
    chart_data = get_balance_history(request, account_list, today_last_year)

    context = {
        'header_data': {
            'title': _('Home'),
            'selected_tab': 'home',
        },
        'accounts': account_list,
        'total_balance': total_balance,
        
        'balances_over_time_json': json.dumps(chart_data, cls=DjangoJSONEncoder),
    }
    
    return render(request, 'index.html', context)

@login_required
def search(request):
    query = request.GET.get('q', '')
    transactions = Transaction.objects.filter(
        Q(description__icontains=query) | 
        Q(sender__name__icontains=query) | 
        Q(receiver__name__icontains=query),
        user=request.user
    ).select_related('sender', 'receiver').prefetch_related('splits__category')
    accounts = Account.objects.filter(user=request.user, name__icontains=query)
    categories = Category.objects.filter(user=request.user, name__icontains=query)
    
    context = {
        'header_data': {
            'title': _('Search: %s') % query,
            'selected_tab': 'home',
        },
        'transactions': transactions,
        'accounts': accounts,
        'categories': categories,
        'query': query,
    }
    return render(request, 'search.html', context)

@login_required
def quicksearch(request):
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return render(request, 'elements/quicksearch_results.html', {'is_empty': True})

    transactions = Transaction.objects.filter(
        Q(description__icontains=query) | 
        Q(sender__name__icontains=query) | 
        Q(receiver__name__icontains=query),
        user=request.user
    ).select_related('sender', 'receiver')[:3]

    accounts = Account.objects.filter(user=request.user, name__icontains=query)[:3]
    categories = Category.objects.filter(user=request.user, name__icontains=query)[:3]
    
    context = {
        'transactions': transactions,
        'accounts': accounts,
        'categories': categories,
        'query': query,
        'has_results': bool(transactions or accounts or categories)
    }
    return render(request, 'elements/quicksearch_results.html', context)

@login_required
def user_settings(request):
    user_settings_obj, created = UserSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        theme = request.POST.get('theme')
        if theme in ['light', 'dark', 'auto']:
            user_settings_obj.theme = theme

        language = request.POST.get('language')
        if language in dict(django_settings.LANGUAGES).keys():
            user_settings_obj.language = language
            
        future_transactions_in_balance = request.POST.get('future_transactions_in_balance') == 'on'
        user_settings_obj.future_transactions_in_balance = future_transactions_in_balance

        user_settings_obj.save()

        return redirect('user_settings')

    context = {
        'header_data': {
            'title': _('User Settings'),
            'selected_tab': '',
        },
        'settings': user_settings_obj
    }
    return render(request, 'user_settings.html', context)

@login_required
def backup_export(request):
    """Exportiert alle Daten des Users als JSON, inklusive Account-Icons als Base64."""
    
    accounts_data = list(Account.objects.filter(user=request.user).values())
    account_objects = {acc.id: acc for acc in Account.objects.filter(user=request.user)}
    
    for acc in accounts_data:
        obj = account_objects[acc['id']]
        if obj.icon:
            try:
                with obj.icon.open('rb') as f:
                    acc['icon_base64'] = base64.b64encode(f.read()).decode('utf-8')
                    acc['icon_filename'] = os.path.basename(obj.icon.name)
            except FileNotFoundError:
                pass

    data = {
        'accounts': accounts_data,
        'categories': list(Category.objects.filter(user=request.user).values()),
        'transactions': list(Transaction.objects.filter(user=request.user).values()),
        'splits': list(TransactionSplit.objects.filter(transaction__user=request.user).values()),
        'refunds': list(Refund.objects.filter(original_transaction__user=request.user).values()),
        'settings': list(UserSettings.objects.filter(user=request.user).values()),
    }
    
    response = HttpResponse(
        json.dumps(data, cls=DjangoJSONEncoder),
        content_type='application/json'
    )
    response['Content-Disposition'] = 'attachment; filename="opencent_backup.json"'
    return response


@login_required
def backup_import(request):
    """Importiert Daten aus einer JSON und stellt auch Bilder wieder her."""
    if request.method == 'POST' and request.FILES.get('backup_file'):
        backup_file = request.FILES['backup_file']
        
        try:
            data = json.load(backup_file)
            
            with transaction.atomic():
                Account.objects.filter(user=request.user).delete()
                Category.objects.filter(user=request.user).delete()
                
                id_maps = {'account': {}, 'category': {}, 'transaction': {}}
                
                for acc_data in data.get('accounts', []):
                    old_id = acc_data.pop('id')
                    acc_data['user_id'] = request.user.id
                    
                    icon_base64 = acc_data.pop('icon_base64', None)
                    icon_filename = acc_data.pop('icon_filename', None)
                    
                    acc_data.pop('icon', None) 
                    
                    new_acc = Account.objects.create(**acc_data)
                    id_maps['account'][old_id] = new_acc.id
                    
                    if icon_base64 and icon_filename:
                        try:
                            decoded_file = base64.b64decode(icon_base64)
                            new_acc.icon.save(icon_filename, ContentFile(decoded_file))
                        except Exception as e:
                            print(f"Fehler beim Bild-Wiederherstellen für {new_acc.name}: {e}")

                parents_to_assign = {}
                for cat_data in data.get('categories', []):
                    old_id = cat_data.pop('id')
                    cat_data['user_id'] = request.user.id
                    old_parent = cat_data.pop('parent_category_id', None)
                    new_cat = Category.objects.create(**cat_data)
                    id_maps['category'][old_id] = new_cat.id
                    
                    if old_parent:
                        parents_to_assign[new_cat.id] = old_parent
                        
                for new_id, old_parent in parents_to_assign.items():
                    if old_parent in id_maps['category']:
                        Category.objects.filter(id=new_id).update(
                            parent_category_id=id_maps['category'][old_parent]
                        )
                        
                for tx_data in data.get('transactions', []):
                    old_id = tx_data.pop('id')
                    tx_data['user_id'] = request.user.id
                    tx_data['sender_id'] = id_maps['account'].get(tx_data.pop('sender_id'))
                    tx_data['receiver_id'] = id_maps['account'].get(tx_data.pop('receiver_id'))
                    
                    if tx_data['sender_id'] and tx_data['receiver_id']:
                        new_tx = Transaction.objects.create(**tx_data)
                        id_maps['transaction'][old_id] = new_tx.id
                        
                for split_data in data.get('splits', []):
                    split_data.pop('id')
                    split_data['transaction_id'] = id_maps['transaction'].get(split_data.pop('transaction_id'))
                    split_data['category_id'] = id_maps['category'].get(split_data.pop('category_id'))
                    
                    if split_data['transaction_id'] and split_data['category_id']:
                        TransactionSplit.objects.create(**split_data)
                        
                for refund_data in data.get('refunds', []):
                    refund_data.pop('id')
                    refund_data['original_transaction_id'] = id_maps['transaction'].get(refund_data.pop('original_transaction_id'))
                    refund_data['refund_transaction_id'] = id_maps['transaction'].get(refund_data.pop('refund_transaction_id'))
                    
                    if refund_data['original_transaction_id'] and refund_data['refund_transaction_id']:
                        Refund.objects.create(**refund_data)
                        
                if data.get('settings'):
                    settings_data = data['settings'][0]
                    settings_data.pop('id', None)
                    settings_data.pop('user_id', None)
                    UserSettings.objects.filter(user=request.user).update(**settings_data)

            messages.success(request, _("Data and images successfully restored!"))
            
        except Exception as e:
            messages.error(request, _("Error importing data. Make sure the file is a valid backup."))
            print(f"Restore Error: {e}")
            
    return redirect('user_settings')

def devview(request):
    pass