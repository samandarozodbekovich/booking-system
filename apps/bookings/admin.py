from django.contrib import admin

from .models import Booking, BookingStatusLog


class BookingStatusLogInline(admin.TabularInline):
    model = BookingStatusLog
    extra = 0
    readonly_fields = ("from_status", "to_status", "changed_by", "note", "changed_at")
    can_delete = False


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "provider", "service", "period", "status")
    list_filter = ("status", "provider")
    inlines = [BookingStatusLogInline]