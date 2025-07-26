#!/usr/bin/env python
import wx
from datetime import datetime
import wx.lib.embeddedimage as embeddedimage
import re

from .message_bus import message_bus, MessageLevel
from .config_utils import get_config_manager
# Eliminar import incorrecto de get_async_client y usar el singleton supabase_manager
from .supabase_manager import supabase_manager
from .realtime_bridge import RealtimeBridge # Import RealtimeBridge class
from .custom_listctrl import CustomListCtrl as UltimateListCtrlAdapter
from .profile_cache_widget import ProfileCacheWidget
from .freezer_widget import FreezerWidget
from .ui_components import DarkThemeButton
from .org_members_widget import OrgMembersWidget

# --- 1. Add checkbox images for filtering ---
CHECKED_IMG = wx.ArtProvider.GetBitmap(wx.ART_TICK_MARK, wx.ART_OTHER, (16, 16))
UNCHECKED_IMG = wx.ArtProvider.GetBitmap(wx.ART_CROSS_MARK, wx.ART_OTHER, (16, 16))

class ConnectedUsersPanel(wx.Panel):
    """Panel para mostrar los usuarios conectados y sus logs compartidos"""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = get_config_manager()
        
        # Variables para almacenar los valores actuales (solo para UI)
        self.current_mode = "Unknown"
        self.current_shard = "Unknown"
        
        # Estado de los filtros de usuario (checkboxes)
        self.user_filter_states = {}  # username -> bool
        
        # Inicializar componentes de la UI
        self._init_ui()
        
        # Suscribirse a eventos relevantes del MessageBus
        message_bus.on("users_online_updated", self.update_users_list)
        message_bus.on("shard_version_update", self.on_shard_version_update)
        message_bus.on("broadcast_ping_missing", lambda *a, **k: wx.CallAfter(self._on_broadcast_ping_missing))
        
        # Lista de usuarios actualmente conectados
        self.users_online = []
        
    def _init_ui(self):
        """Inicializa los componentes de la interfaz de usuario"""
        # Layout horizontal: Connected Users (izq) + Profile Cache (der)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Usar splitter window para mejor control de redimensionamiento
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        self.splitter.SetSashGravity(1.0)  # 1.0 = la derecha se comprime primero
        self.splitter.SetMinimumPaneSize(300)  # Tamaño mínimo para ambos paneles
        
        # Panel izquierdo: Connected Users
        left_panel = wx.Panel(self.splitter)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Agregar título
        self.title = wx.StaticText(left_panel, label="Usuarios conectados")
        title_font = self.title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(title_font)
        left_sizer.Add(self.title, 0, wx.ALL, 5)
        
        # Área de usuarios conectados
        self.users_label = wx.StaticText(left_panel, label="Usuarios online:")
        left_sizer.Add(self.users_label, 0, wx.ALL, 5)
        
        # Restore users_list as UltimateListCtrlAdapter with checkbox images
        self.users_list = UltimateListCtrlAdapter(left_panel, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.users_list.InsertColumn(0, "Filtrar", width=60)
        self.users_list.InsertColumn(1, "Usuario", width=100)
        self.users_list.InsertColumn(2, "Shard", width=150)
        self.users_list.InsertColumn(3, "Versión", width=150)
        self.users_list.InsertColumn(4, "Estado", width=100)
        self.users_list.InsertColumn(5, "Modo", width=100)
        self.users_list.InsertColumn(6, "Última actividad", width=150)
        self.users_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_user_filter_toggle)
        left_sizer.Add(self.users_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Área de logs compartidos
        self.logs_label = wx.StaticText(left_panel, label="Logs compartidos:")
        left_sizer.Add(self.logs_label, 0, wx.ALL, 5)

        # Panel de filtros clásico: debajo de 'Logs compartidos', alineado y escalonado como antes
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Filtros de modo (columna izquierda) - obtener valores del RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        filter_mode_value = bridge.filter_by_current_mode if bridge else False
        include_unknown_mode_value = bridge.include_unknown_mode if bridge else True
        
        mode_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        mode_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mode_filter_checkbox = wx.CheckBox(left_panel, label="Filtrar por modo actual:")
        self.mode_filter_checkbox.SetValue(filter_mode_value)
        self.mode_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_mode_filter_changed)
        mode_row_sizer.Add(self.mode_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.mode_label = wx.StaticText(left_panel, label=f"({self.current_mode})")
        mode_row_sizer.Add(self.mode_label, 0, wx.ALIGN_CENTER_VERTICAL)
        mode_filter_sizer.Add(mode_row_sizer, 0, wx.BOTTOM, 2)
        mode_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.include_unknown_mode_checkbox = wx.CheckBox(left_panel, label="Incluir desconocidos")
        self.include_unknown_mode_checkbox.SetValue(include_unknown_mode_value)
        self.include_unknown_mode_checkbox.Bind(wx.EVT_CHECKBOX, self.on_include_unknown_mode_changed)
        mode_unknown_sizer.Add(self.include_unknown_mode_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        mode_filter_sizer.Add(mode_unknown_sizer, 0, 0)
        filter_sizer.Add(mode_filter_sizer, 0, wx.RIGHT, 15)

        # Filtros de shard (columna central) - obtener valores del RealtimeBridge
        filter_shard_value = bridge.filter_by_current_shard if bridge else False
        include_unknown_shard_value = bridge.include_unknown_shard if bridge else True
        
        shard_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        shard_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.shard_filter_checkbox = wx.CheckBox(left_panel, label="Filtrar por shard actual:")
        self.shard_filter_checkbox.SetValue(filter_shard_value)
        self.shard_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_shard_filter_changed)
        shard_row_sizer.Add(self.shard_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.shard_label = wx.StaticText(left_panel, label=f"({self.current_shard})")
        shard_row_sizer.Add(self.shard_label, 0, wx.ALIGN_CENTER_VERTICAL)
        shard_filter_sizer.Add(shard_row_sizer, 0, wx.BOTTOM, 2)
        shard_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.include_unknown_shard_checkbox = wx.CheckBox(left_panel, label="Incluir desconocidos")
        self.include_unknown_shard_checkbox.SetValue(include_unknown_shard_value)
        self.include_unknown_shard_checkbox.Bind(wx.EVT_CHECKBOX, self.on_include_unknown_shard_changed)
        shard_unknown_sizer.Add(self.include_unknown_shard_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        shard_filter_sizer.Add(shard_unknown_sizer, 0, 0)
        filter_sizer.Add(shard_filter_sizer, 0, 0)

        # Checkbox para filtrar mensajes 'stalled' solo si el jugador está online (columna derecha)
        bridge = RealtimeBridge.get_instance()
        stalled_filter_value = False
        if bridge:
            stalled_filter_value = getattr(bridge, 'filter_stalled_if_online', False)
        self.stalled_filter_checkbox = wx.CheckBox(left_panel, label="Ocultar mensajes 'stalled' si el jugador está online")
        self.stalled_filter_checkbox.SetValue(stalled_filter_value)
        self.stalled_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_stalled_filter_changed)
        filter_sizer.Add(self.stalled_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)

        left_sizer.Add(filter_sizer, 0, wx.ALL, 5)

        # Lista de logs compartidos usando SharedLogsWidget
        from .shared_logs_widget import SharedLogsWidget
        self.shared_logs = SharedLogsWidget(left_panel, max_logs=500)
        left_sizer.Add(self.shared_logs, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones de control
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = DarkThemeButton(left_panel, label="🔄 Refrescar")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self.on_refresh)
        button_sizer.Add(self.refresh_btn, 0, wx.ALL, 5)
        
        self.clear_logs_btn = DarkThemeButton(left_panel, label="🧹 Limpiar logs")
        self.clear_logs_btn.Bind(wx.EVT_BUTTON, self.on_clear_logs)
        button_sizer.Add(self.clear_logs_btn, 0, wx.ALL, 5)

        # Botón Reconectar (siempre visible en debug)
        self.reconnect_btn = DarkThemeButton(left_panel, label="🔌 Reconectar")
        self.reconnect_btn.Bind(wx.EVT_BUTTON, self.on_reconnect)
        # Mostrar siempre en debug al inicializar
        if self._is_debug_mode():
            self.reconnect_btn.Show()
        else:
            self.reconnect_btn.Hide()
        button_sizer.Add(self.reconnect_btn, 0, wx.ALL, 5)

        left_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

        # Estado de pings y temporizadores
        self._last_own_ping = datetime.utcnow()
        self._ping_timeout_sec = 30  # configurable
        self._ping_timer = wx.Timer(self)
        self._ping_timer.Start(5000)  # comprobar cada 5s
        self._alert_blink_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_alert_blink, self._alert_blink_timer)
        self._alert_blink_state = False
        self._alert_label = wx.StaticText(left_panel, label="")
        left_sizer.Add(self._alert_label, 0, wx.ALIGN_LEFT | wx.ALL, 2)
        
        # Layout del panel izquierdo
        left_panel.SetSizer(left_sizer)
        
        # Panel derecho: OrgMembersWidget + ProfileCache + Freezer
        right_panel = wx.Panel(self.splitter)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Crear un splitter vertical para los tres widgets
        right_splitter = wx.SplitterWindow(right_panel, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        right_splitter.SetSashGravity(0.4)  # 40% para org_members, 60% para el resto
        right_splitter.SetMinimumPaneSize(200)  # Tamaño mínimo para ambos paneles
        
        # Panel superior: OrgMembersWidget (solo columna de nombre)
        org_members_panel = wx.Panel(right_splitter)
        org_members_sizer = wx.BoxSizer(wx.VERTICAL)
        # Crear widget con solo la columna de nombre
        self.org_members_widget = OrgMembersWidget(org_members_panel)
        org_members_sizer.Add(self.org_members_widget, 1, wx.EXPAND | wx.ALL, 5)
        org_members_panel.SetSizer(org_members_sizer)
        
        # Panel inferior: Splitter horizontal para ProfileCache + Freezer
        bottom_panel = wx.Panel(right_splitter)
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Splitter horizontal para ProfileCache y Freezer
        bottom_splitter = wx.SplitterWindow(bottom_panel, style=wx.SP_LIVE_UPDATE | wx.SP_3D)
        bottom_splitter.SetSashGravity(0.7)  # 70% para cache, 30% para freezer
        bottom_splitter.SetMinimumPaneSize(150)  # Tamaño mínimo para ambos widgets
        
        # Panel superior: Profile Cache
        cache_panel = wx.Panel(bottom_splitter)
        cache_sizer = wx.BoxSizer(wx.VERTICAL)
        self.cache_widget = ProfileCacheWidget(cache_panel)
        cache_sizer.Add(self.cache_widget, 1, wx.EXPAND | wx.ALL, 5)
        cache_panel.SetSizer(cache_sizer)
        
        # Panel inferior: Freezer
        freezer_panel = wx.Panel(bottom_splitter)
        freezer_sizer = wx.BoxSizer(wx.VERTICAL)
        self.freezer_widget = FreezerWidget(freezer_panel)
        freezer_sizer.Add(self.freezer_widget, 1, wx.EXPAND | wx.ALL, 5)
        freezer_panel.SetSizer(freezer_sizer)
        
        # Configurar splitter horizontal inferior
        bottom_splitter.SplitHorizontally(cache_panel, freezer_panel)
        
        # Añadir splitter horizontal al panel inferior
        bottom_sizer.Add(bottom_splitter, 1, wx.EXPAND)
        bottom_panel.SetSizer(bottom_sizer)
        
        # Configurar splitter vertical principal
        right_splitter.SplitVertically(org_members_panel, bottom_panel)
        
        # Añadir el splitter al sizer principal
        right_sizer.Add(right_splitter, 1, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_sizer)
        
        # Configurar splitter con los dos paneles
        self.splitter.SplitVertically(left_panel, right_panel)
        
        # Configurar posición inicial: columna derecha con más espacio para OrgMembersWidget
        # Calcular posición para que la derecha tenga 400px (más espacio para el nuevo widget)
        self.splitter.SetSashPosition(-400)  # -400px desde la derecha = más espacio derecho
        
        # Añadir splitter al sizer principal
        main_sizer.Add(self.splitter, 1, wx.EXPAND | wx.ALL, 5)

        # Establecer el sizer principal
        self.SetSizer(main_sizer)
        
        # Aplicar tema dark
        self._apply_dark_theme()
        
    def _apply_dark_theme(self):
        """Aplicar tema dark usando los mismos colores que el adapter"""
        # Colores del tema dark (mismos que el adapter)
        dark_row_bg = wx.Colour(80, 80, 80)        # Fondo panel
        dark_row_fg = wx.Colour(230, 230, 230)     # Texto blanco
        
        # Panel principal
        self.SetBackgroundColour(dark_row_bg)
        
        # Todos los wx.StaticText
        self.title.SetForegroundColour(dark_row_fg)
        self.users_label.SetForegroundColour(dark_row_fg)
        self.logs_label.SetForegroundColour(dark_row_fg)
        self.mode_label.SetForegroundColour(dark_row_fg)
        self.shard_label.SetForegroundColour(dark_row_fg)
        self._alert_label.SetForegroundColour(dark_row_fg)
        
        # Todos los wx.CheckBox
        self.mode_filter_checkbox.SetForegroundColour(dark_row_fg)
        self.include_unknown_mode_checkbox.SetForegroundColour(dark_row_fg)
        self.shard_filter_checkbox.SetForegroundColour(dark_row_fg)
        self.include_unknown_shard_checkbox.SetForegroundColour(dark_row_fg)
        self.stalled_filter_checkbox.SetForegroundColour(dark_row_fg)
        
        # Los botones DarkThemeButton ya tienen colores configurados automáticamente

    def _update_ui_users_list(self):
        """Actualiza la UI con la lista de usuarios conectados"""
        self.users_list.DeleteAllItems()
        for i, user in enumerate(self.users_online):
            username = user.get('username', 'Unknown')
            shard = user.get('shard', 'Unknown')
            version = user.get('version', 'Unknown')
            status = user.get('status', 'Unknown')
            mode = user.get('mode', 'Unknown') or 'Unknown'  # fallback seguro
            last_active = user.get('last_active', 'Unknown')
            
            # Convertir timestamp ISO a formato más legible
            try:
                dt = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
                last_active_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                last_active_str = last_active
            
            # Checkbox state
            checked = self.user_filter_states.get(username, False)
            img_idx = 0 if checked else 1
            if i == 0:
                self.img_list = wx.ImageList(16, 16)
                self.img_list.Add(CHECKED_IMG)
                self.img_list.Add(UNCHECKED_IMG)
                self.users_list.AssignImageList(self.img_list, wx.IMAGE_LIST_SMALL)
            index = self.users_list.InsertItem(i, "", img_idx)
            self.users_list.SetItem(index, 1, username)
            self.users_list.SetItem(index, 2, str(shard))
            self.users_list.SetItem(index, 3, str(version))
            self.users_list.SetItem(index, 4, str(status))
            self.users_list.SetItem(index, 5, str(mode))
            self.users_list.SetItem(index, 6, str(last_active_str))
        self.users_list.Refresh()

    def on_user_filter_toggle(self, event):
        # Toggle checkbox state for the clicked user
        index = event.GetIndex()
        username = self.users_list.GetItemText(index, 1)
        current = self.user_filter_states.get(username, False)
        self.user_filter_states[username] = not current
        self._update_ui_users_list()
        self._update_backend_user_filter()

    def update_users_list(self, users_online):
        """
        Actualiza la lista de usuarios conectados. El control de pings ya no depende de presencia ni de broadcast_ping_received.
        """
        self.users_online = users_online
        wx.CallAfter(self._update_ui_users_list)

    def on_shard_version_update(self, shard, version, username, mode=None, private=None):
        """
        Maneja las actualizaciones de shard y versión, ahora con info de lobby privado (argumento extra).
        """
        self.current_shard = shard if shard else "Unknown"
        self.current_mode = mode if mode is not None else self.current_mode
        # Actualizar username si es válido
        if username and username != "Unknown":
            self._my_username = username
        # Actualizar etiquetas y filtros globales
        wx.CallAfter(self._update_filter_labels)
        wx.CallAfter(self._update_global_filters)
    
    def on_mode_filter_changed(self, event):
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            bridge.update_mode_shard_filters(filter_by_current_mode=self.mode_filter_checkbox.GetValue())
        self._update_filter_labels()
        
    def on_include_unknown_mode_changed(self, event):
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            bridge.update_mode_shard_filters(include_unknown_mode=self.include_unknown_mode_checkbox.GetValue())
        self._update_filter_labels()
        
    def on_shard_filter_changed(self, event):
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            bridge.update_mode_shard_filters(filter_by_current_shard=self.shard_filter_checkbox.GetValue())
        self._update_filter_labels()
        
    def on_include_unknown_shard_changed(self, event):
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            bridge.update_mode_shard_filters(include_unknown_shard=self.include_unknown_shard_checkbox.GetValue())
        self._update_filter_labels()
        
    def _update_filter_labels(self):
        """Actualiza las etiquetas de los filtros con los valores actuales"""
        self.mode_label.SetLabel(f"({self.current_mode})")
        self.shard_label.SetLabel(f"({self.current_shard})")
        self.Layout()  # Forzar actualización del layout
    
    def _update_global_filters(self):
        """Actualiza los filtros globales en RealtimeBridge"""
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            bridge.update_mode_shard_filters(
                current_mode=self.current_mode,
                current_shard=self.current_shard
            )
        

    

        
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
        self.shared_logs.clear_logs()  # Usar método del widget
        # Mantener solo la lógica específica de ConnectedUsersPanel
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(clear_all=True)





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
        A partir de la refactorización, message_bus es la única fuente de verdad global.
        """
        return message_bus.is_debug_mode()

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
    
    def _on_broadcast_ping_missing(self, *args, **kwargs):
        """
        Handler para evento de pings broadcast ausentes. Activa la alerta y el botón de reconexión solo si no estamos en debug.
        """
        if not self._is_debug_mode():
            self._show_reconnect_and_alert()
    
    def on_stalled_filter_changed(self, event):
        """Handler para el checkbox de filtro 'stalled': actualiza el backend (RealtimeBridge)"""
        from .realtime_bridge import _realtime_bridge_instance
        if _realtime_bridge_instance:
            _realtime_bridge_instance.filter_stalled_if_online = self.stalled_filter_checkbox.GetValue()
            message_bus.publish(
                content=f"Filtro 'stalled' actualizado en backend: {self.stalled_filter_checkbox.GetValue()}",
                level=MessageLevel.DEBUG,
                metadata={"source": "connected_users_panel", "filter": "stalled_online"}
            )

    def _update_backend_user_filter(self):
        """Update backend with the list of checked users in the filter column."""
        selected = [u for u, checked in self.user_filter_states.items() if checked]
        from .realtime_bridge import _realtime_bridge_instance
        if _realtime_bridge_instance:
            _realtime_bridge_instance.filter_broadcast_usernames = set(selected)
            message_bus.publish(
                content=f"Filtro de usuarios online actualizado: {selected}",
                level=MessageLevel.DEBUG,
                metadata={"source": "connected_users_panel", "filter": "user_online"}
            )
    

        
        # Cleanup existing components
        if hasattr(self, 'cache_widget'):
            self.cache_widget.cleanup()
        if hasattr(self, 'freezer_widget'):
            self.freezer_widget.cleanup()
        
        # Remove message bus subscriptions
        message_bus.off("users_online_updated", self.update_users_list)
        message_bus.off("shard_version_update", self.on_shard_version_update)
        message_bus.off("broadcast_ping_missing", lambda *a, **k: wx.CallAfter(self._on_broadcast_ping_missing))
    