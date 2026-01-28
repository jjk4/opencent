from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import Transaction, Account, Category, TransactionSplit

class TransactionForm(forms.ModelForm):
    timestamp = forms.DateTimeField(
        label="Datum & Zeit",
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
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
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
            ('Meine Konten', get_choices(my_accounts)),
            ('Externe Konten', get_choices(other_accounts)),
        ]

        self.fields['sender'].choices = grouped_choices
        self.fields['receiver'].choices = grouped_choices

    def clean(self):
        cleaned_data = super().clean()
        sender = cleaned_data.get('sender')
        receiver = cleaned_data.get('receiver')
        amount = cleaned_data.get('amount')

        if sender == receiver:
            raise forms.ValidationError("Sender und Empfänger können nicht identisch sein.")
            
        if amount and amount < 0:
             raise forms.ValidationError("Der Betrag darf nicht negativ sein.")
             
        return cleaned_data

class TransactionSplitForm(forms.ModelForm):
    class Meta:
        model = TransactionSplit
        fields = ['category', 'amount']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Betrag'}),
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
             if round(total_split_amount, 2) != round(transaction_amount, 2):
                raise forms.ValidationError(
                    f"Die Summe der Kategorien ({total_split_amount} €) entspricht nicht dem Gesamtbetrag ({transaction_amount} €)."
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
    class Meta:
        model = Account
        fields = ['name', 'start_balance', 'is_mine', 'icon']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'start_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_mine': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'icon': forms.FileInput(attrs={'class': 'form-control'}),
        }
    def clean(self):
        cleaned_data = super().clean()
        start_balance = cleaned_data.get('start_balance')

        if start_balance and start_balance < 0:
            raise forms.ValidationError("Der Anfangssaldo darf nicht negativ sein.")
            
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
        
