"""
NotificationManager: Singleton para gestionar notificaciones Windows Toast con rate limiting y configuración oculta.
"""
import os
import threading
import time
import wx

from ..core.config_utils import get_application_path, get_template_base_dir
from ..core.rate_limiter import MessageRateLimiter

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
        from ..core.message_bus import message_bus
        message_bus.on("show_windows_notification", self._on_show_notification)

    class NotificationPopup(wx.Frame):
        def __init__(self, message, icon_path=None, duration=5, title="SCLogAnalyzer"):
            style = wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.BORDER_NONE
            wx.Frame.__init__(self, None, style=style)
            self.duration = duration
            panel = wx.Panel(self)
            panel.SetBackgroundColour(wx.Colour(140, 140, 140))  # gris clarito
            main_sizer = wx.BoxSizer(wx.VERTICAL)
            # Título
            title_text = wx.StaticText(panel, label=title)
            title_font = wx.Font(15, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            title_text.SetFont(title_font)
            main_sizer.Add(title_text, 0, wx.TOP | wx.LEFT | wx.RIGHT | wx.ALIGN_CENTER_HORIZONTAL, 14)
            # Icono y contenido
            content_sizer = wx.BoxSizer(wx.HORIZONTAL)
            icon_size = (48, 48)
            if icon_path and os.path.exists(icon_path):
                bmp = wx.Bitmap(icon_path, wx.BITMAP_TYPE_ICO)
                if bmp.IsOk():
                    bmp = wx.Bitmap.ConvertToImage(bmp).Scale(icon_size[0], icon_size[1], wx.IMAGE_QUALITY_HIGH)
                    bmp = wx.Bitmap(bmp)
                else:
                    bmp = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, icon_size)
            else:
                bmp = wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, icon_size)
            icon = wx.StaticBitmap(panel, bitmap=bmp)
            content_sizer.Add(icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 12)
            # Texto de contenido
            text = wx.StaticText(panel, label=message)
            font = wx.Font(13, wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            text.SetFont(font)
            text.Wrap(220)  # Más cuadrada, menos larga
            content_sizer.Add(text, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 12)
            main_sizer.Add(content_sizer, 1, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
            panel.SetSizer(main_sizer)
            main_sizer.Fit(panel)
            # Hacer la ventana más cuadrada
            width, height = panel.GetSize()
            self.SetClientSize((max(width, 320), max(height, 120)))
            # self.SetBackgroundColour(wx.Colour(240, 210, 240))
            self._position_bottom_right()
            self.timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_timer, self.timer)
            self.timer.StartOnce(self.duration * 1000)
            self.Show()
            wx.Bell()

        def _position_bottom_right(self):
            display = wx.Display(wx.Display.GetFromWindow(self))
            geometry = display.GetGeometry()
            width, height = self.GetSize()
            x = geometry.GetRight() - width - 40
            y = geometry.GetBottom() - height - 60
            self.SetPosition((x, y))

        def on_timer(self, event):
            self.timer.Stop()
            self.Destroy()

    def _on_show_notification(self, content):
        from ..core.message_bus import message_bus
        from ..core.message_bus import MessageLevel
        import traceback
        # Log entrada (DEBUG)
        message_bus.publish(
            content=f"[NotificationManager] _on_show_notification called with content: {repr(content)}",
            level=MessageLevel.DEBUG,
            metadata={"source": "notification_manager"}
        )
        is_test = (
            isinstance(content, str) and "notificación de prueba" in content.lower()
        )
        if not self.notifications_enabled and not is_test:
            message_bus.publish(
                content="[NotificationManager] Notifications disabled and not test. Skipping.",
                level=MessageLevel.DEBUG,
                metadata={"source": "notification_manager"}
            )
            return 0
        if not is_test and not self._notifier_limiter.should_send(content, "windows_notification"):
            return 0
        def show_notification():
            try:
                from os.path import join, exists
                icon_path = join(get_template_base_dir(),"assets", "SCLogAnalyzer.ico")
                if not exists(icon_path):
                    icon_path = None  # fallback: no icono si no existe
                duration = getattr(self, 'notifications_duration', 5)
                self.NotificationPopup(str(content), icon_path=icon_path, duration=duration)
                message_bus.publish(
                    content=f"[NotificationManager] NotificationPopup shown: {repr(content)}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "notification_manager"}
                )
            except Exception as ex:
                tb = traceback.format_exc()
                message_bus.publish(
                    content=f"[NotificationManager] Error showing notification: {ex}\n{tb}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "notification_manager"}
                )
            return 0
        # Asegura ejecución en hilo principal wx
        if wx.IsMainThread():
            show_notification()
        else:
            wx.CallAfter(show_notification)
        return 0

    def _load_config(self):
        self.notifications_enabled = self.config_manager.get('notifications_enabled', True)
        self.notifications_duration = int(self.config_manager.get('notifications_duration', 5))
        self.notifications_events = set(self.config_manager.get('notifications_events', ["vip"]))

    def reload_config(self):
        self._load_config()
