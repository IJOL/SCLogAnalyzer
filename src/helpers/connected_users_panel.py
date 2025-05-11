#!/usr/bin/env python
import wx
from datetime import datetime
import time

from .message_bus import message_bus, MessageLevel
from .config_utils import get_config_manager
# Eliminar import incorrecto de get_async_client y usar el singleton supabase_manager
from .supabase_manager import supabase_manager

class ConnectedUsersPanel(wx.Panel):
    """Panel para mostrar los usuarios conectados y sus logs compartidos"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = get_config_manager()
        
        # Variables para almacenar los valores actuales
        self.current_mode = "Unknown"
        self.current_shard = "Unknown"
        self.filter_by_current_mode = False
        self.filter_by_current_shard = False
        self.include_unknown_mode = True
        self.include_unknown_shard = True
        
        # Inicializar componentes de la UI
        self._init_ui()
        
        # Suscribirse a eventos relevantes del MessageBus
        message_bus.on("users_online_updated", self.update_users_list)
        message_bus.on("remote_realtime_event", self.add_remote_log)
        message_bus.on("shard_version_update", self.on_shard_version_update)
        # El control de pings ahora depende solo de broadcast_ping_missing
        message_bus.on("broadcast_ping_missing", self._on_broadcast_ping_missing)
        
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
          # Panel de filtros para los logs
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Primer fila: Filtros de modo
        mode_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Contenedor para el filtro de modo y su etiqueta
        mode_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Checkbox para filtrar por modo actual
        self.mode_checkbox = wx.CheckBox(self, label="Filtrar por modo actual:")
        self.mode_checkbox.Bind(wx.EVT_CHECKBOX, self.on_filter_changed)
        mode_row_sizer.Add(self.mode_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        # Etiqueta para mostrar el modo actual
        self.mode_label = wx.StaticText(self, label=f"({self.current_mode})")
        mode_row_sizer.Add(self.mode_label, 0, wx.ALIGN_CENTER_VERTICAL)
        
        # Añadir la primera fila al contenedor de modo
        mode_filter_sizer.Add(mode_row_sizer, 0, wx.BOTTOM, 2)
        
        # Fila para el checkbox de incluir desconocidos en el modo
        mode_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.unknown_mode_checkbox = wx.CheckBox(self, label="Incluir desconocidos")
        self.unknown_mode_checkbox.SetValue(True)  # Por defecto activado
        self.unknown_mode_checkbox.Bind(wx.EVT_CHECKBOX, self.on_filter_changed)
        mode_unknown_sizer.Add(self.unknown_mode_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        
        # Añadir la segunda fila al contenedor de modo
        mode_filter_sizer.Add(mode_unknown_sizer, 0, 0)
        
        # Añadir el contenedor de filtros de modo al sizer principal de filtros
        filter_sizer.Add(mode_filter_sizer, 0, wx.RIGHT, 15)
        
        # Filtros de shard (estructura similar)
        shard_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Primera fila para shard: checkbox y etiqueta
        shard_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.shard_checkbox = wx.CheckBox(self, label="Filtrar por shard actual:")
        self.shard_checkbox.Bind(wx.EVT_CHECKBOX, self.on_filter_changed)
        shard_row_sizer.Add(self.shard_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        # Etiqueta para mostrar el shard actual
        self.shard_label = wx.StaticText(self, label=f"({self.current_shard})")
        shard_row_sizer.Add(self.shard_label, 0, wx.ALIGN_CENTER_VERTICAL)
        
        # Añadir primera fila al contenedor de shard
        shard_filter_sizer.Add(shard_row_sizer, 0, wx.BOTTOM, 2)
        
        # Segunda fila para shard: incluir desconocidos
        shard_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.unknown_shard_checkbox = wx.CheckBox(self, label="Incluir desconocidos")
        self.unknown_shard_checkbox.SetValue(True)  # Por defecto activado
        self.unknown_shard_checkbox.Bind(wx.EVT_CHECKBOX, self.on_filter_changed)
        shard_unknown_sizer.Add(self.unknown_shard_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        
        # Añadir segunda fila al contenedor de shard
        shard_filter_sizer.Add(shard_unknown_sizer, 0, 0)
        
        # Añadir contenedor de filtros de shard al sizer principal
        filter_sizer.Add(shard_filter_sizer, 0, 0)
        
        # Añadir el panel de filtros al sizer principal
        main_sizer.Add(filter_sizer, 0, wx.ALL, 5)
        
        # Lista de logs compartidos
        self.shared_logs = wx.ListCtrl(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.shared_logs.InsertColumn(0, "Hora", width=100)
        self.shared_logs.InsertColumn(1, "Usuario", width=100)
        self.shared_logs.InsertColumn(2, "Tipo", width=100)
        self.shared_logs.InsertColumn(3, "Contenido", width=300)
        self.shared_logs.InsertColumn(4, "Shard", width=100)
        self.shared_logs.InsertColumn(5, "Modo", width=100)  # Nueva columna para modo
        main_sizer.Add(self.shared_logs, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones de control
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = wx.Button(self, label="Refrescar")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        self.clear_logs_btn = wx.Button(self, label="Limpiar logs")
        self.clear_logs_btn.Bind(wx.EVT_BUTTON, self.on_clear_logs)
        button_sizer.Add(self.clear_logs_btn, 0, wx.ALL, 5)

        # Botón Reconectar (siempre visible en debug)
        self.reconnect_btn = wx.Button(self, label="Reconectar")
        self.reconnect_btn.Bind(wx.EVT_BUTTON, self.on_reconnect)
        # Mostrar siempre en debug al inicializar
        if self._is_debug_mode():
            self.reconnect_btn.Show()
        else:
            self.reconnect_btn.Hide()
        button_sizer.Add(self.reconnect_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        # Estado de pings y temporizadores
        self._last_own_ping = datetime.utcnow()
        self._ping_timeout_sec = 30  # configurable
        self._ping_timer = wx.Timer(self)
        self._ping_timer.Start(5000)  # comprobar cada 5s
        self._alert_blink_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_alert_blink, self._alert_blink_timer)
        self._alert_blink_state = False
        self._alert_label = wx.StaticText(self, label="")
        main_sizer.Add(self._alert_label, 0, wx.ALIGN_LEFT | wx.ALL, 2)

        # Establecer el sizer principal
        self.SetSizer(main_sizer)
        
    def update_users_list(self, users_online):
        """
        Actualiza la lista de usuarios conectados. El control de pings ya no depende de presencia ni de broadcast_ping_received.
        """
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
    
    def on_shard_version_update(self, shard, version, username, mode=None):
        """
        Maneja las actualizaciones de shard y versión.
        Actualiza los valores actuales y las etiquetas de los filtros.
        Además, si el username recibido es válido, lo almacena como el username actual.
        """
        self.current_shard = shard if shard else "Unknown"
        self.current_mode = mode if mode is not None else self.current_mode
        # Actualizar username si es válido
        if username and username != "Unknown":
            self._my_username = username
        # Actualizar etiquetas
        wx.CallAfter(self._update_filter_labels)
    
    def _update_filter_labels(self):
        """Actualiza las etiquetas de los filtros con los valores actuales"""
        self.mode_label.SetLabel(f"({self.current_mode})")
        self.shard_label.SetLabel(f"({self.current_shard})")
        self.Layout()  # Forzar actualización del layout
            
    def add_remote_log(self, username, log_data):
        """Agrega un log remoto a la lista de logs compartidos"""
        wx.CallAfter(self._add_ui_remote_log, username, log_data)
        
    def _add_ui_remote_log(self, username, log_data):
        """Actualiza la UI con un nuevo log remoto"""
        # Obtener datos del log
        raw_data = log_data.get('raw_data', {})
        if 'metadata' in log_data:
            timestamp = log_data['metadata'].get('timestamp', datetime.now().isoformat())
            content = log_data['metadata'].get('content', '')
            shard = log_data['metadata'].get('shard', 'Unknown')
            log_type = log_data['metadata'].get('type', 'Unknown')
        else:
            timestamp = raw_data.get('timestamp', datetime.now().isoformat())
            content = log_data.get('content', '')
            log_type = log_data.get('type', 'Unknown')
            shard = raw_data.get('shard', 'Unknown')
        
        # Extraer modo del raw_data si está disponible
        mode = raw_data.get('mode', 'Unknown')
        
        # Convertir timestamp ISO a formato más legible
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp_str = dt.strftime('%H:%M:%S')
        except:
            timestamp_str = timestamp
        
        # Crear entrada de log temporal (sin almacenarla)
        log_entry = {
            'timestamp_str': timestamp_str,
            'username': username,
            'log_type': log_type,
            'content': content,
            'shard': shard,
            'mode': mode
        }
        
        # Mostrar la entrada solo si pasa los filtros actuales
        if self._passes_current_filters(log_entry):
            self._add_log_entry_to_ui(log_entry, 0)  # Insertar al principio
    
    def _add_log_entry_to_ui(self, log_entry, position):
        """Añade una entrada de log a la UI en la posición especificada"""       
        index = self.shared_logs.InsertItem(position, log_entry['timestamp_str'])
        self.shared_logs.SetItem(index, 1, str(log_entry['username'] or 'Unknown'))
        self.shared_logs.SetItem(index, 2, str(log_entry['log_type'] or 'Unknown'))
        self.shared_logs.SetItem(index, 3, str(log_entry['content'] or ''))
        self.shared_logs.SetItem(index, 4, str(log_entry['shard'] or 'Unknown'))
        self.shared_logs.SetItem(index, 5, str(log_entry['mode'] or 'Unknown'))
        
    def _passes_current_filters(self, log_entry):
        """Verifica si una entrada de log pasa los filtros actuales"""
        # Lista de valores considerados como "desconocidos"
        unknown_values = [None, "", "Unknown"]
        
        # Verificar filtro de modo
        if self.filter_by_current_mode:
            mode_value = log_entry.get('mode')
            # Verificar si el modo es desconocido
            if mode_value in unknown_values:
                # Si el modo es desconocido y no estamos incluyendo desconocidos, rechazar
                if not self.include_unknown_mode:
                    return False
            # Si el modo no es desconocido y es diferente al actual, rechazar
            elif mode_value != self.current_mode:
                return False
        
        # Verificar filtro de shard
        if self.filter_by_current_shard:
            shard_value = log_entry.get('shard')
            # Verificar si el shard es desconocido
            if shard_value in unknown_values:
                # Si el shard es desconocido y no estamos incluyendo desconocidos, rechazar
                if not self.include_unknown_shard:
                    return False
            # Si el shard no es desconocido y es diferente al actual, rechazar
            elif shard_value != self.current_shard:
                return False
        
        # Si pasa ambos filtros
        return True
        
    def on_filter_changed(self, event):
        """Maneja el cambio en los checkboxes de filtro"""
        # Actualizar estados de filtro
        self.filter_by_current_mode = self.mode_checkbox.GetValue()
        self.filter_by_current_shard = self.shard_checkbox.GetValue()
        self.include_unknown_mode = self.unknown_mode_checkbox.GetValue()
        self.include_unknown_shard = self.unknown_shard_checkbox.GetValue()
    
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
            realtime_bridge = main_frame.realtime_bridge
            if 'general' in realtime_bridge.channels:
                realtime_bridge._handle_presence_sync(realtime_bridge.channels['general'])
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing users list: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "connected_users_panel"}
            )
        
    def on_clear_logs(self, event):
        """Maneja el evento de clic en el botón limpiar logs"""
        self.shared_logs.DeleteAllItems()

    def _show_reconnect_and_alert(self):
        # Mostrar botón solo si debug o fallo de pings
        if self._is_debug_mode():
            self.reconnect_btn.Show()
        else:
            self.reconnect_btn.Show()
        self._alert_label.SetLabel("¡Sin pings propios! Reconectar.")
        self._alert_blink_timer.Start(500)
        self.Layout()

    def _hide_reconnect_and_alert(self):
        # En debug, el botón siempre visible; fuera de debug, ocultar
        if self._is_debug_mode():
            self.reconnect_btn.Show()
        else:
            self.reconnect_btn.Hide()
        self._alert_label.SetLabel("")
        self._alert_blink_timer.Stop()
        self.Layout()

    def _on_alert_blink(self, event):
        # Parpadeo rojo
        self._alert_blink_state = not self._alert_blink_state
        if self._alert_blink_state:
            self._alert_label.SetForegroundColour("red")
        else:
            self._alert_label.SetForegroundColour("black")
        self._alert_label.Refresh()

    def _is_debug_mode(self):
        """
        Devuelve True si estamos en modo debug.
        Patrón correcto del proyecto:
        1. Intenta leer self.parent.debug_mode (LogAnalyzerFrame), que se activa por flag CLI o combinación secreta en GUI.
        2. Si no existe, consulta el estado global del message_bus (message_bus.is_debug_mode()).
        3. Nunca usar config_manager ni __main__ para debug.
        """
        debug_flag = False
        # 1. Intentar parent.debug_mode
        if hasattr(self.parent, 'debug_mode'):
            debug_flag = getattr(self.parent, 'debug_mode', False)
        else:
            # 2. Fallback: message_bus global
            from .message_bus import message_bus
            debug_flag = message_bus.is_debug_mode()
        return debug_flag

    def on_reconnect(self, event=None):
        """
        Handler para el botón de reconexión. Fuerza la reconexión del cliente realtime usando supabase_manager.get_async_client().
        Muestra mensajes de éxito o error usando message_bus.publish.
        """
        try:
            from .realtime_bridge import _realtime_bridge_instance
            if _realtime_bridge_instance:
                # Llamar al método de reconexión
                result = _realtime_bridge_instance.reconnect()
                if result:
                    message_bus.publish(
                        content="Reconnect requested from ConnectedUsersPanel: success",
                        level=MessageLevel.INFO,
                        metadata={"source": "connected_users_panel"}
                    )
                else:
                    message_bus.publish(
                        content="Reconnect requested from ConnectedUsersPanel: failed",
                        level=MessageLevel.ERROR,
                        metadata={"source": "connected_users_panel"}
                    )
            else:
                message_bus.publish(
                    content="RealtimeBridge singleton not available for reconnect",
                    level=MessageLevel.ERROR,
                    metadata={"source": "connected_users_panel"}
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error al reconectar: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "connected_users_panel"}
            )
    
    def on_reconnect_button(self, event=None):
        """
        Handler for the reconnect button or programmatic reconnect request.
        Calls the singleton RealtimeBridge's reconnect() method, which is sync-safe and handles all async logic internally.
        """
        from .realtime_bridge import _realtime_bridge_instance
        if _realtime_bridge_instance:
            result = _realtime_bridge_instance.reconnect()
            if result:
                message_bus.publish(
                    content="Reconnect requested from ConnectedUsersPanel: success",
                    level=MessageLevel.INFO,
                    metadata={"source": "connected_users_panel"}
                )
            else:
                message_bus.publish(
                    content="Reconnect requested from ConnectedUsersPanel: failed",
                    level=MessageLevel.ERROR,
                    metadata={"source": "connected_users_panel"}
                )
        else:
            message_bus.publish(
                content="RealtimeBridge singleton not available for reconnect",
                level=MessageLevel.ERROR,
                metadata={"source": "connected_users_panel"}
            )

    def _on_broadcast_ping_missing(self, *args, **kwargs):
        """
        Handler para evento de pings broadcast ausentes. Activa la alerta y el botón de reconexión solo si no estamos en debug.
        """
        if not self._is_debug_mode():
            self._show_reconnect_and_alert()
