#!/usr/bin/env python
from concurrent.futures import ThreadPoolExecutor
import uuid
import json
from datetime import datetime
import threading
import time
import traceback  # Añadido para rastrear mejor los errores
import asyncio  # Añadido para manejar coroutines

# Import Supabase manager
from helpers.core.supabase_manager import supabase_manager
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.services.notification_manager import NotificationManager

# Variable global para almacenar el singleton de RealtimeBridge
_realtime_bridge_instance = None

# Función auxiliar global para ejecutar coroutines desde otros módulos
def run_coroutine(coroutine):
    """
    Ejecuta una coroutine utilizando el bucle de eventos del RealtimeBridge singleton.
    Esta función debe usarse desde otros módulos que necesiten ejecutar código asíncrono.
    
    Args:
        coroutine: La coroutine a ejecutar
        
    Returns:
        El resultado de la coroutine
    """
    global _realtime_bridge_instance
    
    # Si no hay instancia, iniciamos un bucle de eventos temporal
    if _realtime_bridge_instance is None or not _realtime_bridge_instance.event_loop_running:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no event loop is available in current thread, create a new one
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(coroutine)
    
    # Si ya existe una instancia con un bucle de eventos, la usamos
    return _realtime_bridge_instance._run_in_loop(coroutine)

class RealtimeBridge:
    """Puente de comunicación en tiempo real para SCLogAnalyzer.
    El filtro de mensajes 'stalled' es controlado por la UI pero reside como propiedad en el backend (esta clase).
    La UI debe modificar el atributo 'filter_stalled_if_online' en la instancia singleton para activar/desactivar el filtro en tiempo real.
    """
    @staticmethod
    def get_instance():
        # Asume que _realtime_bridge_instance está definido a nivel de módulo
        # y se asigna en __init__ de RealtimeBridge
        return _realtime_bridge_instance

    def __init__(self, supabase_client, config_manager, use_singleton=True):
        if use_singleton:
            global _realtime_bridge_instance
            _realtime_bridge_instance = self
            
        # We'll use the async client instead of the passed sync client
        self.sync_supabase = supabase_client  # Keep reference to sync client
        # Get the async client - inicialmente None, lo obtendremos en connect()
        self.supabase = None
        
        self.config_manager = config_manager
        self.username = config_manager.get('username', None)  # Default to None instead of 'Unknown'
        self.shard = None
        self.version = None
        self.channels = {}
        self.is_connected = False
        self.heartbeat_active = False
        self.heartbeat_thread = None
        # Usar el intervalo configurable o el valor por defecto de 30 segundos (cambiado de 120)
        self.heartbeat_interval = int(config_manager.get('active_users_update_interval', 30))  # Segundos
        
        # Nuevo: thread y loop dedicados para asyncio
        self.event_loop = None
        self.event_loop_thread = None
        self.event_loop_running = False
        
        # Nuevo: diccionario para almacenar la última actividad de cada usuario
        self.last_activity = {}  # username -> last ping timestamp
        # New: track last ping from any user
        self._last_any_ping = datetime.utcnow()
        self._ping_missing_check_active = False
        self._ping_missing_thread = None
        self._ping_missing_event_emitted = False
        # Nuevo: filtro de mensajes 'stalled' controlado por la UI
        self.filter_stalled_if_online = True  # Controlado por la UI, usado solo aquí
        self.filter_broadcast_usernames = set()  # Controlado por la UI, usado solo aquí
        self.excluded_remote_content = set() # Para filtro de contenido
        
        # Filtros globales modo/shard (movidos desde ConnectedUsersPanel)
        self.filter_by_current_mode = False
        self.filter_by_current_shard = False
        self.include_unknown_mode = True
        self.include_unknown_shard = True
        self.current_mode = "Unknown"
        self.current_shard = "Unknown"
        
        
        # Nuevo: Lock de reconexión y estado
        self._reconnect_lock = threading.Lock()
        self._reconnect_in_progress = False  # (opcional, para logging)
        
        
        # Nuevo: NotificationManager para notificaciones de eventos relevantes
        self.notification_manager = NotificationManager(config_manager)
        # Suscribirse a los eventos del MessageBus local que nos interesa compartir
        message_bus.on("shard_version_update", self._handle_shard_version_update)
        message_bus.on("realtime_event", self._handle_realtime_event)
        message_bus.on("username_change", self.set_username)  # Subscribe to existing username_change events
        # Subscribe to force_realtime_reconnect event for log truncation/reset
        message_bus.on("realtime_disconnect", self._handle_realtime_disconnect)
        
    def set_username(self, username, old_username=None):
        """Sets or updates the username and connects if needed"""
        # Solo reconectar si el username es válido y diferente al anterior
        if self.username == username:
            return  # No change needed
        if username is None or username == "Unknown":
            self.username = username
            return
        old_username_val = self.username
        self.username = username
        
        message_bus.publish(
            content=f"Username updated to: {username}",
            level=MessageLevel.DEBUG,
            metadata={"source": "realtime_bridge"}
        )
        
        # If we already have a connection but username changed, reconnect
        if self.is_connected:
            self.disconnect()
            self.connect()
        # Si no hay conexión y ahora hay username válido, conectar
        elif not self.is_connected and username:
            self.connect()
        
    def connect(self):
        """Inicializa la conexión con Supabase Realtime usando un solo canal 'general' para presencia y broadcast"""
        if not self.username:
            message_bus.publish(
                content="Cannot connect Realtime Bridge: username not set",
                level=MessageLevel.WARNING,
                metadata={"source": "realtime_bridge"}
            )
            return False
        try:
            self._start_event_loop()
            self.supabase = supabase_manager.get_async_client(self.username)
            if not self.supabase:
                message_bus.publish(
                    content="Failed to get async Supabase client, cannot connect Realtime Bridge",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
                return False
            message_bus.publish(
                content="Successfully obtained async Supabase client",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            self._init_general_channel()
            self.is_connected = True
            self._start_heartbeat()
            self._start_ping_missing_check()  # Start ping absence checker
            message_bus.publish(
                content="Realtime Bridge connected successfully (general channel)",
                level=MessageLevel.INFO,
                metadata={"source": "realtime_bridge"}
            )
            return True
        except Exception as e:
            message_bus.publish(
                content=f"Error connecting Realtime Bridge: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            message_bus.publish(
                content=f"Traceback: {traceback.format_exc()}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            self.is_connected = False
            return False

    def disconnect(self):
        """Desconecta de Supabase Realtime y limpia todos los recursos async y threads."""
        try:
            # Detener el heartbeat
            self._stop_heartbeat()
            self._stop_ping_missing_check()  # Stop ping absence checker

            # Desconectar todos los canales primero
            for channel in self.channels.values():
                self._run_in_loop(channel.unsubscribe())
            self.channels = {}

            # Ahora cerrar cliente async si existe y el event loop está abierto
            if self.supabase:
                try:
                    loop = self.event_loop
                    if loop and loop.is_running() and not loop.is_closed():
                        self._run_in_loop(self.supabase.realtime.close())
                        message_bus.publish(
                            content="RealtimeBridge: async client closed",
                            level=MessageLevel.DEBUG,
                            metadata={"source": "realtime_bridge"}
                        )
                    else:
                        message_bus.publish(
                            content="RealtimeBridge: Event loop is closed or not running, skipping async client close",
                            level=MessageLevel.WARNING,
                            metadata={"source": "realtime_bridge"}
                        )
                except Exception as e:
                    message_bus.publish(
                        content=f"RealtimeBridge: Error closing async client: {e}",
                        level=MessageLevel.ERROR,
                        metadata={"source": "realtime_bridge"}
                    )
                self.supabase = None

            # Detener el bucle de eventos dedicado
            self._stop_event_loop()

            self.is_connected = False

            message_bus.publish(
                content="Realtime Bridge disconnected",
                level=MessageLevel.INFO,
                metadata={"source": "realtime_bridge"}
            )
            
            return True
        except Exception as e:
            message_bus.publish(
                content=f"Error disconnecting Realtime Bridge: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            return False
            
    def _start_event_loop(self):
        """Inicia un thread dedicado para ejecutar el bucle de eventos asyncio"""
        if self.event_loop_running:
            return  # Ya está en ejecución
            
        def run_event_loop_forever():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.event_loop = loop
            
            message_bus.publish(
                content="Dedicated asyncio event loop started",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            
            try:
                # Ejecutar el bucle de eventos indefinidamente
                loop.run_forever()
            except Exception as e:
                message_bus.publish(
                    content=f"Error in event loop thread: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
            finally:
                loop.close()
                self.event_loop = None
                message_bus.publish(
                    content="Dedicated asyncio event loop closed",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
                
        self.event_loop_running = True
        self.event_loop_thread = threading.Thread(target=run_event_loop_forever, daemon=True)
        self.event_loop_thread.start()
        
        # Un pequeño retraso para asegurarse de que el bucle esté listo
        time.sleep(0.5)
        
    def _stop_event_loop(self):
        """Detiene el bucle de eventos dedicado"""
        if not self.event_loop_running:
            return
            
        self.event_loop_running = False
        
        if self.event_loop:
            # Programar la detención del bucle desde dentro del mismo bucle
            if hasattr(self.event_loop, 'call_soon_threadsafe'):
                self.event_loop.call_soon_threadsafe(self.event_loop.stop)
            
        if self.event_loop_thread and self.event_loop_thread.is_alive():
            self.event_loop_thread.join(timeout=3)
            
        self.event_loop_thread = None
            
    def _run_in_loop(self, coroutine):
        """Ejecuta una coroutine en el bucle de eventos dedicado"""
        if not self.event_loop or not self.event_loop_running:
            # Si no hay un bucle de eventos dedicado, usamos el método estándar
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                # If no event loop is available in current thread, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            return loop.run_until_complete(coroutine)
            
        # Crear un objeto Future para obtener el resultado
        future = asyncio.run_coroutine_threadsafe(coroutine, self.event_loop)
        return future.result(10)  # Timeout de 10 segundos
        
    def _build_presence_dict(self, username=None, shard=None, version=None, status=None, mode=None):
        """Builds the presence dictionary for track() calls."""
        return {
            'username': username if username is not None else self.username,
            'shard': shard if shard is not None else self.shard,
            'version': version if version is not None else self.version,
            'status': status if status is not None else 'online',
            'mode': mode if mode is not None else getattr(self, 'current_mode', None)
        }

    def _init_general_channel(self):
        """Inicializa el canal 'general' para presencia y broadcast"""
        try:
            general_channel = self.supabase.realtime.channel('general', {
                'config': {
                    'presence': {'key': self.username},
                    'broadcast': {'self': True}
                }
            })
            def on_subscribe(status, err=None):
                if status == 'SUBSCRIBED':
                    initial_presence = self._build_presence_dict()
                    try:
                        asyncio.create_task(general_channel.track(initial_presence))
                        message_bus.publish(
                            content="Connected to general channel (presencia+broadcast)",
                            level=MessageLevel.DEBUG,
                            metadata={"source": "realtime_bridge"}
                        )
                        # Enviar mensaje broadcast inicial de conexión
                    except Exception as e:
                        message_bus.publish(
                            content=f"Error tracking initial presence: {e}",
                            level=MessageLevel.ERROR,
                            metadata={"source": "realtime_bridge"}
                        )
            # Callbacks de presencia
            general_channel.on_presence_sync(
                callback=lambda: self._handle_presence_sync(general_channel)
            )
            general_channel.on_presence_join(
                callback=lambda key, current, new: self._handle_presence_join(key, current, new)
            )
            general_channel.on_presence_leave(
                callback=lambda key, current, left: self._handle_presence_leave(key, current, left)
            )
            # Callbacks de broadcast
            general_channel.on_broadcast(
                event="realtime-event",
                callback=self._handle_realtime_event_broadcast
            )
            self._run_in_loop(general_channel.subscribe(on_subscribe))
            self.channels = {'general': general_channel}
            self._handle_realtime_event({
                'username': self.username,
                'timestamp': datetime.now().isoformat(),
                'shard': self.shard,
                'version': self.version,
                'last_active': datetime.now().isoformat(),
                'metadata': {'content': 'Connected to general channel', 'type': 'info'}
            })
            
            message_bus.publish(
                content="Initialized general channel (presencia+broadcast)",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error initializing general channel: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _handle_shard_version_update(self, shard, version, username, mode=None, private=None):
        """Maneja actualizaciones de shard y versión para sincronizarlas con Realtime, ahora con info de lobby privado."""
        self.shard = shard
        self.version = version
        self.current_mode = mode  # Mantener actualizado el modo
        # Se puede usar el argumento 'private' para lógica futura si se requiere
        if 'general' in self.channels and self.channels['general']:
            state = self.channels['general'].presence.state
            if username in state:
                if len(state[username]) \
                    and state[username][0].get('metadata', {}).get('mode') == mode \
                    and state[username][0].get('shard') == shard:
                    return
        if 'general' in self.channels and self.channels['general'] and username != 'Unknown':
            presence_data = self._build_presence_dict(username=username, shard=shard, version=version, mode=mode)
            try:
                self._run_in_loop(self.channels['general'].track(presence_data))
                message_bus.publish(
                    content=f"Updated presence status with shard: {shard}, version: {version}, mode: {mode}, private: {private}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
            except Exception as e:
                message_bus.publish(
                    content=f"Error updating presence status: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )

    def _handle_presence_sync(self, channel):
        """Maneja la sincronización de estados de presencia. Usa la hora de última actividad basada en pings si está disponible."""
        try:
            presence_state = channel.presence.state
            users_online = []
            for username, presences in presence_state.items():
                for presence in presences:
                    last_active = self.last_activity.get(username, presence.get('last_active'))
                    users_online.append({
                        'username': username,
                        'shard': presence.get('shard'),
                        'version': presence.get('version'),
                        'status': presence.get('status'),
                        'mode': presence.get('mode'),
                        'last_active': last_active.strftime('%Y-%m-%d %H:%M:%S') if last_active else None,
                        'metadata': presence.get('metadata', {})
                    })
            message_bus.emit("users_online_updated", users_online)
            message_bus.publish(
                content=f"Users online updated: {len(users_online)} users",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error handling presence sync: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _handle_presence_join(self, key, current, new):
        """Maneja cuando un nuevo usuario se une al canal de presencia"""
        try:
            for presence in new:
                username = presence.get('username')
                message_bus.publish(
                    content=f"User '{username}' is now online",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge", "event": "user_joined"}
                )
            if 'general' in self.channels:
                self._handle_presence_sync(self.channels['general'])
        except Exception as e:
            message_bus.publish(
                content=f"Error handling presence join: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _handle_presence_leave(self, key, current, left):
        """Maneja cuando un usuario deja el canal de presencia"""
        try:
            for presence in left:
                username = presence.get('username')
                message_bus.publish(
                    content=f"User '{username}' went offline",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge", "event": "user_left"}
                )
            if 'general' in self.channels:
                self._handle_presence_sync(self.channels['general'])
        except Exception as e:
            message_bus.publish(
                content=f"Error handling presence leave: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _handle_realtime_event(self, event_data):
        """Maneja el evento de realtime_event para transmitirlo a todos los usuarios"""
            
        try:
            # Transmitir el evento en tiempo real a todos los usuarios
            # Incluimos el shard en los datos para posible filtrado en el cliente
            broadcast_data = {
                'username': self.username,
                'timestamp': datetime.now().isoformat(),
                'shard': self.shard,  # Incluir shard en los datos
                'event_data': event_data
            }
            
            # Usar el canal broadcast común en lugar de canales por shard
            if 'general' in self.channels:
                self._run_in_loop(self.channels['general'].send_broadcast('realtime-event', broadcast_data))
                
                message_bus.publish(
                    content=f"Broadcasted realtime event to all users (from shard {self.shard})",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
            else:
                message_bus.publish(
                    content="General channel not initialized, cannot send realtime event",
                    level=MessageLevel.WARNING,
                    metadata={"source": "realtime_bridge"}
                )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error broadcasting realtime event: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _handle_realtime_event_broadcast(self, payload):
        """Maneja los mensajes broadcast de eventos en tiempo real recibidos de otros usuarios.
        Aplica el filtro de 'stalled' si está activado en el singleton (controlado por la UI, almacenado en self).
        Aplica el filtro de usuarios online si filter_broadcast_usernames no está vacío (controlado por la UI).
        Aplica filtro de contenido excluido.
        """
        try:
            # Extraer datos del mensaje
            broadcast_data = payload.get('payload', {})
            username = broadcast_data.get('username','Unknown')
            event_data = broadcast_data.get('event_data', payload)

            # Debug: ver la estructura del evento recibido
            message_bus.publish(
                content=f"Received event_data: type={event_data.get('type')}, keys={list(event_data.keys())}",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge", "action": "debug_event_structure"}
            )

            # Interceptar perfiles recibidos y almacenar en cache
            if event_data.get('type') == 'actor_profile':
                # Buscar player_name en raw_data, no directamente en event_data
                player_name = event_data.get('raw_data', {}).get('player_name')
                if player_name:
                    message_bus.publish(
                        content=f"Processing actor_profile for {player_name} from {username}",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "realtime_bridge", "action": "processing_profile"}
                    )
                    # Emitir actor_profile para que _on_actor_profile lo procese
                    metadata = {
                        'action': 'broadcast',
                        'source_user': username,
                        'raw_data': event_data.get('raw_data', {})
                    }
                    message_bus.emit('actor_profile', 
                                    player_name, 
                                    event_data.get('raw_data', {}).get('org', 'Unknown'), 
                                    event_data.get('raw_data', {}).get('enlisted', 'Unknown'), 
                                    metadata)
                    message_bus.publish(
                        content=f"Profile for {player_name} received from {username}",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "realtime_bridge"}
                    )

            # --- FILTROS GLOBALES MODO/SHARD ---
            if not self._passes_global_filters(event_data):
                return  # SUPRIMIR el mensaje

            # --- FILTRO DE CONTENIDO EXCLUIDO ---
            event_content = event_data.get('content') # O event_data['metadata'].get('content') según estructura
            if event_content and event_content in self.excluded_remote_content:
                # Opcional: loguear a DEBUG si se quiere saber que algo se filtró, pero el plan dice no loguear
                # message_bus.publish(
                #     content=f"Evento remoto filtrado de {username} por exclusión de contenido: {event_content[:70]}...",
                #     level=MessageLevel.DEBUG,
                #     metadata={\"source\": \"realtime_bridge\", \"filtered_content\": event_content}
                # )
                return # No emitir este evento en el bus de mensajes local

            # --- FILTRO DE USUARIO ONLINE ---
            if self.filter_broadcast_usernames:
                if username not in self.filter_broadcast_usernames:
                    message_bus.publish(
                        content=f"Mensaje broadcast filtrado por usuario online: {username}",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "realtime_bridge", "filter": "user_online"}
                    )
                    return  # SUPRIMIR el mensaje

            # --- FILTRO DE 'STALLED' CONTROLADO POR ATRIBUTO BACKEND ---
            if self.filter_stalled_if_online and event_data.get('type') == 'actor_stall':
                users_online = []
                try:
                    if 'general' in self.channels:
                        state = self.channels['general'].presence.state
                        users_online = list(state.keys())
                except Exception:
                    pass
                player = event_data.get('raw_data',{}).get('player')
                if player and player in users_online:
                    return  # SUPRIMIR el mensaje

            # Filtrar y procesar pings
            if event_data.get('type') == 'ping':
                username = event_data.get('username')
                timestamp = event_data.get('timestamp')
                if username and timestamp:
                    self.last_activity[username] = datetime.now()
                try:
                    self._last_any_ping = datetime.utcnow()
                    self._ping_missing_event_emitted = False
                except Exception:
                    pass
                return
            elif self.notification_manager.config_manager.get('notifications_enabled', True) \
                and event_data.get('type') in self.notification_manager.notifications_events:
                message_bus.emit("show_windows_notification", event_data.get('content', ''))


            message_bus.emit("remote_realtime_event", username, event_data)

        except Exception as e:
            message_bus.publish(
                content=f"Error handling realtime event broadcast: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )

    def _start_heartbeat(self):
        """Inicia el heartbeat para mantener actualizada la información de presencia"""
        if self.heartbeat_active:
            return
            
        self.heartbeat_active = True
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self.heartbeat_thread.start()
        
        message_bus.publish(
            content=f"Started heartbeat thread with {self.heartbeat_interval}s interval",
            level=MessageLevel.DEBUG,
            metadata={"source": "realtime_bridge"}
        )
        
    def _stop_heartbeat(self):
        """Detiene el heartbeat"""
        self.heartbeat_active = False
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join(timeout=5)
            
        message_bus.publish(
            content="Stopped heartbeat thread",
            level=MessageLevel.DEBUG,
            metadata={"source": "realtime_bridge"}
        )
        
    def _heartbeat_loop(self):
        """Bucle de heartbeat: además de la lógica de presencia, emite un ping broadcast con timestamp actual."""
        while self.heartbeat_active:
            try:
                # Solo actualizar si tenemos información de shard e información de presencia
                if 'general' in self.channels and self.channels['general'] and self.username != 'Unknown':
                    presence_data = self._build_presence_dict()
                    self._run_in_loop(self.channels['general'].track(presence_data))
                    message_bus.publish(
                        content="Heartbeat presence update sent",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "realtime_bridge"}
                    )
                
                # Emitir ping broadcast
                ping_msg = {
                    'type': 'ping',
                    'username': self.username,
                    'timestamp': datetime.now().isoformat(),
                }
                self._handle_realtime_event(ping_msg)
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error in heartbeat worker: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
                
            # Esperar hasta el próximo intervalo
            for i in range(self.heartbeat_interval):
                if not self.heartbeat_active:
                    break
                time.sleep(1)

    def _start_ping_missing_check(self):
        if self._ping_missing_check_active:
            return
        self._ping_missing_check_active = True
        self._ping_missing_thread = threading.Thread(target=self._ping_missing_loop, daemon=True)
        self._ping_missing_thread.start()

    def _stop_ping_missing_check(self):
        self._ping_missing_check_active = False
        if self._ping_missing_thread and self._ping_missing_thread.is_alive():
            self._ping_missing_thread.join(timeout=3)
        self._ping_missing_thread = None
        message_bus.publish(
            content="Stopped ping missing thread",
            level=MessageLevel.DEBUG,
            metadata={"source": "realtime_bridge"}
        )

    def _ping_missing_loop(self):
        while self._ping_missing_check_active:
            try:
                now = datetime.utcnow()
                delta = (now - self._last_any_ping).total_seconds()
                if delta > 120:
                    if not self._ping_missing_event_emitted:
                        message_bus.emit("broadcast_ping_missing")
                        message_bus.publish(
                            content="No ping received from any user in over 120 seconds (broadcast_ping_missing emitted)",
                            level=MessageLevel.WARNING,
                            metadata={"source": "realtime_bridge"}
                        )
                        self._ping_missing_event_emitted = True
                        # --- Auto reconnection logic ---
                        auto_reconnection = self.config_manager.get('auto_reconnection', True)
                        if auto_reconnection:
                            message_bus.publish(
                                content="Auto-reconnection enabled: attempting to reconnect...",
                                level=MessageLevel.INFO,
                                metadata={"source": "realtime_bridge"}
                            )
                            with ThreadPoolExecutor(max_workers=1) as executor:
                                # Ejecutar reconexión en un thread separado para no bloquear el bucle de eventos
                                f = executor.submit(self.reconnect)
                                # Iniciar reconexión en un thread separado
                                result = f.result()
                                
                            if result:
                                message_bus.emit("realtime_reconnected")
                                message_bus.publish(
                                    content="RealtimeBridge: reconnection successful (event emitted)",
                                    level=MessageLevel.INFO,
                                    metadata={"source": "realtime_bridge"}
                                )
                            else:
                                message_bus.publish(
                                    content="RealtimeBridge: reconnection failed",
                                    level=MessageLevel.ERROR,
                                    metadata={"source": "realtime_bridge"}
                                )
                else:
                    self._ping_missing_event_emitted = False
            except Exception:
                pass
            time.sleep(5)

    def _handle_realtime_disconnect(self, *args, **kwargs):
        """Handle force_realtime_reconnect event: tras reset/truncado solo se desconecta, no se reconecta."""
        if not self.is_connected:
            return
        self.disconnect()

    def reconnect(self):
        """
        Low-level reconnect: closes and reopens the async Supabase client y resuscribe el canal general.
        Protegido contra concurrencia: solo una reconexión puede ejecutarse a la vez.
        Si ya hay una reconexión en curso, la petición se ignora y se emite un aviso por MessageBus.
        """
        if not self._reconnect_lock.acquire(blocking=False):
            message_bus.publish(
                content="RealtimeBridge: reconnection already in progress, ignoring request",
                level=MessageLevel.WARNING,
                metadata={"source": "realtime_bridge"}
            )
            return False
        self._reconnect_in_progress = True
        try:
            message_bus.publish(
                content="RealtimeBridge: reconnect requested",
                level=MessageLevel.INFO,
                metadata={"source": "realtime_bridge"}
            )
            # Siempre llamar a disconnect para limpieza total
            self.disconnect()
            # Ya no se cierra el cliente async aquí, eso ocurre en disconnect
            self.connect()
            message_bus.publish(
                content="RealtimeBridge: reconnect completed (disconnect + connect)",
                level=MessageLevel.INFO,
                metadata={"source": "realtime_bridge"}
            )
            return True
        except Exception as e:
            message_bus.publish(
                content=f"RealtimeBridge: Error during low-level reconnect: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            return False
        finally:
            self._reconnect_in_progress = False
            self._reconnect_lock.release()

    def update_content_exclusions(self, content_to_exclude=None, clear_all=False, add=True):
        if clear_all:
            if self.excluded_remote_content: # Solo actuar si realmente había algo que limpiar
                self.excluded_remote_content.clear()
                # NINGÚN LOG AQUÍ
        elif content_to_exclude:
            if add:
                if content_to_exclude not in self.excluded_remote_content:
                    self.excluded_remote_content.add(content_to_exclude)
                    message_bus.publish(
                        content=f"Filtro de contenido remoto añadido: '{content_to_exclude[:70]}...'",
                        level=MessageLevel.INFO,
                        metadata={"source": "realtime_bridge"}
                    )
            else: 
                if content_to_exclude in self.excluded_remote_content:
                    self.excluded_remote_content.discard(content_to_exclude)
                    # NINGÚN LOG AQUÍ

    def get_active_content_exclusions(self):
        return sorted(list(self.excluded_remote_content))
    
    def update_mode_shard_filters(self, **kwargs):
        """Actualiza filtros globales de modo/shard con kwargs elegantes"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
    def _passes_global_filters(self, event_data):
        """Filtros globales de modo/shard (movidos desde ConnectedUsersPanel)"""
        raw_data = event_data.get('raw_data', {})
        unknown_values = [None, "", "Unknown"]
        
        # Filtro de modo
        if self.filter_by_current_mode:
            mode_value = raw_data.get('mode')
            if mode_value in unknown_values:
                if not self.include_unknown_mode:
                    return False
            elif mode_value != self.current_mode:
                return False
        
        # Filtro de shard
        if self.filter_by_current_shard:
            shard_value = raw_data.get('shard')
            if shard_value in unknown_values:
                if not self.include_unknown_shard:
                    return False
            elif shard_value != self.current_shard:
                return False
        
        return True