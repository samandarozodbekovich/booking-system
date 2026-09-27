from django.contrib import admin

from .models import Provider, TimeOff, WorkingHours


class WorkingHoursInline(admin.TabularInline):
    model = WorkingHours
    extra = 0


class TimeOffInline(admin.TabularInline):
    model = TimeOff
    extra = 0


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("__str__", "timezone", "is_active")
    list_filter = ("is_active",)
    filter_horizontal = ("services",)
    inlines = [WorkingHoursInline, TimeOffInline]