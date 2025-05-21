"""
NotificationManager: Singleton para gestionar notificaciones Windows Toast con rate limiting y configuración oculta.
"""
import os
import threading
import time
from winotify import Notification
from .rate_limiter import MessageRateLimiter

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
        self._load_config()
        # Instancia de rate limiter para notificaciones:
        # - No más de una notificación igual cada 5 minutos
        # - No más de 2 notificaciones en total cada 30 segundos
        self._notifier_limiter = MessageRateLimiter(
            timeout=300, max_duplicates=1, global_limit_count=2, global_limit_window=30
        )
        # Suscribirse al evento de notificación
        from .message_bus import message_bus
        message_bus.on("show_windows_notification", self._on_show_notification)

    def _on_show_notification(self, content):
        # Bypass rate limiting para notificaciones de prueba
        is_test = (
            isinstance(content, str) and "notificación de prueba" in content.lower()
        )
        if not self.notifications_enabled and not is_test:
            return 0
        if not is_test and not self._notifier_limiter.should_send(content, "windows_notification"):
            return 0
        try:
            from os.path import abspath, join, exists
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "SCLogAnalyzer.ico")
            # icon_path = abspath(join("src", "icon.ico"))
            if not exists(icon_path):
                icon_path = None  # fallback: no icono si no existe
            from winotify import audio
            toast = Notification(
                app_id="SCLogAnalyzer",
                title="SCLogAnalyzer",
                msg=content,
                icon=icon_path,  # icono grande 32/48px
                duration="short" if self.notifications_duration < 8 else "long"
            )
            toast.set_audio(audio.Default, loop=False)  # Sonido por defecto de Windows
            # Acción: abrir el log principal
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
