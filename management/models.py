from django.db import models
from django.contrib.auth.models import User
from rbs.models import Hotel, RoomNumber, Booking

class UserManagementPermission(models.Model):
    PERMISSION_TYPES = [
        ('ALL', 'All Hotels Permission (Default)'),
        ('CUSTOM', 'Specific Hotel & Rooms Permission'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='management_permission')
    permission_type = models.CharField(max_length=10, choices=PERMISSION_TYPES, default='ALL')
    
    # Custom Permitted Hotels & Rooms
    allowed_hotels = models.ManyToManyField(Hotel, blank=True)
    allowed_rooms = models.ManyToManyField(RoomNumber, blank=True)
    
    # Custom Action Permissions (기존 + নতুন)
    can_give_discount = models.BooleanField(default=False, help_text="Allow staff to assign discount amount")
    can_cancel_booking = models.BooleanField(default=False, help_text="Allow staff to cancel existing bookings")
    can_modify_bill_and_dates = models.BooleanField(
        default=False, 
        help_text="Allow staff to partially cancel rooms or deduce check-out dates and modify bill"
    )
    can_delete_booking = models.BooleanField(default=False, help_text="Allow staff to delete bookings")
    can_edit_price = models.BooleanField(default=False, help_text="Allow staff to edit room prices")
    can_send_sms = models.BooleanField(default=False, help_text="Allow staff to send SMS to guests")
    can_give_complimentary_breakfast = models.BooleanField(default=False, help_text="Allow staff to grant free breakfast")

    def __str__(self):
        return f"Permissions: {self.user.username} ({self.get_permission_type_display()})"


class GuestRegistrationCard(models.Model):
    """GRC (Guest Registration Card) Model"""
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='grc_card')
    grc_no = models.CharField(max_length=50, blank=True, null=True, unique=True, help_text="Manual GRC Registration Number")
    father_name = models.CharField(max_length=150, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    nationality = models.CharField(max_length=50, default='Bangladeshi')
    nid_passport_no = models.CharField(max_length=100, blank=True, null=True)
    occupation = models.CharField(max_length=100, blank=True, null=True)
    purpose_of_visit = models.CharField(max_length=100, blank=True, null=True)
    vehicle_no = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"GRC #{self.grc_no or 'N/A'} - Booking #{self.booking.booking_id}"

class AdditionalGuest(models.Model):
    """Guest list under a single booking"""
    grc = models.ForeignKey(GuestRegistrationCard, on_delete=models.CASCADE, related_name='additional_guests')
    name = models.CharField(max_length=150)
    age = models.IntegerField(blank=True, null=True)
    relation = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Guest: {self.name}"


class UserActivityLog(models.Model):
    """System activity tracking log"""
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user} - {self.action} ({self.timestamp.strftime('%Y-%m-%d %H:%M')})"


class MessageLog(models.Model):
    """SMS communication log"""
    booking = models.ForeignKey(Booking, on_delete=models.SET_NULL, null=True, blank=True)
    sent_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    message_body = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.phone_number} at {self.sent_at.strftime('%Y-%m-%d %H:%M')}"