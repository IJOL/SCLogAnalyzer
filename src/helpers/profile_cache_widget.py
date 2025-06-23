"""
Widget visual para gestionar el cache de perfiles
"""

import wx
from datetime import datetime
from typing import Dict, Any

from .profile_cache import ProfileCache
from .message_bus import message_bus, MessageLevel
from .custom_listctrl import CustomListCtrl


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
        self.cache_listctrl.InsertColumn(2, "Origen", width=80)
        self.cache_listctrl.InsertColumn(3, "Hora", width=60)
        self.cache_listctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_profile_double_click)
        self.cache_listctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_right_click)
        
        # Botones de control
        button_panel = wx.Panel(self)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_btn = wx.Button(button_panel, label="🔄 Refresh")
        self.refresh_btn.Bind(wx.EVT_BUTTON, self._on_refresh)
        
        self.clear_btn = wx.Button(button_panel, label="🗑️ Clear All")
        self.clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_cache)
        
        self.broadcast_btn = wx.Button(button_panel, label="📡 Broadcast All")
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
        dark_btn_bg = wx.Colour(64, 64, 64)    # Fondo botones
        dark_btn_fg = wx.Colour(240, 240, 240) # Texto botones
        
        # Panel principal
        self.SetBackgroundColour(dark_bg)
        
        # Labels
        if hasattr(self, 'title_label'):
            self.title_label.SetForegroundColour(dark_fg)
        if hasattr(self, 'stats_label'):
            self.stats_label.SetForegroundColour(dark_fg)
        
        # Botones
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.SetBackgroundColour(dark_btn_bg)
            self.refresh_btn.SetForegroundColour(dark_btn_fg)
        if hasattr(self, 'clear_btn'):
            self.clear_btn.SetBackgroundColour(dark_btn_bg)
            self.clear_btn.SetForegroundColour(dark_btn_fg)
        if hasattr(self, 'broadcast_btn'):
            self.broadcast_btn.SetBackgroundColour(dark_btn_bg)
            self.broadcast_btn.SetForegroundColour(dark_btn_fg)
    
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
                org = profile_data.get('organization', 'Unknown')
                source = profile_data.get('origin', 'unknown')
                cached_at = profile_data.get('cached_at', datetime.now())
                time_str = cached_at.strftime("%H:%M")
                
                # Insertar fila con datos en columnas separadas
                index = self.cache_listctrl.InsertItem(self.cache_listctrl.GetItemCount(), player_name)
                self.cache_listctrl.SetItem(index, 1, org)
                self.cache_listctrl.SetItem(index, 2, source)
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
            
            menu = wx.Menu()
            details_item = menu.Append(wx.ID_ANY, "Ver detalles")
            broadcast_item = menu.Append(wx.ID_ANY, "📡 Broadcast profile")
            remove_item = menu.Append(wx.ID_ANY, "Eliminar del cache")
            
            self.Bind(wx.EVT_MENU, lambda e: self._show_profile_details(player_name), details_item)
            self.Bind(wx.EVT_MENU, lambda e: self._broadcast_profile(player_name), broadcast_item)
            self.Bind(wx.EVT_MENU, lambda e: self._remove_profile(player_name), remove_item)
            
            self.PopupMenu(menu)
            menu.Destroy()
    
    def _show_profile_details(self, player_name: str):
        """Muestra detalles de un perfil específico usando tooltip"""
        profiles = self.cache.get_all_profiles()
        if player_name in profiles:
            self._show_profile_tooltip(player_name, profiles[player_name])
    
    def _show_profile_tooltip(self, player_name: str, profile_data: Dict[str, Any]):
        """Muestra un tooltip completo con todos los datos del perfil usando PopupWindow"""
        try:
            # Datos del cache
            cached_at = profile_data.get('cached_at', datetime.now())
            last_accessed = profile_data.get('last_accessed', datetime.now())
            
            # Datos del perfil
            profile_info = profile_data.get('profile_data', {})
            
            # Construir contenido del tooltip en formato lista
            content_lines = [
                f"Jugador: {player_name}",
                f"Organización: {profile_data.get('organization', 'Unknown')}",
                f"Origen: {profile_data.get('origin', 'unknown')}",
                f"Tipo: {profile_data.get('source_type', 'unknown')}",
                f"Solicitado por: {profile_data.get('requested_by', 'unknown')}",
                f"Usuario fuente: {profile_data.get('source_user', 'unknown')}",
                f"Cacheado: {cached_at.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Último acceso: {last_accessed.strftime('%Y-%m-%d %H:%M:%S')}",
                "",  # Línea vacía para separar
                "--- Datos del Perfil ---"
            ]
            
            # Añadir todos los datos del perfil disponibles
            for key, value in profile_info.items():
                if value and value not in ['Unknown', '', 'None', None]:
                    # Formatear el nombre del campo
                    field_name = key.replace('_', ' ').title()
                    content_lines.append(f"{field_name}: {value}")
            
            # Crear popup window personalizado
            popup = ProfileTooltipPopup(self, "\n".join(content_lines))
            
            # Mostrar en la posición del mouse
            mouse_pos = wx.GetMousePosition()
            popup.Position(mouse_pos, (0, 0))
            popup.Show()
            
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
        profiles = self.cache.get_all_profiles()
        if player_name in profiles:
            profile_data = profiles[player_name]['profile_data']
            
            # Emitir evento para que log_analyzer lo procese
            message_bus.emit('force_broadcast_profile', player_name, profile_data)
            
            message_bus.publish(
                content=f"Requesting broadcast for profile {player_name}",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache_widget"}
            )
    
    def cleanup(self):
        """Limpieza al cerrar el widget"""
        # Desconectar eventos del message bus
        message_bus.off("profile_cached", self._on_profile_cached)


class ProfileTooltipPopup(wx.PopupWindow):
    """Popup simple para mostrar detalles de perfiles"""
    
    def __init__(self, parent, content):
        super().__init__(parent)
        self.content = content
        self._setup_ui()
        
        # Solo cerrar al hacer clic, no por tiempo
        self.Bind(wx.EVT_LEFT_DOWN, self._on_click)
    
    def _setup_ui(self):
        """Configura la interfaz del popup simple"""
        # Fondo oscuro sin bordes
        self.SetBackgroundColour(wx.Colour(40, 40, 40))
        
        # Texto con el contenido
        self.text = wx.StaticText(self, label=self.content)
        self.text.SetForegroundColour(wx.Colour(230, 230, 230))  # Texto blanco
        
        # Font monospace para mejor alineación
        font = wx.Font(9, wx.FONTFAMILY_MODERN, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.text.SetFont(font)
        
        # Hacer que el texto también sea clickeable
        self.text.Bind(wx.EVT_LEFT_DOWN, self._on_click)
        
        # Sizer simple
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.text, 1, wx.EXPAND | wx.ALL, 8)
        self.SetSizer(sizer)
        
        # Ajustar tamaño al contenido
        self.SetSize(self.text.GetBestSize() + wx.Size(16, 16))
    
    def _on_click(self, event):
        """Cerrar al hacer clic"""
        self.Destroy()


class ProfileDetailsDialog(wx.Dialog):
    """Diálogo para mostrar detalles de un perfil específico"""
    
    def __init__(self, parent, player_name: str, profile_data: Dict[str, Any]):
        super().__init__(parent, title=f"Detalles: {player_name}", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.player_name = player_name
        self.profile_data = profile_data
        self._setup_ui()
        self.SetSize((500, 400))
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Información del cache
        cache_info = wx.StaticBoxSizer(wx.VERTICAL, self, "Información del Cache")
        
        cached_at = self.profile_data.get('cached_at', datetime.now())
        last_accessed = self.profile_data.get('last_accessed', datetime.now())
        
        cache_info.Add(wx.StaticText(self, label=f"Jugador: {self.player_name}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Organización: {self.profile_data.get('organization', 'Unknown')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Origen: {self.profile_data.get('origin', 'unknown')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Tipo: {self.profile_data.get('source_type', 'unknown')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Solicitado por: {self.profile_data.get('requested_by', 'unknown')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Usuario fuente: {self.profile_data.get('source_user', 'unknown')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Cacheado: {cached_at.strftime('%Y-%m-%d %H:%M:%S')}"), 0, wx.ALL, 5)
        cache_info.Add(wx.StaticText(self, label=f"Último acceso: {last_accessed.strftime('%Y-%m-%d %H:%M:%S')}"), 0, wx.ALL, 5)
        
        # Datos del perfil
        profile_info = wx.StaticBoxSizer(wx.VERTICAL, self, "Datos del Perfil")
        
        profile_text = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY)
        profile_data_str = str(self.profile_data.get('profile_data', {}))
        profile_text.SetValue(profile_data_str)
        
        profile_info.Add(profile_text, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        close_btn = wx.Button(self, wx.ID_CLOSE, "Cerrar")
        close_btn.Bind(wx.EVT_BUTTON, self._on_close)
        button_sizer.Add(close_btn, 0, wx.ALL, 5)
        
        # Layout principal
        main_sizer.Add(cache_info, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(profile_info, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    
    def _on_close(self, event):
        """Cierra el diálogo"""
        self.EndModal(wx.ID_CLOSE)


class CacheDetailsDialog(wx.Dialog):
    """Diálogo para mostrar estadísticas completas del cache"""
    
    def __init__(self, parent):
        super().__init__(parent, title="Estadísticas del Cache", 
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self.cache = ProfileCache.get_instance()
        self._setup_ui()
        self.SetSize((400, 300))
    
    def _setup_ui(self):
        """Configura la interfaz del diálogo"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
