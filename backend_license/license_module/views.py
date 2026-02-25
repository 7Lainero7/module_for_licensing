from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.shortcuts import get_object_or_404
from .models import License, Activation

class ActivateLicenseView(APIView):
    """
    Эндпоинт для активации и проверки ключа.
    Принимает: key (str), hwid (str)
    """
    
    def post(self, request):
        key = request.data.get('key')
        hwid = request.data.get('hwid')

        # 1. Проверка входных данных
        if not key or not hwid:
            return Response(
                {"status": "error", "message": "Не передан ключ или HWID"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2. Поиск ключа в базе
        try:
            license_obj = License.objects.get(key=key)
        except License.DoesNotExist:
            return Response(
                {"status": "error", "message": "Ключ не найден"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # 3. Проверка админского флага (если админ отключил ключ вручную)
        if not license_obj.is_active:
            return Response(
                {"status": "error", "message": "Ключ заблокирован администратором"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 4. Проверка срока действия (сравниваем с серверным временем)
        if license_obj.expiration_date < timezone.now():
            return Response(
                {"status": "error", "message": "Срок действия ключа истек"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        # 5. Проверка HWID (уже активировали на этом ПК?)
        activation, created = Activation.objects.get_or_create(license=license_obj, hwid=hwid)

        if created:
            # Это НОВЫЙ ПК для этого ключа
            # Проверяем лимит активаций
            if license_obj.current_activations >= license_obj.activation_limit:
                # Лимит исчерпан, удаляем запись активации и шлем отказ
                activation.delete()
                return Response(
                    {"status": "error", "message": f"Лимит активаций ({license_obj.activation_limit}) исчерпан"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Лимит есть - увеличиваем счетчик
            license_obj.current_activations += 1
            license_obj.save()
            
            return Response({
                "status": "success", 
                "message": "Активация успешна",
                "expiration_date": license_obj.expiration_date,
                "server_time": timezone.now()
            }, status=status.HTTP_201_CREATED)
        
        else:
            # Этот ПК УЖЕ был активирован этим ключом
            # Просто обновляем дату (на случай, если админ продлил) и пускаем
            return Response({
                "status": "success", 
                "message": "Ключ валиден",
                "expiration_date": license_obj.expiration_date,
                "server_time": timezone.now()
            }, status=status.HTTP_200_OK)