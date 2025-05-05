#!/usr/bin/env python
import wx
from datetime import datetime
import time

from .message_bus import message_bus, MessageLevel
from .config_utils import get_config_manager

class ConnectedUsersPanel(wx.Panel):
    """Panel para mostrar los usuarios conectados y sus logs compartidos"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = get_config_manager()
        
        # Inicializar componentes de la UI
        self._init_ui()
        
        # Suscribirse a eventos relevantes del MessageBus
        message_bus.on("users_online_updated", self.update_users_list)
        message_bus.on("remote_realtime_event", self.add_remote_log)
        
        # Lista de usuarios actualmente conectados
        self.users_online = []
        
    def _init_ui(self):
        """Inicializa los componentes de la interfaz de usuario"""
        # Crear layout principal
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Agregar título
        title = wx.StaticText(self, label="Usuarios conectados")
        title_font = title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL, 5)
        
        # Área de usuarios conectados
        users_label = wx.StaticText(self, label="Usuarios online:")
        main_sizer.Add(users_label, 0, wx.ALL, 5)
        
        # Lista de usuarios
        self.users_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.users_list.InsertColumn(0, "Usuario", width=100)
        self.users_list.InsertColumn(1, "Shard", width=100)
        self.users_list.InsertColumn(2, "Versión", width=100)
        self.users_list.InsertColumn(3, "Estado", width=100)
        self.users_list.InsertColumn(4, "Última actividad", width=150)
        main_sizer.Add(self.users_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Área de logs compartidos
        logs_label = wx.StaticText(self, label="Logs compartidos:")
        main_sizer.Add(logs_label, 0, wx.ALL, 5)
        
        # Lista de logs compartidos
        self.shared_logs = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.shared_logs.InsertColumn(0, "Hora", width=100)
        self.shared_logs.InsertColumn(1, "Usuario", width=100)
        self.shared_logs.InsertColumn(2, "Tipo", width=100)
        self.shared_logs.InsertColumn(3, "Contenido", width=300)
        self.shared_logs.InsertColumn(4, "Shard", width=100)
        main_sizer.Add(self.shared_logs, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones de control
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = wx.Button(self, label="Refrescar")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        self.clear_logs_btn = wx.Button(self, label="Limpiar logs")
        self.clear_logs_btn.Bind(wx.EVT_BUTTON, self.on_clear_logs)
        button_sizer.Add(self.clear_logs_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)
        
        # Establecer el sizer principal
        self.SetSizer(main_sizer)
        
    def update_users_list(self, users_online):
        """Actualiza la lista de usuarios conectados"""
        self.users_online = users_online
        wx.CallAfter(self._update_ui_users_list)
        
    def _update_ui_users_list(self):
        """Actualiza la UI con la lista de usuarios conectados"""
        # Limpiar lista actual
        self.users_list.DeleteAllItems()
        
        # Agregar usuarios a la lista
        for i, user in enumerate(self.users_online):
            username = user.get('username', 'Unknown')
            shard = user.get('shard', 'Unknown')
            version = user.get('version', 'Unknown')
            status = user.get('status', 'Unknown')
            last_active = user.get('last_active', 'Unknown')
            
            # Convertir timestamp ISO a formato más legible
            try:
                dt = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
                last_active_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                last_active_str = last_active
            
            # Insertar en la lista
            index = self.users_list.InsertItem(i, username)
            self.users_list.SetItem(index, 1, str(shard))
            self.users_list.SetItem(index, 2, str(version))
            self.users_list.SetItem(index, 3, str(status))
            self.users_list.SetItem(index, 4, str(last_active_str))
            
    def add_remote_log(self, username, log_data):
        """Agrega un log remoto a la lista de logs compartidos"""
        wx.CallAfter(self._add_ui_remote_log, username, log_data)
        
    def _add_ui_remote_log(self, username, log_data):
        """Actualiza la UI con un nuevo log remoto"""
        # Obtener datos del log
        timestamp = log_data.get('timestamp', datetime.now().isoformat())
        content = log_data.get('content', '')
        shard = log_data.get('shard', 'Unknown')
        log_type = log_data.get('type', 'stalled')
        
        # Convertir timestamp ISO a formato más legible
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp_str = dt.strftime('%H:%M:%S')
        except:
            timestamp_str = timestamp
        
        # Insertar en la lista de logs compartidos
        index = self.shared_logs.InsertItem(0, timestamp_str)  # Insertar al principio
        self.shared_logs.SetItem(index, 1, username)
        self.shared_logs.SetItem(index, 2, log_type)
        self.shared_logs.SetItem(index, 3, content)
        self.shared_logs.SetItem(index, 4, shard)
        
    def on_refresh(self, event):
        """Maneja el evento de clic en el botón refrescar"""
        # Emitir un evento para solicitar actualización de usuarios
        message_bus.publish(
            content="Requesting refresh of connected users",
            level=MessageLevel.INFO,
            metadata={"source": "connected_users_panel"}
        )
        
        # Intentar obtener la instancia de RealtimeBridge y forzar una sincronización
        try:
            main_frame = wx.GetTopLevelParent(self)
            if hasattr(main_frame, 'realtime_bridge'):
                realtime_bridge = main_frame.realtime_bridge
                if hasattr(realtime_bridge, '_handle_presence_sync') and 'presence' in realtime_bridge.channels:
                    realtime_bridge._handle_presence_sync(realtime_bridge.channels['presence'])
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing users list: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "connected_users_panel"}
            )
        
    def on_clear_logs(self, event):
        """Maneja el evento de clic en el botón limpiar logs"""
        self.shared_logs.DeleteAllItems()