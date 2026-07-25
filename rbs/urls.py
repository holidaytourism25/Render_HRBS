from django.urls import path
from . import views

urlpatterns = [
    # ১. হোম পেজ (হোটেল লিস্ট)
    path('', views.hotel_list, name='hotel_list'),
    
    # ২. হোটেল ডিটেইল ও ৩০ দিনের ক্যালেন্ডার
    path('hotel/<int:hotel_id>/', views.hotel_detail, name='hotel_detail'),
    
    # ৩. কার্টে রুম যোগ করা
    path('add-to-cart/<int:room_id>/', views.add_to_cart, name='add_to_cart'),
    
    # ৪. কার্ট থেকে রুম মুছে ফেলা (নতুন যুক্ত করা হয়েছে)
    path('remove-from-cart/<int:index>/', views.remove_from_cart, name='remove_from_cart'),
    
    # ৫. চেকআউট ও পেমেন্ট টাইপ নির্ধারণ
    path('checkout/', views.checkout, name='checkout'),
    
    # ৬. রিসিট ফরম (ঠিকানা দেওয়ার পেজ)
    path('receipt/form/<int:booking_id>/', views.receipt_form, name='receipt_form'),
    
    # ৭. বুকিং ট্র্যাকিং অপশন (আপনার আগের তৈরি করা ফিচার)
    path('track/', views.track_booking, name='track_booking'),
    
    # ৮. ম্যানেজার ও সুপার অ্যাডমিনের জন্য রিপোর্ট এবং পিডিএফ ডাউনলোড
    path('reports/', views.booking_report, name='booking_report'),
]