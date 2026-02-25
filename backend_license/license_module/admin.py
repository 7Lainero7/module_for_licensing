from django.contrib import admin
from .models import License, Activation

class ActivationInline(admin.TabularInline):
    model = Activation
    extra = 0
    readonly_fields = ('hwid', 'activated_at')
    can_delete = True
    verbose_name = "Привязанный ПК"
    verbose_name_plural = "Список активированных ПК"

@admin.register(License)
class LicenseAdmin(admin.ModelAdmin):
    list_display = ('key', 'owner_name', 'expiration_date', 'get_status', 'activation_limit', 'current_activations', 'is_active')
    list_filter = ('is_active', 'expiration_date')
    search_fields = ('key', 'owner_name')
    readonly_fields = ('current_activations', 'created_at')
    inlines = [ActivationInline] # Показываем HWID прямо внутри лицензии
    
    fieldsets = (
        (None, {
            'fields': ('key', 'owner_name', 'is_active')
        }),
        ('Срок действия', {
            'fields': ('expiration_date',)
        }),
        ('Лимиты', {
            'fields': ('activation_limit', 'current_activations')
        }),
    )

    def get_status(self, obj):
        from django.utils import timezone
        if not obj.is_active:
            return "Отключен"
        if obj.expiration_date < timezone.now():
            return "Истек"
        return "Активен"
    get_status.short_description = "Статус"