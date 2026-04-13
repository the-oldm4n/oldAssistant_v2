import re
import requests
import json
import os
from datetime import datetime
from path_builder import get_path, get_app_data_dir
from log_config import debuglog
from config import dev_mode

if dev_mode:
    config_file = get_path("user_data", "auth_config.json")
else:
    config_file = os.path.join(get_app_data_dir(), "user_data", "auth_config.json")


class AuthManager:
    def __init__(self, base_url="http://owl-app.ru"):
        self.base_url = base_url
        self.token = None
        self.user_data = None
        self.is_user_guest = False
        self.temp_2fa_token = None
        self.config_file = config_file
        
    def is_valid_email(self, email):
        if not isinstance(email, str):
            return False
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None
        
    def login(self, email, password):
        """Вход в систему с поддержкой 2FA"""
        try:
            debuglog.info(f"[AUTH] Попытка входа: {email}")
            
            response = requests.post(
                f"{self.base_url}/api/login",
                json={"email": email, "password": password},
                timeout=2,
                verify=False
            )
            
            debuglog.info(f"[AUTH] Статус ответа: {response.status_code}")
            debuglog.info(f"[AUTH] Текст ответа: {response.text}")
            
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                return False, f"Сервер вернул не JSON: {content_type}"
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    if data.get('requires_2fa'):
                        self.temp_2fa_token = data['temp_token']
                        debuglog.info(f"[AUTH] Сохранен temp_token: {self.temp_2fa_token}")
                        return '2fa_required', data.get('message', 'Требуется 2FA')
                    
                    self.token = data['token']
                    self.user_data = data['user']
                    self._save_auth_data()
                    return True, data.get('message', 'Успешный вход')
                else:
                    return False, data.get('error', 'Ошибка входа')
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('error', f'Ошибка {response.status_code}')
                except:
                    return False, f'Ошибка сервера: {response.status_code}'
                    
        except requests.exceptions.ConnectionError:
            return False, "Не удалось подключиться к серверу"
        except requests.exceptions.Timeout:
            return False, "Таймаут подключения"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
        
    def verify_2fa(self, code):
        """Верификация кода 2FA"""
        if not self.temp_2fa_token:
            return False, "Нет активной сессии 2FA"
            
        try:
            debuglog.info(f"[AUTH] Верификация 2FA кода: {code}")
            
            response = requests.post(
                f"{self.base_url}/api/2fa/verify",
                json={"temp_token": self.temp_2fa_token, "code": code},
                timeout=10,
                verify=False
            )
            
            debuglog.info(f"[AUTH] Статус ответа 2FA: {response.status_code}")
            debuglog.info(f"[AUTH] Текст ответа 2FA: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.token = data['token']
                    self.user_data = data['user']
                    self.temp_2fa_token = None
                    self._save_auth_data()
                    return True, data.get('message', '2FA верификация успешна')
                else:
                    return False, data.get('error', 'Ошибка верификации')
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('error', f'Ошибка {response.status_code}')
                except:
                    return False, f'Ошибка сервера: {response.status_code}'
                    
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def resend_2fa_code(self):
        """Повторная отправка кода 2FA"""
        if not self.temp_2fa_token:
            return False, "Нет активной сессии 2FA"
            
        try:
            debuglog.info("[AUTH] Запрос повторной отправки 2FA кода")
            
            response = requests.post(
                f"{self.base_url}/api/2fa/resend",
                json={"temp_token": self.temp_2fa_token},
                timeout=10,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                message = data.get("message")
                debuglog.info(f"[AUTH] Код отправлен повторно! message:{message}")
                return True, data.get('message', 'Код отправлен повторно')
            else:
                try:
                    error_data = response.json()
                    message = error_data.get("error")
                    debuglog.error(f"[AUTH] Ошибка! message:{message}")
                    return False, error_data.get('error', f'Ошибка {response.status_code}')
                except:
                    return False, f'Ошибка сервера: {response.status_code}'
                    
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
     
    def make_authenticated_request(self, endpoint, method="GET", data=None):
        """Выполнить авторизованный запрос с JWT"""
        if not self.token:
            return None
            
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            if method == "GET":
                response = requests.get(f"{self.base_url}{endpoint}", headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(f"{self.base_url}{endpoint}", json=data, headers=headers, timeout=10)
            
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None
    
    def register(self, username, email, password):
        """Регистрация"""
        try:
            debuglog.info(f"[AUTH] Попытка регистрации: {username}, {email}")
            
            response = requests.post(
                f"{self.base_url}/api/register", 
                json={"username": username, "email": email, "password": password},
                timeout=10,
                verify=False
            )
            
            debuglog.info(f"[AUTH] Статус ответа регистрации: {response.status_code}")
            debuglog.info(f"[AUTH] Текст ответа регистрации: {response.text}")
            
            content_type = response.headers.get('content-type', '')
            if 'application/json' not in content_type:
                return False, f"Сервер вернул не JSON: {content_type}"
            
            if response.status_code == 201:
                data = response.json()
                if data.get('success'):
                    return True, {
                        'message': 'Регистрация успешна! Проверьте email для подтверждения',
                        'email_sent': data.get('email_sent', False),
                        'verification_required': True
                    }
                else:
                    return False, data.get('error', 'Ошибка регистрации')
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('error', f'Ошибка {response.status_code}')
                except:
                    return False, f'Ошибка сервера: {response.status_code}'
                    
        except requests.exceptions.ConnectionError:
            return False, "Не удалось подключиться к серверу"
        except requests.exceptions.Timeout:
            return False, "Таймаут подключения"
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
        
    def resend_verification_email(self, email):
        """Отправить письмо подтверждения повторно"""
        try:
            debuglog.info(f"[AUTH] Повторная отправка письма для: {email}")
            
            response = requests.post(
                f"{self.base_url}/api/resend-verification",
                json={"email": email},
                timeout=10,
                verify=False
            )
            
            debuglog.info(f"[AUTH] Статус ответа: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                return True, data.get('message', 'Письмо отправлено')
            else:
                try:
                    error_data = response.json()
                    return False, error_data.get('error', f'Ошибка {response.status_code}')
                except:
                    return False, f'Ошибка сервера: {response.status_code}'
                    
        except Exception as e:
            return False, f"Ошибка: {str(e)}"
    
    def logout(self):
        """Выход из системы"""
        self.token = None
        self.user_data = None
        self._clear_auth_data()
    
    def _clear_auth_data(self):
        """Очистить данные аутентификации"""
        try:
            if os.path.exists(self.config_file):
                os.remove(self.config_file)
        except:
            pass
        
    def is_guest(self):
        """Проверить находится ли пользователь в гостевом режиме"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    auth_data = json.load(f)
                    return auth_data.get('is_guest', False)
        except:
            pass
        
        return False
    
    def is_authenticated(self):
        """Проверить авторизован ли пользователь"""
        debuglog.info("[AUTH] Проверка аутентификации...")

        # Сначала пробуем загрузить из файла
        if not self.token:
            loaded = self._load_auth_data()
            if loaded:
                debuglog.info(f"[AUTH] Токен: {bool(self.token)}")
                debuglog.info(f"[AUTH] Данные пользователя: {bool(self.user_data)}")
            else:
                return False, "Требуется авторизация"
                
        if self.is_guest():
            return True, "Гостевой доступ"
        
        # Если есть токен, проверяем его
        if self.token:
            is_valid = self.verify_token()
            debuglog.info(f"[AUTH] Token status: {is_valid}")
            return is_valid
        
        return False, "Ошибка авторизации"

    def verify_token(self):
        """Проверка JWT токена и обновление user_data"""
        if not self.token:
            return False, "Токен отсутствует"
            
        try:
            debuglog.info(f"[AUTH] Check token...")

            response = requests.post(
                f"{self.base_url}/api/verify-jwt",
                json={"token": self.token},
                timeout=5,
                verify=False
            )
        
            debuglog.info(f"[AUTH] Token status(response): {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.user_data = data['user']
                    debuglog.info(f"[AUTH] Обновлены данные пользователя: {self.user_data['username']}")
                    return True, "Токен валиден"
                else:
                    return False, data.get('message', 'Токен недействителен')
            elif response.status_code == 401:
                return False, "Токен истёк или недействителен"
            else:
                return False, f"Сервер вернул ошибку: {response.status_code}"
            
        except Exception as e:
            return False, "Сервер не отвечает. Проверьте подключение."
        except requests.exceptions.Timeout:
            return False, "Сервер не отвечает (таймаут). Попробуйте позже."
        except Exception as e:
            debuglog.error(f"[AUTH] Failed check token: {e}")
            return False, f"Ошибка проверки токена: {str(e)}"

    def _load_auth_data(self):
        """Загрузить данные аутентификации"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    auth_data = json.load(f)
                    self.token = auth_data.get('token')
                    self.user_data = auth_data.get('user_data')
                    self.is_user_guest = auth_data.get('is_guest')
                    return True
            else:
                debuglog.error(f"[AUTH] Файл конфигурации auth_config.json не найден")
        except Exception as e:
            debuglog.error(f"[AUTH] Ошибка загрузки конфигурации: {e}")
        return False
    
    def load_auth_data_id(self):
        """Загрузить данные аутентификации"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    auth_data = json.load(f)
                    self.user_id = auth_data["user_data"]["id"]
                    return self.user_id
            else:
                debuglog.error(f"[AUTH] Файл конфигурации auth_config.json не найден")
        except Exception as e:
            debuglog.error(f"[AUTH] Ошибка загрузки конфигурации: {e}")
        return False

    def _save_auth_data(self, guest=False):
        """Сохранить данные аутентификации"""
        try:
            auth_data = {
                'token': self.token,
                'user_data': self.user_data,
                'saved_at': datetime.now().isoformat(),
                'is_guest': guest if guest else self.is_guest()
            }
            
            debuglog.info(f"[AUTH] Сохранение данных в auth_config.json")
            with open(self.config_file, 'w') as f:
                json.dump(auth_data, f, indent=2)

        except Exception as e:
            debuglog.error(f"[AUTH] Ошибка сохранения: {e}")

    def upload_user_data(self, data_type, file_path):
        """Отправляет файл с данными на сервер"""
        if not self.token:
            return False, "Нет авторизации"
        
        if not os.path.exists(file_path):
            return False, "Файл не найден"
        
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (f'{data_type}.json', f, 'application/json')}
                data = {
                    'type': data_type,
                    'token': self.token
                }
                
                response = requests.post(
                    f"{self.base_url}/api/upload-data",
                    files=files,
                    data=data,
                    timeout=30,
                    verify=False
                )
            
            if response.status_code == 200:
                return True, "Данные сохранены"
            else:
                return False, f"Ошибка: {response.status_code}"
                
        except Exception as e:
            return False, str(e)
        
    def download_user_data(self, data_type):
        """Загружает данные с сервера"""
        if not self.token:
            return False, "Нет авторизации"
        
        try:
            response = requests.post(
                f"{self.base_url}/api/download-data",
                json={"token": self.token, "type": data_type},
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return True, data.get('data', {})
                else:
                    return False, data.get('error', 'Ошибка загрузки')
            else:
                return False, f"Ошибка сервера: {response.status_code}"
                
        except Exception as e:
            return False, str(e)