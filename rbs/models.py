import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class Hotel(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255)
    manager = models.ForeignKey(User, on_delete=models.CASCADE)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage %")
    contact_number = models.CharField(max_length=15)
    image = models.ImageField(upload_to='hotels/', blank=True, null=True)

    def __str__(self):
        return self.name

class Room(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='rooms/', blank=True, null=True)
    bed_count = models.IntegerField(default=1)
    has_ac = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    total_inventory = models.IntegerField(default=5)

    def __str__(self):
        return f"{self.hotel.name} - {self.room_type}"

class RoomNumber(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='room_numbers')
    room_number = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.room.hotel.name} | {self.room.room_type} - Room #{self.room_number}"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed (Booked)'),
        ('Reserved', 'Reserved'),
        ('Cancelled', 'Cancelled')
    ]
    PAYMENT_METHODS = [('Online', 'Online/SSLCommerz'), ('Cash', 'Cash/Manual')]
    IS_APPROVED_CHOICES = [
        ('Approved', 'Approved'),
        ('Pending_Approval', 'Pending Super Admin Approval'),
        ('Rejected', 'Rejected')
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_bookings')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    rooms = models.ManyToManyField(Room)
    assigned_room_numbers = models.ManyToManyField(RoomNumber, blank=True)

    booking_id = models.CharField(max_length=20, unique=True, editable=False)
    guest_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    check_in = models.DateField(default=now)
    check_out = models.DateField(default=now)
    original_check_out = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    room_count = models.IntegerField(default=1)

    # Financial Fields
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    service_charge_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Additional Charges
    other_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    other_charge_reference = models.CharField(max_length=100, blank=True, null=True)
    other_charge_description = models.TextField(blank=True, null=True)

    # Features & Notifications
    has_complementary_breakfast = models.BooleanField(default=True)
    send_sms_notification = models.BooleanField(default=True)

    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    is_bill_modified = models.BooleanField(default=False)
    modified_bill_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    modification_reason = models.TextField(blank=True, null=True)
    approval_status = models.CharField(max_length=20, choices=IS_APPROVED_CHOICES, default='Approved')

    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='Cash')
    ssl_tran_id = models.CharField(max_length=100, blank=True, null=True)
    admin_commission = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)
    present_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.booking_id:
            year = now().year
            unique_seq = str(uuid.uuid4().int)[:4]
            self.booking_id = f"BK-{year}-{unique_seq}"

        if not self.is_bill_modified:
            after_discount = float(self.base_price) - float(self.discount_amount)
            vat_val = (after_discount * float(self.vat_percentage)) / 100
            sc_val = (after_discount * float(self.service_charge_percentage)) / 100
            self.total_bill = max(0.0, after_discount + vat_val + sc_val + float(self.other_charge))

        self.due_amount = max(0.0, float(self.total_bill) - float(self.paid_amount))
        if self.hotel and self.hotel.commission_rate:
            self.admin_commission = (float(self.paid_amount) * float(self.hotel.commission_rate)) / 100

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_id} - {self.guest_name}"

class SubBookingItem(models.Model):
    parent_booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='sub_items')
    room_number = models.ForeignKey(RoomNumber, on_delete=models.CASCADE)
    sub_booking_id = models.CharField(max_length=30, unique=True, editable=False)
    check_in = models.DateField()
    check_out = models.DateField()
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    has_breakfast = models.BooleanField(default=True)
    is_cancelled = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.sub_booking_id:
            count = SubBookingItem.objects.filter(parent_booking=self.parent_booking).count() + 1
            self.sub_booking_id = f"{self.parent_booking.booking_id}-{count:02d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sub_booking_id

class BookingDayItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='daily_items')
    room_number = models.ForeignKey(RoomNumber, on_delete=models.CASCADE)
    date = models.DateField()
    sub_booking_id = models.CharField(max_length=35, unique=True, editable=False)
    is_cancelled = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.sub_booking_id:
            date_str = self.date.strftime('%Y%m%d')
            self.sub_booking_id = f"{self.booking.booking_id}-R{self.room_number.room_number}-{date_str}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sub_booking_id

class PaymentTransaction(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.booking.booking_id} - Tk. {self.amount}"


'''
import uuid
from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

class Hotel(models.Model):
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=255)
    manager = models.ForeignKey(User, on_delete=models.CASCADE)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2, help_text="Percentage %")
    contact_number = models.CharField(max_length=15)
    image = models.ImageField(upload_to='hotels/', blank=True, null=True)

    def __str__(self):
        return self.name

class Room(models.Model):
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE, related_name='rooms')
    room_type = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='rooms/', blank=True, null=True)
    bed_count = models.IntegerField(default=1)
    has_ac = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    total_inventory = models.IntegerField(default=5)

    def __str__(self):
        return f"{self.hotel.name} - {self.room_type}"

class RoomNumber(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='room_numbers')
    room_number = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.room.hotel.name} | {self.room.room_type} - Room #{self.room_number}"

class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed (Booked)'),
        ('Reserved', 'Reserved'),
        ('Cancelled', 'Cancelled')
    ]
    PAYMENT_METHODS = [('Online', 'Online/SSLCommerz'), ('Cash', 'Cash/Manual')]
    IS_APPROVED_CHOICES = [
        ('Approved', 'Approved'),
        ('Pending_Approval', 'Pending Super Admin Approval'),
        ('Rejected', 'Rejected')
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='user_bookings')
    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    rooms = models.ManyToManyField(Room)
    assigned_room_numbers = models.ManyToManyField(RoomNumber, blank=True)

    booking_id = models.CharField(max_length=12, unique=True, editable=False)
    guest_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    check_in = models.DateField(default=now)
    check_out = models.DateField(default=now)
    original_check_out = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    room_count = models.IntegerField(default=1)

    # Financial Fields
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    service_charge_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)

    # Additional Charges
    other_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    other_charge_reference = models.CharField(max_length=100, blank=True, null=True)
    other_charge_description = models.TextField(blank=True, null=True)

    # Features & Notifications
    has_complementary_breakfast = models.BooleanField(default=False)
    send_sms_notification = models.BooleanField(default=True)

    total_bill = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    due_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    # Bill Customization & Approval Tracking
    is_bill_modified = models.BooleanField(default=False)
    modified_bill_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    modification_reason = models.TextField(blank=True, null=True)
    approval_status = models.CharField(max_length=20, choices=IS_APPROVED_CHOICES, default='Approved')

    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='Online')
    ssl_tran_id = models.CharField(max_length=100, blank=True, null=True)
    admin_commission = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)
    present_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.booking_id:
            self.booking_id = "BK-" + str(uuid.uuid4()).upper()[:6]

        if not self.is_bill_modified:
            after_discount = float(self.base_price) - float(self.discount_amount)
            vat_val = (after_discount * float(self.vat_percentage)) / 100
            sc_val = (after_discount * float(self.service_charge_percentage)) / 100
            self.total_bill = after_discount + vat_val + sc_val + float(self.other_charge)

        self.due_amount = float(self.total_bill) - float(self.paid_amount)
        self.admin_commission = (float(self.paid_amount) * float(self.hotel.commission_rate)) / 100

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.booking_id} - {self.guest_name}"

# Daily Sub-ID tracking per room number for partial management
class BookingDayItem(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='daily_items')
    room_number = models.ForeignKey(RoomNumber, on_delete=models.CASCADE)
    date = models.DateField()
    sub_booking_id = models.CharField(max_length=30, unique=True, editable=False)
    is_cancelled = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.sub_booking_id:
            date_str = self.date.strftime('%Y%m%d')
            self.sub_booking_id = f"{self.booking.booking_id}-R{self.room_number.room_number}-{date_str}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.sub_booking_id

class PaymentTransaction(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='Cash')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    note = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.booking.booking_id} - {self.amount}"
        
'''