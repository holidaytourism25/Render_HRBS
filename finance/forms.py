from django import forms

from .models import Account, Invoice, Payment, Transaction


class DateRangeForm(forms.Form):
    """Reused by every report view to filter by a date range."""
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['code', 'name', 'account_type', 'opening_balance', 'is_active']


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'date', 'transaction_type', 'amount', 'description', 'reference']
        widgets = {'date': forms.DateInput(attrs={'type': 'date'})}


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['invoice_number', 'guest_name', 'room_number', 'booking_reference',
                  'issue_date', 'due_date', 'amount', 'tax', 'status', 'notes']
        widgets = {
            'issue_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['invoice', 'amount', 'payment_date', 'method', 'reference_no']
        widgets = {'payment_date': forms.DateInput(attrs={'type': 'date'})}
