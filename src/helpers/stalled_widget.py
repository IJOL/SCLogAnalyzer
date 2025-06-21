"""
Widget para mostrar información de usuarios stalled en tiempo real.
Incluye tracking de fuentes, TTL automático, y actualización periódica.
"""

import wx
import csv
import threading
from datetime import datetime, timedelta
from .message_bus import message_bus, MessageLevel
from .ultimate_listctrl_adapter import UltimateListCtrlAdapter


class StalledWidget(wx.Panel):
    """Widget para tracking de usuarios stalled con múltiples fuentes"""
    
    def __init__(self, parent, base_ttl_seconds=30):
        super().__init__(parent)
        
        # Configuración TTL progresivo
        self.base_ttl_seconds = base_ttl_seconds
        
        # Datos thread-safe
        self.data_lock = threading.Lock()
        self.stalled_data = {}  # {player_name: {count, sources, timestamps}}
        
        # Timers
        self.ttl_timer = None
        self.ui_refresh_timer = None
        
        # Inicializar
        self._init_ui()
        self._subscribe_to_events()
        self._start_ttl_timer()
        self._start_ui_refresh_timer()
    
    def _init_ui(self):
        """Inicializa la interfaz de usuario"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Header con título y botón reset
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title_label = wx.StaticText(self, label="Stalled Users")
        title_font = title_label.GetFont()
        title_font.SetPointSize(9)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_label.SetFont(title_font)
        header_sizer.Add(title_label, 1, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)
        
        # Botón Reset compacto
        reset_btn = wx.Button(self, label="Reset", size=(50, 25))
        reset_btn.Bind(wx.EVT_BUTTON, self._on_reset)
        header_sizer.Add(reset_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        main_sizer.Add(header_sizer, 0, wx.EXPAND | wx.ALL, 2)
        
        # Lista con tema dark automático via UltimateListCtrlAdapter
        self.stalled_list = UltimateListCtrlAdapter(
            self, 
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_HRULES | wx.LC_VRULES
        )
        
        # Configurar columnas
        self.stalled_list.InsertColumn(0, "Jugador", width=80)
        self.stalled_list.InsertColumn(1, "Stalls", width=45)
        self.stalled_list.InsertColumn(2, "Fuentes", width=55)
        self.stalled_list.InsertColumn(3, "Último", width=60)
        self.stalled_list.InsertColumn(4, "TTL", width=50)
        
        # Eventos
        self.stalled_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_context_menu)
        
        main_sizer.Add(self.stalled_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Aplicar tema dark al panel
        self._apply_dark_theme()
        
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
        message_bus.on("remote_realtime_event", self._handle_remote_event)
    
    def _calculate_progressive_ttl(self, player_data):
        """Calcula TTL progresivo basado en importancia del problema"""
        # TTL base mínimo (30s para casos triviales)
        ttl = self.base_ttl_seconds
        
        # Factores de importancia
        sources_count = len(player_data['sources'])
        total_stalls = player_data['count']
        
        # +30s por cada fuente adicional (múltiples usuarios reportando = más grave)
        if sources_count > 1:
            ttl += (sources_count - 1) * 30
        
        # +5s por cada stall adicional, con límite de +150s (máximo 30 stalls)
        if total_stalls > 1:
            extra_stalls = min(total_stalls - 1, 30)
            ttl += extra_stalls * 5
        
        # Bonus por persistencia: si tiene más de 10 stalls de la misma fuente
        max_single_source = max((src['count'] for src in player_data['sources'].values()), default=0)
        if max_single_source >= 10:
            ttl += 60  # Problema persistente
        
        # TTL máximo razonable de 10 minutos
        return min(ttl, 600)
    
    def _handle_remote_event(self, username, event_data):
        """Procesa eventos remotos de tiempo real"""
        # Verificar que event_data sea dict
        if not isinstance(event_data, dict):
            return
        
        if not event_data or event_data.get('type') != 'actor_stall':
            return
        
        raw_data = event_data.get('raw_data', {})
        player_name = raw_data.get('player')
        source_user = raw_data.get('username')
        timestamp_str = raw_data.get('timestamp')
        
        # Validar datos requeridos
        if not all([player_name, source_user, timestamp_str]):
            return
        
        # Usar tiempo actual de llegada en lugar del timestamp del servidor
        timestamp = datetime.now()
        
        # Actualizar datos thread-safe
        with self.data_lock:
            if player_name not in self.stalled_data:
                self.stalled_data[player_name] = {
                    'count': 0,
                    'sources': {},
                    'last_source': source_user,
                    'first_timestamp': timestamp,
                    'last_timestamp': timestamp
                }
            
            player_data = self.stalled_data[player_name]
            
            # Actualizar conteo total
            player_data['count'] += 1
            player_data['last_source'] = source_user
            player_data['last_timestamp'] = timestamp
            
            # Actualizar información de fuentes
            if source_user not in player_data['sources']:
                player_data['sources'][source_user] = {
                    'count': 0,
                    'first_seen': timestamp,
                    'last_seen': timestamp
                }
            
            source_data = player_data['sources'][source_user]
            source_data['count'] += 1
            source_data['last_seen'] = timestamp
        
        # Actualizar UI
        wx.CallAfter(self._refresh_ui)
    
    def _start_ttl_timer(self):
        """Inicia el timer para limpieza automática TTL"""
        self.ttl_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._cleanup_expired_data, self.ttl_timer)
        self.ttl_timer.Start(30000)  # Revisar cada 30 segundos
    
    def _start_ui_refresh_timer(self):
        """Inicia el timer para actualización periódica de UI (TTL, tiempos)"""
        self.ui_refresh_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._periodic_ui_refresh, self.ui_refresh_timer)
        self.ui_refresh_timer.Start(5000)  # Actualizar UI cada 5 segundos
    
    def _cleanup_expired_data(self, event):
        """Limpia datos expirados según TTL progresivo"""
        current_time = datetime.now()
        expired_players = []
        
        with self.data_lock:
            for player_name, data in list(self.stalled_data.items()):
                # Calcular TTL específico para este jugador
                player_ttl = self._calculate_progressive_ttl(data)
                ttl_delta = timedelta(seconds=player_ttl)
                
                time_since_last = current_time - data['last_timestamp']
                if time_since_last > ttl_delta:
                    expired_players.append(player_name)
                    del self.stalled_data[player_name]
        
        # Refrescar UI si hubo cambios
        if expired_players:
            wx.CallAfter(self._refresh_ui)
    
    def _periodic_ui_refresh(self, event):
        """Actualización periódica de UI para mostrar TTL y tiempos en tiempo real"""
        # Solo refrescar si hay datos y el widget es visible
        if self.stalled_data and self.IsShown():
            wx.CallAfter(self._refresh_ui)
    
    def _refresh_ui(self):
        """Refresca la UI con valores actualizados y TTL progresivo"""
        # Limpiar lista actual
        self.stalled_list.DeleteAllItems()
        
        # Calcular tiempo actual una sola vez para consistencia
        current_time = datetime.now()
        
        with self.data_lock:
            # Ordenar por conteo descendente
            sorted_players = sorted(
                self.stalled_data.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )
            
            for player, data in sorted_players:
                # Calcular TTL progresivo específico para este jugador
                player_ttl = self._calculate_progressive_ttl(data)
                time_since_last = current_time - data['last_timestamp']
                ttl_remaining = timedelta(seconds=player_ttl) - time_since_last
                ttl_seconds = max(0, int(ttl_remaining.total_seconds()))
                
                # Skip entradas ya expiradas (serán eliminadas en próximo cleanup)
                if ttl_seconds <= 0:
                    continue
                
                # Información de fuentes
                sources_count = len(data['sources'])
                last_source = data['last_source']
                
                # Formato "hace X tiempo" más legible
                minutes_ago = int(time_since_last.total_seconds() / 60)
                if minutes_ago == 0:
                    last_display = "ahora"
                elif minutes_ago == 1:
                    last_display = "1min"
                else:
                    last_display = f"{minutes_ago}min"
                
                # Añadir fila con todas las columnas
                index = self.stalled_list.InsertItem(self.stalled_list.GetItemCount(), player)
                self.stalled_list.SetItem(index, 1, str(data['count']))           # Stalls
                self.stalled_list.SetItem(index, 2, str(sources_count))          # Fuentes  
                self.stalled_list.SetItem(index, 3, f"{last_source[:8]}")        # Último usuario (truncado)
                self.stalled_list.SetItem(index, 4, f"{ttl_seconds}s")           # TTL progresivo
    
    def _on_context_menu(self, event):
        """Maneja clic derecho para mostrar menú contextual"""
        selected = event.GetIndex()
        if selected == -1:
            return
        
        player_name = self.stalled_list.GetItemText(selected, 0)
        
        # Crear menú contextual
        menu = wx.Menu()
        
        # Get Profile
        profile_item = menu.Append(wx.ID_ANY, f"Get Profile: {player_name}")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_get_profile(player_name), profile_item)
        
        # Filtrar stalled de este jugador
        filter_item = menu.Append(wx.ID_ANY, f"Filtrar stalled de {player_name}")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_filter_player_stalled(player_name), filter_item)
        
        # Eliminar jugador
        remove_item = menu.Append(wx.ID_ANY, f"Eliminar {player_name}")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_remove_player(player_name), remove_item)
        
        menu.AppendSeparator()
        
        # Mostrar estadísticas del jugador
        stats_item = menu.Append(wx.ID_ANY, f"Ver estadísticas")
        self.Bind(wx.EVT_MENU, lambda evt: self._on_show_player_stats(player_name), stats_item)
        
        # Exportar datos
        export_item = menu.Append(wx.ID_ANY, f"Exportar datos CSV")
        self.Bind(wx.EVT_MENU, lambda evt: self.export_data_csv(), export_item)
        
        # Mostrar menú
        self.PopupMenu(menu, event.GetPoint())
        menu.Destroy()
    
    def _on_show_player_stats(self, player_name):
        """Muestra estadísticas detalladas del jugador"""
        stats = self.get_player_stats(player_name)
        if stats:
            # Obtener información detallada de fuentes
            sources_info = self._get_sources_info(player_name)
            
            info_text = f"""Estadísticas de {player_name}:
            
• Total stalls: {stats['count']}
• Fuentes que reportan: {sources_info['count']} usuarios
• Primera vez: {stats['first_seen'].strftime('%H:%M:%S')}
• Última vez: {stats['last_seen'].strftime('%H:%M:%S')}
• Duración: {stats['duration_minutes']} minutos
• Promedio: {stats['avg_per_minute']} stalls/min

Detalle por fuente:
{sources_info['details']}"""
            
            dlg = wx.MessageDialog(
                self,
                info_text,
                f"Estadísticas - {player_name}",
                wx.OK | wx.ICON_INFORMATION
            )
            dlg.ShowModal()
            dlg.Destroy()
        else:
            message_bus.publish(
                content=f"No hay datos para {player_name}",
                level=MessageLevel.WARNING
            )
    
    def _on_get_profile(self, player_name):
        """Solicita perfil del jugador"""
        event_data = {
            'player_name': player_name,
            'action': 'get',
            'timestamp': datetime.now().isoformat(),
            'source': 'stalled_widget'
        }
        message_bus.emit("request_profile", event_data, "manual_request")
    
    def _on_filter_player_stalled(self, player_name):
        """Filtra eventos stalled de un jugador específico"""
        from .realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge and hasattr(bridge, 'update_content_exclusions'):
            # Filtrar contenido que contenga "player_name: Stalled"
            filter_content = f"{player_name}: Stalled"
            bridge.update_content_exclusions(content_to_exclude=filter_content, add=True)
            
            message_bus.publish(
                content=f"Filtrados eventos stalled de {player_name}",
                level=MessageLevel.INFO
            )
    
    def _on_remove_player(self, player_name):
        """Elimina un jugador específico"""
        with self.data_lock:
            if player_name in self.stalled_data:
                del self.stalled_data[player_name]
                wx.CallAfter(self._refresh_ui)
    
    def _on_reset(self, event):
        """Limpia la lista con confirmación visual"""
        count = len(self.stalled_data)
        
        if count > 0:
            # Mostrar confirmación si hay datos
            dlg = wx.MessageDialog(
                self, 
                f"¿Limpiar {count} jugadores de la lista stalled?",
                "Confirmar Reset",
                wx.YES_NO | wx.ICON_QUESTION
            )
            
            if dlg.ShowModal() == wx.ID_YES:
                with self.data_lock:
                    self.stalled_data.clear()
                
                wx.CallAfter(self._refresh_ui)
                
                message_bus.publish(
                    content=f"Lista de {count} usuarios stalled reiniciada",
                    level=MessageLevel.INFO
                )
            
            dlg.Destroy()
        else:
            # Lista ya vacía
            message_bus.publish(
                content="Lista stalled ya está vacía",
                level=MessageLevel.INFO
            )
    
    def get_stalled_count(self):
        """Retorna el número de jugadores stalled"""
        with self.data_lock:
            return len(self.stalled_data)
    
    def get_total_stalls(self):
        """Retorna el total de eventos stalled"""
        with self.data_lock:
            return sum(data['count'] for data in self.stalled_data.values())
    
    def clear_data(self):
        """Método público para limpiar datos"""
        self._on_reset(None)
    
    def get_player_stats(self, player_name):
        """Obtiene estadísticas específicas de un jugador"""
        with self.data_lock:
            if player_name in self.stalled_data:
                data = self.stalled_data[player_name]
                duration = datetime.now() - data['first_timestamp']
                duration_minutes = max(1, int(duration.total_seconds() / 60))
                return {
                    'count': data['count'],
                    'first_seen': data['first_timestamp'],
                    'last_seen': data['last_timestamp'],
                    'duration_minutes': duration_minutes,
                    'avg_per_minute': round(data['count'] / duration_minutes, 1)
                }
        return None
    
    def export_data_csv(self):
        """Exporta datos a CSV"""
        if not self.stalled_data:
            message_bus.publish(
                content="No hay datos para exportar",
                level=MessageLevel.INFO
            )
            return False
        
        # Generar nombre de archivo con timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"stalled_data_{timestamp}.csv"
        
        with wx.FileDialog(
            self,
            "Guardar datos stalled",
            defaultFile=filename,
            wildcard="CSV files (*.csv)|*.csv",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
        ) as fileDialog:
            
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return False
            
            filepath = fileDialog.GetPath()
            
            try:
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Jugador', 'Conteo', 'Primera_Vez', 'Ultima_Vez', 'Duracion_Min'])
                    
                    for player, data in self.stalled_data.items():
                        duration = datetime.now() - data['first_timestamp']
                        writer.writerow([
                            player,
                            data['count'],
                            data['first_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                            data['last_timestamp'].strftime('%Y-%m-%d %H:%M:%S'),
                            int(duration.total_seconds() / 60)
                        ])
                
                message_bus.publish(
                    content=f"Datos exportados a: {filename}",
                    level=MessageLevel.INFO
                )
                return True
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error exportando datos: {str(e)}",
                    level=MessageLevel.ERROR
                )
                return False
    
    def cleanup_timers(self):
        """Limpia y detiene todos los timers"""
        # Detener timer TTL
        if hasattr(self, 'ttl_timer') and self.ttl_timer:
            self.ttl_timer.Stop()
            del self.ttl_timer
        
        # Detener timer de actualización UI
        if hasattr(self, 'ui_refresh_timer') and self.ui_refresh_timer:
            self.ui_refresh_timer.Stop()
            del self.ui_refresh_timer
    
    def __del__(self):
        """Cleanup al destruir el widget"""
        self.cleanup_timers()
    
    def _get_sources_info(self, player_name):
        """Obtiene información detallada de las fuentes que reportan un jugador"""
        with self.data_lock:
            if player_name not in self.stalled_data:
                return {'count': 0, 'details': 'No hay datos'}
            
            sources = self.stalled_data[player_name]['sources']
            details_lines = []
            
            # Ordenar fuentes por conteo descendente
            sorted_sources = sorted(
                sources.items(), 
                key=lambda x: x[1]['count'], 
                reverse=True
            )
            
            for source_user, source_data in sorted_sources:
                duration = datetime.now() - source_data['first_seen']
                duration_min = int(duration.total_seconds() / 60)
                details_lines.append(
                    f"• {source_user}: {source_data['count']} stalls "
                    f"({duration_min}min ago)"
                )
            
            return {
                'count': len(sources),
                'details': '\n'.join(details_lines)
            }