from django.urls import path
from . import views

app_name = 'management'

urlpatterns = [
    path('dashboard/', views.manager_dashboard, name='dashboard'),
    path('room-status/', views.room_status_grid, name='room_status_grid'),
    
    # Initial Booking list
    path('bookings/', views.booking_list_view, name='booking_list'),
    path('api/booking/<int:booking_id>/details/', views.get_booking_details_api, name='get_booking_details_api'),
    path('api/booking/<int:booking_id>/update/', views.update_booking_and_grc_api, name='update_booking_and_grc_api'),
    
    # Booking & Editing & GRC
    path('booking/<int:booking_id>/edit/', views.edit_booking, name='edit_booking'),
    path('booking/<int:booking_id>/process-report/', views.process_booking_report, name='process_booking_report'),
    path('booking/<int:booking_id>/grc/', views.grc_entry, name='grc_entry'),
    path('booking/<int:booking_id>/send-sms/', views.send_guest_sms, name='send_guest_sms'),
    
    # হোটেল রুম টাইপ পেতে
    path('api/get-room-types/<int:hotel_id>/', views.get_hotel_room_types, name='get_hotel_room_types'),
    
    # Staff Multi-Room Cart Flow
    path('room-search/', views.staff_room_search, name='staff_room_search'),
    path('add-to-cart/<int:room_number_id>/', views.add_room_to_booking_cart, name='add_room_to_booking_cart'),
    path('booking-cart/', views.view_booking_cart, name='view_booking_cart'),
    path('update-cart-item/<int:index>/', views.update_cart_item, name='update_cart_item'),
    path('remove-cart-item/<int:index>/', views.remove_from_booking_cart, name='remove_from_booking_cart'),
    
    # Reports
    path('reports/', views.booking_report, name='booking_report'),
    path('reports/daily-sales/', views.daily_sales_report, name='daily_sales_report'),
    path('reports/collection/', views.collection_report, name='collection_report'),
    path('reports/reservation/', views.reservation_report, name='reservation_report'),
    path('reports/daily-in-house/', views.daily_in_house_report, name='daily_in_house_report'),
    
    # মডালের মাধ্যমে GRC তে ডাটা এন্ট্রি আপডেট ইত্যাদি এর জন্য
    path('api/booking/<int:booking_id>/detail/', views.booking_detail_api, name='api_booking_detail'),
    path('api/booking/<int:booking_id>/manage-rooms/', views.manage_booking_rooms_api, name='api_manage_booking_rooms'),
]