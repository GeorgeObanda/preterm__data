from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from axes.models import AccessAttempt

from .models import (
    CustomUser, Site, Participant, NotificationLog,
    ScreeningSession, DailyLog
)

# -----------------------
# Admin Site Branding
# -----------------------
admin.site.site_header = "Preterm Study Admin Portal"
admin.site.site_title = "Preterm Study Admin Portal"
admin.site.index_title = "Welcome to the Preterm Study Administration"

# -----------------------
# Custom User Admin
# -----------------------
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Extra Info', {'fields': ('role', 'site')} ),
    )
    list_display = ('username', 'email', 'role', 'site', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'site', 'is_staff', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('-date_joined',)

    actions = ['approve_users', 'reject_users']

    @admin.action(description="Approve selected users")
    def approve_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) approved.")

    @admin.action(description="Reject selected users")
    def reject_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) marked as inactive.")

# -----------------------
# Site Admin
# -----------------------
@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)

# -----------------------
# Screening Session Admin
# -----------------------
@admin.register(ScreeningSession)
class ScreeningSessionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'ra', 'site', 'date', 'number_screened', 'number_eligible', 'created_at')
    list_filter = ('ra', 'site', 'date')
    search_fields = ('ra__username', 'site__name')
    ordering = ('-date', '-created_at')

# -----------------------
# Participant Admin
# -----------------------
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        "study_id", "site", "date_of_birth", "enrollment_date", "due_date",
        "monitor_downloaded", "monitor_downloaded_comment",
        "ultrasound_downloaded", "ultrasound_downloaded_comment",
        "case_report_form_uploaded", "case_report_form_uploaded_comment",
        "video_laryngoscope_uploaded", "video_laryngoscope_uploaded_comment",
        "rop_final_report_uploaded", "rop_final_report_uploaded_comment",
        "head_ultrasound_images_uploaded", "head_ultrasound_images_uploaded_comment",
        "head_ultrasound_report_uploaded", "head_ultrasound_report_uploaded_comment",
        "cost_effectiveness_data_uploaded", "cost_effectiveness_data_uploaded_comment",
        "blood_culture_done", "blood_culture_done_comment",
        "admission_notes_day1_uploaded", "admission_notes_day1_uploaded_comment",
        "admission_notes_24hr_uploaded", "admission_notes_24hr_uploaded_comment",
        "vital_sign_monitoring_done", "vital_sign_monitoring_done_comment",
        "is_completed_display",
    )
    list_filter = ("site", "monitor_downloaded", "ultrasound_downloaded", "enrollment_date")
    search_fields = ("study_id",)
    list_editable = (
        "monitor_downloaded", "ultrasound_downloaded",
        "case_report_form_uploaded", "video_laryngoscope_uploaded",
        "rop_final_report_uploaded", "head_ultrasound_images_uploaded",
        "head_ultrasound_report_uploaded", "cost_effectiveness_data_uploaded",
        "blood_culture_done", "admission_notes_day1_uploaded",
        "admission_notes_24hr_uploaded", "vital_sign_monitoring_done",
    )
    ordering = ("-enrollment_date",)
    readonly_fields = ("due_date",)

    fieldsets = (
        ("Basic Info", {
            "fields": ("study_id", "site", "date_of_birth", "enrollment_date", "due_date")
        }),
        ("RO/Admin Uploads", {
            "fields": (
                ("monitor_downloaded", "monitor_downloaded_comment"),
                ("ultrasound_downloaded", "ultrasound_downloaded_comment"),
                ("case_report_form_uploaded", "case_report_form_uploaded_comment"),
                ("video_laryngoscope_uploaded", "video_laryngoscope_uploaded_comment"),
                ("rop_final_report_uploaded", "rop_final_report_uploaded_comment"),
                ("head_ultrasound_images_uploaded", "head_ultrasound_images_uploaded_comment"),
                ("head_ultrasound_report_uploaded", "head_ultrasound_report_uploaded_comment"),
                ("cost_effectiveness_data_uploaded", "cost_effectiveness_data_uploaded_comment"),
                ("blood_culture_done", "blood_culture_done_comment"),
                ("admission_notes_day1_uploaded", "admission_notes_day1_uploaded_comment"),
                ("admission_notes_24hr_uploaded", "admission_notes_24hr_uploaded_comment"),
                ("vital_sign_monitoring_done", "vital_sign_monitoring_done_comment"),
            )
        }),
    )

    @admin.display(boolean=True, description="Completed")
    def is_completed_display(self, obj):
        return obj.is_completed()

# -----------------------
# Notification Log Admin
# -----------------------
@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('participant', 'notification_type', 'sent_at', 'recipient')
    list_filter = ('notification_type',)
    search_fields = ('participant__study_id', 'recipient__username')
    ordering = ('-sent_at',)

# -----------------------
# Daily Log Admin
# -----------------------
@admin.register(DailyLog)
class DailyLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'title', 'tag_colored', 'content', 'created_at', 'updated_at')
    list_filter = ('tag', 'date', 'user')
    search_fields = ('title', 'content', 'user__username')
    ordering = ('-date', '-created_at')
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Tag')
    def tag_colored(self, obj):
        colors = {'OBS': 'blue', 'EQP': 'green', 'REM': 'orange', 'MISC': 'gray'}
        color = colors.get(obj.tag, 'black')
        return format_html('<span style="color:{}; font-weight:bold;">{}</span>', color, obj.get_tag_display())

# -----------------------
# Custom AccessAttempt Admin (Axes)
# -----------------------
# Unregister default
admin.site.unregister(AccessAttempt)

@admin.register(AccessAttempt)
class CustomAccessAttemptAdmin(admin.ModelAdmin):
    list_display = ('username', 'ip_address', 'attempt_time', 'failures_since_start', 'is_locked')
    list_filter = ('username', 'ip_address', 'attempt_time')
    search_fields = ('username', 'ip_address')

    actions = ['unlock_selected']

    @admin.display(boolean=True, description='Locked?')
    def is_locked(self, obj):
        # Use Axes-provided 'locked' property
        return obj.locked

    @admin.action(description="Unlock selected permanently blocked usernames/IPs")
    def unlock_selected(self, request, queryset):
        for attempt in queryset:
            attempt.delete()  # Remove the lock
        self.message_user(request, f"{queryset.count()} blocked username/IP unlocked.")
