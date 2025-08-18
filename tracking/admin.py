from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Site, Participant, NotificationLog

# Customize the admin site titles
admin.site.site_header = "Preterm Study Admin Portal"
admin.site.site_title = "Preterm Study Admin Portal"
admin.site.index_title = "Welcome to the Preterm Study Administration"

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('Extra', {'fields': ('role', 'site')}),
    )
    list_display = ('username', 'email', 'role', 'site', 'is_staff', 'is_active', 'date_joined')
    list_filter = ('role', 'site', 'is_staff', 'is_active')
    search_fields = ('username', 'email')

    actions = ['approve_users', 'reject_users']

    @admin.action(description="Approve selected users")
    def approve_users(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} user(s) successfully approved.")

    @admin.action(description="Reject selected users")
    def reject_users(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} user(s) marked as inactive/rejected.")


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        'study_id', 'site', 'enrollment_date', 'due_date',
        'monitor_downloaded', 'ultrasound_downloaded', 'is_completed'
    )
    list_filter = ('site', 'monitor_downloaded', 'ultrasound_downloaded')
    search_fields = ('study_id',)

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('participant', 'notification_type', 'sent_at', 'recipient')
    list_filter = ('notification_type',)
    search_fields = ('participant__study_id', 'recipient__username')
