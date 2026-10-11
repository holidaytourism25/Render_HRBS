from django.contrib import admin
from .models import UserManagementPermission, GuestRegistrationCard, AdditionalGuest, UserActivityLog, MessageLog

@admin.register(UserManagementPermission)
class UserManagementPermissionAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'permission_type', 'can_give_discount', 'can_cancel_booking',
        'can_modify_bill_and_dates', 'can_delete_booking', 'can_edit_price',
        'can_send_sms', 'can_give_complimentary_breakfast'
    )
    list_filter = (
        'permission_type', 'can_give_discount', 'can_cancel_booking',
        'can_modify_bill_and_dates', 'can_send_sms'
    )
    search_fields = ('user__username', 'user__email')
    filter_horizontal = ('allowed_hotels', 'allowed_rooms')
    radio_fields = {'permission_type': admin.HORIZONTAL}

class AdditionalGuestInline(admin.TabularInline):
    model = AdditionalGuest
    extra = 1

@admin.register(GuestRegistrationCard)
class GuestRegistrationCardAdmin(admin.ModelAdmin):
    list_display = ('booking', 'father_name', 'nid_passport_no', 'nationality', 'created_at')
    search_fields = ('booking__booking_id', 'nid_passport_no', 'father_name')
    inlines = [AdditionalGuestInline]

@admin.register(UserActivityLog)
class UserActivityLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'action', 'details')
    readonly_fields = ('user', 'action', 'details', 'ip_address', 'timestamp')

@admin.register(MessageLog)
class MessageLogAdmin(admin.ModelAdmin):
    list_display = ('booking', 'sent_by', 'phone_number', 'sent_at')
    search_fields = ('phone_number', 'message_body')
    readonly_fields = ('booking', 'sent_by', 'phone_number', 'message_body', 'sent_at')