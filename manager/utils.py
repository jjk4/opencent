from django.utils import timezone
from datetime import datetime
from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import Coalesce
from .models import Transaction, Account
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

def chart_timerange(request):
    last_tx = Transaction.objects.filter(user=request.user).last()
    start_date_fallback = last_tx.timestamp if last_tx else timezone.now()
    first_tx = Transaction.objects.filter(user=request.user).first()
    end_date_fallback = first_tx.timestamp if first_tx else timezone.now()
    
    # Determine time range
    if request.POST.get('time') == 'custom':
        try:
            start_date = timezone.make_aware(datetime.strptime(request.POST.get('start_date'), '%Y-%m-%dT%H:%M'))
            end_date = timezone.make_aware(datetime.strptime(request.POST.get('end_date'), '%Y-%m-%dT%H:%M'))
        except ValueError:
            start_date = start_date_fallback
            end_date = end_date_fallback

    else:
        if request.POST.get('time') == 'this-month':
            now = timezone.now()
            start_date = timezone.make_aware(datetime(now.year, now.month, 1))
            end_date = timezone.make_aware(datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1))
        elif request.POST.get('time') == 'last-month':
            now = timezone.now()
            start_date = timezone.make_aware(datetime(now.year, now.month - 1, 1) if now.month > 1 else datetime(now.year - 1, 12, 1))
            end_date = timezone.make_aware(datetime(now.year, now.month, 1))
        elif request.POST.get('time') == 'this-year':
            now = timezone.now()
            start_date = timezone.make_aware(datetime(now.year, 1, 1))
            end_date = timezone.make_aware(datetime(now.year + 1, 1, 1))
        elif request.POST.get('time') == 'last-year':
            now = timezone.now()
            start_date = timezone.make_aware(datetime(now.year - 1, 1, 1))
            end_date = timezone.make_aware(datetime(now.year, 1, 1))
        elif request.POST.get('time') == 'all-time':
            start_date = start_date_fallback
            end_date = end_date_fallback
        else:
            start_date = start_date_fallback
            end_date = end_date_fallback

    return [start_date, end_date]

def chart_startbalance(request, start_date, end_date, account_selected):
    if account_selected:
        account_id = request.POST.get('account')
        start_balance = Account.objects.get(id=account_id, user=request.user).start_balance
        
        incoming = Transaction.objects.filter(
            user=request.user, 
            timestamp__lt=start_date, 
            receiver__id=account_id
        ).aggregate(total=Coalesce(Sum('amount'), Decimal(0)))['total']
        
        outgoing = Transaction.objects.filter(
            user=request.user, 
            timestamp__lt=start_date, 
            sender__id=account_id
        ).aggregate(total=Coalesce(Sum('amount'), Decimal(0)))['total']
        
        start_balance = start_balance + incoming - outgoing
        
    else:
        start_balance = Account.objects.filter(
            is_mine=True, 
            user=request.user
        ).aggregate(total=Coalesce(Sum('start_balance'), Decimal(0)))['total']
        
        incoming = Transaction.objects.filter(
            user=request.user, 
            timestamp__lt=start_date, 
            receiver__is_mine=True
        ).aggregate(total=Coalesce(Sum('amount'), Decimal(0)))['total']
        
        outgoing = Transaction.objects.filter(
            user=request.user, 
            timestamp__lt=start_date, 
            sender__is_mine=True
        ).aggregate(total=Coalesce(Sum('amount'), Decimal(0)))['total']
        
        start_balance = start_balance + incoming - outgoing
        
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
    ).filter(user=request.user, timestamp__lte=timezone.now()).order_by('timestamp')
    
    if from_date:
        transactions = transactions.filter(timestamp__gte=from_date)

    if not transactions.exists():
         return [{'date': _('Start'), 'balance': float(current_balance)}]

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
