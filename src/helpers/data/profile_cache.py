"""
Sistema de Cache LRU para Perfiles de Jugadores
Implementa cache thread-safe con patrón singleton
"""

import threading
from datetime import datetime
from collections import OrderedDict
from typing import Optional, Dict, Any

from helpers import ensure_all_field

from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager


class ProfileCache:
    """
    Cache LRU thread-safe para perfiles de jugadores.
    Implementa patrón singleton para acceso global.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._cache_lock = threading.RLock()
            self._cache = OrderedDict()
            self._max_size = self._get_max_cache_size()
            self._initialized = True
    
    @classmethod
    def get_instance(cls):
        """Obtiene la instancia singleton del cache"""
        return cls()
    
    def _get_max_cache_size(self) -> int:
        """Obtiene el tamaño máximo del cache desde configuración"""
        try:
            config = get_config_manager()
            return int(config.get('profile_cache_max_size', 1000))
        except:
            return 1000
    
    def get_profile(self, player_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene un perfil del cache.
        
        Args:
            player_name: Nombre del jugador
            
        Returns:
            Dict con datos del perfil o None si no existe
        """
        with self._cache_lock:
            if player_name in self._cache:
                # Mover al final (más reciente)
                profile_data = self._cache.pop(player_name)
                self._cache[player_name] = profile_data
                
                # Actualizar última consulta
                profile_data['last_accessed'] = datetime.now()
                
                message_bus.publish(
                    content=f"Cache HIT for player {player_name}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "profile_cache", "action": "get"}
                )
                
                return profile_data.copy()
            
            message_bus.publish(
                content=f"Cache MISS for player {player_name}",
                level=MessageLevel.DEBUG,
                metadata={"source": "profile_cache", "action": "get"}
            )
            return None
    
    def add_profile(self, player_name: str, profile_data: Dict[str, Any], 
                   source_type: str = 'automatic', origin: str = 'unknown',
                   requested_by: str = 'unknown', source_user: str = 'unknown'):
        """
        Añade un perfil al cache.
        
        Args:
            player_name: Nombre del jugador
            profile_data: Datos del perfil
            source_type: 'automatic' o 'manual'
            origin: 'manual', 'killer', 'victim', 'broadcast_received'
            requested_by: Usuario que hizo la solicitud original
            source_user: Usuario fuente del perfil
        """
        with self._cache_lock:
            now = datetime.now()
            # Limpiar el perfil antes de guardar
            cache_entry = {
                'last_accessed': now,
                'profile_data': profile_data,
                'source_type': source_type,
                'origin': origin,
                'cached_at': now,
                'organization': profile_data.get('main_org_sid', 'Unknown'),
                'requested_by': requested_by,
                'source_user': source_user
            }
            
            # Si ya existe, actualizar
            if player_name in self._cache:
                self._cache.pop(player_name)
            
            # Añadir al final
            self._cache[player_name] = cache_entry
            
            # Aplicar límite LRU
            while len(self._cache) > self._max_size:
                oldest_player = next(iter(self._cache))
                removed_entry = self._cache.pop(oldest_player)
                message_bus.publish(
                    content=f"Cache evicted player {oldest_player} (LRU policy)",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "profile_cache", "action": "evict"}
                )
            
            message_bus.publish(
                content=f"Cache STORE for player {player_name} (source: {source_type}, origin: {origin})",
                level=MessageLevel.DEBUG,
                metadata={"source": "profile_cache", "action": "store"}
            )
            
            # Emitir evento profile_cached para que el widget se actualice
            message_bus.emit("profile_cached", player_name, cache_entry)
    
    def remove_profile(self, player_name: str) -> bool:
        """
        Elimina un perfil del cache.
        
        Args:
            player_name: Nombre del jugador
            
        Returns:
            True si se eliminó, False si no existía
        """
        with self._cache_lock:
            if player_name in self._cache:
                self._cache.pop(player_name)
                
                message_bus.publish(
                    content=f"Profile removed from cache: {player_name}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "profile_cache", "action": "remove"}
                )
                return True
            return False
    
    def clear_cache(self):
        """Limpia todo el cache"""
        with self._cache_lock:
            count = len(self._cache)
            self._cache.clear()
            
            message_bus.publish(
                content=f"Cache cleared: {count} profiles removed",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache", "action": "clear"}
            )
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del cache"""
        with self._cache_lock:
            return {
                'total_profiles': len(self._cache),
                'max_size': self._max_size,
                'usage_percent': (len(self._cache) / self._max_size) * 100,
                'profiles': list(self._cache.keys())
            }
    
    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Obtiene todos los perfiles del cache (para debugging)"""
        with self._cache_lock:
            return {name: data.copy() for name, data in self._cache.items()}
    
    def broadcast_all(self):
        """Envía todos los perfiles del cache a todos los usuarios conectados"""
        with self._cache_lock:
            profiles = list(self._cache.items())
        
        if not profiles:
            message_bus.publish(
                content="No profiles in cache to broadcast",
                level=MessageLevel.WARNING,
                metadata={"source": "profile_cache", "action": "broadcast_all"}
            )
            return
        
        broadcast_count = 0
        for player_name, cache_entry in profiles:
            try:
                self.broadcast_profile(player_name)
                broadcast_count += 1
            except Exception as e:
                message_bus.publish(
                    content=f"Error broadcasting profile {player_name}: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "profile_cache", "action": "broadcast_error", "player": player_name}
                )
        
        message_bus.publish(
            content=f"Broadcast completed: {broadcast_count}/{len(profiles)} profiles sent",
            level=MessageLevel.INFO,
            metadata={"source": "profile_cache", "action": "broadcast_all_complete", "count": broadcast_count}
        )
    
    def broadcast_profile(self, player_name: str):
        """Envía un perfil específico a todos los conectados via force_broadcast"""
        with self._cache_lock:
            if player_name not in self._cache:
                message_bus.publish(
                    content=f"Profile {player_name} not found in cache for broadcast",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_cache", "action": "broadcast_profile_not_found"}
                )
                return False
            
            cache_entry = self._cache[player_name]
            profile_data = cache_entry['profile_data']
        
        try:
            # Crear estructura completa para el broadcast
            broadcast_data = {
                'player_name': player_name,
                'org': profile_data.get('main_org_sid', 'Unknown'),
                'enlisted': profile_data.get('enlisted', 'Unknown'),
                'action': 'force_broadcast',
                **profile_data  # Incluir todos los datos del perfil
            }
            
            # Emitir evento para que log_analyzer lo procese
            message_bus.emit('force_broadcast_profile', player_name, broadcast_data)
            
            message_bus.publish(
                content=f"Requesting force broadcast for profile {player_name}",
                level=MessageLevel.INFO,
                metadata={"source": "profile_cache", "action": "force_broadcast_profile"}
            )
            
            return True
            
        except Exception as e:
            message_bus.publish(
                content=f"Error in force broadcast for profile {player_name}: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "profile_cache", "action": "force_broadcast_error"}
            )
            return False 
    
    def send_discord_message(self, player_name: str):
        """Envía un perfil específico a Discord"""
        with self._cache_lock:
            if player_name not in self._cache:
                message_bus.publish(
                    content=f"Profile {player_name} not found in cache for Discord",
                    level=MessageLevel.WARNING,
                    metadata={"source": "profile_cache", "action": "send_discord_not_found"}
                )
                return False
            cache_entry = self._cache[player_name]
            profile_data = cache_entry['profile_data']
            message_bus.emit("send_discord", profile_data, pattern_name="actor_profile")

