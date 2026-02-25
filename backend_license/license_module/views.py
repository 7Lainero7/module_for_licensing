from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings # Импортируем настройки
from .models import License, Activation

class ActivateLicenseView(APIView):
    def post(self, request):
        # --- ПРОВЕРКА API ТОКЕНА ---
        api_key = request.headers.get('X-API-KEY')
        if api_key != settings.API_SECRET_TOKEN:
            return Response(
                {"status": "error", "message": "Неверный API токен или доступ запрещен"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        # ---------------------------

        key = request.data.get('key')
        hwid = request.data.get('hwid')

        if not key or not hwid:
            return Response(
                {"status": "error", "message": "Не передан ключ или HWID"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            license_obj = License.objects.get(key=key)
        except License.DoesNotExist:
            return Response(
                {"status": "error", "message": "Ключ не найден"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        if not license_obj.is_active:
            return Response(
                {"status": "error", "message": "Ключ заблокирован администратором"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        if license_obj.expiration_date < timezone.now():
            return Response(
                {"status": "error", "message": "Срок действия ключа истек"}, 
                status=status.HTTP_403_FORBIDDEN
            )

        activation, created = Activation.objects.get_or_create(license=license_obj, hwid=hwid)

        if created:
            if license_obj.current_activations >= license_obj.activation_limit:
                activation.delete()
                return Response(
                    {"status": "error", "message": f"Лимит активаций ({license_obj.activation_limit}) исчерпан"}, 
                    status=status.HTTP_403_FORBIDDEN
                )
            
            license_obj.current_activations += 1
            license_obj.save()
            
            return Response({
                "status": "success", 
                "message": "Активация успешна",
                "expiration_date": license_obj.expiration_date,
                "server_time": timezone.now()
            }, status=status.HTTP_201_CREATED)
        
        else:
            return Response({
                "status": "success", 
                "message": "Ключ валиден",
                "expiration_date": license_obj.expiration_date,
                "server_time": timezone.now()
            }, status=status.HTTP_200_OK)