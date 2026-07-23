from django.contrib import admin
from .models import Hotel, Room, Booking

# ১. হোটেল মডেল রেজিস্টার
@admin.register(Hotel)
class HotelAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'manager', 'commission_rate')
    search_fields = ('name', 'location')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # ম্যানেজার শুধু তার নিজের হোটেল দেখবে
        return qs.filter(manager=request.user)

# ২. রুম মডেল রেজিস্টার
@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_type', 'hotel', 'price')
    list_filter = ('hotel',)
    search_fields = ('room_type',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # ম্যানেজার শুধু তার হোটেলের রুমগুলো দেখবে
        return qs.filter(hotel__manager=request.user)

# ৩. বুকিং মডেল রেজিস্টার
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'guest_name', 'hotel', 'paid_amount', 'admin_commission', 'status')
    list_filter = ('status', 'hotel')
    search_fields = ('booking_id', 'guest_name', 'mobile')
    readonly_fields = ('admin_commission',) # এটি অটো-ক্যালকুলেট হয় তাই রিড-অনলি রাখা ভালো

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        # ম্যানেজার শুধু তার হোটেলের বুকিং দেখবে
        return qs.filter(hotel__manager=request.user)



admin.site.site_header = "Hotel Room Booking System Admin Panel"
admin.site.site_title = "HRBS Admin"
admin.site.index_title = "Welcome to HRBS Dashboard"