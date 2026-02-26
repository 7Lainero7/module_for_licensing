import os
import json
import datetime
import requests
import uuid
import sys
import hashlib
import platform
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# --- Определение путей ---
if getattr(sys, 'frozen', False):
    # Режим скомпилированного EXE
    APP_PATH = os.path.dirname(sys.executable)
    BASE_DIR = sys._MEIPASS
else:
    # Режим скрипта
    APP_PATH = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = APP_PATH

# Файл лицензии всегда пишем рядом с EXE
LICENSE_FILE = os.path.join(APP_PATH, "license.key")

# Загружаем .env
dotenv_path = os.path.join(BASE_DIR, '.env')
load_dotenv(dotenv_path)

SERVER_URL = os.getenv("SERVER_URL")
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

# ВАЛИДНЫЙ КЛЮЧ ШИФРОВАНИЯ (32 url-safe base64-encoded bytes)
# Этот ключ должен быть одинаковым при создании файла и его чтении.
LOCAL_CRYPTO_KEY = b'5w8z_Y6tX9qK3mN7pL2vR4sT1hG8jF0aBcDeFgHiJkL='

class LicenseManager:
    def __init__(self):
        self.cipher = Fernet(LOCAL_CRYPTO_KEY)

    def get_hwid(self):
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) for elements in range(0,2*6,2)][::-1])
            user = os.getlogin()
            hwid_raw = f"{mac}-{user}-{platform.machine()}"
            return hashlib.md5(hwid_raw.encode()).hexdigest()
        except Exception as e:
            print(f"HWID Error: {e}")
            return "unknown-hwid"

    def check_online(self, license_key):
        hwid = self.get_hwid()
        headers = {"X-API-KEY": API_SECRET_TOKEN, "Content-Type": "application/json"}
        data = {"key": license_key, "hwid": hwid}
        
        try:
            response = requests.post(SERVER_URL, json=data, headers=headers, timeout=5)
            if response.status_code == 200:
                resp_data = response.json()
                if resp_data.get("status") == "success":
                    self.save_license(resp_data)
                    return True, "Успешная активация!"
            
            try:
                msg = response.json().get("message", "Ошибка соединения")
            except:
                msg = f"Ошибка сервера (Code {response.status_code})"
            return False, msg
        except Exception as e:
            return False, f"Ошибка сети: {e}"

    def save_license(self, data):
        payload = {
            "expiration_date": data["expiration_date"],
            "last_run_time": datetime.datetime.utcnow().isoformat()
        }
        json_data = json.dumps(payload).encode()
        encrypted_data = self.cipher.encrypt(json_data)
        with open(LICENSE_FILE, "wb") as f:
            f.write(encrypted_data)

    def check_local_license(self):
        if not os.path.exists(LICENSE_FILE):
            return False, "Файл лицензии не найден."

        try:
            with open(LICENSE_FILE, "rb") as f:
                encrypted_data = f.read()
            
            decrypted_data = self.cipher.decrypt(encrypted_data)
            data = json.loads(decrypted_data)
            
            exp_date_str = data.get("expiration_date")
            last_run_str = data.get("last_run_time")
            
            exp_date = datetime.datetime.fromisoformat(exp_date_str.replace("Z", ""))
            last_run = datetime.datetime.fromisoformat(last_run_str)
            now = datetime.datetime.utcnow()

            if now < last_run:
                return False, "Обнаружен откат системного времени!"

            if now > exp_date:
                return False, "Срок действия лицензии истек."

            self.update_last_run()
            return True, f"Лицензия активна до {exp_date.date()}"

        except Exception as e:
            return False, f"Ошибка чтения лицензии: {e}"

    def update_last_run(self):
        try:
            if not os.path.exists(LICENSE_FILE): return
            with open(LICENSE_FILE, "rb") as f: data = f.read()
            dec_data = self.cipher.decrypt(data)
            payload = json.loads(dec_data)
            payload["last_run_time"] = datetime.datetime.utcnow().isoformat()
            new_data = json.dumps(payload).encode()
            enc_new_data = self.cipher.encrypt(new_data)
            with open(LICENSE_FILE, "wb") as f: f.write(enc_new_data)
        except: pass