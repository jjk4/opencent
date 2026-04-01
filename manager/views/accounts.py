from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import gettext as _

from ..models import Account
from ..forms import AccountForm

@login_required
def accounts(request):
    account_list = Account.objects.filter(user=request.user)
    context = {
        'header_data': {
            'title': _('Accounts'),
            'selected_tab': 'accounts',
        },
        'accounts': account_list,
    }
    return render(request, 'accounts/index.html', context)

@login_required
def account_detail(request, account_id):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    account.current_balance = account.get_current_balance()
    context = {
        'header_data': {
            'title': f"{account.name} {_('Details')}",
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
            'title': _('New Account'),
            'selected_tab': 'accounts',
        },
        'form': form,
    }
    return render(request, 'accounts/add.html', context)

@login_required
def account_edit(request, account_id):
    account = get_object_or_404(Account, id=account_id, user=request.user)
    if request.method == 'POST':
        form = AccountForm(request.POST, request.FILES, instance=account)
        if form.is_valid():
            form.save()
            return redirect('accounts')
    else:
        form = AccountForm(instance=account)
    
    context = {
        'header_data': {
            'title': _('Edit Account'),
            'selected_tab': 'accounts',
        },
        'form': form,
        'is_edit': True
    }
    return render(request, 'accounts/add.html', context)

@login_required
def account_delete(request, account_id):
    account = get_object_or_404(Account, id=account_id, user=request.user)

    if request.method == 'POST':
        account.delete()
        return redirect('accounts')
        
    context = {
         'header_data': {
            'title': _('Delete Account'),
            'selected_tab': 'accounts',
        },
        'account': account
    }
    return render(request, 'accounts/delete.html', context)