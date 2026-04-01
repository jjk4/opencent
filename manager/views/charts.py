from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _

from ..models import Account
from ..utils import chart_timerange, chart_startbalance, chart_transactions

@login_required
def charts(request):
    template = loader.get_template('charts/index.html')
    context = {
        'header_data': {
            'title': _('Analysis'),
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
            'title': _('Charts'),
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

        income_by_category = {-2: {'name': _('Uncategorized'), 'amount': 0, 'parent': None}}
        expenses_by_category = {-1: {'name': _('Uncategorized'), 'amount': 0, 'parent': None}}
        
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
                
                current_cat = split.category
                
                while current_cat is not None:
                    if current_cat.id not in target_dict:
                        target_dict[current_cat.id] = {
                            'name': current_cat.name, 
                            'amount': 0, 
                            'parent': current_cat.parent_category.id if current_cat.parent_category else None
                        }
                    
                    target_dict[current_cat.id]["amount"] += adjusted_split_amount
                    
                    current_cat = current_cat.parent_category

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
            'title': _('Charts'),
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'income_by_category': income_by_category,
        'expenses_by_category': expenses_by_category,
        'total_expenses': total_expenses,
        'total_income': total_income,
    }
    return HttpResponse(template.render(context, request))

