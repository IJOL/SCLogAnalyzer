"""
Widget visual para gestionar el cache de perfiles
"""

import wx
from datetime import datetime
from typing import Dict, Any

from .profile_cache import ProfileCache
from .message_bus import message_bus, MessageLevel
from .custom_listctrl import CustomListCtrl
from .ui_components import DarkThemeButton


class ProfileCacheWidget(wx.Panel):
    """Widget para mostrar y gestionar el cache de perfiles"""
    
    def __init__(self, parent):
        super().__init__(parent)
        self.cache = ProfileCache.get_instance()
        self._setup_ui()
        self._refresh_cache_display()
        
        # Escuchar eventos de profile_cached en lugar de usar timer
        message_bus.on("profile_cached", self._on_profile_cached)
    
    def _setup_ui(self):
        """Configura la interfaz del widget"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header con título y estadísticas
        header_panel = wx.Panel(self)
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.title_label = wx.StaticText(header_panel, label="Profile Cache")
        title_font = self.title_label.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.title_label.SetFont(title_font)
        
        self.stats_label = wx.StaticText(header_panel, label="0/1000 (0%)")
        
        header_sizer.Add(self.title_label, 0, wx.ALIGN_CENTER_VERTICAL)
        header_sizer.AddStretchSpacer()
        header_sizer.Add(self.stats_label, 0, wx.ALIGN_CENTER_VERTICAL)
        header_panel.SetSizer(header_sizer)
        
        # ListCtrl para mostrar perfiles con colores oscuros
        self.cache_listctrl = CustomListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.cache_listctrl.InsertColumn(0, "Jugador", width=150)
        self.cache_listctrl.InsertColumn(1, "Organización", width=100)
        self.cache_listctrl.InsertColumn(2, "Acción", width=80)
        self.cache_listctrl.InsertColumn(3, "Hora", width=60)
        self.cache_listctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_profile_double_click)
        self.cache_listctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_right_click)
        
        # Botones de control
        button_panel = wx.Panel(self)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = DarkThemeButton(button_panel, label="🔄 Refresh")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        
        self.clear_btn = DarkThemeButton(button_panel, label="🗑️ Clear All")
        self.clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_cache)
        
        self.broadcast_btn = DarkThemeButton(button_panel, label="📡 Broadcast All")
        self.broadcast_btn.Bind(wx.EVT_BUTTON, self._on_broadcast_all)
        
        button_sizer.Add(self.refresh_btn, 0, wx.RIGHT, 5)
        button_sizer.Add(self.clear_btn, 0, wx.RIGHT, 5)
        button_sizer.Add(self.broadcast_btn, 0)
        
        button_panel.SetSizer(button_sizer)
        
        # Layout principal
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(self.cache_listctrl, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(button_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
        
        # Aplicar tema oscuro
        self._apply_dark_theme()
    
    def _apply_dark_theme(self):
        """Aplicar tema oscuro al widget"""
        # Colores del tema dark
        dark_bg = wx.Colour(80, 80, 80)        # Fondo panel
        dark_fg = wx.Colour(230, 230, 230)     # Texto blanco
        
        # Panel principal
        self.SetBackgroundColour(dark_bg)
        
        # Labels
        if hasattr(self, 'title_label'):
            self.title_label.SetForegroundColour(dark_fg)
        if hasattr(self, 'stats_label'):
            self.stats_label.SetForegroundColour(dark_fg)
        
        # Los botones DarkThemeButton ya tienen colores configurados automáticamente
    
    def _refresh_cache_display(self):
        """Actualiza la visualización del cache"""
        try:
            stats = self.cache.get_cache_stats()
            profiles = self.cache.get_all_profiles()
            
            # Actualizar estadísticas
            self.stats_label.SetLabel(
                f"{stats['total_profiles']}/{stats['max_size']} ({stats['usage_percent']:.1f}%)"
            )
            
            # Actualizar lista
            self.cache_listctrl.DeleteAllItems()
            
            for player_name, profile_data in profiles.items():
                data = profile_data.get('profile_data', {})
                org = profile_data.get('organization', 'Unknown')
                action = data.get('action', 'unknown')
                cached_at = profile_data.get('cached_at', datetime.now())
                time_str = cached_at.strftime("%H:%M")
                
                # Insertar fila con datos en columnas separadas
                index = self.cache_listctrl.InsertItem(self.cache_listctrl.GetItemCount(), player_name)
                self.cache_listctrl.SetItem(index, 1, org)
                self.cache_listctrl.SetItem(index, 2, action)
                self.cache_listctrl.SetItem(index, 3, time_str)
                self.cache_listctrl.SetItemData(index, hash(player_name))
                
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing cache display: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "profile_cache_widget"}
            )
    
    def _on_profile_cached(self, player_name, profile_data):
        """Handler para eventos de profile_cached - actualiza la vista cuando se cachea un perfil"""
        wx.CallAfter(self._refresh_cache_display)
    
    def _on_refresh(self, event):
        """Handler para botón refresh"""
        self._refresh_cache_display()
    
    def _on_clear_cache(self, event):
        """Handler para limpiar todo el cache"""
        dlg = wx.MessageDialog(
            self,
            "¿Estás seguro de que quieres limpiar todo el cache?",
            "Confirmar limpieza",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            self.cache.clear_cache()
            self._refresh_cache_display()
            
        dlg.Destroy()
    
    def _on_broadcast_all(self, event):
        """Handler para botón broadcast all"""
        self.cache.broadcast_all()
        self._refresh_cache_display()
    
    def _on_profile_double_click(self, event):
        """Handler para doble clic en perfil"""
        selection = event.GetIndex()
        if selection != -1:
            player_name = self.cache_listctrl.GetItemText(selection, 0)
            self._show_profile_details(player_name)
    
    def _on_right_click(self, event):
        """Menu contextual para perfiles"""
        selection = event.GetIndex()
        if selection != -1:
            player_name = self.cache_listctrl.GetItemText(selection, 0)
            
            # Obtener datos del perfil
            profiles = self.cache.get_all_profiles()
            profile_data = profiles.get(player_name, {})
            organization = profile_data.get('organization', 'Unknown')
            has_organization = organization and organization != 'Unknown'
            
            menu = wx.Menu()
            details_item = menu.Append(wx.ID_ANY, "🔍 Ver detalles")
            
            # Opción de búsqueda de organización (solo si tiene org)
            if has_organization:
                search_org_item = menu.Append(wx.ID_ANY, f"🏢 Buscar org: {organization}")
                self.Bind(wx.EVT_MENU, lambda e: self._search_organization(player_name, organization), search_org_item)
            
            broadcast_item = menu.Append(wx.ID_ANY, "📡 Broadcast profile")
            discord_item = menu.Append(wx.ID_ANY, "🔊 Enviar a Discord")
            remove_item = menu.Append(wx.ID_ANY, "🗑️ Eliminar del cache")
            
            # Separador y opciones VIP
            self._extend_context_menu_with_vip(menu, player_name)
            
            self.Bind(wx.EVT_MENU, lambda e: self._show_profile_details(player_name), details_item)
            self.Bind(wx.EVT_MENU, lambda e: self._broadcast_profile(player_name), broadcast_item)
            self.Bind(wx.EVT_MENU, lambda e: self._send_discord(player_name), discord_item)
            self.Bind(wx.EVT_MENU, lambda e: self._remove_profile(player_name), remove_item)
            
            self.PopupMenu(menu)
            menu.Destroy()
    
    def _send_discord(self, player_name: str):
        """Envía un perfil específico a Discord"""
        self.cache.send_discord_message(player_name)
    
    def _show_profile_details(self, player_name: str):
        """Muestra detalles de un perfil específico usando tooltip"""
        profiles = self.cache.get_all_profiles()
        if player_name in profiles:
            self._show_profile_tooltip(player_name, profiles[player_name])
    
    def _show_profile_tooltip(self, player_name: str, profile_data: Dict[str, Any]):
        """Muestra un tooltip completo con todos los datos del perfil usando Dialog modal (temporalmente)"""
        try:
            dlg = ProfileDetailsDialog(self, player_name, profile_data)
            dlg.ShowModal()
            dlg.Destroy()
        except Exception as e:
            message_bus.publish(
                content=f"Error showing profile tooltip: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "profile_cache_widget"}
            )
    
    def _remove_profile(self, player_name: str):
        """Elimina un perfil del cache"""
        if self.cache.remove_profile(player_name):
            self._refresh_cache_display()
            message_bus.publish(
                content=f"Profile {player_name} removed from cache",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache_widget"}
            )
    
    def _broadcast_profile(self, player_name: str):
        """Envía un perfil específico a todos los conectados"""
        success = self.cache.broadcast_profile(player_name)
        if success:
            message_bus.publish(
                content=f"Broadcast requested for profile {player_name}",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache_widget"}
            )
    
    def _search_organization(self, player_name: str, org_symbol: str):
        """Busca la organización del jugador"""
        # Emitir evento de búsqueda de organización
        message_bus.emit("search_organization", org_symbol, "ProfileCacheWidget")
        
        message_bus.publish(
            content=f"Searching organization {org_symbol} for player {player_name}",
            level=MessageLevel.INFO,
            metadata={"source": "profile_cache_widget"}
        )
    
    def _extend_context_menu_with_vip(self, menu, player_name):
        """Añadir opciones VIP al menú contextual"""
        from .config_utils import ConfigManager
        
        config_manager = ConfigManager.get_instance()
        is_vip = config_manager.is_vip_player(player_name)
        
        menu.AppendSeparator()
        
        if is_vip:
            vip_item = menu.Append(wx.ID_ANY, f"🚫 Borrar {player_name} de VIPs temporales")
            self.Bind(wx.EVT_MENU, lambda evt: self._toggle_vip_player(player_name), vip_item)
        else:
            vip_item = menu.Append(wx.ID_ANY, f"⭐ Añadir {player_name} a VIPs temporales")
            self.Bind(wx.EVT_MENU, lambda evt: self._toggle_vip_player(player_name), vip_item)

    def _toggle_vip_player(self, player_name: str):
        """Toggle jugador en VIP list usando ConfigManager"""
        from .config_utils import ConfigManager
        
        config_manager = ConfigManager.get_instance()
        was_vip = config_manager.is_vip_player(player_name)
        success = config_manager.toggle_vip_player(player_name)
        
        if success:
            action = "removed from" if was_vip else "added to"
            message_bus.publish(
                content=f"Player {player_name} {action} VIP list",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache_widget"}
            )
    

def _build_profile_text_block(player_name, profile_data):
    """Devuelve el bloque de texto para tooltip/dialogo, igual que el popup."""
    cached_at = profile_data.get('cached_at', datetime.now())
    last_accessed = profile_data.get('last_accessed', datetime.now())
    profile_info = profile_data.get('profile_data', {})
    # Buscar 'action' primero en el dict anidado, luego en el raíz
    action = profile_info.get('action') or profile_data.get('action', 'unknown')
    content_lines = [
        f"Jugador: {player_name}",
        f"Organización: {profile_data.get('organization', 'Unknown')}",
        f"Acción: {action}",
        f"Solicitado por: {profile_data.get('requested_by', 'unknown')}",
        f"Usuario fuente: {profile_data.get('source_user', 'unknown')}",
        f"Cacheado: {cached_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Último acceso: {last_accessed.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "--- Datos del Perfil ---"
    ]
    for key, value in profile_info.items():
        if value and value not in ['Unknown', '', 'None', None]:
            field_name = key.replace('_', ' ').title()
            content_lines.append(f"{field_name}: {value}")
    return "\n".join(content_lines)


class ProfileDetailsDialog(wx.Dialog):
    """Diálogo compacto y dark para mostrar detalles de un perfil específico, tipo tooltip"""
    def __init__(self, parent, player_name: str, profile_data: dict):
        super().__init__(parent, title=f"Detalles: {player_name}",
                         style=wx.BORDER_SIMPLE | wx.STAY_ON_TOP)
        self.SetBackgroundColour(wx.Colour(40, 40, 40))
        self._setup_ui(player_name, profile_data)
        self.Fit()
        self.SetMinSize(self.GetSize())
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key_down)
        # Capturar clics fuera del diálogo
        self.Bind(wx.EVT_KILL_FOCUS, self._on_kill_focus)

    def _setup_ui(self, player_name, profile_data):
        from .ui_components import DarkThemeButton
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        # Bloque de texto igual que el tooltip
        text_block = _build_profile_text_block(player_name, profile_data)
        self.text = wx.StaticText(self, label=text_block)
        self.text.SetForegroundColour(wx.Colour(230, 230, 230))
        font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.text.SetFont(font)
        # Capturar clics en el texto también
        self.text.Bind(wx.EVT_LEFT_DOWN, self._on_close)
        main_sizer.Add(self.text, 0, wx.ALL, 10)
        
        # Botón cerrar pequeño con DarkThemeButton
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_btn = DarkThemeButton(self, label="❌ Cerrar", size=(60, 25))
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND)
        self.SetSizer(main_sizer)

    def _on_close(self, event):
        self.EndModal(wx.ID_CLOSE)
    
    def _on_kill_focus(self, event):
        """Cerrar el diálogo cuando pierde el foco"""
        # Solo cerrar si no es porque se está cerrando ya
        if self.IsShown():
            self.EndModal(wx.ID_CLOSE)
        event.Skip()

    def _on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.EndModal(wx.ID_CLOSE)
        else:
            event.Skip()


# El popup sigue igual, pero ahora usa la función reutilizable para el bloque de texto
class ProfileTooltipPopup(wx.PopupWindow):
    """Popup simple para mostrar detalles de perfiles"""
    
    def __init__(self, parent, content):
        super().__init__(parent)
        self.content = content
        self._setup_ui()
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
        self.SetFocus()
    
    def _setup_ui(self):
        self.SetBackgroundColour(wx.Colour(40, 40, 40))
        self.text = wx.StaticText(self, label=self.content)
        self.text.SetForegroundColour(wx.Colour(230, 230, 230))
        font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.text.SetFont(font)
        self.text.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        self.SetSize(self.text.GetBestSize() + wx.Size(16, 16))
    
    def _on_click(self, event):
        self.Destroy()
    
    def _on_key_down(self, event):
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self.Destroy()
        else:
            event.Skip()
