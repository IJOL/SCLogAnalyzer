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
        reset_btn = DarkThemeButton(self, label="🔄 Reset", size=(50, 25))
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
        """NEW TTL calculation with 300s initial and max 600s"""
        
        # PHASE 1: Base TTL (300s for first appearance)
        if self._is_first_appearance(player_name):
            base_ttl = 300  # 5 minutes for new sightings
        else:
            base_ttl = 200  # 3.33 minutes for returning players
        
        # PHASE 2: Conservative increments
        sources_count = len(player_data['sources'])
        total_stalls = player_data['count']
        
        # Modest source bonuses: +30s per additional reporter (max 4 sources = +90s)
        if sources_count > 1:
            source_bonus = min((sources_count - 1) * 30, 90)
            base_ttl += source_bonus
        
        # Small stall increments: +2s per additional stall (max 50 stalls = +100s) 
        if total_stalls > 1:
            stall_bonus = min((total_stalls - 1) * 2, 100)
            base_ttl += stall_bonus
        
        # PHASE 3: Historical persistence bonus (modest)
        historical_detections = player_data.get('historical_detections', 0)
        if historical_detections > 0:
            # +10s per historical detection (max +50s)
            history_bonus = min(historical_detections * 10, 50)
            base_ttl += history_bonus
        
        # PHASE 4: Apply maximum limit
        final_ttl = min(base_ttl, 600)  # Maximum 10 minutes
        
        return final_ttl
    
    def _is_first_appearance(self, player_name):
        """Check if this is the first appearance of a player"""
        return player_name not in self.historical_cache
    
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
    
    def _calculate_activity_intensity(self, player_data):
        """Calculate color intensity based on sighting count and reporter diversity"""
        
        # METRIC 1: Total sighting frequency
        total_stalls = player_data['count']
        stall_score = min(total_stalls / 10.0, 1.0)  # Normalize to 0-1 (10+ stalls = max)
        
        # METRIC 2: Reporter diversity  
        sources_count = len(player_data['sources'])
        diversity_score = min(sources_count / 4.0, 1.0)  # Normalize to 0-1 (4+ sources = max)
        
        # METRIC 3: Recent activity (last 2 minutes instead of 90s)
        recent_activity = self._count_recent_activity(player_data, window_seconds=120)
        recent_score = min(recent_activity / 8.0, 1.0)  # Normalize to 0-1 (8+ recent = max)
        
        # COMPOSITE INTENSITY: Weighted combination
        intensity = (
            stall_score * 0.4 +      # 40% weight on total activity
            diversity_score * 0.35 + # 35% weight on reporter diversity  
            recent_score * 0.25      # 25% weight on recent activity
        )
        
        return intensity  # Returns 0.0 to 1.0
    
    def _intensity_to_color(self, intensity):
        """Convert intensity (0-1) to background color"""
        
        if intensity >= 0.8:    # High intensity (80-100%)
            return wx.Colour(180, 30, 30)   # Dark red
        elif intensity >= 0.6:  # Medium-high intensity (60-80%)
            return wx.Colour(140, 40, 40)   # Medium red
        elif intensity >= 0.4:  # Medium intensity (40-60%)
            return wx.Colour(100, 50, 50)   # Light red
        elif intensity >= 0.2:  # Low intensity (20-40%)
            return wx.Colour(80, 60, 60)    # Very light red
        else:                   # Minimal intensity (0-20%)
            return wx.Colour(80, 80, 80)    # Normal dark theme background
    
    def _count_recent_activity(self, player_data, window_seconds=120):
        """Count activity within the specified time window"""
        recent_detections = 0
        current_time = datetime.now()
        
        for source_data in player_data['sources'].values():
            time_diff = current_time - source_data['last_seen']
            if time_diff.total_seconds() <= window_seconds:
                recent_detections += source_data['count']
        
        return recent_detections
    
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
                
                # Better TTL display formatting for longer times
                if ttl_seconds <= 0:
                    ttl_display = "0s"
                elif ttl_seconds < 60:
                    ttl_display = f"{ttl_seconds}s"
                elif ttl_seconds < 600:  # Less than 10 minutes
                    minutes = ttl_seconds // 60
                    seconds = ttl_seconds % 60
                    ttl_display = f"{minutes}:{seconds:02d}"
                else:  # 10+ minutes
                    minutes = ttl_seconds // 60
                    ttl_display = f"{minutes}m"
                
                # Información de fuentes
                sources_count = len(data['sources'])
                last_source = data['last_source']
                
                # More readable "time ago" format for longer TTL times
                seconds_ago = int(time_since_last.total_seconds())
                if seconds_ago < 60:
                    last_display = "ahora" if seconds_ago < 30 else f"{seconds_ago}s"
                else:
                    minutes_ago = int(seconds_ago / 60)
                    if minutes_ago == 1:
                        last_display = "1min"
                    elif minutes_ago < 10:
                        last_display = f"{minutes_ago}min"
                    else:
                        last_display = f"{minutes_ago}m"
                
                # Add activity indicator to player name (visual only)
                activity_intensity = self._calculate_activity_intensity(data)
                if activity_intensity >= 0.6:    # High activity
                    player_display = f"● {player}"  # Filled circle
                elif activity_intensity >= 0.3:  # Medium activity  
                    player_display = f"◐ {player}"  # Half-filled circle
                elif activity_intensity > 0.1:   # Low activity
                    player_display = f"○ {player}"  # Empty circle
                else:                           # Minimal activity
                    player_display = f"  {player}"  # No indicator
                
                # Añadir fila con todas las columnas
                index = self.stalled_list.InsertItem(self.stalled_list.GetItemCount(), player_display)
                self.stalled_list.SetItem(index, 1, str(data['count']))           # Stalls
                self.stalled_list.SetItem(index, 2, str(sources_count))          # Fuentes  
                self.stalled_list.SetItem(index, 3, last_display)                # Último tiempo
                self.stalled_list.SetItem(index, 4, ttl_display)                 # TTL progresivo
                
                # Almacenar nombre limpio para acceso posterior
                self.row_to_player[index] = player
                
                # Apply background color based on activity intensity
                activity_intensity = self._calculate_activity_intensity(data)
                background_color = self._intensity_to_color(activity_intensity)
                self.stalled_list.SetItemBackgroundColour(index, background_color)
                
                # Text color: white for high intensity, light gray for low intensity
                if activity_intensity > 0.2:
                    self.stalled_list.SetItemTextColour(index, wx.Colour(255, 255, 255))
                else:
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