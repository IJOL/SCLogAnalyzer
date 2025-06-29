#!/usr/bin/env python
import wx
from datetime import datetime
import re

from .message_bus import message_bus, MessageLevel
from .custom_listctrl import CustomListCtrl as UltimateListCtrlAdapter

class SharedLogsWidget(UltimateListCtrlAdapter):
    """Widget auto-contenido para logs compartidos con sistema de primera instancia controladora"""
    
    # Variables de clase compartidas
    _shared_log_entries = []
    _shared_max_logs = 500
    _controller_instance = None  # Instancia que controla el procesamiento
    _listener_instances = []     # Lista de instancias oyentes
    
    def __init__(self, parent, max_logs=500, style=wx.LC_REPORT | wx.BORDER_SUNKEN):
        super().__init__(parent, style=style)
        self.max_logs = max_logs
        
        # Determinar si esta instancia es la controladora
        if SharedLogsWidget._controller_instance is None:
            # Primera instancia - toma el control
            SharedLogsWidget._controller_instance = self
            self._init_as_controller()
        else:
            # Instancia siguiente - se registra como oyente
            self._init_as_listener()
        
        self._init_columns()
        self._populate_ui_from_shared_data()
    
    def _init_as_controller(self):
        """Inicializa como instancia controladora"""
        self.is_controller = True
        self._subscribe_to_events()
        
    def _init_as_listener(self):
        """Inicializa como instancia oyente"""
        self.is_controller = False
        SharedLogsWidget._listener_instances.append(self)
    
    def _init_columns(self):
        """Inicializa las columnas de la lista (EXACTAMENTE igual que ConnectedUsersPanel original)"""
        self.InsertColumn(0, "Hora", width=100)
        self.InsertColumn(1, "Hora local", width=120)
        self.InsertColumn(2, "Usuario", width=100)
        self.InsertColumn(3, "Tipo", width=100)
        self.InsertColumn(4, "Contenido", width=300)
        self.InsertColumn(5, "Shard", width=100)
        self.InsertColumn(6, "Modo", width=100)
        
        # Menú contexto
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_right_click)
    
    def _subscribe_to_events(self):
        """Solo la instancia controladora se suscribe a eventos externos"""
        if self.is_controller:
            message_bus.on("remote_realtime_event", self._on_remote_log_event)
    
    def _populate_ui_from_shared_data(self):
        """Popula la UI inicial desde los datos compartidos existentes"""
        for i, log_entry in enumerate(SharedLogsWidget._shared_log_entries):
            if i >= self.max_logs:  # Respetar límite individual de UI
                break
            self._add_log_entry_to_ui_only(log_entry, i)
    
    def _on_remote_log_event(self, username, log_data):
        """Solo la instancia controladora procesa eventos externos"""
        if self.is_controller:
            wx.CallAfter(self._process_remote_log, username, log_data)
    
    def _process_remote_log(self, username, log_data):
        """Procesa el log y notifica a todas las instancias"""
        # Crear entrada de log usando la lógica existente
        log_entry = self._create_log_entry(username, log_data)
        
        # Añadir a estructura compartida
        SharedLogsWidget._shared_log_entries.insert(0, log_entry)
        
        # Aplicar límite global
        if len(SharedLogsWidget._shared_log_entries) > SharedLogsWidget._shared_max_logs:
            SharedLogsWidget._shared_log_entries = SharedLogsWidget._shared_log_entries[:SharedLogsWidget._shared_max_logs]
        
        # Notificar a todas las instancias (incluyendo la controladora)
        self._notify_all_instances()
    
    def _create_log_entry(self, username, log_data):
        """Crea entrada de log usando la lógica existente"""
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
        
        return {
            'timestamp_str': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'hora_local_str': hora_local_str,
            'username': username,
            'log_type': log_type,
            'content': content,
            'shard': shard,
            'mode': mode
        }
    
    def _notify_all_instances(self):
        """Notifica a todas las instancias sobre cambios en los datos"""
        # Notificar a la instancia controladora
        if SharedLogsWidget._controller_instance:
            wx.CallAfter(SharedLogsWidget._controller_instance._update_ui_from_shared_data)
        
        # Notificar a todas las instancias oyentes (limpiar referencias muertas)
        alive_listeners = []
        for listener in SharedLogsWidget._listener_instances:
            try:
                # Verificar que la instancia aún existe y es válida
                if listener and hasattr(listener, '_update_ui_from_shared_data'):
                    wx.CallAfter(listener._update_ui_from_shared_data)
                    alive_listeners.append(listener)
            except (AttributeError, RuntimeError):
                # Instancia muerta, no la mantenemos
                pass
        
        # Actualizar lista con solo las instancias vivas
        SharedLogsWidget._listener_instances = alive_listeners
    
    def _update_ui_from_shared_data(self):
        """Actualiza UI desde los datos compartidos"""
        # Limpiar UI actual
        self.DeleteAllItems()
        
        # Repoblar desde datos compartidos (respetando límite individual)
        for i, log_entry in enumerate(SharedLogsWidget._shared_log_entries):
            if i >= self.max_logs:  # Respetar límite individual de UI
                break
            self._add_log_entry_to_ui_only(log_entry, i)
    
    def _add_log_entry_to_ui_only(self, log_entry, position):
        """Añade log entry solo a la UI (sin tocar datos compartidos)"""
        index = self.InsertItem(position, log_entry['timestamp_str'])
        self.SetItem(index, 1, str(log_entry.get('hora_local_str', 'Desconocido')))
        self.SetItem(index, 2, str(log_entry.get('username', 'Unknown')))
        self.SetItem(index, 3, str(log_entry.get('log_type', 'Unknown')))
        self.SetItem(index, 4, str(log_entry.get('content', '')))
        self.SetItem(index, 5, str(log_entry.get('shard', 'Unknown')))
        self.SetItem(index, 6, str(log_entry.get('mode', 'Unknown')))

    def _on_right_click(self, event):
        """Menú contexto dinámico completo (igual que ConnectedUsersPanel)"""
        from .realtime_bridge import RealtimeBridge
        
        menu = wx.Menu()
        bridge_instance = RealtimeBridge.get_instance()

        clicked_idx = event.GetIndex()
        if clicked_idx == -1:
            menu.Destroy()
            return

        # Obtener contenido del ítem clickeado (columna "Contenido" es la #4, índice 4)
        actual_content_to_filter = self.GetItemText(clicked_idx, 4)  # Columna "Contenido"
        clicked_content_display = (actual_content_to_filter[:50] + '...') if len(actual_content_to_filter) > 50 else actual_content_to_filter

        active_exclusions = []
        if bridge_instance:
            active_exclusions = bridge_instance.get_active_content_exclusions()
        else:
            # Error si bridge no disponible
            menu_error = wx.Menu()
            menu_error.Append(wx.ID_ANY, "Error: Servicio de filtros no disponible").Enable(False)
            self.PopupMenu(menu_error, event.GetPoint())
            menu_error.Destroy()
            menu.Destroy()
            return
        
        # Opción "Filtrar: [contenido]" - siempre presente
        filter_item = menu.Append(wx.ID_ANY, f"Filtrar: {clicked_content_display}")
        if actual_content_to_filter in active_exclusions:
            filter_item.Enable(False)
        else:
            self.Bind(wx.EVT_MENU, lambda evt, c=actual_content_to_filter: self._on_toggle_filter_state(c, add=True), filter_item)

        # Listar filtros activos para quitarlos
        if active_exclusions:
            if menu.GetMenuItemCount() > 0 and not menu.FindItemByPosition(menu.GetMenuItemCount()-1).IsSeparator():
                 menu.AppendSeparator()
            
            for ex_content in active_exclusions:
                ex_display = (ex_content[:50] + '...') if len(ex_content) > 50 else ex_content
                menu_item = menu.Append(wx.ID_ANY, f"Quitar filtro: {ex_display}")
                self.Bind(wx.EVT_MENU, lambda evt, c=ex_content: self._on_toggle_filter_state(c, add=False), menu_item)
        
        # Opción "Borrar todos" si hay filtros activos
        if active_exclusions: 
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
            self.Bind(wx.EVT_MENU, self._on_clear_all_content_filters, clear_all_item)

        # Separador y opción "Get Profile"
        if menu.GetMenuItemCount() > 0:
            menu.AppendSeparator()
        
        get_profile_item = menu.Append(wx.ID_ANY, "Get Profile")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_get_profile(evt, clicked_idx), get_profile_item)

        # Separador y opción "Limpiar lista"
        if menu.GetMenuItemCount() > 0:
            menu.AppendSeparator()
        
        clear_logs_item = menu.Append(wx.ID_ANY, "Limpiar lista")
        self.Bind(wx.EVT_MENU, self._on_clear_logs, clear_logs_item)

        if menu.GetMenuItemCount() > 0:
            client_point = event.GetPoint()
            self.PopupMenu(menu, client_point)

        menu.Destroy()
    
    def _on_clear_logs(self, event):
        """Limpia logs compartidos y notifica a todas las instancias"""
        SharedLogsWidget._shared_log_entries.clear()
        self._notify_all_instances()
    
    def _on_toggle_filter_state(self, content, add):
        """Maneja filtros de contenido a través de RealtimeBridge"""
        from .realtime_bridge import RealtimeBridge
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(content_to_exclude=content, add=add)

    def _on_clear_all_content_filters(self, event):
        """Limpia todos los filtros de contenido"""
        from .realtime_bridge import RealtimeBridge
        bridge_instance = RealtimeBridge.get_instance()
        if bridge_instance:
            bridge_instance.update_content_exclusions(clear_all=True)

    def _on_get_profile(self, event, idx):
        """Solicita perfil del jugador (implementación real de ConnectedUsersPanel)"""
        log_content = self.GetItemText(idx, 4)  # Columna "Contenido" (índice 4)
        log_sender = self.GetItemText(idx, 2)   # Columna "Usuario" (índice 2)

        # Implementación exacta del código real
        all_potential_players = re.findall(r'\b[A-Za-z0-9_-]{4,}\b', log_content)
        potential_players = [p for p in all_potential_players if p.lower() != 'stalled']
        
        target_player = next((p for p in potential_players if p.lower() != log_sender.lower()), None)

        if target_player:
            event_data = {
                'player_name': target_player,
                'action': 'get',
                'timestamp': datetime.now().isoformat(),
                'source': 'shared_logs_widget_context_menu'
            }
            message_bus.emit(
                "request_profile",
                event_data,
                "manual_request"
            )
        else:
            message_bus.publish(
                content="No other player name found in log content to request a profile.",
                level=MessageLevel.WARNING
            )

    def get_log_count(self):
        """Retorna el número de logs en la lista"""
        return len(SharedLogsWidget._shared_log_entries)
    
    def clear_logs(self):
        """Método público para limpiar logs compartidos"""
        SharedLogsWidget._shared_log_entries.clear()
        self._notify_all_instances()
    
    def __del__(self):
        """Cleanup al destruir instancia"""
        try:
            if hasattr(self, 'is_controller') and self.is_controller:
                # Si se destruye la controladora, resetear para que la próxima tome control
                SharedLogsWidget._controller_instance = None
            else:
                # Remover de la lista de oyentes
                if self in SharedLogsWidget._listener_instances:
                    SharedLogsWidget._listener_instances.remove(self)
        except (AttributeError, ValueError):
            pass  # Ignorar errores de cleanup durante destrucción