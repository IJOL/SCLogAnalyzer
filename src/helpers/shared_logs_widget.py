#!/usr/bin/env python
import wx
from datetime import datetime
import re

from .message_bus import message_bus, MessageLevel
from .ultimate_listctrl_adapter import UltimateListCtrlAdapter

class SharedLogsWidget(UltimateListCtrlAdapter):
    """Widget auto-contenido para logs compartidos que se suscribe a eventos directamente"""
    
    def __init__(self, parent, max_logs=500, style=wx.LC_REPORT | wx.BORDER_SUNKEN):
        super().__init__(parent, style=style)
        self.max_logs = max_logs
        self.log_entries = []  # Lista interna de logs
        
        self._init_columns()
        self._subscribe_to_events()
    
    def _init_columns(self):
        """Inicializa las columnas de la lista"""
        self.InsertColumn(0, "Hora", width=80)
        self.InsertColumn(1, "Usuario", width=100)
        self.InsertColumn(2, "Contenido", width=250)
        self.InsertColumn(3, "Shard", width=80)
        self.InsertColumn(4, "Modo", width=80)
        
        # Menú contexto
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_right_click)
    
    def _subscribe_to_events(self):
        """Se suscribe directamente a eventos del message_bus"""
        message_bus.on("remote_realtime_event", self._on_remote_log_event)
    
    def _on_remote_log_event(self, username, log_data):
        """Maneja eventos de logs remotos directamente (igual que ConnectedUsersPanel)"""
        wx.CallAfter(self._add_ui_remote_log, username, log_data)
        
    def _add_ui_remote_log(self, username, log_data):
        """Actualiza la UI con un nuevo log remoto (copiado de ConnectedUsersPanel)"""
        # Obtener datos del log (EXACTAMENTE igual que ConnectedUsersPanel)
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
        
        # Los filtros se aplican globalmente ahora, así que todos los eventos que llegan ya pasaron filtros
        self._add_log_entry_to_ui(log_entry, 0)  # Insertar al principio
    
    def _add_log_entry_to_ui(self, log_entry, position):
        """Añade un log entry a la UI (copiado de ConnectedUsersPanel)"""
        index = self.InsertItem(position, log_entry['timestamp_str'])
        self.SetItem(index, 1, str(log_entry.get('username', 'Unknown')))
        self.SetItem(index, 2, str(log_entry.get('content', '')))
        self.SetItem(index, 3, str(log_entry.get('shard', 'Unknown')))
        self.SetItem(index, 4, str(log_entry.get('mode', 'Unknown')))
        
        # Añadir a lista interna
        self.log_entries.insert(0, log_entry)
        
        # Mantener límite de logs
        if len(self.log_entries) > self.max_logs:
            self.log_entries = self.log_entries[:self.max_logs]
        
        # Mantener límite en UI también
        if self.GetItemCount() > self.max_logs:
            self.DeleteItem(self.max_logs)
    
    def _on_right_click(self, event):
        """Menú contexto dinámico completo (igual que ConnectedUsersPanel)"""
        from .realtime_bridge import RealtimeBridge
        
        menu = wx.Menu()
        bridge_instance = RealtimeBridge.get_instance()

        clicked_idx = event.GetIndex()
        if clicked_idx == -1:
            menu.Destroy()
            return

        # Obtener contenido del ítem clickeado (columna "Contenido" es la #2, índice 2)
        actual_content_to_filter = self.GetItemText(clicked_idx, 2)  # Columna "Contenido"
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
        """Limpia la lista de logs"""
        self.DeleteAllItems()
        self.log_entries.clear()
    
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
        log_content = self.GetItemText(idx, 2)  # Columna "Contenido"
        log_sender = self.GetItemText(idx, 1)   # Columna "Usuario"

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
        return len(self.log_entries)
    
    def clear_logs(self):
        """Método público para limpiar logs"""
        self._on_clear_logs(None) 