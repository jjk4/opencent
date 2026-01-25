from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from .models import Transaction, Account, Category
from .forms import TransactionForm, AccountForm, CategoryForm
from datetime import datetime, timedelta
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
import json

month_names = ['Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember']

# ------------------- Util functions ----------------------
def chart_timerange(request):
    start_date_fallback = Transaction.objects.filter(user=request.user).last().timestamp
    end_date_fallback = Transaction.objects.filter(user=request.user).first().timestamp
    # Determine time range
    if request.POST.get('time') == 'custom':
        try:
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%dT%H:%M')
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%dT%H:%M')
        except ValueError:
            start_date = start_date_fallback
            end_date = end_date_fallback

    else:
        if request.POST.get('time') == 'this-month':
            now = datetime.now()
            start_date = datetime(now.year, now.month, 1)
            end_date = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
        elif request.POST.get('time') == 'last-month':
            now = datetime.now()
            start_date = datetime(now.year, now.month - 1, 1) if now.month > 1 else datetime(now.year - 1, 12, 1)
            end_date = datetime(now.year, now.month, 1)
        elif request.POST.get('time') == 'this-year':
            now = datetime.now()
            start_date = datetime(now.year, 1, 1)
            end_date = datetime(now.year + 1, 1, 1)
        elif request.POST.get('time') == 'last-year':
            now = datetime.now()
            start_date = datetime(now.year - 1, 1, 1)
            end_date = datetime(now.year, 1, 1)
        elif request.POST.get('time') == 'all-time':
            start_date = start_date_fallback
            end_date = end_date_fallback
        else:
            start_date = start_date_fallback
            end_date = end_date_fallback

    return [start_date, end_date]

def chart_startbalance(request, start_date, end_date, account_selected):
        if account_selected:
            start_balance = Account.objects.get(id=request.POST.get('account'), user=request.user).start_balance
            start_balance += sum(t.amount for t in Transaction.objects.all().filter(user=request.user, timestamp__lt=start_date, receiver__id=request.POST.get('account')))
            start_balance -= sum(t.amount for t in Transaction.objects.all().filter(user=request.user, timestamp__lt=start_date, sender__id=request.POST.get('account')))
        else:
            start_balance = sum(account.start_balance for account in Account.objects.filter(is_mine=True, user=request.user))
            start_balance += sum(t.amount for t in Transaction.objects.all().filter(user=request.user, timestamp__lt=start_date, receiver__is_mine=True))
            start_balance -= sum(t.amount for t in Transaction.objects.all().filter(user=request.user, timestamp__lt=start_date, sender__is_mine=True))
        
        return start_balance

def chart_transactions(request, start_date, end_date, account_selected):
        transactions = Transaction.objects.all().filter(user=request.user, timestamp__gte=start_date, timestamp__lte=end_date).order_by('timestamp')
        if account_selected:
            transactions = transactions.filter(sender__id=request.POST.get('account')) | transactions.filter(receiver__id=request.POST.get('account'))
        return transactions

def get_balance_history(request, my_accounts, from_date=None):
    """
    Berechnet den Verlauf des Gesamtvermögens über die Zeit.
    """
    current_balance = chart_startbalance(request, from_date, None, None)
    history = []
    
    transactions = Transaction.objects.filter(
        Q(sender__in=my_accounts) | Q(receiver__in=my_accounts)
    ).filter(user=request.user).order_by('timestamp')
    
    if from_date:
        transactions = transactions.filter(timestamp__gte=from_date)

    if not transactions.exists():
         return [{'date': 'Start', 'balance': float(current_balance)}]

    for t in transactions:
        if t.receiver in my_accounts:
            current_balance += t.amount
            
        if t.sender in my_accounts:
            current_balance -= t.amount

        history.append({
            'date': t.timestamp.isoformat(), 
            'balance': float(current_balance)
        })
        
    return history
# ---------------------------------------------------------
@login_required
def transactions(request):
    filter = False
    transaction_list = Transaction.objects.filter(user=request.user).select_related('sender', 'receiver', 'category').prefetch_related('original_transaction_refunds', 'original_transaction_refunds__refund_transaction').all()
    filter_accounts = request.GET.getlist('account')
    if filter_accounts:
        filter = True
        transaction_list = transaction_list.filter(
            Q(sender__id__in=filter_accounts) | Q(receiver__id__in=filter_accounts)
        )

    filter_categories = request.GET.getlist('category')
    if filter_categories:
        filter = True
        category_ids = []
        for cat_id in filter_categories:
            category_ids.append(int(cat_id))
            category = Category.objects.get(id=cat_id)
            subcategories = category.get_all_subcategories_recursive()
            for subcat in subcategories:
                if subcat.id not in category_ids:
                    category_ids.append(subcat.id)
        transaction_list = transaction_list.filter(category__id__in=category_ids)

    context = {
        'header_data': {
            'title': 'Transaktionen',
            'selected_tab': 'transactions',
        },
        'transaction_list': transaction_list,
        'my_accounts': Account.objects.filter(is_mine=True, user=request.user),
        'show_refunds': request.GET.get('refunds') == 'on',
        'filter': filter,
    }
    
    return render(request, 'transactions/index.html', context)

@login_required
def transaction_detail(request, transaction_id):
    transaction = Transaction.objects.get(id=transaction_id)
    if transaction.user != request.user: # TODO: Fehlermeldung
        return redirect('transactions')
    context = {
        'header_data': {
            'title': (transaction.description or f"Transaktion {transaction.id}") + " Details",
            'selected_tab': 'transactions',
        },
        'transaction': transaction,
        'is_refund_of': transaction.is_refund_of,
        'refunds': transaction.refunds,
    }
    return render(request, 'transactions/detail.html', context)

@login_required
def transaction_add(request):
    if request.method == 'POST':
        form = TransactionForm(request.POST)
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            return redirect('transactions') 
    else:
        form = TransactionForm(initial={'timestamp': datetime.now()})
    
    context = {
        'header_data': {
            'title': 'Neue Transaktion',
            'selected_tab': 'transactions',
        },
        'form': form,
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if transaction.user != request.user: # TODO: Fehlermeldung
        return redirect('transactions')
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction)
        if form.is_valid():
            form.save()
            return redirect('transactions')
    else:
        form = TransactionForm(instance=transaction)
    
    context = {
        'header_data': {
            'title': 'Transaktion bearbeiten',
            'selected_tab': 'transactions',
        },
        'form': form,
        'is_edit': True
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_delete(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if transaction.user != request.user: # TODO: Fehlermeldung
        return redirect('transactions')
    if request.method == 'POST':
        transaction.delete()
        return redirect('transactions')
        
    context = {
         'header_data': {
            'title': 'Transaktion löschen',
            'selected_tab': 'transactions',
        },
        'transaction': transaction
    }
    return render(request, 'transactions/delete.html', context)

@login_required
def homepage(request):
    account_list = Account.objects.filter(is_mine=True, user=request.user)
    
    total_balance = sum(acc.get_current_balance() for acc in account_list)

    today_last_year = datetime.now() - timedelta(days=365)
    
    chart_data = get_balance_history(request, account_list, today_last_year)

    context = {
        'header_data': {
            'title': 'Startseite',
            'selected_tab': 'home',
        },
        'accounts': account_list,
        'total_balance': total_balance,
        
        'balances_over_time_json': json.dumps(chart_data, cls=DjangoJSONEncoder),
    }
    
    return render(request, 'index.html', context)

@login_required
def accounts(request):
    account_list = Account.objects.filter(is_mine=True, user=request.user)
    context = {
        'header_data': {
            'title': 'Konten',
            'selected_tab': 'accounts',
        },
        'accounts': account_list,
    }
    return render(request, 'accounts/index.html', context)

@login_required
def account_detail(request, account_id):
    account = Account.objects.get(id=account_id)
    if account.user != request.user: # TODO: Fehlermeldung
        return redirect('accounts')
    account.current_balance = account.get_current_balance()
    context = {
        'header_data': {
            'title': account.name + " Details",
            'selected_tab': 'accounts',
        },
        'account': account,
    }
    return render(request, 'accounts/detail.html', context)

@login_required
def account_add(request):
    if request.method == 'POST':
        form = AccountForm(request.POST, request.FILES)
        
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            return redirect('accounts') 
    else:
        form = AccountForm()
    
    context = {
        'header_data': {
            'title': 'Neues Konto',
            'selected_tab': 'accounts',
        },
        'form': form,
    }
    return render(request, 'accounts/add.html', context)

@login_required
def account_edit(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    if account.user != request.user: # TODO: Fehlermeldung
        return redirect('accounts')
    if request.method == 'POST':
        form = AccountForm(request.POST, request.FILES, instance=account)
        if form.is_valid():
            form.save()
            return redirect('accounts')
    else:
        form = AccountForm(instance=account)
    
    context = {
        'header_data': {
            'title': 'Konto bearbeiten',
            'selected_tab': 'accounts',
        },
        'form': form,
        'is_edit': True
    }
    return render(request, 'accounts/add.html', context)

@login_required
def account_delete(request, account_id):
    account = get_object_or_404(Account, id=account_id)
    if account.user != request.user: # TODO: Fehlermeldung
        return redirect('accounts')
    if request.method == 'POST':
        account.delete()
        return redirect('accounts')
        
    context = {
         'header_data': {
            'title': 'Konto löschen',
            'selected_tab': 'accounts',
        },
        'account': account
    }
    return render(request, 'accounts/delete.html', context)

@login_required
def categories(request):
    categories = Category.objects.filter(parent_category__isnull=True, user=request.user)
    context = {
        'header_data': {
            'title': "Kategorien",
            'selected_tab': 'categories',
        },
        'categories': categories,
    }
    return render(request, 'categories/index.html', context)

@login_required
def category_detail(request, category_id):
    category = Category.objects.get(id=category_id)
    if category.user != request.user: # TODO: Fehlermeldung
        return redirect('categories')
    context = {
        'header_data': {
            'title': category.name + " Details",
            'selected_tab': 'categories',
        },
        'category': category,
    }
    return render(request, 'categories/detail.html', context)

@login_required
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        
        if form.is_valid():
            instance = form.save(commit=False)
            instance.user = request.user
            instance.save()
            return redirect('categories') 
    else:
        form = CategoryForm()
    
    context = {
        'header_data': {
            'title': 'Neue Kategorie',
            'selected_tab': 'categories',
        },
        'form': form,
    }
    return render(request, 'categories/add.html', context)

@login_required
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if category.user != request.user: # TODO: Fehlermeldung
        return redirect('categories')
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('categories')
    else:
        form = CategoryForm(instance=category)
    
    context = {
        'header_data': {
            'title': 'Kategorie bearbeiten',
            'selected_tab': 'categories',
        },
        'form': form,
        'is_edit': True
    }
    return render(request, 'categories/add.html', context)

@login_required
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if category.user != request.user: # TODO: Fehlermeldung
        return redirect('categories')
    if request.method == 'POST':
        category.delete()
        return redirect('categories')
        
    context = {
         'header_data': {
            'title': 'Kategorie löschen',
            'selected_tab': 'categories',
        },
        'category': category
    }
    return render(request, 'categories/delete.html', context)

@login_required
def charts(request):
    template = loader.get_template('charts/index.html')
    context = {
        'header_data': {
            'title': "Analyse",
            'selected_tab': 'analysis',
        },
    }
    return HttpResponse(template.render(context, request))

@login_required
def chart_balance_over_time(request):
    template = loader.get_template('charts/balance_over_time.html')
    if request.method == 'POST':
        timerange = chart_timerange(request)
        start_date = timerange[0]
        end_date = timerange[1]
        
        account_selected = request.POST.get('account') and request.POST.get('account') != 'all'
        start_balance = chart_startbalance(request, start_date, end_date, account_selected)
        transactions = chart_transactions(request, start_date, end_date, account_selected)
        
        current_balance = start_balance
        balances_over_time = [{'date': int(start_date.timestamp()), 'balance': current_balance}]
        
        for t in transactions:
            if account_selected:
                if t.receiver.id == int(request.POST.get('account')):
                    current_balance += t.amount
                if t.sender.id == int(request.POST.get('account')):
                    current_balance -= t.amount
            else:
                if t.receiver.is_mine:
                    current_balance += t.amount
                if t.sender.is_mine:
                    current_balance -= t.amount

            balances_over_time.append({'date': int(t.timestamp.timestamp()), 'balance': current_balance})
    else:
        balances_over_time = []
   
    context = {
        'header_data': {
            'title': "Diagramme",
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'balances_over_time': balances_over_time,
    }
    return HttpResponse(template.render(context, request))

@login_required
def chart_sankey(request):
    template = loader.get_template('charts/sankey.html')
    if request.method == 'POST':
        timerange = chart_timerange(request)
        start_date = timerange[0]
        end_date = timerange[1]
        
        account_selected = request.POST.get('account') and request.POST.get('account') != 'all'
        transactions = chart_transactions(request, start_date, end_date, account_selected)
        # Income by category
        income_by_category = {-2: {'name': 'Nicht kategorisiert', 'amount': 0, 'parent': None}}
        total_income = 0
        for t in transactions:
            if t.receiver.is_mine and t.sender.is_mine == False and t.is_refund ==False and t.has_refunds == False: # TODO: Calculate refunds correctly
                if t.category is not None:
                    if t.category.id not in income_by_category:
                        income_by_category[t.category.id] = {'name': t.category.name, 'amount': 0, 'parent': t.category.parent_category.id if t.category.parent_category else None}
                    income_by_category[t.category.id]["amount"] += t.amount
                else:
                    income_by_category[-2]["amount"] += t.amount
                total_income += t.amount
                
        # Expenses by category
        expenses_by_category = {-1: {'name': 'Nicht kategorisiert', 'amount': 0, 'parent': None}}
        total_expenses = 0
        for t in transactions:
            if t.receiver.is_mine == False and t.sender.is_mine and t.is_refund ==False and t.has_refunds == False: # TODO: Calculate refunds correctly
                if t.category is not None:
                    if t.category.id not in expenses_by_category:
                        expenses_by_category[t.category.id] = {'name': t.category.name, 'amount': 0, 'parent': t.category.parent_category.id if t.category.parent_category else None}
                    expenses_by_category[t.category.id]["amount"] += t.amount
                    # Add Expenses to parent
                    if expenses_by_category[t.category.id]["parent"] is not None:
                        if expenses_by_category[t.category.id]["parent"] not in expenses_by_category:
                            category = Category.objects.get(id=expenses_by_category[t.category.id]["parent"])
                            expenses_by_category[expenses_by_category[t.category.id]["parent"]] = {'name': category.name, 'amount': 0, 'parent': category.parent_category.id if category.parent_category else None}
                        expenses_by_category[expenses_by_category[t.category.id]["parent"]]["amount"] += t.amount
                else:
                    expenses_by_category[-1]["amount"] += t.amount
                total_expenses += t.amount
            

    else:
        total_income = 0
        total_expenses = 0
        income_by_category = {}
        expenses_by_category = {}
    
    income_by_category = dict(sorted(income_by_category.items(), key=lambda item: item[1]['amount'], reverse=True))
    expenses_by_category = dict(sorted(expenses_by_category.items(), key=lambda item: item[1]['amount'], reverse=True))
    print(total_expenses)
    context = {
        'header_data': {
            'title': "Diagramme",
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'income_by_category': income_by_category,
        'expenses_by_category': expenses_by_category,
        'total_expenses': total_expenses,
        'total_income': total_income,
        
    }
    return HttpResponse(template.render(context, request))

def devview(request):
    pass