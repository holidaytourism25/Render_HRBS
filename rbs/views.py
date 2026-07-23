from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.timezone import localdate, now
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa 

from .models import Hotel, Room, Booking


# ১. হোম পেজ (হোটেল লিস্ট)
def hotel_list(request):
    hotels = Hotel.objects.all()
    return render(request, 'rbs/index.html', {'hotels': hotels})


# ২. hotel_detail ভিউ (৩০ দিনের ক্যালেন্ডারসহ)
def hotel_detail(request, hotel_id):
    hotel = get_object_or_404(Hotel, id=hotel_id)
    rooms = hotel.rooms.all()
    
    check_in_str = request.GET.get('check_in')
    check_out_str = request.GET.get('check_out')
    
    today = localdate()
    next_30_days = [today + timedelta(days=i) for i in range(30)]

    for room in rooms:
        calendar_data = []
        for day in next_30_days:
            booked_on_day = Booking.objects.filter(
                rooms=room,
                status='Confirmed',
                check_in__lte=day,
                check_out__gt=day
            ).count()
            
            rem_inventory = room.total_inventory - booked_on_day
            calendar_data.append({
                'date': day,
                'available_count': max(0, rem_inventory),
                'is_full': rem_inventory <= 0
            })
        room.calendar = calendar_data

        if check_in_str and check_out_str:
            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                
                # সেশনে চেক-ইন/আউট ডেট সেভ রাখা যাতে চেকআউটে কাজে লাগে
                request.session['check_in'] = check_in_str
                request.session['check_out'] = check_out_str
                
                max_booked = 0
                current_day = check_in
                while current_day < check_out:
                    day_booked = Booking.objects.filter(
                        rooms=room,
                        status='Confirmed',
                        check_in__lte=current_day,
                        check_out__gt=current_day
                    ).count()
                    if day_booked > max_booked:
                        max_booked = day_booked
                    current_day += timedelta(days=1)
                    
                room.available_count = max(0, room.total_inventory - max_booked)
            except ValueError:
                room.available_count = room.total_inventory
        else:
            room.available_count = room.total_inventory

    return render(request, 'rbs/detail.html', {
        'hotel': hotel, 
        'rooms': rooms,
        'next_30_days': next_30_days
    })


# ৩. কার্টে রুম যোগ করা
def add_to_cart(request, room_id):
    if 'cart' not in request.session:
        request.session['cart'] = []
    
    cart = request.session['cart']
    quantity = int(request.POST.get('quantity', 1))
    
    item = {'room_id': int(room_id), 'quantity': quantity}
    
    clean_cart = []
    for i in cart:
        if isinstance(i, dict) and 'room_id' in i:
            if int(i['room_id']) != int(room_id):
                clean_cart.append(i)
                
    clean_cart.append(item)
    request.session['cart'] = clean_cart
    
    return redirect('checkout')


# ৪. কার্ট থেকে রুম মুছে ফেলা
def remove_from_cart(request, room_id):
    cart = request.session.get('cart', [])
    updated_cart = [item for item in cart if isinstance(item, dict) and int(item.get('room_id', 0)) != int(room_id)]
    request.session['cart'] = updated_cart
    messages.success(request, "রুমটি কার্ট থেকে বাদ দেওয়া হয়েছে।")
    return redirect('checkout')


# ৫. চেকআউট ও পেমেন্ট টাইপ নির্ধারণ
def checkout(request):
    cart = request.session.get('cart', [])
    if not cart:
        messages.warning(request, "আপনার কার্ট খালি।")
        return redirect('hotel_list')
        
    cart_items = []
    total_price = Decimal('0.00')
    
    for item in cart:
        room = get_object_or_404(Room, id=item['room_id'])
        item_total = room.price * item['quantity']
        total_price += item_total
        cart_items.append({'room': room, 'quantity': item['quantity'], 'total': item_total})

    if request.method == 'POST':
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        payment_type = request.POST.get('payment_type')
        
        paid_amount = total_price
        if payment_type == 'Partial':
            paid_amount = total_price / Decimal('2.0')
            
        check_in_str = request.session.get('check_in', str(localdate()))
        check_out_str = request.session.get('check_out', str(localdate() + timedelta(days=1)))
        
        booking = Booking.objects.create(
            hotel=cart_items[0]['room'].hotel,
            guest_name=name,
            mobile=mobile,
            check_in=check_in_str,
            check_out=check_out_str,
            total_bill=total_price,
            paid_amount=paid_amount,
            payment_type=payment_type,
            room_count=sum(item['quantity'] for item in cart_items)
        )
        for item in cart_items:
            booking.rooms.add(item['room'])
            
        request.session['cart'] = []
        return redirect('receipt_form', booking_id=booking.id)

    return render(request, 'rbs/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })


# ৬. রিসিট ফরম
def receipt_form(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.method == 'POST':
        booking.present_address = request.POST.get('present_address')
        booking.save()
        return render(request, 'rbs/receipt_final.html', {'booking': booking})
    return render(request, 'rbs/receipt_form.html', {'booking': booking})


# ৭. বুকিং ট্র্যাকিং ভিউ
def track_booking(request):
    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        bookings = Booking.objects.filter(mobile=mobile).order_by('-created_at')
        if bookings.exists():
            return render(request, 'rbs/track_results.html', {'bookings': bookings})
        else:
            messages.error(request, "এই নম্বরে কোনো বুকিং পাওয়া যায়নি।")
    return render(request, 'rbs/track_form.html')


# ৮. ম্যানেজার ও সুপার অ্যাডমিন রিপোর্ট মডিউল
def booking_report(request):
    user = request.user
    if user.is_superuser:
        bookings = Booking.objects.all().order_by('-created_at')
        hotels = Hotel.objects.all()
    else:
        bookings = Booking.objects.filter(hotel__manager=user).order_by('-created_at')
        hotels = Hotel.objects.filter(manager=user)

    hotel_filter = request.GET.get('hotel')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    if hotel_filter:
        bookings = bookings.filter(hotel_id=hotel_filter)
    if start_date and end_date:
        bookings = bookings.filter(check_in__range=[start_date, end_date])

    if 'download_pdf' in request.GET:
        html = render_to_string('rbs/report_pdf.html', {'bookings': bookings, 'report_date': now()})
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="booking_report.pdf"'
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('PDF তৈরি করতে সমস্যা হয়েছে', status=500)
        return response

    return render(request, 'rbs/report.html', {'bookings': bookings, 'hotels': hotels})