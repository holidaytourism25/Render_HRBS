from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, render

from .forms import DateRangeForm
from .models import Account, AccountType, Invoice, InvoiceStatus, Payment, Transaction


def _parse_range(request):
    """Pull start_date / end_date off the query string into a bound form."""
    form = DateRangeForm(request.GET or None)
    start_date = end_date = None
    if form.is_valid():
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
    return form, start_date, end_date


@login_required
def dashboard(request):
    context = {
        'total_accounts': Account.objects.filter(is_active=True).count(),
        'total_invoices': Invoice.objects.count(),
        'outstanding_invoices': Invoice.objects.exclude(
            status__in=[InvoiceStatus.PAID, InvoiceStatus.CANCELLED]
        ).count(),
        'total_revenue': Payment.objects.aggregate(t=Sum('amount'))['t'] or Decimal('0'),
    }
    return render(request, 'finance/dashboard.html', context)


@login_required
def financial_summary_report(request):
    """Totals grouped by account type (income, expense, asset, etc.) for a date range."""
    form, start_date, end_date = _parse_range(request)

    rows = []
    grand_total = Decimal('0')
    for value, label in AccountType.choices:
        accounts = Account.objects.filter(account_type=value, is_active=True)
        type_total = Decimal('0')
        account_rows = []
        for account in accounts:
            balance = account.get_balance(as_of=end_date) if end_date else account.get_balance()
            account_rows.append({'account': account, 'balance': balance})
            type_total += balance
        rows.append({'type_label': label, 'accounts': account_rows, 'type_total': type_total})
        grand_total += type_total

    context = {
        'form': form, 'rows': rows, 'grand_total': grand_total,
        'start_date': start_date, 'end_date': end_date,
    }
    return render(request, 'finance/financial_summary.html', context)


@login_required
def ledger_report(request, account_id=None):
    """Transaction-level ledger for one account, with a running balance."""
    accounts = Account.objects.filter(is_active=True)
    account = get_object_or_404(Account, pk=account_id) if account_id else accounts.first()

    form, start_date, end_date = _parse_range(request)
    transactions = Transaction.objects.filter(account=account) if account else Transaction.objects.none()
    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    transactions = transactions.order_by('date', 'created_at')

    running = account.opening_balance if account else Decimal('0')
    rows = []
    for txn in transactions:
        if account and account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            running += txn.amount if txn.transaction_type == Transaction.Type.DEBIT else -txn.amount
        else:
            running += txn.amount if txn.transaction_type == Transaction.Type.CREDIT else -txn.amount
        rows.append({'txn': txn, 'running_balance': running})

    context = {
        'form': form, 'accounts': accounts, 'account': account, 'rows': rows,
        'start_date': start_date, 'end_date': end_date,
    }
    return render(request, 'finance/ledger_report.html', context)


@login_required
def invoice_list_report(request):
    """Filterable list of invoices with running totals."""
    form, start_date, end_date = _parse_range(request)
    status = request.GET.get('status', '')

    invoices = Invoice.objects.all()
    if start_date:
        invoices = invoices.filter(issue_date__gte=start_date)
    if end_date:
        invoices = invoices.filter(issue_date__lte=end_date)
    if status:
        invoices = invoices.filter(status=status)

    total_billed = sum((inv.total for inv in invoices), Decimal('0'))
    total_paid = sum((inv.total_paid for inv in invoices), Decimal('0'))

    context = {
        'form': form, 'invoices': invoices, 'status': status,
        'status_choices': InvoiceStatus.choices,
        'total_billed': total_billed, 'total_paid': total_paid,
        'total_outstanding': total_billed - total_paid,
        'start_date': start_date, 'end_date': end_date,
    }
    return render(request, 'finance/invoice_list.html', context)


@login_required
def revenue_report(request):
    """Payments received, grouped by method, for a date range."""
    form, start_date, end_date = _parse_range(request)

    payments = Payment.objects.all()
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)

    by_method = payments.values('method').annotate(total=Sum('amount')).order_by('-total')
    grand_total = payments.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    context = {
        'form': form, 'payments': payments.order_by('-payment_date'),
        'by_method': by_method, 'grand_total': grand_total,
        'start_date': start_date, 'end_date': end_date,
    }
    return render(request, 'finance/revenue_report.html', context)


@login_required
def account_statement(request, account_id):
    """Printable statement for a single account."""
    account = get_object_or_404(Account, pk=account_id)
    form, start_date, end_date = _parse_range(request)

    transactions = account.transactions.all()
    if start_date:
        transactions = transactions.filter(date__gte=start_date)
    if end_date:
        transactions = transactions.filter(date__lte=end_date)
    transactions = transactions.order_by('date', 'created_at')

    running = account.opening_balance
    rows = []
    for txn in transactions:
        if account.account_type in (AccountType.ASSET, AccountType.EXPENSE):
            running += txn.amount if txn.transaction_type == Transaction.Type.DEBIT else -txn.amount
        else:
            running += txn.amount if txn.transaction_type == Transaction.Type.CREDIT else -txn.amount
        rows.append({'txn': txn, 'running_balance': running})

    context = {
        'form': form, 'account': account, 'rows': rows, 'closing_balance': running,
        'start_date': start_date, 'end_date': end_date,
    }
    return render(request, 'finance/account_statement.html', context)
