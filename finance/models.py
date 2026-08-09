from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone


# ---------------------------------------------------------------------------
# Chart of accounts / ledger
# ---------------------------------------------------------------------------

class AccountType(models.TextChoices):
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'
    INCOME = 'INCOME', 'Income'
    EXPENSE = 'EXPENSE', 'Expense'


class Account(models.Model):
    """A single line in the chart of accounts, e.g. 'Room Revenue', 'Cash'."""
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    opening_balance = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def get_balance(self, as_of=None):
        qs = self.transactions.all()
        if as_of:
            qs = qs.filter(date__lte=as_of)
        debit = qs.filter(transaction_type=Transaction.Type.DEBIT).aggregate(t=Sum('amount'))['t'] or Decimal('0')
        credit = qs.filter(transaction_type=Transaction.Type.CREDIT).aggregate(t=Sum('amount'))['t'] or Decimal('0')

        # Normal balance side depends on account type.
        if self.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            return self.opening_balance + debit - credit
        return self.opening_balance + credit - debit


class Transaction(models.Model):
    """A single ledger entry against an account."""
    class Type(models.TextChoices):
        DEBIT = 'DEBIT', 'Debit'
        CREDIT = 'CREDIT', 'Credit'

    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='transactions')
    date = models.DateField(default=timezone.now)
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    reference = models.CharField(max_length=100, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_transactions_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"{self.date} | {self.account.code} | {self.transaction_type} {self.amount}"


# ---------------------------------------------------------------------------
# Invoices & payments (guest billing tied loosely to bookings)
# ---------------------------------------------------------------------------

class InvoiceStatus(models.TextChoices):
    DRAFT = 'DRAFT', 'Draft'
    ISSUED = 'ISSUED', 'Issued'
    PAID = 'PAID', 'Paid'
    OVERDUE = 'OVERDUE', 'Overdue'
    CANCELLED = 'CANCELLED', 'Cancelled'


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=30, unique=True)
    guest_name = models.CharField(max_length=150)
    room_number = models.CharField(max_length=20, blank=True)
    # Optional loose link to the booking app, kept as plain fields so this
    # app doesn't hard-depend on rbs's models. Wire up a real FK later if useful.
    booking_reference = models.CharField(max_length=50, blank=True)

    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_invoices_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-issue_date']

    def __str__(self):
        return f"{self.invoice_number} - {self.guest_name}"

    @property
    def total(self):
        return self.amount + self.tax

    @property
    def total_paid(self):
        return self.payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    @property
    def balance_due(self):
        return self.total - self.total_paid


class PaymentMethod(models.TextChoices):
    CASH = 'CASH', 'Cash'
    CARD = 'CARD', 'Card'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
    ONLINE = 'ONLINE', 'Online'


class Payment(models.Model):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    reference_no = models.CharField(max_length=100, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='finance_payments_received'
    )

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.invoice.invoice_number} - {self.amount} on {self.payment_date}"
