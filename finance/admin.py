from django.contrib import admin

from .models import Account, Invoice, Payment, Transaction


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'account_type', 'opening_balance', 'is_active')
    list_filter = ('account_type', 'is_active')
    search_fields = ('code', 'name')


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date', 'account', 'transaction_type', 'amount', 'reference', 'created_by')
    list_filter = ('transaction_type', 'account')
    search_fields = ('description', 'reference')
    date_hierarchy = 'date'


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'guest_name', 'room_number', 'issue_date',
                     'due_date', 'total', 'balance_due', 'status')
    list_filter = ('status',)
    search_fields = ('invoice_number', 'guest_name', 'room_number', 'booking_reference')
    date_hierarchy = 'issue_date'
    inlines = [PaymentInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'payment_date', 'method', 'received_by')
    list_filter = ('method',)
    date_hierarchy = 'payment_date'
