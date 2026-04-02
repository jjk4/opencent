from django.http import HttpResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from collections import defaultdict
import datetime
import json
from decimal import Decimal

from ..models import Account, Category
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

@login_required
def chart_income_expense_bar(request):
    template = loader.get_template('charts/income_expense_bar.html')
    
    group_by = request.POST.get('group_by', 'month')
    
    if request.method == 'POST':
        timerange = chart_timerange(request)
        start_date = timerange[0]
        end_date = timerange[1]
        
        account_selected = request.POST.get('account') and request.POST.get('account') != 'all'
        transactions = chart_transactions(request, start_date, end_date, account_selected)
        
        grouped_data = {}
        
        for t in transactions:
            effective_amount = t.amount
            if t.has_refunds:
                effective_amount = t.remainder_after_refunds
            elif t.is_refund:
                effective_amount = t.remainder_of_refund

            if effective_amount == 0:
                continue

            is_income = t.receiver.is_mine and not t.sender.is_mine
            is_expense = not t.receiver.is_mine and t.sender.is_mine
            
            if not (is_income or is_expense):
                continue

            if group_by == 'year':
                key = t.timestamp.strftime('%Y')
                sort_key = t.timestamp.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            elif group_by == 'week':
                key = t.timestamp.strftime('%G-W%V')
                sort_key = t.timestamp - datetime.timedelta(days=t.timestamp.weekday())
                sort_key = sort_key.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                key = t.timestamp.strftime('%Y-%m')
                sort_key = t.timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

            if key not in grouped_data:
                grouped_data[key] = {'sort_key': sort_key, 'income': 0, 'expense': 0, 'label': key}

            if is_income:
                grouped_data[key]['income'] += effective_amount
            elif is_expense:
                grouped_data[key]['expense'] += effective_amount

        sorted_data = sorted(grouped_data.values(), key=lambda x: x['sort_key'])
        
        categories = [item['label'] for item in sorted_data]
        incomes = [float(item['income']) for item in sorted_data]
        expenses = [float(item['expense']) for item in sorted_data]
        
    else:
        categories = []
        incomes = []
        expenses = []
   
    context = {
        'header_data': {
            'title': _('Charts'),
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'categories': json.dumps(categories),
        'incomes': json.dumps(incomes),
        'expenses': json.dumps(expenses),
        'group_by': group_by,
    }
    return HttpResponse(template.render(context, request))

@login_required
def chart_category_comparison(request):
    template = loader.get_template('charts/category_comparison.html')
    
    group_by = request.POST.get('group_by', 'month')
    selected_category_ids = request.POST.getlist('categories')
    
    # Alle Kategorien des Users
    all_categories = Category.objects.filter(user=request.user)
    
    context = {
        'header_data': {
            'title': _('Charts'),
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'all_categories': all_categories,
        'selected_categories': [int(cat_id) for cat_id in selected_category_ids if cat_id.isdigit()],
        'group_by': group_by,
        'chart_categories': '[]',
        'series': '[]',
        'error_message': None,
    }

    if request.method == 'POST' and selected_category_ids:
        timerange = chart_timerange(request)
        start_date, end_date = timerange[0], timerange[1]
        
        account_selected = request.POST.get('account') and request.POST.get('account') != 'all'
        
        transactions = chart_transactions(request, start_date, end_date, account_selected).prefetch_related('splits__category')
        
        category_mapping = defaultdict(list)
        
        for cat_id_str in selected_category_ids:
            cat = all_categories.filter(id=int(cat_id_str)).first()
            if cat:
                category_mapping[cat.id].append(cat_id_str)
                for subcat in cat.get_all_subcategories_recursive():
                    category_mapping[subcat.id].append(cat_id_str)

        category_types = {}
        data_by_cat_and_time = defaultdict(lambda: defaultdict(Decimal))
        time_keys = set()
        time_sort_keys = {}
        
        error_found = False
        
        for t in transactions:
            effective_amount = t.amount
            if t.has_refunds:
                effective_amount = t.remainder_after_refunds
            elif t.is_refund:
                effective_amount = t.remainder_of_refund

            if effective_amount <= 0:
                continue

            is_income = t.receiver.is_mine and not t.sender.is_mine
            is_expense = not t.receiver.is_mine and t.sender.is_mine
            
            if not (is_income or is_expense):
                continue
                
            t_type = 'income' if is_income else 'expense'
            scale_factor = effective_amount / t.amount if t.amount > 0 else 0
            
            if group_by == 'year':
                time_key = t.timestamp.strftime('%Y')
                sort_key = t.timestamp.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            elif group_by == 'week':
                time_key = t.timestamp.strftime('%G-W%V')
                sort_key = t.timestamp - datetime.timedelta(days=t.timestamp.weekday())
                sort_key = sort_key.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                time_key = t.timestamp.strftime('%Y-%m')
                sort_key = t.timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                
            for split in t.splits.all():
                split_cat_id = split.category.id
                
                if split_cat_id in category_mapping:
                    
                    for target_cat_id in category_mapping[split_cat_id]:
                        
                        if target_cat_id in category_types and category_types[target_cat_id] != t_type:
                            target_cat_name = all_categories.filter(id=int(target_cat_id)).first().name
                            context['error_message'] = _(f"The category '{target_cat_name}' (or one of its subcategories) contains both income and expenses in the selected period. A comparison is not possible.")
                            error_found = True
                            break
                        
                        category_types[target_cat_id] = t_type
                        time_keys.add(time_key)
                        time_sort_keys[time_key] = sort_key
                        
                        adjusted_amount = split.amount * scale_factor
                        data_by_cat_and_time[target_cat_id][time_key] += adjusted_amount
                
                if error_found:
                    break
            
            if error_found:
                break
                
        if not error_found and time_keys:
            sorted_time_keys = sorted(list(time_keys), key=lambda k: time_sort_keys[k])
            
            series = []
            for cat_id in selected_category_ids:
                cat = all_categories.filter(id=int(cat_id)).first()
                if cat:
                    data = []
                    for tk in sorted_time_keys:
                        data.append(float(data_by_cat_and_time[str(cat.id)][tk]))
                    
                    if any(val > 0 for val in data):
                        series.append({
                            'name': cat.name,
                            'data': data
                        })
            
            context['chart_categories'] = json.dumps(sorted_time_keys)
            context['series'] = json.dumps(series)

    return HttpResponse(template.render(context, request))

@login_required
def chart_expense_heatmap(request):
    template = loader.get_template('charts/expense_heatmap.html')
    
    group_by = request.POST.get('group_by', 'day_of_week')
    
    context = {
        'header_data': {
            'title': _('Charts'),
            'selected_tab': 'analysis',
        },
        'accounts': Account.objects.filter(is_mine=True, user=request.user),
        'group_by': group_by,
        'series': '[]',
    }

    if request.method == 'POST':
        timerange = chart_timerange(request)
        start_date, end_date = timerange[0], timerange[1]
        
        account_selected = request.POST.get('account') and request.POST.get('account') != 'all'
        transactions = chart_transactions(request, start_date, end_date, account_selected)
        
        data_dict = defaultdict(lambda: defaultdict(float))
        x_labels_set = set()
        
        for t in transactions:
            effective_amount = t.amount
            if t.has_refunds:
                effective_amount = t.remainder_after_refunds
            elif t.is_refund:
                effective_amount = t.remainder_of_refund

            if effective_amount <= 0:
                continue

            is_expense = not t.receiver.is_mine and t.sender.is_mine
            if not is_expense:
                continue
                
            if group_by == 'day_of_week':
                y_key = str(t.timestamp.weekday())
                x_key = t.timestamp.strftime('%G-W%V')
            elif group_by == 'day_of_month':
                y_key = t.timestamp.strftime('%Y-%m')
                x_key = str(t.timestamp.day)
            elif group_by == 'month_of_year':
                y_key = t.timestamp.strftime('%Y')
                x_key = str(t.timestamp.month)

            data_dict[y_key][x_key] += float(effective_amount)
            x_labels_set.add(x_key)

        series_data = []
        
        if group_by == 'day_of_week':
            weekday_names = {
                0: _('Monday'), 1: _('Tuesday'), 2: _('Wednesday'), 
                3: _('Thursday'), 4: _('Friday'), 5: _('Saturday'), 6: _('Sunday')
            }
            sorted_x = sorted(list(x_labels_set))
            for y_idx in range(7):
                y_str = str(y_idx)
                data_points = [{'x': x, 'y': data_dict[y_str].get(x, 0)} for x in sorted_x]
                series_data.append({'name': weekday_names[y_idx], 'data': data_points})
                
        elif group_by == 'day_of_month':
            sorted_y = sorted(list(data_dict.keys()), reverse=True)
            sorted_x = [str(i) for i in range(1, 32)]
            for y_str in sorted_y:
                data_points = [{'x': x, 'y': data_dict[y_str].get(x, 0)} for x in sorted_x]
                series_data.append({'name': y_str, 'data': data_points})
                
        elif group_by == 'month_of_year':
            sorted_y = sorted(list(data_dict.keys()), reverse=True)
            sorted_x = [str(i) for i in range(1, 13)]
            month_names = {
                '1': _('Jan'), '2': _('Feb'), '3': _('Mar'), '4': _('Apr'), 
                '5': _('May'), '6': _('Jun'), '7': _('Jul'), '8': _('Aug'), 
                '9': _('Sep'), '10': _('Oct'), '11': _('Nov'), '12': _('Dec')
            }
            for y_str in sorted_y:
                data_points = [{'x': month_names[x], 'y': data_dict[y_str].get(x, 0)} for x in sorted_x]
                series_data.append({'name': y_str, 'data': data_points})

        context['series'] = json.dumps(series_data)
        
        totals_data = []
        totals_categories = []
        totals_title = ""

        if group_by == 'day_of_week':
            for y_idx in range(7):
                y_str = str(y_idx)
                total = sum(data_dict[y_str].values())
                totals_data.append(float(total))
                totals_categories.append(weekday_names[y_idx])
            totals_title = _("Total per Weekday")

        elif group_by == 'day_of_month':
            for x_idx in range(1, 32):
                x_str = str(x_idx)
                total = sum(data_dict[y_key].get(x_str, 0) for y_key in data_dict.keys())
                totals_data.append(float(total))
                totals_categories.append(x_str)
            totals_title = _("Total per Day of Month")

        elif group_by == 'month_of_year':
            for x_idx in range(1, 13):
                x_str = str(x_idx)
                total = sum(data_dict[y_key].get(x_str, 0) for y_key in data_dict.keys())
                totals_data.append(float(total))
                totals_categories.append(month_names[x_str])
            totals_title = _("Total per Month")

        context['totals_series'] = json.dumps([{'name': _('Total'), 'data': totals_data}])
        context['totals_categories'] = json.dumps(totals_categories)
        context['totals_title'] = totals_title

    return HttpResponse(template.render(context, request))
