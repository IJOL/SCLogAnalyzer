"""
OrgMembersWidget - Widget para búsqueda y visualización de miembros de organizaciones

Este widget permite buscar organizaciones de Star Citizen y mostrar sus miembros
no redacted con funcionalidad de menú contextual para obtener perfiles.
"""

import wx
import threading
from datetime import datetime

from .message_bus import message_bus, MessageLevel
from .custom_listctrl import CustomListCtrl as UltimateListCtrlAdapter
from .ui_components import DarkThemeButton
from .rsi_org_scraper import get_org_members, get_org_info


class OrgMembersWidget(wx.Panel):
    """Widget para búsqueda y visualización de miembros de organizaciones"""
    
    def __init__(self, parent, columns=None):
        super().__init__(parent)
        
        # Configuración de columnas por defecto
        self.default_columns = ["Name", "Rank", "Status", "Last Activity"]
        self.columns = columns if columns is not None else self.default_columns
        
        # Datos thread-safe
        self.data_lock = threading.Lock()
        self.current_org_data = []
        self.current_org_symbol = ""
        
        # Estado de búsqueda
        self.is_searching = False
        
        # Mapping de índice de fila a datos de miembro
        self.row_to_member = {}  # {row_index: member_data}
        

        
        # Inicializar
        self._init_ui()
        self._subscribe_to_events()
        self._apply_dark_theme()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header con título
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title_label = wx.StaticText(self, label="Organization Members")
        title_font = title_label.GetFont()
        title_font.SetPointSize(9)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_label.SetFont(title_font)
        header_sizer.Add(title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        
        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 2)
        
        # Panel de búsqueda
        search_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Campo de entrada
        self.org_input = wx.TextCtrl(
            self, 
            value="", 
            style=wx.TE_PROCESS_ENTER
        )
        self.org_input.Bind(wx.EVT_TEXT_ENTER, self._on_search)
        search_sizer.Add(self.org_input, 1, wx.EXPAND | wx.RIGHT, 5)
        
        # Botón de búsqueda
        self.search_btn = DarkThemeButton(self, label="🔍 Search", size=(80, 25))
        self.search_btn.Bind(wx.EVT_BUTTON, self._on_search)
        search_sizer.Add(self.search_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        
        main_sizer.Add(search_sizer, 0, wx.EXPAND | wx.ALL, 2)
        
        # Lista de miembros con tema dark automático
        self.members_list = UltimateListCtrlAdapter(
            self, 
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES
        )
        
        # Configurar columnas dinámicamente
        for i, column_name in enumerate(self.columns):
            width = 120 if column_name == "Name" else 80
            self.members_list.InsertColumn(i, column_name, width=width)
        
        # Eventos
        self.members_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_context_menu)
        
        main_sizer.Add(self.members_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Panel de estado
        self.status_label = wx.StaticText(self, label="Enter organization symbol to search")
        status_font = self.status_label.GetFont()
        status_font.SetPointSize(8)
        self.status_label.SetFont(status_font)
        main_sizer.Add(self.status_label, 0, wx.EXPAND | wx.ALL, 2)
        
        self.SetSizer(main_sizer)
    
    def _apply_dark_theme(self):
        """Aplica tema dark consistente"""
        dark_bg = wx.Colour(80, 80, 80)
        dark_fg = wx.Colour(230, 230, 230)
        
        self.SetBackgroundColour(dark_bg)
        
        # Todos los StaticText
        for child in self.GetChildren():
            if isinstance(child, wx.StaticText):
                child.SetForegroundColour(dark_fg)
    
    def _subscribe_to_events(self):
        """Suscribe a eventos del message bus"""
        message_bus.on("search_organization", self._on_search_organization_event)
    
    def _on_search_organization_event(self, org_symbol, source=None):
        """Handler para eventos de búsqueda de organizaciones"""
        if org_symbol and isinstance(org_symbol, str):
            wx.CallAfter(self._set_org_input, org_symbol)
            wx.CallAfter(self._perform_search, org_symbol)
    
    def _set_org_input(self, org_symbol):
        """Establece el símbolo de organización en el campo de entrada"""
        self.org_input.SetValue(org_symbol)
    
    def _on_search(self, event):
        """Maneja la búsqueda de organización"""
        org_symbol = self.org_input.GetValue().strip().upper()
        if org_symbol:
            self._perform_search(org_symbol)
    
    def _perform_search(self, org_symbol):
        """Ejecuta la búsqueda de organización"""
        if self.is_searching:
            return
        
        self.is_searching = True
        self.current_org_symbol = org_symbol
        self._update_status(f"Searching for organization: {org_symbol}")
        self.search_btn.Enable(False)
        
        # Ejecutar búsqueda en thread separado
        search_thread = threading.Thread(
            target=self._search_organization_thread,
            args=(org_symbol,),
            daemon=True
        )
        search_thread.start()
    
    def _search_organization_thread(self, org_symbol):
        """Thread para búsqueda de organización"""
        try:
            # Obtener miembros de la organización (solo no redacted)
            members = get_org_members(org_symbol, full=True, redacted=False)
            
            # Actualizar UI en el thread principal
            wx.CallAfter(self._on_search_complete, org_symbol, members)
            
        except Exception as e:
            error_msg = f"Error searching organization {org_symbol}: {str(e)}"
            message_bus.publish(error_msg, level=MessageLevel.ERROR)
            wx.CallAfter(self._on_search_error, error_msg)
    
    def _on_search_complete(self, org_symbol, members):
        """Maneja la finalización exitosa de la búsqueda"""
        self.is_searching = False
        self.search_btn.Enable(True)
        
        with self.data_lock:
            self.current_org_data = members
            self.current_org_symbol = org_symbol
        
        self._update_members_list(members)
        self._update_status(f"Found {len(members)} members for {org_symbol}")
        
        # Emitir evento de búsqueda completada
        message_bus.emit("org_search_complete", {
            "org_symbol": org_symbol,
            "member_count": len(members)
        }, "OrgMembersWidget")
    
    def _on_search_error(self, error_msg):
        """Maneja errores de búsqueda"""
        self.is_searching = False
        self.search_btn.Enable(True)
        self._update_status(error_msg)
        self._clear_members_list()
    
    def _update_members_list(self, members):
        """Actualiza la lista de miembros"""
        self.members_list.DeleteAllItems()
        self.row_to_member.clear()
        
        for i, member in enumerate(members):
            # Solo mostrar miembros no redacted
            if member.get('visibility') != 'R':
                self._add_member_to_list(i, member)
    
    def _add_member_to_list(self, index, member):
        """Añade un miembro a la lista usando columnas dinámicas"""
        row = self.members_list.GetItemCount()
        
        # Datos del miembro - usar campos correctos del scraper RSI
        name = member.get('display_name', member.get('username', 'Unknown'))
        rank = member.get('rank', 'Unknown')
        status = "Active" if member.get('visibility') == 'V' else "Redacted"
        last_activity = "N/A"  # El scraper no proporciona esta información
        
        # Mapeo de columnas a datos
        column_data = {
            "Name": name,
            "Rank": rank,
            "Status": status,
            "Last Activity": last_activity
        }
        
        # Insertar en la lista usando solo las columnas configuradas
        for i, column_name in enumerate(self.columns):
            data = column_data.get(column_name, "")
            if i == 0:
                self.members_list.InsertItem(row, data)
            else:
                self.members_list.SetItem(row, i, data)
        
        # Guardar mapping
        self.row_to_member[row] = member
    
    def _clear_members_list(self):
        """Limpia la lista de miembros"""
        self.members_list.DeleteAllItems()
        self.row_to_member.clear()
    
    def _update_status(self, message):
        """Actualiza el mensaje de estado"""
        self.status_label.SetLabel(message)
    
    def _on_context_menu(self, event):
        """Maneja el menú contextual en la lista"""
        index = event.GetIndex()
        if index >= 0 and index in self.row_to_member:
            member = self.row_to_member[index]
            self._show_context_menu(event.GetPoint(), member)
    
    def _show_context_menu(self, point, member):
        """Muestra el menú contextual para un miembro"""
        menu = wx.Menu()
        
        # Opción "Get Profile" con emoticono
        get_profile_item = menu.Append(wx.ID_ANY, f"🔍 Get Profile: {member.get('display_name', member.get('username', 'Unknown'))}")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_get_profile(member), get_profile_item)
        
        # Opción "Copy Name" con emoticono
        copy_name_item = menu.Append(wx.ID_ANY, f"📋 Copy Name: {member.get('display_name', member.get('username', 'Unknown'))}")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_copy_name(member), copy_name_item)
        
        # Mostrar menú
        self.PopupMenu(menu, point)
        menu.Destroy()
    
    def _on_get_profile(self, member):
        """Maneja la opción 'Get Profile' del menú contextual"""
        member_name = member.get('username', member.get('display_name', 'Unknown'))
        
        # Usar el mismo patrón que SharedLogsWidget
        event_data = {
            'player_name': member_name,
            'action': 'get',
            'timestamp': datetime.now().isoformat(),
            'source': 'org_members_widget_context_menu',
            'org_symbol': self.current_org_symbol,
            'member_data': member
        }
        message_bus.emit(
            "request_profile",
            event_data,
            "manual_request"
        )
        
        message_bus.publish(f"Requesting profile for: {member_name}", level=MessageLevel.INFO)
    
    def _on_copy_name(self, member):
        """Maneja la opción 'Copy Name' del menú contextual"""
        member_name = member.get('display_name', member.get('username', 'Unknown'))
        
        # Copiar al portapapeles
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(member_name))
            wx.TheClipboard.Close()
            
            message_bus.publish(f"Copied to clipboard: {member_name}", level=MessageLevel.INFO)
    
 