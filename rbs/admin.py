from django.contrib import admin
from .models import Hotel, Room, RoomNumber, Booking, PaymentTransaction

# ১. হোটেল মডেল রেজিস্টার
@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'manager', 'commission_rate')
    search_fields = ('name', 'location')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(manager=request.user)


# ২. রুম মডেল রেজিস্টার
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'hotel', 'price', 'total_inventory')
    list_filter = ('hotel',)
    search_fields = ('room_type',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(hotel__manager=request.user)


# ৩. রুম নম্বর অ্যাসাইনমেন্ট রেজিস্টার
@admin.register(RoomNumber)
class RoomNumberAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'get_hotel', 'get_room_type', 'is_available')
    search_fields = ('room_number', 'room__room_type', 'room__hotel__name')
    list_filter = ('room__hotel', 'room__room_type', 'is_available')

    def get_hotel(self, obj):
        return obj.room.hotel.name
    get_hotel.short_description = 'Hotel'

    def get_room_type(self, obj):
        return obj.room.room_type
    get_room_type.short_description = 'Room Type'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(room__hotel__manager=request.user)


# ৪. পারশিয়াল পেমেন্ট ট্রানজ্যাকশন ইনলাইন (বুকিং এর ভেতর পেমেন্ট যুক্ত করার জন্য)
class PaymentTransactionInline(admin.TabularInline):
    model = PaymentTransaction
    extra = 1
    readonly_fields = ('created_at',)


# ৫. বুকিং মডেল রেজিস্টার
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'guest_name', 'hotel', 'status', 'approval_status', 'total_bill', 'paid_amount', 'due_amount', 'admin_commission')
    list_filter = ('status', 'approval_status', 'hotel', 'has_complementary_breakfast', 'send_sms_notification')
    search_fields = ('booking_id', 'guest_name', 'mobile', 'hotel__name')
    readonly_fields = ('admin_commission', 'booking_id')
    inlines = [PaymentTransactionInline]
    filter_horizontal = ('assigned_room_numbers', 'rooms')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(hotel__manager=request.user)


# Admin Header customization
admin.site.site_header = "Hotel Room Booking System Admin Panel"
admin.site.site_title = "HRBS Admin"
admin.site.index_title = "Welcome to HRBS Dashboard"