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
    image = models.ImageField(upload_to='rooms/')
    bed_count = models.IntegerField(default=1)
    has_ac = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    total_inventory = models.IntegerField(default=5, help_text="এই টাইপের মোট কয়টি রুম হোটেলে আছে")

    def __str__(self):
        return f"{self.hotel.name} - {self.room_type}"

class Booking(models.Model):
    STATUS_CHOICES = [('Pending', 'Pending'), ('Confirmed', 'Confirmed'), ('Cancelled', 'Cancelled')]
    PAYMENT_METHODS = [('Online', 'Online/SSLCommerz'), ('Cash', 'Cash/Manual')]
    PAYMENT_TYPES = [('Full', 'Full Payment (100%)'), ('Partial', 'Partial Payment (50%)')]

    hotel = models.ForeignKey(Hotel, on_delete=models.CASCADE)
    rooms = models.ManyToManyField(Room)
    booking_id = models.CharField(max_length=12, unique=True, editable=False)
    guest_name = models.CharField(max_length=100)
    mobile = models.CharField(max_length=15)
    check_in = models.DateField(default=now)
    check_out = models.DateField(default=now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    
    room_count = models.IntegerField(default=1) 
    total_bill = models.DecimalField(max_digits=10, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='Online')
    payment_type = models.CharField(max_length=10, choices=PAYMENT_TYPES, default='Full')
    ssl_tran_id = models.CharField(max_length=100, blank=True, null=True)
    
    admin_commission = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    present_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.booking_id:
            self.booking_id = "BK-" + str(uuid.uuid4()).upper()[:6]
        self.admin_commission = (self.paid_amount * self.hotel.commission_rate) / 100
        super().save(*args, **kwargs)

    def __str__(self):
        return self.booking_id