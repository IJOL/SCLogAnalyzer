"""
NotificationManager: Singleton para gestionar notificaciones Windows Toast con rate limiting y configuración oculta.
"""
import threading
import time
from winotify import Notification

class NotificationManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, config_manager):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self, config_manager):
        if self._initialized:
            return
        self._initialized = True
        self.config_manager = config_manager
        # winotify no requiere instancia global, solo se usa Notification
        self._load_config()
        self._last_sent = {}  # {(type, content): timestamp}
        self._recent_times = []  # [timestamp]
        self._rate_limit_lock = threading.Lock()
        # Suscribirse al evento de notificación
        from .message_bus import message_bus
        message_bus.on("show_windows_notification", self._on_show_notification)

    def _on_show_notification(self, content):
        if not self.notifications_enabled:
            return 0
        if self._rate_limited("windows_notification", content):
            return 0
        try:
            toast = Notification(
                app_id="SCLogAnalyzer",
                title="SCLogAnalyzer",
                msg=content,
                duration="short" if self.notifications_duration < 8 else "long"
            )
            toast.show()
        except Exception:
            pass  # Nunca debe bloquear la app
        return 0

    def _load_config(self):
        self.notifications_enabled = self.config_manager.get('notifications_enabled', False)
        self.notifications_events = set(self.config_manager.get('notifications_events', ["vip"]))
        self.notifications_duration = int(self.config_manager.get('notifications_duration', 5))

    def reload_config(self):
        self._load_config()

    def _rate_limited(self, notif_type, content):
        now = time.time()
        key = (notif_type, content)
        with self._rate_limit_lock:
            # No más de una notificación igual cada 5 minutos
            last = self._last_sent.get(key, 0)
            if now - last < 300:
                return True
            # No más de 2 notificaciones en total cada 30 segundos
            self._recent_times = [t for t in self._recent_times if now - t < 30]
            if len(self._recent_times) >= 2:
                return True
            # Si pasa, actualiza los registros
            self._last_sent[key] = now
            self._recent_times.append(now)
        return False
