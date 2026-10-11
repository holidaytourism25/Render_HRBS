from django.urls import path
from . import views

app_name = 'rbs'

urlpatterns = [
    path('', views.hotel_list, name='hotel_list'),
    path('hotel/<int:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    path('add-to-cart/<int:room_id>/', views.add_to_cart, name='add_to_cart'),
    path('remove-from-cart/<int:index>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('receipt/form/<int:booking_id>/', views.receipt_form, name='receipt_form'),
    path('track/', views.track_booking, name='track_booking'),
    # path('reports/', views.booking_report, name='booking_report'),
    # path('dashboard/', views.user_dashboard, name='user_dashboard'),
    # path('booking/<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    # ইউজার প্রোফাইল আপডেট রাউট
    # path('profile/edit/', views.profile_update, name='profile_update'),
]