from django.db import models
import secrets

class License(models.Model):
    # Основные поля
    key = models.CharField("Ключ активации", max_length=64, unique=True, blank=True)
    owner_name = models.CharField("Имя клиента (для себя)", max_length=255, blank=True, null=True)
    
    # Срок действия (Задает админ вручную)
    expiration_date = models.DateTimeField("Действует до")
    
    # Лимиты и контроль
    activation_limit = models.PositiveIntegerField("Лимит активаций (шт)", default=1)
    current_activations = models.PositiveIntegerField("Текущее кол-во активаций", default=0, editable=False)
    
    is_active = models.BooleanField("Ключ активен", default=True)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    def save(self, *args, **kwargs):
        # Автоматическая генерация ключа при создании
        if not self.key:
            self.key = f"KEY-{secrets.token_hex(8).upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.owner_name or 'Без имени'} ({self.key[:10]}...)"

    class Meta:
        verbose_name = "Лицензия"
        verbose_name_plural = "Лицензии"

# Отдельная таблица для хранения HWID (кто активировал)
class Activation(models.Model):
    license = models.ForeignKey(License, on_delete=models.CASCADE, related_name='activations')
    hwid = models.CharField("HWID компьютера", max_length=255)
    activated_at = models.DateTimeField("Дата активации", auto_now_add=True)

    class Meta:
        # Один и тот же HWID не может быть привязан к одной лицензии дважды
        unique_together = ('license', 'hwid')
        verbose_name = "Активация (HWID)"
        verbose_name_plural = "Активации"

    def __str__(self):
        return self.hwid