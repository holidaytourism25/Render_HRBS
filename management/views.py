import json
import uuid
import os
from datetime import datetime, time, timedelta
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.timezone import make_aware, get_current_timezone, now
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string, get_template
from django.db.models import Sum,F
from django.conf import settings
from django.contrib.staticfiles import finders
from xhtml2pdf import pisa

from rbs.models import Booking, Hotel, Room, RoomNumber, PaymentTransaction, BookingDayItem, SubBookingItem
from .models import GuestRegistrationCard, AdditionalGuest, UserActivityLog, MessageLog


def fetch_resources(uri, rel):
    """
    pdf-এ static files/images (যেমন: pad_background.jpeg) সঠিক পাথ থেকে লোড করার লজিক।
    """
    if uri.startswith(settings.STATIC_URL):
        path = uri.replace(settings.STATIC_URL, "")
    else:
        path = uri

    absolute_path = finders.find(path)
    if absolute_path:
        return absolute_path

    direct_path = os.path.join(settings.BASE_DIR, 'management', 'static', path)
    if os.path.exists(direct_path):
        return direct_path

    parts = [p for p in path.split('/') if p]
    if len(parts) > 1:
        app_name = parts[0]
        rest_path = os.path.join(*parts[1:])
        app_manual_path = os.path.join(settings.BASE_DIR, app_name, 'static', rest_path)
        if os.path.exists(app_manual_path):
            return app_manual_path

    return uri

def is_staff_user(user):
    return user.is_staff or user.is_superuser

def log_action(user, action, details="", request=None):
    """ইউজার অ্যাক্টিভিটি ট্র্যাক করার হেলপার ফাংশন"""
    ip = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
    UserActivityLog.objects.create(
        user=user if user.is_authenticated else None,
        action=action,
        details=details,
        ip_address=ip
    )

def safe_decimal(val, default='0.00'):
    """খালি স্ট্রিং বা ভুল ইনপুট আসলে ক্র্যাশ না করে ডিফল্ট মান রিটার্ন করবে"""
    if not val or str(val).strip() == '':
        return Decimal(default)
    try:
        return Decimal(str(val).strip())
    except Exception:
        return Decimal(default)

    
''' List for initial bookings '''

@login_required
@user_passes_test(is_staff_user)
def booking_list_view(request):
    """হোটেল ওয়াইজ, ডেট ওয়াইজ এবং মোবাইল নম্বর ওয়াইজ বুকিং ফিল্টারিং"""
    selected_hotel_id = request.GET.get('hotel')
    filter_date = request.GET.get('date')
    filter_mobile = request.GET.get('mobile', '').strip()  # ✅ মোবাইল নম্বর ফিল্টার parámetro

    hotels = Hotel.objects.all()
    bookings = Booking.objects.all().select_related('hotel').prefetch_related('grc_card')

    # ১. হোটেল ফিল্টার (যদি একাধিক হোটেল থাকে)
    if selected_hotel_id:
        bookings = bookings.filter(hotel_id=selected_hotel_id)
    elif hotels.exists() and not filter_mobile: 
        # মোবাইল নম্বর না থাকলে প্রথম হোটেলটি বাই-ডিফল্ট সিলেক্ট থাকবে
        selected_hotel_id = str(hotels.first().id)
        bookings = bookings.filter(hotel_id=selected_hotel_id)

    # ২. তারিখ ওয়াইজ ফিল্টার
    if filter_date:
        bookings = bookings.filter(check_in=filter_date)

    # ৩. ✅ মোবাইল নম্বর ফিল্টার (Exact matching বা Partial matching)
    if filter_mobile:
        bookings = bookings.filter(mobile__icontains=filter_mobile)

    bookings = bookings.order_by('-created_at')

    context = {
        'hotels': hotels,
        'selected_hotel_id': int(selected_hotel_id) if selected_hotel_id and selected_hotel_id.isdigit() else None,
        'filter_date': filter_date,
        'filter_mobile': filter_mobile,  # ✅ টেমপ্লেট ইনপুটে ভ্যালু ধরে রাখার জন্য
        'bookings': bookings,
    }
    return render(request, 'management/booking_list.html', context)


@login_required
@user_passes_test(is_staff_user)
def get_booking_details_api(request, booking_id):
    """View/Edit ও GRC Modal-এর ডাটা পাঠানোর জন্য API"""
    booking = get_object_or_404(Booking, id=booking_id)

    # GRC তথ্য চেক করা
    has_grc = hasattr(booking, 'grc_card') and bool(booking.grc_card.grc_no)
    grc_no = booking.grc_card.grc_no if has_grc else ""

    data = {
        'id': booking.id,
        'booking_id': booking.booking_id,
        'hotel_name': booking.hotel.name,
        'guest_name': booking.guest_name,
        'mobile': booking.mobile,
        'check_in': booking.check_in.strftime('%Y-%m-%d'),
        'check_out': booking.check_out.strftime('%Y-%m-%d'),
        'status': booking.status,
        'room_count': booking.room_count,
        'base_price': str(booking.base_price),
        'discount_amount': str(booking.discount_amount),
        'vat_percentage': str(booking.vat_percentage),
        'service_charge_percentage': str(booking.service_charge_percentage),
        'total_bill': str(booking.total_bill),
        'paid_amount': str(booking.paid_amount),
        'due_amount': str(booking.due_amount),
        
        # GRC Specific Data
        'has_grc': has_grc,
        'grc_no': grc_no,
        'father_name': booking.grc_card.father_name if has_grc else "",
        'address': booking.grc_card.address if has_grc else "",
        'nid_passport_no': booking.grc_card.nid_passport_no if has_grc else "",
    }
    return JsonResponse({'status': 'success', 'data': data})


@login_required
@user_passes_test(is_staff_user)
def update_booking_and_grc_api(request, booking_id):
    """Edit Mode থেকে ডাটা আপডেট ও Manual GRC Entry সেভ করা"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id)

        # ১. Booking Data Update
        booking.guest_name = request.POST.get('guest_name', booking.guest_name)
        booking.mobile = request.POST.get('mobile', booking.mobile)
        booking.discount_amount = Decimal(request.POST.get('discount_amount', 0.00))
        booking.vat_percentage = Decimal(request.POST.get('vat_percentage', 0.00))
        booking.service_charge_percentage = Decimal(request.POST.get('service_charge_percentage', 0.00))
        
        # models_2.py এর save() মেথড টোটাল বিল স্বয়ংক্রিয়ভাবে রি-ক্যালকুলেট করবে
        booking.save()

        # ২. Manual GRC Entry/Update
        manual_grc = request.POST.get('grc_no', '').strip()
        if manual_grc:
            grc_card, created = GuestRegistrationCard.objects.get_or_create(booking=booking)
            grc_card.grc_no = manual_grc
            grc_card.father_name = request.POST.get('father_name', grc_card.father_name)
            grc_card.address = request.POST.get('address', grc_card.address)
            grc_card.nid_passport_no = request.POST.get('nid_passport_no', grc_card.nid_passport_no)
            grc_card.save()

        return JsonResponse({'status': 'success', 'message': 'তথ্য সফলভাবে সংরক্ষিত হয়েছে!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid Request'}, status=400)    
    


@login_required
@user_passes_test(is_staff_user)
def manager_dashboard(request):
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)
    
    total_bookings = Booking.objects.filter(hotel__in=hotels).count() if hotels.exists() else 0
    pending_count = Booking.objects.filter(hotel__in=hotels, status='Pending').count() if hotels.exists() else 0
    confirmed_count = Booking.objects.filter(hotel__in=hotels, status='Confirmed').count() if hotels.exists() else 0
    available_rooms_count = RoomNumber.objects.filter(room__hotel__in=hotels, is_available=True).count() if hotels.exists() else 0

    context = {
        'total_bookings': total_bookings,
        'pending_count': pending_count,
        'confirmed_count': confirmed_count,
        'available_rooms_count': available_rooms_count,
    }
    return render(request, 'management/dashboard.html', context)

# --- 1. DAILY SALES REPORT ---
@login_required
@user_passes_test(is_staff_user)
def daily_sales_report(request):
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)

    selected_hotel_id = request.GET.get('hotel')
    date_str = request.GET.get('date')

    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else now().date()
    active_hotel = hotels.filter(id=selected_hotel_id).first() if selected_hotel_id else hotels.first()

    sales_bookings = Booking.objects.filter(
        hotel=active_hotel,
        created_at__date=selected_date
    ).exclude(status='Cancelled') if active_hotel else Booking.objects.none()

    total_sales_amount = sales_bookings.aggregate(total=Sum('base_price'))['total'] or Decimal('0.00')
    total_paid_against_sales = sales_bookings.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
    total_due_against_sales = sales_bookings.aggregate(total=Sum('due_amount'))['total'] or Decimal('0.00')

    context = {
        'hotels': hotels,
        'selected_hotel': active_hotel,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'bookings': sales_bookings,
        'total_sales_amount': total_sales_amount,
        'total_paid_against_sales': total_paid_against_sales,
        'total_due_against_sales': total_due_against_sales,
        'report_generated_at': now(),
    }

    if request.GET.get('download') == 'pdf':
        context['static_url'] = settings.STATIC_URL
        html = render_to_string('reports/pdf_daily_sales.html', context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Daily_Sales_{selected_date}.pdf"'
        pisa.CreatePDF(html, dest=response, link_callback=fetch_resources)
        return response

    return render(request, 'reports/daily_sales_report.html', context)

# --- 2. DAILY COLLECTION REPORT ---
@login_required
@user_passes_test(is_staff_user)
def collection_report(request):
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)

    selected_hotel_id = request.GET.get('hotel')
    date_str = request.GET.get('date')

    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else now().date()
    active_hotel = hotels.filter(id=selected_hotel_id).first() if selected_hotel_id else hotels.first()

    tz = get_current_timezone()
    start_dt = make_aware(datetime.combine(selected_date, time(0, 0, 1)), tz)
    end_dt = make_aware(datetime.combine(selected_date + timedelta(days=1), time(0, 0, 0)), tz)

    transactions = PaymentTransaction.objects.filter(
        booking__hotel=active_hotel,
        created_at__gte=start_dt,
        created_at__lte=end_dt
    ).select_related('booking') if active_hotel else PaymentTransaction.objects.none()

    total_collection = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    cash_collection = transactions.filter(payment_method='Cash').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    online_collection = transactions.exclude(payment_method='Cash').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'hotels': hotels,
        'selected_hotel': active_hotel,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'transactions': transactions,
        'total_collection': total_collection,
        'cash_collection': cash_collection,
        'online_collection': online_collection,
    }

    if request.GET.get('download') == 'pdf':
        context['static_url'] = settings.STATIC_URL
        html = render_to_string('reports/pdf_collection.html', context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Collection_Report_{selected_date}.pdf"'
        pisa.CreatePDF(html, dest=response, link_callback=fetch_resources)
        return response

    return render(request, 'reports/collection_report.html', context)

# --- 3. RESERVATION REPORT ---
@login_required
@user_passes_test(is_staff_user)
def reservation_report(request):
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)

    selected_hotel_id = request.GET.get('hotel')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    active_hotel = hotels.filter(id=selected_hotel_id).first() if selected_hotel_id else hotels.first()
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else now().date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else start_date + timedelta(days=7)

    reserved_bookings = Booking.objects.filter(
        hotel=active_hotel,
        check_in__gte=start_date,
        check_in__lte=end_date,
        status='Reserved'
    ) if active_hotel else Booking.objects.none()

    total_advance = reserved_bookings.aggregate(total=Sum('paid_amount'))['total'] or Decimal('0.00')
    total_due = reserved_bookings.aggregate(total=Sum('due_amount'))['total'] or Decimal('0.00')

    context = {
        'hotels': hotels,
        'selected_hotel': active_hotel,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'bookings': reserved_bookings,
        'total_advance': total_advance,
        'total_due': total_due,
    }

    if request.GET.get('download') == 'pdf':
        context['static_url'] = settings.STATIC_URL
        html = render_to_string('reports/pdf_reservation.html', context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Reservation_Report_{start_date}_to_{end_date}.pdf"'
        pisa.CreatePDF(html, dest=response, link_callback=fetch_resources)
        return response

    return render(request, 'reports/reservation_report.html', context)

# --- 4. DAILY IN HOUSE LIST REPORT ---
@login_required
@user_passes_test(is_staff_user)
def daily_in_house_report(request):
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)

    selected_hotel_id = request.GET.get('hotel')
    date_str = request.GET.get('date')

    selected_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else now().date()
    active_hotel = hotels.filter(id=selected_hotel_id).first() if selected_hotel_id else hotels.first()

    in_house_bookings = Booking.objects.filter(
        hotel=active_hotel,
        check_in__lte=selected_date,
        check_out__gte=selected_date,
        status='Confirmed'
    ) if active_hotel else Booking.objects.none()

    total_in_house_rent = in_house_bookings.aggregate(total=Sum('base_price'))['total'] or Decimal('0.00')

    context = {
        'hotels': hotels,
        'selected_hotel': active_hotel,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'bookings': in_house_bookings,
        'total_in_house_rent': total_in_house_rent,
    }

    if request.GET.get('download') == 'pdf':
        context['static_url'] = settings.STATIC_URL
        html = render_to_string('reports/pdf_daily_in_house.html', context)
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="In_House_List_{selected_date}.pdf"'
        pisa.CreatePDF(html, dest=response, link_callback=fetch_resources)
        return response

    return render(request, 'reports/daily_in_house_report.html', context)

@login_required
@user_passes_test(is_staff_user)
def room_status_grid(request):
    """Room Matrix Visualizer with GRC checking boolean"""
    user = request.user
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)
    
    selected_hotel_id = request.GET.get('hotel')
    filter_date_str = request.GET.get('checkout_date')
    
    filter_date = datetime.strptime(filter_date_str, '%Y-%m-%d').date() if filter_date_str else now().date()
    active_hotel = hotels.filter(id=selected_hotel_id).first() if selected_hotel_id else hotels.first()

    all_rooms = RoomNumber.objects.filter(room__hotel=active_hotel) if active_hotel else RoomNumber.objects.none()
    
    active_bookings = Booking.objects.filter(
        hotel=active_hotel,
        check_in__lte=filter_date,
        check_out__gte=filter_date
    ).exclude(status='Cancelled').prefetch_related('grc_card') if active_hotel else []

    room_grid_data = []
    for rn in all_rooms:
        b = active_bookings.filter(assigned_room_numbers=rn).first()
        has_grc = False
        if not b:
            status_color = 'white'
            booking_info = None
        else:
            booking_info = b
            has_grc = hasattr(b, 'grc_card') and bool(b.grc_card.grc_no)
            if b.status == 'Reserved':
                status_color = 'yellow'
            elif b.status == 'Confirmed':
                if b.due_amount <= 0:
                    status_color = 'green'
                else:
                    status_color = 'red'
            else:
                status_color = 'white'

        room_grid_data.append({
            'room_obj': rn,
            'color': status_color,
            'booking': booking_info,
            'has_grc': has_grc
        })

    context = {
        'hotels': hotels,
        'selected_hotel': active_hotel,
        'filter_date': filter_date.strftime('%Y-%m-%d'),
        'room_grid': room_grid_data,
    }
    return render(request, 'management/room_status_grid.html', context)

@login_required
@user_passes_test(is_staff_user)
def staff_room_search(request):
    user = request.user
    perm = getattr(user, 'management_permission', None)

    if user.is_superuser:
        allowed_hotels = Hotel.objects.all()
    elif perm and perm.permission_type == 'CUSTOM':
        allowed_hotels = perm.allowed_hotels.all()
    else:
        allowed_hotels = Hotel.objects.filter(manager=user)

    selected_hotel_id = request.GET.get('hotel')
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    room_type = request.GET.get('room_type', '')

    room_numbers_list = []
    hotel_room_types = []
    searched = False

    if selected_hotel_id and check_in and check_out:
        searched = True
        hotel = get_object_or_404(Hotel, id=selected_hotel_id)
        hotel_room_types = Room.objects.filter(hotel=hotel).values_list('room_type', flat=True).distinct()
        rooms = Room.objects.filter(hotel=hotel)

        if room_type:
            rooms = rooms.filter(room_type=room_type)

        all_room_numbers = RoomNumber.objects.filter(room__in=rooms).order_by('room_number')

        overlapping_bookings = Booking.objects.filter(
            hotel=hotel,
            status__in=['Confirmed', 'Reserved'],
            check_in__lt=check_out,
            check_out__gt=check_in
        )

        booked_rn_ids = set()
        reserved_rn_ids = set()

        for b in overlapping_bookings:
            rns = b.assigned_room_numbers.all().values_list('id', flat=True)
            if b.status == 'Confirmed':
                booked_rn_ids.update(rns)
            elif b.status == 'Reserved':
                reserved_rn_ids.update(rns)

        for rn in all_room_numbers:
            if rn.id in booked_rn_ids:
                status = 'Booked'
            elif rn.id in reserved_rn_ids:
                status = 'Reserved'
            else:
                status = 'Available'

            room_numbers_list.append({'obj': rn, 'status': status})

    context = {
        'allowed_hotels': allowed_hotels,
        'today_date': now().strftime('%Y-%m-%d'),
        'searched': searched,
        'selected_hotel': selected_hotel_id,
        'check_in': check_in,
        'check_out': check_out,
        'room_type': room_type,
        'hotel_room_types': hotel_room_types,
        'room_numbers_list': room_numbers_list,
    }
    return render(request, 'management/room_search.html', context)

@login_required
@user_passes_test(is_staff_user)
def add_room_to_booking_cart(request, room_number_id):
    room_number_obj = get_object_or_404(RoomNumber, id=room_number_id)
    check_in = request.GET.get('check_in', now().strftime('%Y-%m-%d'))
    check_out = request.GET.get('check_out', now().strftime('%Y-%m-%d'))

    d1 = datetime.strptime(check_in, '%Y-%m-%d').date()
    d2 = datetime.strptime(check_out, '%Y-%m-%d').date()
    nights = max(1, (d2 - d1).days)

    staff_cart = request.session.get('staff_cart', [])
    
    for item in staff_cart:
        if item['room_number_id'] == room_number_obj.id:
            messages.info(request, f"রুম {room_number_obj.room_number} ইতিপূর্বে কার্টে যোগ করা হয়েছে।")
            return redirect(f"/management/booking-cart/?hotel_id={room_number_obj.room.hotel.id}")

    unit_price = float(room_number_obj.room.price)
    staff_cart.append({
        'room_number_id': room_number_obj.id,
        'room_number': room_number_obj.room_number,
        'room_type': room_number_obj.room.room_type,
        'hotel_id': room_number_obj.room.hotel.id,
        'hotel_name': room_number_obj.room.hotel.name,
        'price': unit_price,
        'check_in': check_in,
        'check_out': check_out,
        'nights': nights,
        'has_breakfast': True,
        'item_discount': 0.0,
        'item_total': unit_price * nights
    })

    request.session['staff_cart'] = staff_cart
    request.session.modified = True
    messages.success(request, f"রুম {room_number_obj.room_number} কার্টে যোগ করা হয়েছে।")
    return redirect(f"/management/booking-cart/?hotel_id={room_number_obj.room.hotel.id}")

@login_required
@user_passes_test(is_staff_user)
def update_cart_item(request, index):
    staff_cart = request.session.get('staff_cart', [])
    if 0 <= index < len(staff_cart):
        if request.method == 'POST':
            has_breakfast = request.POST.get('has_breakfast') == 'on'
            try:
                item_discount = float(request.POST.get('item_discount', 0.0))
            except ValueError:
                item_discount = 0.0

            base_price = float(staff_cart[index]['price'])
            nights = staff_cart[index]['nights']
            
            subtotal = base_price * nights
            item_total = max(0.0, subtotal - item_discount)

            staff_cart[index]['has_breakfast'] = has_breakfast
            staff_cart[index]['item_discount'] = item_discount
            staff_cart[index]['item_total'] = item_total

            request.session['staff_cart'] = staff_cart
            request.session.modified = True
            messages.success(request, f"রুম #{staff_cart[index]['room_number']} আপডেট করা হয়েছে।")

    return redirect('management:view_booking_cart')

@login_required
@user_passes_test(is_staff_user)
def view_booking_cart(request):
    user = request.user
    perm = getattr(user, 'management_permission', None)
    staff_cart = request.session.get('staff_cart', [])
    can_give_discount = user.is_superuser or (perm and perm.can_give_discount)

    if not staff_cart:
        messages.warning(request, "বুকিং কার্ট বর্তমানে খালি রয়েছে।")
        return redirect('management:staff_room_search')

    for item in staff_cart:
        if 'has_breakfast' not in item:
            item['has_breakfast'] = True
        if 'item_discount' not in item:
            item['item_discount'] = 0.0
        if 'item_total' not in item:
            item['item_total'] = float(item['price']) * item['nights']

    total_base_price = sum(item['item_total'] for item in staff_cart)
    total_item_discounts = sum(item.get('item_discount', 0.0) for item in staff_cart)
    hotel_obj = Hotel.objects.get(id=staff_cart[0]['hotel_id'])

    if request.method == 'POST':
        guest_name = request.POST.get('guest_name')
        mobile = request.POST.get('mobile')
        booking_type = request.POST.get('booking_type', 'Confirmed')

        overall_discount = safe_decimal(request.POST.get('discount_amount')) if can_give_discount else Decimal('0.00')
        total_combined_discount = Decimal(str(total_item_discounts)) + overall_discount

        vat_percentage = safe_decimal(request.POST.get('vat_percentage'))
        service_charge_percentage = safe_decimal(request.POST.get('service_charge_percentage'))
        other_charge = safe_decimal(request.POST.get('other_charge'))
        other_charge_ref = request.POST.get('other_charge_reference', '')
        paid_amount = safe_decimal(request.POST.get('paid_amount'))
        payment_method = request.POST.get('payment_method', 'Cash')

        earliest_check_in = min(item['check_in'] for item in staff_cart)
        latest_check_out = max(item['check_out'] for item in staff_cart)

        booking = Booking.objects.create(
            user=user,
            hotel=hotel_obj,
            guest_name=guest_name,
            mobile=mobile,
            check_in=earliest_check_in,
            check_out=latest_check_out,
            original_check_out=latest_check_out,
            status=booking_type,
            base_price=Decimal(str(total_base_price)),
            discount_amount=total_combined_discount,
            vat_percentage=vat_percentage,
            service_charge_percentage=service_charge_percentage,
            other_charge=other_charge,
            other_charge_reference=other_charge_ref,
            paid_amount=paid_amount,
            payment_method=payment_method,
            room_count=len(staff_cart)
        )

        for item in staff_cart:
            rn = RoomNumber.objects.get(id=item['room_number_id'])
            booking.rooms.add(rn.room)
            booking.assigned_room_numbers.add(rn)

            SubBookingItem.objects.create(
                parent_booking=booking,
                room_number=rn,
                check_in=item['check_in'],
                check_out=item['check_out'],
                price_per_night=safe_decimal(item['price']),
                has_breakfast=item['has_breakfast']
            )

        if paid_amount > 0:
            PaymentTransaction.objects.create(
                booking=booking,
                amount=paid_amount,
                payment_method=payment_method,
                note="Initial collection during cart booking"
            )

        log_action(user, "Booking Created", f"Booking ID #{booking.booking_id} created for {guest_name}", request)

        request.session['staff_cart'] = []
        messages.success(request, f"বুকিং ID #{booking.booking_id} সফলভাবে তৈরি হয়েছে!")
        return redirect('management:dashboard')

    context = {
        'staff_cart': staff_cart,
        'total_base_price': total_base_price,
        'total_item_discounts': total_item_discounts,
        'hotel': hotel_obj,
        'can_give_discount': can_give_discount,
    }
    return render(request, 'management/booking_cart.html', context)

@login_required
@user_passes_test(is_staff_user)
def remove_from_booking_cart(request, index):
    staff_cart = request.session.get('staff_cart', [])
    if 0 <= index < len(staff_cart):
        removed = staff_cart.pop(index)
        request.session['staff_cart'] = staff_cart
        request.session.modified = True
        messages.success(request, f"রুম #{removed['room_number']} কার্ট থেকে সরানো হয়েছে।")
    return redirect('management:view_booking_cart')

@login_required
@user_passes_test(is_staff_user)
def edit_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    user = request.user
    perm = getattr(user, 'management_permission', None)
    can_modify_bill_and_dates = user.is_superuser or (perm and perm.can_modify_bill_and_dates)
    can_send_sms = user.is_superuser or (perm and perm.can_send_sms)

    grc_exists = hasattr(booking, 'grc_card')

    if request.method == 'POST':
        booking.guest_name = request.POST.get('guest_name', booking.guest_name)
        booking.mobile = request.POST.get('mobile', booking.mobile)
        booking.status = request.POST.get('status', booking.status)

        new_check_out_str = request.POST.get('check_out')
        if can_modify_bill_and_dates and new_check_out_str:
            new_check_out = datetime.strptime(new_check_out_str, '%Y-%m-%d').date()
            if new_check_out != booking.check_out:
                if not booking.original_check_out:
                    booking.original_check_out = booking.check_out
                booking.check_out = new_check_out

                nights = max(1, (new_check_out - booking.check_in).days)
                avg_room_rate = sum([r.price for r in booking.rooms.all()]) or Decimal('0.00')
                booking.base_price = Decimal(nights) * Decimal(avg_room_rate)
                booking.is_bill_modified = True

        add_payment = safe_decimal(request.POST.get('add_payment'))
        if add_payment > 0:
            booking.paid_amount = Decimal(booking.paid_amount) + add_payment
            PaymentTransaction.objects.create(
                booking=booking,
                amount=add_payment,
                payment_method=request.POST.get('payment_method', 'Cash'),
                note="Payment collected during edit"
            )

        booking.save()
        log_action(user, "Booking Edited", f"Booking ID #{booking.booking_id} updated", request)
        messages.success(request, f"বুকিং #{booking.booking_id} সফলভাবে আপডেট হয়েছে!")
        return redirect('management:edit_booking', booking_id=booking.id)

    return render(request, 'management/edit_booking.html', {
        'booking': booking,
        'can_modify_bill_and_dates': can_modify_bill_and_dates,
        'can_send_sms': can_send_sms,
        'grc_exists': grc_exists,
    })

@login_required
@user_passes_test(is_staff_user)
def grc_entry(request, booking_id):
    """Guest Registration Card (GRC) তৈরি এবং এডিট ভিউ"""
    booking = get_object_or_404(Booking, id=booking_id)
    grc, created = GuestRegistrationCard.objects.get_or_create(booking=booking)

    if request.method == 'POST':
        grc.father_name = request.POST.get('father_name')
        grc.address = request.POST.get('address')
        grc.nationality = request.POST.get('nationality', 'Bangladeshi')
        grc.nid_passport_no = request.POST.get('nid_passport_no')
        grc.occupation = request.POST.get('occupation')
        grc.purpose_of_visit = request.POST.get('purpose_of_visit')
        grc.vehicle_no = request.POST.get('vehicle_no')
        grc.save()

        guest_names = request.POST.getlist('additional_guest_name')
        guest_ages = request.POST.getlist('additional_guest_age')
        guest_relations = request.POST.getlist('additional_guest_relation')

        grc.additional_guests.all().delete()
        for g_name, g_age, g_rel in zip(guest_names, guest_ages, guest_relations):
            if g_name.strip():
                AdditionalGuest.objects.create(
                    grc=grc,
                    name=g_name.strip(),
                    age=int(g_age) if g_age.isdigit() else None,
                    relation=g_rel.strip()
                )

        log_action(request.user, "GRC Saved", f"GRC entry saved for Booking #{booking.booking_id}", request)
        messages.success(request, f"বুকিং #{booking.booking_id}-এর জন্য GRC ডাটা সংরক্ষন করা হয়েছে।")
        return redirect('management:edit_booking', booking_id=booking.id)

    return render(request, 'management/grc_form.html', {'booking': booking, 'grc': grc})

@login_required
@user_passes_test(is_staff_user)
def send_guest_sms(request, booking_id):
    """গেস্টের মোবাইলে SMS পাঠানোর লজিক"""
    booking = get_object_or_404(Booking, id=booking_id)
    user = request.user
    perm = getattr(user, 'management_permission', None)

    if not (user.is_superuser or (perm and perm.can_send_sms)):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)

    if request.method == 'POST':
        phone_number = request.POST.get('phone_number', booking.mobile)
        message_body = request.POST.get('message_body', '')

        if phone_number and message_body:
            MessageLog.objects.create(
                booking=booking,
                sent_by=user,
                phone_number=phone_number,
                message_body=message_body
            )
            log_action(user, "SMS Sent", f"SMS sent to {phone_number} for Booking #{booking.booking_id}", request)
            return JsonResponse({'status': 'success', 'message': f'SMS sent to {phone_number}'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
@user_passes_test(is_staff_user)
def process_booking_report(request, booking_id):
    """ইনভয়েস PDF ডাউনলোড/ভিউ প্রসেসিং"""
    booking = get_object_or_404(Booking, id=booking_id)
    html = render_to_string('reports/booking_invoice_pdf.html', {'booking': booking, 'request': request})
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Invoice_{booking.booking_id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response, link_callback=fetch_resources)
    if pisa_status.err:
        return HttpResponse('PDF তৈরির সময়ে ত্রুটি হয়েছে', status=500)
    return response

@login_required
@user_passes_test(is_staff_user)
def booking_report(request):
    user = request.user
    bookings = Booking.objects.all() if user.is_superuser else Booking.objects.filter(hotel__manager=user)
    hotels = Hotel.objects.all() if user.is_superuser else Hotel.objects.filter(manager=user)

    hotel_filter = request.GET.get('hotel')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if hotel_filter:
        bookings = bookings.filter(hotel_id=hotel_filter)
    if start_date and end_date:
        bookings = bookings.filter(check_in__range=[start_date, end_date])

    return render(request, 'management/report.html', {'bookings': bookings, 'hotels': hotels})

@login_required
@user_passes_test(is_staff_user)
def get_hotel_room_types(request, hotel_id):
    room_types = Room.objects.filter(hotel_id=hotel_id).values_list('room_type', flat=True).distinct()
    return JsonResponse({'room_types': list(room_types)})


# মডালের মাধ্যমে GRC তে ডাটা এন্ট্রি আপডেট ইত্যাদি এর জন্য 

@login_required
@user_passes_test(is_staff_user)
def booking_detail_api(request, booking_id):
    """মডালের পূর্ণ ডাটা এবং এডিশনাল গেস্ট এন্ট্রি পাঠানোর API"""
    booking = get_object_or_404(Booking, id=booking_id)
    
    transactions = list(booking.transactions.all().order_by('-created_at').values(
        'created_at', 'amount', 'payment_method', 'note'
    ))
    for t in transactions:
        t['created_at'] = t['created_at'].strftime('%d %b %Y, %I:%M %p')
        t['amount'] = str(t['amount'])

    # Assigned Rooms List
    assigned_rooms = []
    for rn in booking.assigned_room_numbers.all():
        sub_item = SubBookingItem.objects.filter(parent_booking=booking, room_number=rn).first()
        assigned_rooms.append({
            'id': rn.id,
            'room_number': rn.room_number,
            'room_type': rn.room.room_type,
            'price': str(rn.room.price),
            'has_breakfast': sub_item.has_breakfast if sub_item else True
        })

    # Available Rooms List
    booked_room_ids = Booking.objects.filter(
        hotel=booking.hotel, status='Confirmed'
    ).exclude(id=booking.id).values_list('assigned_room_numbers__id', flat=True)
    
    available_rooms = list(
        RoomNumber.objects.filter(room__hotel=booking.hotel)
        .exclude(id__in=booked_room_ids)
        .values('id', 'room_number', room_type=F('room__room_type'), price=F('room__price'))
    )

    # Additional Guests Data
    additional_guests = []
    if hasattr(booking, 'grc_card'):
        additional_guests = list(booking.grc_card.additional_guests.all().values('name', 'age', 'relation'))

    data = {
        'id': booking.id,
        'booking_id': booking.booking_id,
        'guest_name': booking.guest_name,
        'mobile': booking.mobile,
        'status': booking.status,
        'check_in': booking.check_in.strftime('%Y-%m-%d'),
        'check_out': booking.check_out.strftime('%Y-%m-%d'),
        'discount_amount': str(booking.discount_amount),
        'vat_percentage': str(booking.vat_percentage),
        'service_charge_percentage': str(booking.service_charge_percentage),
        'other_charge': str(booking.other_charge),
        'other_charge_reference': booking.other_charge_reference or '',
        'total_bill': str(booking.total_bill),
        'paid_amount': str(booking.paid_amount),
        'due_amount': str(booking.due_amount),
        'transactions': transactions,
        'assigned_rooms': assigned_rooms,
        'available_rooms': available_rooms,
        'additional_guests': additional_guests,
    }
    return JsonResponse({'status': 'success', 'data': data})


@login_required
@user_passes_test(is_staff_user)
def manage_booking_rooms_api(request, booking_id):
    """রুম যোগ বা বাতিল করার সাথে সাথে সঠিক বিল পুনর্নির্ধারণ করা"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id)
        action = request.POST.get('action') 
        room_number_id = request.POST.get('room_number_id')
        has_breakfast = request.POST.get('has_breakfast') == 'true'

        rn = get_object_or_404(RoomNumber, id=room_number_id)

        if action == 'add':
            booking.assigned_room_numbers.add(rn)
            booking.rooms.add(rn.room)
            SubBookingItem.objects.get_or_create(
                parent_booking=booking,
                room_number=rn,
                defaults={
                    'check_in': booking.check_in,
                    'check_out': booking.check_out,
                    'price_per_night': rn.room.price,
                    'has_breakfast': has_breakfast
                }
            )
        elif action == 'remove':
            booking.assigned_room_numbers.remove(rn)
            SubBookingItem.objects.filter(parent_booking=booking, room_number=rn).delete()
            if not booking.assigned_room_numbers.filter(room=rn.room).exists():
                booking.rooms.remove(rn.room)

        # বিল পুনর্গণনা
        nights = max(1, (booking.check_out - booking.check_in).days)
        new_base_price = sum([r.price for r in booking.rooms.all()]) * Decimal(nights)
        booking.base_price = new_base_price
        booking.room_count = booking.assigned_room_numbers.count()
        booking.save()  # Auto calls total_bill & due recalculation in model

        return JsonResponse({'status': 'success', 'message': 'Room updated successfully'})
    return JsonResponse({'status': 'error', 'message': 'Invalid method'}, status=400)

@login_required
@user_passes_test(is_staff_user)
def update_full_booking_api(request, booking_id):
    """মডাল থেকে ডাটা সম্পাদন, এডিশনাল গেস্ট এবং পেমেন্ট রিসিভ গ্রহণ করা"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id)

        # ১. বেসিক তথ্যাবলী আপডেট
        booking.guest_name = request.POST.get('guest_name', booking.guest_name)
        booking.mobile = request.POST.get('mobile', booking.mobile)
        booking.status = request.POST.get('status', booking.status)

        # তারিখ পরিবর্তন চেক
        check_out_str = request.POST.get('check_out')
        if check_out_str:
            new_check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
            if new_check_out != booking.check_out:
                booking.check_out = new_check_out
                nights = max(1, (new_check_out - booking.check_in).days)
                avg_rate = sum([r.price for r in booking.rooms.all()]) or Decimal('0.00')
                booking.base_price = Decimal(nights) * Decimal(avg_rate)

        # চার্জ ও ডিসকাউন্ট
        booking.discount_amount = Decimal(request.POST.get('discount_amount', '0.00'))
        booking.vat_percentage = Decimal(request.POST.get('vat_percentage', '0.00'))
        booking.service_charge_percentage = Decimal(request.POST.get('service_charge_percentage', '0.00'))
        booking.other_charge = Decimal(request.POST.get('other_charge', '0.00'))
        booking.other_charge_reference = request.POST.get('other_charge_reference', '')

        # পেমেন্ট নেওয়া
        add_payment = Decimal(request.POST.get('add_payment') or '0.00')
        if add_payment > 0:
            booking.paid_amount = Decimal(booking.paid_amount) + add_payment
            PaymentTransaction.objects.create(
                booking=booking,
                amount=add_payment,
                payment_method=request.POST.get('payment_method', 'Cash'),
                note=request.POST.get('payment_note', 'Modal collection')
            )

        booking.save()

        # ২. Additional Guests সেভ করা
        grc_card, _ = GuestRegistrationCard.objects.get_or_create(booking=booking)
        guest_names = request.POST.getlist('additional_guest_name')
        guest_ages = request.POST.getlist('additional_guest_age')
        guest_relations = request.POST.getlist('additional_guest_relation')

        grc_card.additional_guests.all().delete()
        for name, age, rel in zip(guest_names, guest_ages, guest_relations):
            if name.strip():
                AdditionalGuest.objects.create(
                    grc=grc_card,
                    name=name.strip(),
                    age=int(age) if age.isdigit() else None,
                    relation=rel.strip()
                )

        return JsonResponse({'status': 'success', 'message': 'All details saved successfully!'})
    return JsonResponse({'status': 'error', 'message': 'Invalid Method'}, status=400)


# ইনভয়েজ তৈরীর জন্য
def process_report(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    # নতুন তৈরি করা ইনভয়েস টেমপ্লেটটি লোড করা হচ্ছে
    template = get_template('reports/booking_invoice_pdf.html')
    context = {
        'booking': booking,
        'request': request, # প্যাড ব্যাকগ্রাউন্ডের Absolute URL পাওয়ার জন্য request অবজেক্ট আবশ্যক
    }
    html = template.render(context)

    # PDF তৈরি করা
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Invoice_{booking.booking_id}.pdf"'
    
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('PDF তৈরির সময় সমস্যা হয়েছে', status=500)
    return response