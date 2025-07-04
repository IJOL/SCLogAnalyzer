"""
Widget para mostrar información de usuarios stalled en tiempo real.
Incluye tracking de fuentes, TTL automático, y actualización periódica.
"""

import wx
import threading
from datetime import datetime, timedelta
from .message_bus import message_bus, MessageLevel
from .custom_listctrl import CustomListCtrl as UltimateListCtrlAdapter
from .ui_components import DarkThemeButton


class StalledWidget(wx.Panel):
    """Widget para tracking de usuarios stalled con múltiples fuentes"""
    
    def __init__(self, parent, base_ttl_seconds=30):
        super().__init__(parent)
        
        # Configuración TTL progresivo
        self.base_ttl_seconds = base_ttl_seconds
        
        # Datos thread-safe
        self.data_lock = threading.Lock()
        self.stalled_data = {}  # {player_name: {count, sources, timestamps, base_ttl_multiplier, historical_detections}}
        
        # Cache histórico (no visible)
        self.historical_cache = {}  # {player_name: {count, sources, last_seen, detection_count, base_ttl_multiplier}}
        
        # Mapping de índice de fila a nombre de jugador limpio
        self.row_to_player = {}  # {row_index: player_name}
        
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
        reset_btn = DarkThemeButton(self, label="Reset", size=(50, 25))
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
        self.stalled_list.InsertColumn(3, "Hace", width=60)
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
    
    def _calculate_progressive_ttl(self, player_data, player_name):
        """Calcula TTL progresivo con penalizaciones agresivas por reincidencia"""
        # TTL base progresivo
        ttl = self._calculate_base_ttl(player_name)
        
        # Factores de importancia actuales
        sources_count = len(player_data['sources'])
        total_stalls = player_data['count']
        
        # +45s por cada fuente adicional
        if sources_count > 1:
            ttl += (sources_count - 1) * 45
        
        # +4s por cada stall adicional (máximo 30 stalls = +120s)
        if total_stalls > 1:
            extra_stalls = min(total_stalls - 1, 30)
            ttl += extra_stalls * 4
        
        # NUEVO: Penalizaciones por reincidencia histórica
        historical_detections = player_data.get('historical_detections', 0)
        if historical_detections > 0:
            # 4ta detección: 2 minutos base
            if historical_detections == 4:
                ttl = max(ttl, 120)
            # 5ta detección en adelante: +40 segundos por detección adicional
            elif historical_detections >= 5:
                additional_penalty = (historical_detections - 4) * 40
                ttl = max(ttl, 120 + additional_penalty)
        
        # Bonus por persistencia: si tiene más de 10 stalls de la misma fuente
        max_single_source = max((src['count'] for src in player_data['sources'].values()), default=0)
        if max_single_source >= 10:
            ttl += 60
        
        # Bonus por múltiples avistamientos
        if sources_count >= 4:
            ttl += 90
        elif sources_count >= 3:
            ttl += 60
        
        # TTL máximo de 6 minutos
        final_ttl = min(ttl, 360)
        
        return final_ttl
    
    def _calculate_base_ttl(self, player_name):
        """Calcula TTL base progresivo basado en historial"""
        base_ttl = self.base_ttl_seconds  # TTL base inicial
        
        if player_name in self.historical_cache:
            multiplier = self.historical_cache[player_name]['base_ttl_multiplier']
            base_ttl *= multiplier
        
        return base_ttl
    
    def _move_to_historical_cache(self, player_name):
        """Mueve datos activos a cache histórico con multiplicadores más agresivos"""
        if player_name in self.stalled_data:
            player_data = self.stalled_data[player_name]
            
            current_multiplier = player_data.get('base_ttl_multiplier', 1)
            historical_detections = player_data.get('historical_detections', 0)
            
            # NUEVO: Multiplicador más agresivo
            # 1ra reaparición: 2x, 2da: 3x, 3ra: 5x, 4ra+: 8x
            if historical_detections == 0:
                new_multiplier = 2
            elif historical_detections == 1:
                new_multiplier = 3
            elif historical_detections == 2:
                new_multiplier = 5
            else:
                new_multiplier = 8
            
            self.historical_cache[player_name] = {
                'count': player_data['count'],
                'sources': player_data['sources'].copy(),
                'last_seen': player_data['last_timestamp'],
                'detection_count': historical_detections + 1,
                'base_ttl_multiplier': new_multiplier,
                'last_source': player_data['last_source'],
                'first_timestamp': player_data['first_timestamp']
            }
            
            del self.stalled_data[player_name]
    
    def _promote_from_historical(self, player_name):
        """Promueve jugador del cache histórico a activo"""
        if player_name in self.historical_cache:
            historical_data = self.historical_cache[player_name]
            
            # Restaurar datos con multiplicador actualizado
            self.stalled_data[player_name] = {
                'count': historical_data['count'],
                'sources': historical_data['sources'].copy(),
                'last_source': historical_data['last_source'],
                'first_timestamp': historical_data['first_timestamp'],
                'last_timestamp': datetime.now(),
                'base_ttl_multiplier': historical_data['base_ttl_multiplier'],
                'historical_detections': historical_data['detection_count']
            }
            
            # Eliminar del cache histórico
            del self.historical_cache[player_name]
    
    def _calculate_heat_color(self, player_data):
        """Calcula color basado en actividad reciente (últimos 90s)"""
        recent_detections = 0
        current_time = datetime.now()
        
        for source_data in player_data['sources'].values():
            time_diff = current_time - source_data['last_seen']
            if time_diff.total_seconds() <= 90:  # 3 períodos de 30s
                recent_detections += source_data['count']
        
        # Calcular intensidad (0-255)
        if recent_detections >= 10:
            intensity = 255  # Rojo máximo
        elif recent_detections >= 5:
            intensity = 200  # Rojo intenso
        elif recent_detections >= 3:
            intensity = 150  # Rojo medio
        elif recent_detections >= 1:
            intensity = 100  # Rojo suave
        else:
            intensity = 230  # Blanco (normal)
        
        return wx.Colour(intensity, 50, 50)
    
    def _calculate_background_color(self, player_data):
        """Calcula color de fondo basado en actividad reciente (últimos 90s)"""
        recent_detections = 0
        current_time = datetime.now()
        
        for source_data in player_data['sources'].values():
            time_diff = current_time - source_data['last_seen']
            if time_diff.total_seconds() <= 90:  # 3 períodos de 30s
                recent_detections += source_data['count']
        
        # Colores de fondo que contrastan bien con texto blanco
        if recent_detections >= 10:
            return wx.Colour(180, 30, 30)   # Rojo oscuro intenso
        elif recent_detections >= 5:
            return wx.Colour(140, 40, 40)   # Rojo oscuro medio
        elif recent_detections >= 3:
            return wx.Colour(100, 50, 50)   # Rojo oscuro suave
        elif recent_detections >= 1:
            return wx.Colour(80, 60, 60)    # Rojo muy oscuro
        else:
            return wx.Colour(80, 80, 80)    # Gris normal (fondo base)
    
    def _calculate_heat_level(self, player_data):
        """Calcula nivel de actividad reciente (0-4) para determinar si mostrar punto coloreado"""
        recent_detections = 0
        current_time = datetime.now()
        
        for source_data in player_data['sources'].values():
            time_diff = current_time - source_data['last_seen']
            if time_diff.total_seconds() <= 90:  # 3 períodos de 30s
                recent_detections += source_data['count']
        
        # Retornar nivel de actividad (0 = normal, 1-4 = actividad creciente)
        if recent_detections >= 10:
            return 4  # Actividad máxima
        elif recent_detections >= 5:
            return 3  # Actividad alta
        elif recent_detections >= 3:
            return 2  # Actividad media
        elif recent_detections >= 1:
            return 1  # Actividad baja
        else:
            return 0  # Sin actividad reciente
    
    def _get_historical_stats(self, player_name):
        """Obtiene estadísticas incluyendo cache histórico"""
        stats = {}
        
        # Datos activos
        if player_name in self.stalled_data:
            stats['active'] = self.stalled_data[player_name]
        
        # Datos históricos
        if player_name in self.historical_cache:
            stats['historical'] = self.historical_cache[player_name]
        
        return stats
    
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
            # Verificar si el jugador está en cache histórico
            if player_name in self.historical_cache:
                self._promote_from_historical(player_name)
            
            if player_name not in self.stalled_data:
                self.stalled_data[player_name] = {
                    'count': 0,
                    'sources': {},
                    'last_source': source_user,
                    'first_timestamp': timestamp,
                    'last_timestamp': timestamp,
                    'base_ttl_multiplier': 1,
                    'historical_detections': 0
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
        self.ui_refresh_timer.Start(2000)  # Actualizar UI cada 2 segundos
    
    def _cleanup_expired_data(self, event):
        """Limpia datos expirados según TTL progresivo"""
        current_time = datetime.now()
        expired_players = []
        
        with self.data_lock:
            for player_name, data in list(self.stalled_data.items()):
                # Calcular TTL específico para este jugador
                player_ttl = self._calculate_progressive_ttl(data, player_name)
                ttl_delta = timedelta(seconds=player_ttl)
                
                time_since_last = current_time - data['last_timestamp']
                if time_since_last > ttl_delta:
                    # Mover a cache histórico en lugar de borrar
                    self._move_to_historical_cache(player_name)
                    expired_players.append(player_name)
        
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
        
        # Limpiar mapping de filas al refrescar
        self.row_to_player.clear()
        
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
                player_ttl = self._calculate_progressive_ttl(data, player)
                time_since_last = current_time - data['last_timestamp']
                ttl_remaining = timedelta(seconds=player_ttl) - time_since_last
                ttl_seconds = max(0, int(ttl_remaining.total_seconds()))
                
                # Mostrar incluso si TTL es 0, pero marcar como "expirando"
                # El cleanup real se encarga de eliminar los datos
                if ttl_seconds <= 0:
                    ttl_display = "0s"
                else:
                    ttl_display = f"{ttl_seconds}s"
                
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
                
                # Añadir punto indicador al nombre del jugador (solo visual)
                heat_level = self._calculate_heat_level(data)
                player_display = f"● {player}" if heat_level > 0 else f"○ {player}"
                
                # Añadir fila con todas las columnas
                index = self.stalled_list.InsertItem(self.stalled_list.GetItemCount(), player_display)
                self.stalled_list.SetItem(index, 1, str(data['count']))           # Stalls
                self.stalled_list.SetItem(index, 2, str(sources_count))          # Fuentes  
                self.stalled_list.SetItem(index, 3, last_display)                # Último tiempo
                self.stalled_list.SetItem(index, 4, ttl_display)                 # TTL progresivo
                
                # Almacenar nombre limpio para acceso posterior
                self.row_to_player[index] = player
                
                # Aplicar fondo coloreado basado en actividad reciente
                if heat_level > 0:
                    background_color = self._calculate_background_color(data)
                    self.stalled_list.SetItemBackgroundColour(index, background_color)
                    # Texto siempre blanco para máximo contraste
                    self.stalled_list.SetItemTextColour(index, wx.Colour(255, 255, 255))
                else:
                    # Sin actividad: fondo normal, texto blanco
                    self.stalled_list.SetItemBackgroundColour(index, wx.Colour(80, 80, 80))
                    self.stalled_list.SetItemTextColour(index, wx.Colour(230, 230, 230))
    
    def _get_player_name_by_index(self, index):
        """Obtiene el nombre limpio del jugador usando el mapping simple"""
        if index == -1:
            return None
        
        return self.row_to_player.get(index)
    
    def _on_context_menu(self, event):
        """Maneja clic derecho para mostrar menú contextual"""
        selected = event.GetIndex()
        if selected == -1:
            return
        
        player_name = self._get_player_name_by_index(selected)
        if not player_name:
            return
        
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
        
        # Mostrar menú
        self.PopupMenu(menu, event.GetPoint())
        menu.Destroy()
    
    def _on_show_player_stats(self, player_name):
        """Muestra estadísticas detalladas del jugador"""
        stats = self.get_player_stats(player_name)
        historical_stats = self._get_historical_stats(player_name)
        
        if stats:
            # Obtener información detallada de fuentes
            sources_info = self._get_sources_info(player_name)
            
            # Información base
            info_text = f"""Estadísticas de {player_name}:
            
• Total stalls: {stats['count']}
• Fuentes que reportan: {sources_info['count']} usuarios
• Primera vez: {stats['first_seen'].strftime('%H:%M:%S')}
• Última vez: {stats['last_seen'].strftime('%H:%M:%S')}
• Duración: {stats['duration_minutes']} minutos
• Promedio: {stats['avg_per_minute']} stalls/min"""
            
            # Añadir información histórica si existe
            if 'historical' in historical_stats:
                historical_data = historical_stats['historical']
                info_text += f"""
• Detecciones históricas: {historical_data['detection_count']}
• Multiplicador TTL: x{historical_data['base_ttl_multiplier']}"""
            
            info_text += f"""

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
        """Elimina un jugador específico y aplica filtro"""
        with self.data_lock:
            if player_name in self.stalled_data:
                # Aplicar filtro primero
                self._on_filter_player_stalled(player_name)
                
                # Eliminar del dataset
                del self.stalled_data[player_name]
                
                # Notificar éxito
                message_bus.publish(
                    content=f"Jugador {player_name} eliminado y filtrado",
                    level=MessageLevel.INFO
                )
                
                # Actualizar UI
                wx.CallAfter(self._refresh_ui)
            else:
                # Jugador no encontrado
                message_bus.publish(
                    content=f"Jugador {player_name} no encontrado en la lista",
                    level=MessageLevel.WARNING
                )
    
    def _on_reset(self, event):
        """Limpia la lista con confirmación visual"""
        count = len(self.stalled_data)
        historical_count = len(self.historical_cache)
        total_count = count + historical_count
        
        if total_count > 0:
            # Mostrar confirmación si hay datos
            message = f"¿Limpiar {count} jugadores activos y {historical_count} históricos de la lista stalled?"
            dlg = wx.MessageDialog(
                self, 
                message,
                "Confirmar Reset",
                wx.YES_NO | wx.ICON_QUESTION
            )
            
            if dlg.ShowModal() == wx.ID_YES:
                with self.data_lock:
                    self.stalled_data.clear()
                    self.historical_cache.clear()
                
                wx.CallAfter(self._refresh_ui)
                
                message_bus.publish(
                    content=f"Lista de {total_count} usuarios stalled reiniciada",
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