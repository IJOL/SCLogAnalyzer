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
from .ultimate_listctrl_adapter import UltimateListCtrlAdapter

# --- 1. Add checkbox images for filtering ---
CHECKED_IMG = wx.ArtProvider.GetBitmap(wx.ART_TICK_MARK, wx.ART_OTHER, (16, 16))
UNCHECKED_IMG = wx.ArtProvider.GetBitmap(wx.ART_CROSS_MARK, wx.ART_OTHER, (16, 16))

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
        
        # Estado de los filtros de usuario (checkboxes)
        self.user_filter_states = {}  # username -> bool
        
        # Inicializar componentes de la UI
        self._init_ui()
        
        # Suscribirse a eventos relevantes del MessageBus
        message_bus.on("users_online_updated", self.update_users_list)
        message_bus.on("remote_realtime_event", self.add_remote_log)
        message_bus.on("shard_version_update", self.on_shard_version_update)
        message_bus.on("broadcast_ping_missing", lambda *a, **k: wx.CallAfter(self._on_broadcast_ping_missing))
        
        # Lista de usuarios actualmente conectados
        self.users_online = []
        
    def _init_ui(self):
        """Inicializa los componentes de la interfaz de usuario"""
        # Crear layout principal
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Agregar título
        self.title = wx.StaticText(self, label="Usuarios conectados")
        title_font = self.title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title.SetFont(title_font)
        main_sizer.Add(self.title, 0, wx.ALL, 5)
        
        # Área de usuarios conectados
        self.users_label = wx.StaticText(self, label="Usuarios online:")
        main_sizer.Add(self.users_label, 0, wx.ALL, 5)
        
        # Restore users_list as UltimateListCtrlAdapter with checkbox images
        self.users_list = UltimateListCtrlAdapter(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.users_list.InsertColumn(0, "Filtrar", width=60)
        self.users_list.InsertColumn(1, "Usuario", width=100)
        self.users_list.InsertColumn(2, "Shard", width=150)
        self.users_list.InsertColumn(3, "Versión", width=150)
        self.users_list.InsertColumn(4, "Estado", width=100)
        self.users_list.InsertColumn(5, "Modo", width=100)
        self.users_list.InsertColumn(6, "Última actividad", width=150)
        self.users_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.on_user_filter_toggle)
        main_sizer.Add(self.users_list, 1, wx.EXPAND | wx.ALL, 5)
        
        # Área de logs compartidos
        self.logs_label = wx.StaticText(self, label="Logs compartidos:")
        main_sizer.Add(self.logs_label, 0, wx.ALL, 5)

        # Panel de filtros clásico: debajo de 'Logs compartidos', alineado y escalonado como antes
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Filtros de modo (columna izquierda)
        mode_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        mode_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.mode_filter_checkbox = wx.CheckBox(self, label="Filtrar por modo actual:")
        self.mode_filter_checkbox.SetValue(self.filter_by_current_mode)
        self.mode_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_mode_filter_changed)
        mode_row_sizer.Add(self.mode_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.mode_label = wx.StaticText(self, label=f"({self.current_mode})")
        mode_row_sizer.Add(self.mode_label, 0, wx.ALIGN_CENTER_VERTICAL)
        mode_filter_sizer.Add(mode_row_sizer, 0, wx.BOTTOM, 2)
        mode_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.include_unknown_mode_checkbox = wx.CheckBox(self, label="Incluir desconocidos")
        self.include_unknown_mode_checkbox.SetValue(self.include_unknown_mode)
        self.include_unknown_mode_checkbox.Bind(wx.EVT_CHECKBOX, self.on_include_unknown_mode_changed)
        mode_unknown_sizer.Add(self.include_unknown_mode_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        mode_filter_sizer.Add(mode_unknown_sizer, 0, 0)
        filter_sizer.Add(mode_filter_sizer, 0, wx.RIGHT, 15)

        # Filtros de shard (columna central)
        shard_filter_sizer = wx.BoxSizer(wx.VERTICAL)
        shard_row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.shard_filter_checkbox = wx.CheckBox(self, label="Filtrar por shard actual:")
        self.shard_filter_checkbox.SetValue(self.filter_by_current_shard)
        self.shard_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_shard_filter_changed)
        shard_row_sizer.Add(self.shard_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.shard_label = wx.StaticText(self, label=f"({self.current_shard})")
        shard_row_sizer.Add(self.shard_label, 0, wx.ALIGN_CENTER_VERTICAL)
        shard_filter_sizer.Add(shard_row_sizer, 0, wx.BOTTOM, 2)
        shard_unknown_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.include_unknown_shard_checkbox = wx.CheckBox(self, label="Incluir desconocidos")
        self.include_unknown_shard_checkbox.SetValue(self.include_unknown_shard)
        self.include_unknown_shard_checkbox.Bind(wx.EVT_CHECKBOX, self.on_include_unknown_shard_changed)
        shard_unknown_sizer.Add(self.include_unknown_shard_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        shard_filter_sizer.Add(shard_unknown_sizer, 0, 0)
        filter_sizer.Add(shard_filter_sizer, 0, 0)

        # Checkbox para filtrar mensajes 'stalled' solo si el jugador está online (columna derecha)
        bridge = RealtimeBridge.get_instance()
        stalled_filter_value = False
        if bridge:
            stalled_filter_value = getattr(bridge, 'filter_stalled_if_online', False)
        self.stalled_filter_checkbox = wx.CheckBox(self, label="Ocultar mensajes 'stalled' si el jugador está online")
        self.stalled_filter_checkbox.SetValue(stalled_filter_value)
        self.stalled_filter_checkbox.Bind(wx.EVT_CHECKBOX, self.on_stalled_filter_changed)
        filter_sizer.Add(self.stalled_filter_checkbox, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)

        main_sizer.Add(filter_sizer, 0, wx.ALL, 5)

        # Lista de logs compartidos
        self.shared_logs = UltimateListCtrlAdapter(self, style=wx.LC_REPORT | wx.BORDER_SUNKEN)
        self.shared_logs.InsertColumn(0, "Hora", width=100)
        self.shared_logs.InsertColumn(1, "Hora local", width=120)
        self.shared_logs.InsertColumn(2, "Usuario", width=100)
        self.shared_logs.InsertColumn(3, "Tipo", width=100)
        self.shared_logs.InsertColumn(4, "Contenido", width=300)
        self.shared_logs.InsertColumn(5, "Shard", width=100)
        self.shared_logs.InsertColumn(6, "Modo", width=100)
        self.shared_logs.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_log_item_right_click) # Bind right click
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
        
        # Aplicar tema dark
        self._apply_dark_theme()
        
    def _apply_dark_theme(self):
        """Aplicar tema dark usando los mismos colores que el adapter"""
        # Colores del tema dark (mismos que el adapter)
        dark_row_bg = wx.Colour(80, 80, 80)        # Fondo panel
        dark_row_fg = wx.Colour(230, 230, 230)     # Texto blanco
        dark_header_bg = wx.Colour(64, 64, 64)     # Fondo botones
        dark_header_fg = wx.Colour(240, 240, 240)  # Texto botones
        
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
        
        # Todos los wx.Button
        self.refresh_btn.SetBackgroundColour(dark_header_bg)
        self.refresh_btn.SetForegroundColour(dark_header_fg)
        self.clear_logs_btn.SetBackgroundColour(dark_header_bg)
        self.clear_logs_btn.SetForegroundColour(dark_header_fg)
        self.reconnect_btn.SetBackgroundColour(dark_header_bg)
        self.reconnect_btn.SetForegroundColour(dark_header_fg)
        
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
        # Actualizar etiquetas
        wx.CallAfter(self._update_filter_labels)
    
    def on_mode_filter_changed(self, event):
        self.filter_by_current_mode = self.mode_filter_checkbox.GetValue()
        self._update_filter_labels()
        
    def on_include_unknown_mode_changed(self, event):
        self.include_unknown_mode = self.include_unknown_mode_checkbox.GetValue()
        self._update_filter_labels()
        
    def on_shard_filter_changed(self, event):
        self.filter_by_current_shard = self.shard_filter_checkbox.GetValue()
        self._update_filter_labels()
        
    def on_include_unknown_shard_changed(self, event):
        self.include_unknown_shard = self.include_unknown_shard_checkbox.GetValue()
        self._update_filter_labels()
        
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
        timestamp = datetime.now()
        if 'metadata' in log_data:
            content = log_data['metadata'].get('content', '')
            shard = log_data['metadata'].get('shard', 'Unknown')
            log_type = log_data['metadata'].get('type', 'Unknown')
        else:
            content = log_data.get('content', '')
            log_type = log_data.get('type', 'Unknown')
            shard = raw_data.get('shard', 'Unknown')
        
        # Extraer modo del raw_data si está disponible
        mode = raw_data.get('mode', 'Unknown')
        
        # Extraer hora local del campo datetime del payload si está disponible
        hora_local = raw_data.get('datetime', 'Desconocido')
        hora_local_str = str(hora_local) if hora_local else 'Desconocido'
        # Crear entrada de log temporal (sin almacenarla)
        log_entry = {
            'timestamp_str': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'hora_local_str': hora_local_str,
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
        index = self.shared_logs.InsertItem(position, log_entry['timestamp_str'])
        self.shared_logs.SetItem(index, 1, str(log_entry['hora_local_str'] or 'Desconocido'))
        self.shared_logs.SetItem(index, 2, str(log_entry['username'] or 'Unknown'))
        self.shared_logs.SetItem(index, 3, str(log_entry['log_type'] or 'Unknown'))
        self.shared_logs.SetItem(index, 4, str(log_entry['content'] or ''))
        self.shared_logs.SetItem(index, 5, str(log_entry['shard'] or 'Unknown'))
        self.shared_logs.SetItem(index, 6, str(log_entry['mode'] or 'Unknown'))

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
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(clear_all=True)

    def on_get_profile(self, event, idx):
        log_content = self.shared_logs.GetItemText(idx, 4)
        log_sender = self.shared_logs.GetItemText(idx, 2)

        # Se corrige el error re.PatternError simplificando la lógica.
        # Primero, se encuentran todos los nombres potenciales.
        all_potential_players = re.findall(r'\b[A-Za-z0-9_-]{4,}\b', log_content)
        # Luego, se excluye 'stalled' de la lista.
        potential_players = [p for p in all_potential_players if p.lower() != 'stalled']
        
        target_player = next((p for p in potential_players if p.lower() != log_sender.lower()), None)

        if target_player:
            event_data = {
                'player_name': target_player,
                'action': 'get',
                'timestamp': datetime.now().isoformat(),
                'source': 'connected_users_panel_context_menu'
            }
            message_bus.emit(
                "request_profile",
                event_data,
                "manual_request"
            )
        else:
            # Usar el sistema de logs para mostrar una advertencia
            message_bus.publish(
                content="No other player name found in log content to request a profile.",
                level=MessageLevel.WARNING
            )

    def on_log_item_right_click(self, event):
        menu = wx.Menu()
        bridge_instance = RealtimeBridge.get_instance()

        clicked_idx = event.GetIndex()
        if clicked_idx == -1:
            # Click was not on an item
            menu.Destroy()
            return

        # Get the actual content from the 'Contenido' column (index 4)
        actual_content_to_filter = self.shared_logs.GetItemText(clicked_idx, 4)
        # Display a shortened version in the menu
        clicked_content_display = (actual_content_to_filter[:50] + '...') if len(actual_content_to_filter) > 50 else actual_content_to_filter

        active_exclusions = []
        if bridge_instance:
            active_exclusions = bridge_instance.get_active_content_exclusions()
        else:
            # Si el bridge no está disponible, mostrar un menú simple con error y salir.
            menu_error = wx.Menu()
            menu_error.Append(wx.ID_ANY, "Error: Servicio de filtros no disponible").Enable(False)
            self.shared_logs.PopupMenu(menu_error, event.GetPoint())
            menu_error.Destroy()
            menu.Destroy() # Destruir el menú principal también
            return
        
        # Opción "Filtrar: [contenido del ítem clickeado]" - siempre presente
        filter_item = menu.Append(wx.ID_ANY, f"Filtrar: {clicked_content_display}")
        if actual_content_to_filter in active_exclusions:
            filter_item.Enable(False)
        else:
            self.Bind(wx.EVT_MENU, lambda evt, c=actual_content_to_filter: self.on_toggle_filter_state(c, add=True), filter_item)

        # Listar TODOS los filtros activos para permitir quitarlos (incluye el del ítem clickeado si está filtrado)
        if active_exclusions:
            # Añadir separador si la opción "Filtrar" (del ítem clickeado) ya se añadió Y hay filtros activos para listar.
            if menu.GetMenuItemCount() > 0 and not menu.FindItemByPosition(menu.GetMenuItemCount()-1).IsSeparator():
                 menu.AppendSeparator() # Separador ANTES de la lista de "Quitar filtro"
            
            for ex_content in active_exclusions:
                ex_display = (ex_content[:50] + '...') if len(ex_content) > 50 else ex_content
                menu_item = menu.Append(wx.ID_ANY, f"Quitar filtro: {ex_display}")
                self.Bind(wx.EVT_MENU, lambda evt, c=ex_content: self.on_toggle_filter_state(c, add=False), menu_item)
        
        # Añadir "Borrar todos" si hay CUALQUIER filtro activo
        if active_exclusions: 
            # Añadir separador ANTES de "Borrar todos" solo si el último ítem añadido NO es ya un separador.
            if menu.GetMenuItemCount() > 0:
                last_item_is_separator = False
                try:
                    if menu.FindItemByPosition(menu.GetMenuItemCount() - 1).IsSeparator():
                        last_item_is_separator = True
                except wx.WXAssertionError: 
                    pass 
                
                if not last_item_is_separator:
                     menu.AppendSeparator()
 
            clear_all_item = menu.Append(wx.ID_ANY, "Borrar todos")
            self.Bind(wx.EVT_MENU, self.on_clear_all_content_filters, clear_all_item)

        # --- Separador y nueva opción Get Profile ---
        if menu.GetMenuItemCount() > 0:
            menu.AppendSeparator()
        
        get_profile_item = menu.Append(wx.ID_ANY, "Get Profile")
        self.Bind(wx.EVT_MENU, lambda evt: self.on_get_profile(evt, clicked_idx), get_profile_item)

        if menu.GetMenuItemCount() > 0:
            client_point = event.GetPoint() # Coordinates relative to self.shared_logs
            self.shared_logs.PopupMenu(menu, client_point) # Use self.shared_logs and client_point

        menu.Destroy()

    def on_toggle_filter_state(self, content, add):
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(content_to_exclude=content, add=add)
        # else:
            # YA NO SE PUBLICA AL MESSAGE_BUS DESDE AQUÍ SI EL BRIDGE NO ESTÁ

    def on_clear_all_content_filters(self, event):
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(clear_all=True)
        # else:
            # YA NO SE PUBLICA AL MESSAGE_BUS DESDE AQUÍ SI EL BRIDGE NO ESTÁ

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
