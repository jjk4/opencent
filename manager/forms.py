from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.utils.translation import gettext_lazy as _
from .models import Transaction, Account, Category, TransactionSplit

class TransactionForm(forms.ModelForm):
    amount = forms.DecimalField(
        label=_("Amount"),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    is_refund = forms.BooleanField(
        label=_("Is a refund"), 
        required=False, 
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    refund_links = forms.ModelMultipleChoiceField(
        queryset=Transaction.objects.none(),
        required=False,
        label=_("Original transaction(s)"),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2-transactions'}) 
    )

    timestamp = forms.DateTimeField(
        label=_("Date & Time"),
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local', 'class': 'form-control'},
            format='%Y-%m-%dT%H:%M'
        ),
        input_formats=['%Y-%m-%dT%H:%M']
    )
    
    class Meta:
        model = Transaction
        fields = ['sender', 'receiver', 'amount', 'timestamp', 'description']
        
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'sender': forms.Select(attrs={'class': 'form-select'}),
            'receiver': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Trennen der auszuwählenden Konten in eigene / fremde
        my_accounts = Account.objects.filter(is_mine=True, user=user).order_by('name')
        other_accounts = Account.objects.filter(is_mine=False, user=user).order_by('name')
        
        def get_choices(objects):
            return [(obj.id, str(obj)) for obj in objects]

        grouped_choices = [
            ('', '---------'), 
            (_('My Accounts'), get_choices(my_accounts)),
            (_('External Accounts'), get_choices(other_accounts)),
        ]

        self.fields['sender'].choices = grouped_choices
        self.fields['receiver'].choices = grouped_choices

        if user:
            qs = Transaction.objects.filter(user=user)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            selected_ids = []
            
            if self.instance.pk and self.instance.refund_transaction_refunds.exists():
                selected_ids = list(self.instance.refund_transaction_refunds.values_list('original_transaction_id', flat=True))
                self.fields['is_refund'].initial = True
                self.fields['refund_links'].initial = selected_ids
            
            if self.is_bound:
                if hasattr(self.data, 'getlist'):
                    raw_links = self.data.getlist('refund_links')
                else:
                    raw_links = self.data.get('refund_links', [])
                    if not isinstance(raw_links, list):
                        raw_links = [raw_links]

                if raw_links:
                    try:
                        selected_ids.extend([int(link_id) for link_id in raw_links])
                    except (ValueError, TypeError):
                        pass
            
            if selected_ids:
                self.fields['refund_links'].queryset = qs.filter(id__in=selected_ids)
            else:
                self.fields['refund_links'].queryset = qs.none()

    def clean(self):
        cleaned_data = super().clean()
        sender = cleaned_data.get('sender')
        receiver = cleaned_data.get('receiver')
        amount = cleaned_data.get('amount')
        is_refund = cleaned_data.get('is_refund')
        refund_links = cleaned_data.get('refund_links')

        if sender and receiver and sender == receiver:
            raise forms.ValidationError(_("Sender and receiver cannot be identical."))
            
        if amount and amount < 0:
             raise forms.ValidationError(_("The amount cannot be negative."))
        
        if is_refund and not refund_links:
            self.add_error('refund_links', _("Please select at least one original transaction."))
             
        return cleaned_data


class TransactionSplitForm(forms.ModelForm):
    amount = forms.DecimalField(
        label=_("Amount"),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': _('Amount')})
    )

    class Meta:
        model = TransactionSplit
        fields = ['category', 'amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['category'].queryset = Category.objects.filter(user=user)


class BaseTransactionSplitFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        
        if any(self.errors):
            return

        total_split_amount = 0
        has_splits = False
        
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get('DELETE'):
                continue
            
            amount = form.cleaned_data.get('amount')
            if amount:
                total_split_amount += amount
                has_splits = True

        transaction_amount = self.instance.amount
        
        if has_splits and transaction_amount is not None:
             if round(total_split_amount, 2) > round(transaction_amount, 2):
                raise forms.ValidationError(
                    _("The sum of the categories (%(split_amount)s €) cannot exceed the total amount (%(total_amount)s €).") % {
                        'split_amount': total_split_amount,
                        'total_amount': transaction_amount
                    }
                )

TransactionSplitFormSet = inlineformset_factory(
    Transaction,
    TransactionSplit,
    form=TransactionSplitForm,
    formset=BaseTransactionSplitFormSet, 
    extra=1,
    can_delete=True
)


class AccountForm(forms.ModelForm):
    start_balance = forms.DecimalField(
        label=_("Starting balance"),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )

    class Meta:
        model = Account
        fields = ['name', 'start_balance', 'is_mine', 'is_closed', 'icon', 'account_nr']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_nr': forms.TextInput(attrs={'class': 'form-control'}),
            'is_mine': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_closed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon': forms.FileInput(attrs={'class': 'form-control'}),
        }
    def clean(self):
        cleaned_data = super().clean()            
        return cleaned_data
    
class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent_category', 'icon']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'parent_category': forms.Select(attrs={'class': 'form-select'}),
            'icon': forms.TextInput(attrs={'class': 'form-control'}),
        }
    def __init__(self, *args, **kwargs):
            user = kwargs.pop('user', None)
            super().__init__(*args, **kwargs)
            if user:
                self.fields['parent_category'].queryset = Category.objects.filter(user=user)