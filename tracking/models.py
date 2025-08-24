from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


# -----------------------
# Site Model
# -----------------------
class Site(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


# -----------------------
# Custom User Model
# -----------------------
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('RA', 'Research Assistant'),
        ('RO', 'Research Officer'),
        ('AD', 'PI'),
    )

    role = models.CharField(max_length=2, choices=ROLE_CHOICES)
    site = models.ForeignKey(Site, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


# -----------------------
# Screening Session Model
# -----------------------
class ScreeningSession(models.Model):
    ra = models.ForeignKey(CustomUser, limit_choices_to={'role': 'RA'}, on_delete=models.CASCADE)
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    date = models.DateField(default=timezone.localdate)
    number_screened = models.PositiveIntegerField(default=0)
    number_eligible = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"Session {self.pk} by {self.ra} at {self.site} on {self.date}"


# -----------------------
# Participant Model
# -----------------------
class Participant(models.Model):
    site = models.ForeignKey(Site, on_delete=models.CASCADE)
    screening_session = models.ForeignKey(
        ScreeningSession,
        on_delete=models.CASCADE,
        null=True,
        blank=True,  # allow empty for older participants
    )
    study_id = models.CharField(max_length=50, unique=True)
    enrollment_date = models.DateField(default=timezone.localdate)
    due_date = models.DateField(editable=False)

    # -----------------------
    # Core Tracking (RO/Admin)
    # -----------------------
    monitor_downloaded = models.BooleanField(default=False)
    monitor_downloaded_at = models.DateTimeField(null=True, blank=True)
    monitor_downloaded_by = models.ForeignKey(
        'CustomUser', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='monitor_downloads'
    )

    ultrasound_downloaded = models.BooleanField(default=False)
    ultrasound_downloaded_at = models.DateTimeField(null=True, blank=True)
    ultrasound_downloaded_by = models.ForeignKey(
        'CustomUser', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ultrasound_downloads'
    )

    monitor_downloaded_on = models.DateTimeField(null=True, blank=True)
    ultrasound_downloaded_on = models.DateTimeField(null=True, blank=True)

    # -----------------------
    # Form Upload Tracking (RO/Admin)
    # -----------------------
    case_report_form_uploaded = models.BooleanField(default=False)
    video_laryngoscope_uploaded = models.BooleanField(default=False)
    rop_final_report_uploaded = models.BooleanField(default=False)
    head_ultrasound_images_uploaded = models.BooleanField(default=False)
    head_ultrasound_report_uploaded = models.BooleanField(default=False)
    cost_effectiveness_data_uploaded = models.BooleanField(default=False)
    blood_culture_done = models.BooleanField(default=False)
    admission_notes_day1_uploaded = models.BooleanField(default=False)
    admission_notes_24hr_uploaded = models.BooleanField(default=False)
    vital_sign_monitoring_done = models.BooleanField(default=False)

    # -----------------------
    # New Fields for RA Tracking
    # -----------------------
    date_of_birth = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-enrollment_date']

    def save(self, *args, **kwargs):
        if not self.due_date:
            self.due_date = self.enrollment_date + timedelta(days=7)
        super().save(*args, **kwargs)

    def days_remaining(self):
        return (self.due_date - timezone.localdate()).days

    def status_color(self):
        days = self.days_remaining()
        if days >= 4:
            return 'green'
        elif 2 <= days <= 3:
            return 'yellow'
        elif 0 <= days <= 1:
            return 'red'
        else:
            return 'overdue'

    def is_completed(self):
        """Check if all required downloads/uploads are done."""
        required_items = [
            self.monitor_downloaded,
            self.ultrasound_downloaded,
            self.head_ultrasound_images_uploaded,
            self.head_ultrasound_report_uploaded,
            self.case_report_form_uploaded,
            self.video_laryngoscope_uploaded,
            self.rop_final_report_uploaded,
            self.cost_effectiveness_data_uploaded,
            self.admission_notes_day1_uploaded,
            # self.admission_notes_24hr_uploaded,
            # self.vital_sign_monitoring_done
        ]
        return all(required_items)

    def __str__(self):
        return f"{self.study_id} ({self.site.name})"


# -----------------------
# Notification Log
# -----------------------
class NotificationLog(models.Model):
    NOTIFICATION_TYPES = (
        ('DAILY_PROMPT', 'Daily Prompt'),
        ('EARLY_REMINDER', 'Early Reminder'),
        ('FINAL_REMINDER', 'Final Reminder'),
        ('OVERDUE_ALERT', 'Overdue Alert'),
    )

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    sent_at = models.DateTimeField(auto_now_add=True)
    recipient = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.get_notification_type_display()} → {self.participant.study_id} at {self.sent_at}"
