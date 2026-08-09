# finance app — integration guide (HRBS)

Pure financial-accounts app: chart of accounts, general ledger, invoices,
payments. No user/staff account management here — that's coming later as its
own `accounts` app.

Drop the `finance/` folder into your HRBS project root, next to `rbs` and `htg`.

## 1. Register the app

In `config/settings.py`:

```python
INSTALLED_APPS = [
    ...
    'rbs',
    'htg',
    'finance',
]
```

## 2. Wire up URLs

In `config/urls.py`:

```python
from django.urls import include, path

urlpatterns = [
    ...
    path('finance/', include('finance.urls')),
]
```

## 3. Migrate

```bash
python manage.py makemigrations finance
python manage.py migrate
```

## 4. Create a couple of accounts to see reports populate

```bash
python manage.py shell
```
```python
from finance.models import Account, AccountType
Account.objects.create(code='1000', name='Cash', account_type=AccountType.ASSET)
Account.objects.create(code='4000', name='Room Revenue', account_type=AccountType.INCOME)
Account.objects.create(code='5000', name='Utilities Expense', account_type=AccountType.EXPENSE)
```

## What you get

| URL name                      | Purpose                                                   |
|--------------------------------|-------------------------------------------------------------|
| `finance:dashboard`            | Landing page linking to every report                       |
| `finance:financial_summary`    | Balances grouped by Asset/Liability/Equity/Income/Expense   |
| `finance:ledger`               | Transaction-level ledger per account, with running balance  |
| `finance:invoice_list`         | Filterable invoice list with billed/paid/outstanding totals |
| `finance:revenue`              | Payments received, grouped by method, for a date range      |
| `finance:account_statement`    | Printable single-account statement                          |

All report views take optional `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`
query params (a filter form on each page sets these for you). Every report
page has a Print button (`window.print()`) with print-specific CSS that hides
the nav and filter bar.

## Models

- **Account** — chart of accounts entry (code, name, type, opening balance).
  `.get_balance(as_of=None)` computes the balance from transactions.
- **Transaction** — a debit/credit ledger entry against an `Account`.
- **Invoice** — guest billing; `booking_reference` and `room_number` are plain
  text fields so this app doesn't hard-depend on `rbs`'s models. Swap in a real
  `ForeignKey` to your booking model once you're ready to link them.
- **Payment** — payments applied against an `Invoice`.

`Transaction.created_by` and `Payment.received_by`/`Invoice.created_by` point
at `settings.AUTH_USER_MODEL` (Django's built-in `User`) so you can already
see who did what — no dependency on the future `accounts` app is needed for
that. When you build the `accounts` app with `StaffProfile`, you can access
`transaction.created_by.staff_profile.role` etc. directly, since both apps
share the same underlying `User`.

## Notes / next steps

- Add `@permission_required` per view once roles exist (e.g. only accountants
  should see the financial summary / ledger).
- No CRUD views/templates were generated for Account/Transaction/Invoice/
  Payment — for now those are managed through Django admin (already
  registered in `admin.py`). Say the word if you want dedicated create/edit
  forms + templates for those too.
- CSV/PDF export isn't included — right now "export" is print-to-PDF via the
  browser. Ask if you want real CSV/XLSX downloads on any report.
