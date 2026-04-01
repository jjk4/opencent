from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from decimal import Decimal

from ..models import Transaction, Account, Category, Refund
from ..forms import TransactionForm, TransactionSplitFormSet

@login_required
def transactions(request):
    is_filter_active = False
    transaction_list = Transaction.objects.filter(user=request.user, timestamp__lte=timezone.now()).select_related(
            'sender', 'receiver'
        ).prefetch_related(
            'splits__category',
            'original_transaction_refunds', 
            'original_transaction_refunds__refund_transaction'
        ).order_by('-timestamp')
    transaction_list_future = Transaction.objects.filter(user=request.user, timestamp__gt=timezone.now()).select_related(
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
        transaction_list_future = transaction_list_future.filter(
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
        transaction_list_future = transaction_list_future.filter(categories__id__in=category_ids).distinct()

    paginator = Paginator(transaction_list, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj,
        'header_data': {
            'title': _('Transactions'),
            'selected_tab': 'transactions',
        },
        'transaction_list': transaction_list,
        'transaction_list_future': transaction_list_future,
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
        id=transaction_id,
        user=request.user
    )

    context = {
        'header_data': {
            'title': f"{transaction.description or _('Transaction')} {transaction.id} - {_('Details')}",
            'selected_tab': 'transactions',
        },
        'transaction': transaction,
        'is_refund_of': transaction.is_refund_of,
        'refunds': transaction.refunds,
    }
    return render(request, 'transactions/detail.html', context)

@login_required
def transaction_add(request, copy_id=None):
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
                
                is_refund = form.cleaned_data.get('is_refund')
                refund_links = form.cleaned_data.get('refund_links')
                
                if is_refund and refund_links:
                    for original in refund_links:
                        Refund.objects.create(
                            original_transaction=original,
                            refund_transaction=new_transaction
                        )
                
                return redirect('transactions')
    else:
        if copy_id:
            original_transaction = get_object_or_404(Transaction, id=copy_id, user=request.user)
            
            initial_transaction = {
                'sender': original_transaction.sender,
                'receiver': original_transaction.receiver,
                'amount': original_transaction.amount,
                'description': original_transaction.description,
                'timestamp': original_transaction.timestamp,
            }
            initial_splits = []

            for split in original_transaction.splits.all():
                initial_splits.append({
                    'category': split.category,
                    'amount': split.amount
                })
                
        else:
            initial_transaction = {
                'timestamp': timezone.now(),
            }
            initial_splits = []
        form = TransactionForm(initial=initial_transaction, user=request.user)

        TransactionSplitFormSet.extra = len(initial_splits) if len(initial_splits)>0 else 1
        formset = TransactionSplitFormSet(
            queryset=Transaction.objects.none(), 
            initial=initial_splits, 
            form_kwargs={'user': request.user}
        )
    
    context = {
        'header_data': {
            'title': _('New Transaction'),
            'selected_tab': 'transactions',
        },
        'form': form,
        'formset': formset,
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_search_ajax(request):
    """AJAX endpoint for Select2 to search transactions."""
    query = request.GET.get('q', '')
    
    qs = Transaction.objects.filter(user=request.user).select_related('sender', 'receiver').order_by('-timestamp')
    
    if query:
        filter_q = Q(description__icontains=query) | \
                   Q(sender__name__icontains=query) | \
                   Q(receiver__name__icontains=query)
                   
        try:
            amount_query = Decimal(query.replace(',', '.'))
            filter_q |= Q(amount=amount_query)
        except (ValueError, TypeError, ArithmeticError):
            pass
            
        qs = qs.filter(filter_q)
        
    qs = qs[:30]
    
    results = []
    for t in qs:
        date_str = t.timestamp.strftime('%d.%m.%Y')
        text = f"{date_str} | {t.sender.name} -> {t.receiver.name} | {t.amount} €"
        if t.description:
            text += f" | {t.description}"
            
        results.append({
            'id': t.id,
            'text': text
        })
        
    return JsonResponse({'results': results})

@login_required
def transaction_edit(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)

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
            
            Refund.objects.filter(refund_transaction=transaction).delete()
            
            is_refund = form.cleaned_data.get('is_refund')
            refund_links = form.cleaned_data.get('refund_links')
            
            if is_refund and refund_links:
                for original in refund_links:
                    Refund.objects.create(
                        original_transaction=original,
                        refund_transaction=transaction
                    )
            
            return redirect('transactions')
    else:
        form = TransactionForm(instance=transaction, user=request.user)
        formset = TransactionSplitFormSet(
            instance=transaction, 
            form_kwargs={'user': request.user}
        )
    
    context = {
        'header_data': {
            'title': _('Edit Transaction'),
            'selected_tab': 'transactions',
        },
        'form': form,
        'formset': formset,
        'is_edit': True
    }
    return render(request, 'transactions/add.html', context)

@login_required
def transaction_delete(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, user=request.user)

    if request.method == 'POST':
        transaction.delete()
        return redirect('transactions')
        
    context = {
         'header_data': {
            'title': _('Delete Transaction'),
            'selected_tab': 'transactions',
        },
        'transaction': transaction
    }
    return render(request, 'transactions/delete.html', context)