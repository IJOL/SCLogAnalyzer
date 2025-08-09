"""
MessageRateLimiter: clase reutilizable para rate limiting configurable por contexto.
Permite limitar mensajes repetidos y aplicar límites globales de eventos en ventana de tiempo.
"""
import time
import threading

class MessageRateLimiter:
    def __init__(self, timeout=300, max_duplicates=1, cleanup_interval=60, global_limit_count=None, global_limit_window=None):
        """
        Args:
            timeout: Tiempo en segundos antes de permitir el mismo mensaje de nuevo.
            max_duplicates: Máximo de duplicados permitidos en el periodo timeout.
            cleanup_interval: Cada cuánto limpiar mensajes antiguos.
            global_limit_count: Máximo de eventos globales permitidos en la ventana global_limit_window.
            global_limit_window: Ventana de tiempo (segundos) para el límite global.
        """
        self.messages = {}  # {message_hash: (timestamp, count)}
        self.timeout = timeout
        self.max_duplicates = max_duplicates
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = time.time()
        self._lock = threading.Lock()
        # Límite global
        self.global_limit_count = global_limit_count
        self.global_limit_window = global_limit_window
        self._recent_times = []  # [timestamp]

    def should_send(self, message, message_type=None):
        """
        Devuelve True si el mensaje puede enviarse según la configuración de rate limiting.
        """
        now = time.time()
        key = f"{message_type}:{message}" if message_type else message
        with self._lock:
            # Límite global de eventos
            if self.global_limit_count and self.global_limit_window:
                self._recent_times = [t for t in self._recent_times if now - t < self.global_limit_window]
                if len(self._recent_times) >= self.global_limit_count:
                    return False
            # Cleanup periódico
            if now - self.last_cleanup > self.cleanup_interval:
                self.cleanup_messages(now)
            # Límite por mensaje
            if key in self.messages:
                last_time, count = self.messages[key]
                if count >= self.max_duplicates and now - last_time < self.timeout:
                    self.messages[key] = (last_time, count + 1)
                    return False
                if now - last_time >= self.timeout:
                    self.messages[key] = (now, 1)
                else:
                    self.messages[key] = (last_time, count + 1)
            else:
                self.messages[key] = (now, 1)
            # Registrar evento global
            if self.global_limit_count and self.global_limit_window:
                self._recent_times.append(now)
        return True

    def cleanup_messages(self, current_time):
        stale_keys = [key for key, (last_time, _) in self.messages.items() if current_time - last_time > self.cleanup_interval]
        for key in stale_keys:
            del self.messages[key]
        self.last_cleanup = current_time

    def get_stats(self, message, message_type=None):
        key = f"{message_type}:{message}" if message_type else message
        if key in self.messages:
            last_time, count = self.messages[key]
            blocked = count > self.max_duplicates and (time.time() - last_time < self.timeout)
            return {"last_sent": last_time, "count": count, "blocked": blocked}
        return None
