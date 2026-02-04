from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.template import loader
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from .models import Transaction, Account, Category, Refund
from django.contrib.auth.models import User
from .forms import TransactionForm, AccountForm, CategoryForm, TransactionSplitFormSet
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

def calculate_refunds(request):
    print("Calculating refunds...")
    print("----------------------")
    reset_transactions = []
    refund_transactions = Transaction.objects.filter(user=request.user)
    for transaction in refund_transactions:
        if transaction.is_refund:
            transaction.remainder_of_refund = transaction.amount
            transaction.remainder_after_refunds = 0
            for refund in transaction.is_refund_of:
                if refund.original_transaction.id not in reset_transactions:
                    reset_transactions.append(refund.original_transaction.id)
                    refund.original_transaction.remainder_after_refunds = refund.original_transaction.amount
                    refund.original_transaction.remainder_of_refund = 0
                if refund.original_transaction.remainder_after_refunds >= transaction.remainder_of_refund:
                    refund.original_transaction.remainder_after_refunds -= transaction.remainder_of_refund
                    transaction.remainder_of_refund = 0
                else:
                    transaction.remainder_of_refund -= refund.original_transaction.remainder_after_refunds
                    refund.original_transaction.remainder_after_refunds = 0
                refund.original_transaction.save()
            transaction.save()
        else:
            if transaction.id not in reset_transactions:
                transaction.remainder_after_refunds = transaction.amount
                transaction.remainder_of_refund = 0
                transaction.save()
    return

def handle_refund_save(transaction, form):
    is_refund = form.cleaned_data.get('is_refund')
    refund_links = form.cleaned_data.get('refund_links')
    
    Refund.objects.filter(refund_transaction=transaction).delete()
    
    if is_refund and refund_links:
        for original in refund_links:
            Refund.objects.create(
                original_transaction=original,
                refund_transaction=transaction
            )
# ---------------------------------------------------------
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
            'title': 'Einrichtungsassistent',
            'selected_tab': 'home',
        },
        'superuser_exists': superuser_exists,
    }
    
    return render(request, 'first_run_setup.html', context)

@login_required
def transactions(request):
    is_filter_active = False
    transaction_list = Transaction.objects.filter(user=request.user).select_related(
            'sender', 'receiver'
        ).prefetch_related(
            'splits__category',
            'original_transaction_refunds', 
            'original_transaction_refunds__refund_transaction'
        ).order_by('-timestamp')
    filter_accounts = request.GET.getlist('account')
    if filter_accounts:
        is_filter_active = True
        transaction_list = transaction_list.filter(
            Q(sender__id__in=filter_accounts) | Q(receiver__id__in=filter_accounts)
        )

    filter_categories = request.GET.getlist('category')
    if filter_categories:
        is_filter_active = True
        category_ids = []
        for cat_id in filter_categories:
            category_ids.append(int(cat_id))
            category = Category.objects.get(id=cat_id)
            subcategories = category.get_all_subcategories_recursive()
            for subcat in subcategories:
                if subcat.id not in category_ids:
                    category_ids.append(subcat.id)
        transaction_list = transaction_list.filter(categories__id__in=category_ids).distinct()

    paginator = Paginator(transaction_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj,
        'header_data': {
            'title': 'Transaktionen',
            'selected_tab': 'transactions',
        },
        'transaction_list': transaction_list,
        'my_accounts': Account.objects.filter(is_mine=True, user=request.user),
        'show_refunds': request.GET.get('refunds') == 'on',
        'is_filter_active': is_filter_active,
        'last_month_grouper': request.GET.get('last_month'),
    }
    if request.headers.get('HX-Request'):
        return render(request, 'transactions/_transaction_list_partial.html', context)
    
    return render(request, 'transactions/index.html', context)

@login_required
def transaction_detail(request, transaction_id):
    transaction = get_object_or_404(
        Transaction.objects.prefetch_related('splits__category'), 
        id=transaction_id
    )
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
        form = TransactionForm(request.POST, user=request.user)
        formset = TransactionSplitFormSet(request.POST, form_kwargs={'user': request.user})
        if form.is_valid():
            new_transaction = form.save(commit=False)
            new_transaction.user = request.user
            formset = TransactionSplitFormSet(
                request.POST, 
                instance=new_transaction, 
                form_kwargs={'user': request.user}
            )
            if formset.is_valid():
                new_transaction.save()
                formset.save()
                handle_refund_save(new_transaction, form)
                if form.cleaned_data.get('is_refund'):
                    calculate_refunds(request)
                return redirect('transactions') 
    else:
        form = TransactionForm(initial={'timestamp': datetime.now()}, user=request.user)
        formset = TransactionSplitFormSet(queryset=Transaction.objects.none(), form_kwargs={'user': request.user})
    
    context = {
        'header_data': {
            'title': 'Neue Transaktion',
            'selected_tab': 'transactions',
        },
        'form': form,
        'formset': formset,
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if transaction.user != request.user: # TODO: Fehlermeldung
        return redirect('transactions')
    if request.method == 'POST':
        form = TransactionForm(request.POST, instance=transaction, user=request.user)
        formset = TransactionSplitFormSet(
            request.POST, 
            instance=transaction, 
            form_kwargs={'user': request.user}
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            handle_refund_save(transaction, form)
            if transaction.is_refund or transaction.has_refunds or form.cleaned_data.get('is_refund'):
                calculate_refunds(request)
            return redirect('transactions')
    else:
        form = TransactionForm(instance=transaction, user=request.user)
        formset = TransactionSplitFormSet(
            instance=transaction, 
            form_kwargs={'user': request.user}
        )
    
    context = {
        'header_data': {
            'title': 'Transaktion bearbeiten',
            'selected_tab': 'transactions',
        },
        'form': form,
        'formset': formset,
        'is_edit': True
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_delete(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if transaction.user != request.user: # TODO: Fehlermeldung
        return redirect('transactions')
    if request.method == 'POST':
        if transaction.is_refund or transaction.has_refunds:
            recalculate_refunds = True
        else:
            recalculate_refunds = False
        transaction.delete()
        if recalculate_refunds:
            calculate_refunds(request)
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
    all_accounts = Account.objects.filter(is_mine=True, user=request.user)
    account_list = all_accounts.filter(is_closed=False)
    
    total_balance = sum(acc.get_current_balance() for acc in all_accounts)

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
    account_list = Account.objects.filter(user=request.user)
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
        
        transactions = chart_transactions(request, start_date, end_date, account_selected).prefetch_related('splits__category')

        income_by_category = {-2: {'name': 'Nicht kategorisiert', 'amount': 0, 'parent': None}}
        expenses_by_category = {-1: {'name': 'Nicht kategorisiert', 'amount': 0, 'parent': None}}
        
        total_income = 0
        total_expenses = 0
        
        for t in transactions:
            effective_amount = t.amount

            if t.has_refunds:
                effective_amount = t.remainder_after_refunds
                
            elif t.is_refund:
                effective_amount = t.remainder_of_refund

            if effective_amount == 0:
                continue

            scale_factor = effective_amount / t.amount if t.amount > 0 else 0


            is_income = t.receiver.is_mine and not t.sender.is_mine
            is_expense = not t.receiver.is_mine and t.sender.is_mine
            
            target_dict = None
            if is_income:
                target_dict = income_by_category
                total_income += effective_amount
            elif is_expense:
                target_dict = expenses_by_category
                total_expenses += effective_amount
            else:
                continue


            splits_sum_original = 0
            
            for split in t.splits.all():
                splits_sum_original += split.amount
                
                adjusted_split_amount = split.amount * scale_factor
                
                cat = split.category
                
                if cat.id not in target_dict:
                    target_dict[cat.id] = {
                        'name': cat.name, 
                        'amount': 0, 
                        'parent': cat.parent_category.id if cat.parent_category else None
                    }
                
                target_dict[cat.id]["amount"] += adjusted_split_amount

                if is_expense and target_dict[cat.id]["parent"] is not None:
                    parent_id = target_dict[cat.id]["parent"]
                    if parent_id not in target_dict:
                        parent_obj = cat.parent_category
                        target_dict[parent_id] = {
                            'name': parent_obj.name, 
                            'amount': 0, 
                            'parent': parent_obj.parent_category.id if parent_obj.parent_category else None
                        }
                    target_dict[parent_id]["amount"] += adjusted_split_amount

            uncategorized_original = t.amount - splits_sum_original
            
            if uncategorized_original > 0:
                adjusted_uncategorized = uncategorized_original * scale_factor
                uncat_key = -2 if is_income else -1
                target_dict[uncat_key]["amount"] += adjusted_uncategorized

    else:
        total_income = 0
        total_expenses = 0
        income_by_category = {}
        expenses_by_category = {}
    
    income_by_category = dict(sorted(income_by_category.items(), key=lambda item: item[1]['amount'], reverse=True))
    expenses_by_category = dict(sorted(expenses_by_category.items(), key=lambda item: item[1]['amount'], reverse=True))
    
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