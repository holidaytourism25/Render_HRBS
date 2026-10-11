from decimal import Decimal
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.timezone import localdate, now
from django.http import HttpResponse
from django.template.loader import render_to_string
from xhtml2pdf import pisa 

from .models import Hotel, Room, Booking
from .forms import UserProfileForm

# 1. Home Page (Hotel List)
def hotel_list(request):
    hotels = Hotel.objects.all()
    return render(request, 'rbs/index.html', {'hotels': hotels})

# 2. Hotel Detail View
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
                status__in=['Confirmed', 'Reserved'],
                check_in__lte=day,
                check_out__gt=day
            ).count()

            rem_inventory = room.total_inventory - booked_on_day
            calendar_data.append({
                'date': day,
                'date_str': day.strftime('%Y-%m-%d'),
                'available_count': max(0, rem_inventory),
                'is_full': rem_inventory <= 0
            })
        room.calendar = calendar_data

        if check_in_str and check_out_str:
            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

                request.session['check_in'] = check_in_str
                request.session['check_out'] = check_out_str

                max_booked = 0
                current_day = check_in
                while current_day < check_out:
                    day_booked = Booking.objects.filter(
                        rooms=room,
                        status__in=['Confirmed', 'Reserved'],
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

# 3. Add to Cart View
def add_to_cart(request, room_id):
    if request.method == 'POST':
        room = get_object_or_404(Room, id=room_id)
        quantity = int(request.POST.get('quantity', 1))
        check_in_str = request.POST.get('check_in')
        check_out_str = request.POST.get('check_out')

        if not check_in_str:
            check_in_str = request.session.get('check_in', str(localdate()))
        if not check_out_str:
            check_out_str = request.session.get('check_out', str(localdate() + timedelta(days=1)))

        try:
            d1 = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            d2 = datetime.strptime(check_out_str, '%Y-%m-%d').date()
            nights = (d2 - d1).days
            if nights <= 0:
                nights = 1
        except ValueError:
            nights = 1

        cart = request.session.get('cart', [])
        item = {
            'room_id': int(room_id),
            'quantity': quantity,
            'check_in': check_in_str,
            'check_out': check_out_str,
            'nights': nights
        }

        cart.append(item)
        request.session['cart'] = cart
        request.session.modified = True

        messages.success(request, "Room added to cart successfully!")
        return redirect('rbs:checkout')

    return redirect('rbs:hotel_list')

# 4. Remove from Cart View
def remove_from_cart(request, index):
    cart = request.session.get('cart', [])
    if 0 <= index < len(cart):
        cart.pop(index)
        request.session['cart'] = cart
        request.session.modified = True
        messages.success(request, "Item removed from cart.")
    return redirect('rbs:checkout')

# 5. Checkout View
def checkout(request):
    cart = request.session.get('cart', [])
    if not cart:
        messages.warning(request, "Your cart is empty.")
        return redirect('rbs:hotel_list')

    cart_items = []
    total_price = Decimal('0.00')

    for item in cart:
        room = get_object_or_404(Room, id=item['room_id'])
        quantity = item.get('quantity', 1)
        nights = item.get('nights', 1)

        item_total = Decimal(str(room.price)) * Decimal(str(quantity)) * Decimal(str(nights))
        total_price += item_total

        cart_items.append({
            'room': room, 
            'quantity': quantity, 
            'check_in': item.get('check_in', ''),
            'check_out': item.get('check_out', ''),
            'nights': nights,
            'total': item_total
        })

    if request.method == 'POST':
        name = request.POST.get('name')
        mobile = request.POST.get('mobile')
        payment_type = request.POST.get('payment_type')

        paid_amount = total_price
        if payment_type == 'Partial':
            paid_amount = total_price / Decimal('2.0')

        first_item_check_in = cart_items[0]['check_in'] if cart_items else str(localdate())
        first_item_check_out = cart_items[0]['check_out'] if cart_items else str(localdate() + timedelta(days=1))

        booking = Booking.objects.create(
            user=request.user if request.user.is_authenticated else None,
            hotel=cart_items[0]['room'].hotel,
            guest_name=name,
            mobile=mobile,
            check_in=first_item_check_in,
            check_out=first_item_check_out,
            total_bill=total_price,
            paid_amount=paid_amount,
            payment_type=payment_type,
            room_count=sum(item['quantity'] for item in cart_items)
        )
        for item in cart_items:
            booking.rooms.add(item['room'])

        request.session['cart'] = []
        return redirect('rbs:receipt_form', booking_id=booking.id)

    return render(request, 'rbs/checkout.html', {
        'cart_items': cart_items,
        'total_price': total_price
    })

# 6. Receipt Form View
def receipt_form(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.method == 'POST':
        booking.present_address = request.POST.get('present_address')
        booking.save()
        return render(request, 'rbs/receipt_final.html', {'booking': booking})
    return render(request, 'rbs/receipt_form.html', {'booking': booking})

# 7. Track Booking View
def track_booking(request):
    if request.method == 'POST':
        mobile = request.POST.get('mobile')
        bookings = Booking.objects.filter(mobile=mobile).order_by('-created_at')
        if bookings.exists():
            return render(request, 'rbs/track_results.html', {'bookings': bookings})
        else:
            messages.error(request, "No booking found with this mobile number.")
    return render(request, 'rbs/track_form.html')

# 8. Booking Report View
# @login_required
# def booking_report(request):
#     user = request.user
#     if user.is_superuser:
#         bookings = Booking.objects.all().order_by('-created_at')
#         hotels = Hotel.objects.all()
#     else:
#         bookings = Booking.objects.filter(hotel__manager=user).order_by('-created_at')
#         hotels = Hotel.objects.filter(manager=user)

#     hotel_filter = request.GET.get('hotel')
#     start_date = request.GET.get('start_date')
#     end_date = request.GET.get('end_date')

#     if hotel_filter:
#         bookings = bookings.filter(hotel_id=hotel_filter)
#     if start_date and end_date:
#         bookings = bookings.filter(check_in__range=[start_date, end_date])

#     if 'download_pdf' in request.GET:
#         html = render_to_string('rbs/report_pdf.html', {'bookings': bookings, 'report_date': now()})
#         response = HttpResponse(content_type='application/pdf')
#         response['Content-Disposition'] = 'attachment; filename="booking_report.pdf"'
#         pisa_status = pisa.CreatePDF(html, dest=response)
#         if pisa_status.err:
#             return HttpResponse('Error generating PDF', status=500)
#         return response

#     return render(request, 'rbs/report.html', {'bookings': bookings, 'hotels': hotels})

# # 9. User Dashboard View
# @login_required
# def user_dashboard(request):
#     status_filter = request.GET.get('status', 'all')
#     user_bookings = Booking.objects.filter(user=request.user)

#     if status_filter != 'all':
#         user_bookings = user_bookings.filter(status=status_filter)

#     user_bookings = user_bookings.order_by('-created_at')

#     calendar_events = []
#     color_map = {
#         'Confirmed': '#198754',
#         'Reserved': '#0d6efd',
#         'Pending': '#ffc107',
#         'Cancelled': '#dc3545',
#     }

#     for b in Booking.objects.filter(user=request.user):
#         room_names = ", ".join([r.room_type for r in b.rooms.all()])
#         calendar_events.append({
#             'id': b.id,
#             'title': f"{b.booking_id}: {room_names} ({b.get_status_display()})",
#             'start': b.check_in.strftime('%Y-%m-%d'),
#             'end': b.check_out.strftime('%Y-%m-%d'),
#             'backgroundColor': color_map.get(b.status, '#6c757d'),
#             'borderColor': color_map.get(b.status, '#6c757d'),
#             'textColor': '#ffffff' if b.status != 'Pending' else '#000000'
#         })

#     context = {
#         'bookings': user_bookings,
#         'total_bookings': Booking.objects.filter(user=request.user).count(),
#         'active_filter': status_filter,
#         'calendar_events': calendar_events,
#     }
#     return render(request, 'rbs/user_dashboard.html', context)

# # 10. Cancel Booking View
# @login_required
# def cancel_booking(request, booking_id):
#     booking = get_object_or_404(Booking, id=booking_id, user=request.user)
#     if request.method == 'POST':
#         if booking.status != 'Cancelled':
#             booking.status = 'Cancelled'
#             booking.save()
#             messages.success(request, f"Booking #{booking.booking_id} has been cancelled.")
#         else:
#             messages.warning(request, "This booking is already cancelled.")
#     return redirect('rbs:user_dashboard')

# # 11. Edit User Profile View
# @login_required
# def profile_update(request):
#     if request.method == 'POST':
#         form = UserProfileForm(request.POST, instance=request.user)
#         if form.is_valid():
#             form.save()
#             messages.success(request, "Profile updated successfully!")
#             return redirect('rbs:user_dashboard')
#     else:
#         form = UserProfileForm(instance=request.user)
#     return render(request, 'rbs/profile_update.html', {'form': form})