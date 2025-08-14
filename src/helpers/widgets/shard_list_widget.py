import wx
from datetime import datetime
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.ui.ui_components import MiniDarkThemeButton
from helpers.widgets.dark_listctrl import DarkListCtrl

class ShardListWidget(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self.shard_data = []  # Lista de entradas: [{'player': str, 'shard': str, 'timestamp': datetime}]
        self._setup_ui()
        self._subscribe_events()
    
    def _setup_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Fila superior con checkbox y botón clean
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.auto_shard_checkbox = wx.CheckBox(self, label="Auto-shard en modo Live (SC_Default)")
        self.auto_shard_checkbox.Bind(wx.EVT_CHECKBOX, self._on_auto_shard_toggle)
        top_sizer.Add(self.auto_shard_checkbox, 1, wx.ALIGN_CENTER_VERTICAL, 5)
        
        # Botón clean compacto
        self.clear_btn = MiniDarkThemeButton(self, label="🗑️")
        self.clear_btn.SetToolTip("Limpiar lista de shards")
        self.clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_shards)
        top_sizer.Add(self.clear_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        
        sizer.Add(top_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        self.list_ctrl = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN)
        self.list_ctrl.InsertColumn(0, "Player", width=150)
        self.list_ctrl.InsertColumn(1, "Shard", width=100)
        self.list_ctrl.InsertColumn(2, "Time", width=120)
        
        sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(sizer)
        
    def _subscribe_events(self):
        message_bus.on('shard_version_update', self._on_local_shard)
        message_bus.on('users_online_updated', self._on_users_online_updated)
        message_bus.on('mode_change', self._on_mode_change)
        
    def _parse_shard(self, shard_full):
        """Parse shard format {modo}_{region}_{version}_{numero} -> region_numero"""
        try:
            parts = shard_full.split('_')
            if len(parts) >= 4:
                # Formato: [modo, region, version, numero] o más elementos
                region = parts[1]  # Segundo elemento es siempre la región
                numero = parts[-1]  # Último elemento es siempre el número de shard
                return f"{region}_{numero}"
        except Exception:
            pass
        return shard_full  # Si no se puede parsear, devolver original
        
    def _on_local_shard(self, shard, version, username, mode=None, private=None):
        self._add_shard_entry(username, shard)
        
    def _on_users_online_updated(self, users_online):
        for user in users_online:
            username = user.get('username')
            shard = user.get('shard')
            if username and shard and shard != 'Unknown':
                self._add_shard_entry(username, shard)
                
    def _on_mode_change(self, new_mode, old_mode=None, live=False):
        if self.auto_shard_checkbox.GetValue() and new_mode == "SC_Default" and live:
            message_bus.emit('system_auto_shard')
            
    def _on_auto_shard_toggle(self, event):
        enabled = self.auto_shard_checkbox.GetValue()
        message_bus.publish(
            content=f"Auto-shard en modo Live: {'habilitado' if enabled else 'deshabilitado'}",
            level=MessageLevel.INFO
        )
        
    def _on_clear_shards(self, event):
        """Limpiar toda la lista de shards"""
        self.shard_data.clear()
        wx.CallAfter(self._update_display)
        message_bus.publish(
            content="Lista de shards limpiada",
            level=MessageLevel.INFO
        )
        
    def _add_shard_entry(self, player, shard):
        # Validar que el shard no sea None, vacío o 'Unknown'
        if not shard or shard in ['Unknown', 'None']:
            return  # No agregar shards inválidos

        parsed_shard = self._parse_shard(shard)

        # Solo agregar si el último registro es exactamente igual (usuario y shard)
        if self.shard_data:
            last_entry = self.shard_data[-1]
            if last_entry['player'] == player and last_entry['shard'] == parsed_shard:
                return

        # Buscar la última entrada de este usuario
        last_user_entry = None
        for entry in reversed(self.shard_data):
            if entry['player'] == player:
                last_user_entry = entry
                break

        # Solo agregar si el shard es diferente al último registrado para este usuario
        if last_user_entry is None or last_user_entry['shard'] != parsed_shard:
            self.shard_data.append({
                'player': player,
                'shard': parsed_shard,
                'timestamp': datetime.now()
            })
            wx.CallAfter(self._update_display)
        
    def _update_display(self):
        self.list_ctrl.DeleteAllItems()
        # Ordenar por timestamp más reciente primero
        sorted_data = sorted(self.shard_data, key=lambda x: x['timestamp'], reverse=True)
        
        for entry in sorted_data:
            try:
                # Validar que todos los datos sean válidos antes de mostrar
                if not entry.get('player') or not entry.get('shard') or not entry.get('timestamp'):
                    continue
                    
                index = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), str(entry['player']))
                self.list_ctrl.SetItem(index, 1, str(entry['shard']))
                self.list_ctrl.SetItem(index, 2, entry['timestamp'].strftime('%H:%M:%S'))
            except Exception as e:
                # Log error pero no detener el resto de la visualización
                message_bus.publish(
                    content=f"Error updating display for {entry.get('player', 'unknown')}: {e}",
                    level=MessageLevel.DEBUG
                )