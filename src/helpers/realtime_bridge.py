#!/usr/bin/env python
import uuid
import json
from datetime import datetime
import threading
import time
import traceback  # Añadido para rastrear mejor los errores
import asyncio  # Añadido para manejar coroutines

# Import Supabase manager
from .supabase_manager import supabase_manager
from .message_bus import message_bus, MessageLevel

def run_async(coroutine):
    """Helper function to run a coroutine synchronously in the event loop"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        # If no event loop is available in current thread, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coroutine)

class RealtimeBridge:
    """
    Clase puente que conecta el MessageBus local con Supabase Realtime para
    permitir la comunicación entre diferentes instancias de SCLogAnalyzer.
    """
    def __init__(self, supabase_client, config_manager):
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
        # Usar el intervalo configurable o el valor por defecto de 120 segundos
        self.heartbeat_interval = config_manager.get('active_users_update_interval', 120)  # Segundos
        
        # Suscribirse a los eventos del MessageBus local que nos interesa compartir
        message_bus.on("shard_version_update", self._handle_shard_version_update)
        message_bus.on("realtime_event", self._handle_realtime_event)
        message_bus.on("username_change", self.set_username)  # Subscribe to existing username_change events
        
    def set_username(self, username, old_username=None):
        """Sets or updates the username and connects if needed"""
        if self.username == username:
            return  # No change needed
            
        self.username = username
        
        message_bus.publish(
            content=f"Username updated to: {username}",
            level=MessageLevel.DEBUG,
            metadata={"source": "realtime_bridge"}
        )
        
        # If we already have a connection but username changed, reconnect
        if self.is_connected:
            message_bus.publish(
                content="Username changed, reconnecting Realtime Bridge...",
                level=MessageLevel.INFO,
                metadata={"source": "realtime_bridge"}
            )
            self.disconnect()
            self.connect()
        # If we don't have a connection yet but now have a username, connect
        elif not self.is_connected and username:
            self.connect()
        
    def connect(self):
        """Inicializa la conexión con Supabase Realtime"""
        # Check if we have a valid username first
        if not self.username:
            message_bus.publish(
                content="Cannot connect Realtime Bridge: username not set",
                level=MessageLevel.WARNING,
                metadata={"source": "realtime_bridge"}
            )
            return False
            
        try:
            # Obtener el cliente asíncrono explícitamente
            self.supabase = run_async(supabase_manager.get_async_client())
            # Verificar si obtuvimos un cliente válido
            if not self.supabase:
                message_bus.publish(
                    content="Failed to get async Supabase client, cannot connect Realtime Bridge",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
                return False
                
            # Registrar la inicialización del cliente
            message_bus.publish(
                content="Successfully obtained async Supabase client",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            
            # Conectarse al canal de usuarios activos
            self._init_presence_channel()
            # Conectarse al canal de broadcast general
            self._init_broadcast_channel()
            self.is_connected = True
            
            # Iniciar el heartbeat para mantener actualizado el estado en el sistema de presencia
            self._start_heartbeat()
            
            message_bus.publish(
                content="Realtime Bridge connected successfully",
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
        """Desconecta de Supabase Realtime"""
        try:
            # Detener el heartbeat
            self._stop_heartbeat()
            
            # Desconectar todos los canales
            for channel_name, channel in self.channels.items():
                if hasattr(channel, 'unsubscribe'):
                    channel.unsubscribe()
            
            self.channels = {}
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
        
    def _init_presence_channel(self):
        """Inicializa el canal de presencia para rastrear usuarios activos"""
        try:
            presence_channel = self.supabase.channel('online-users', {
                'config': {
                    'presence': {
                        'key': self.username,
                    }
                }
            })
            
            # Define the subscription status callback
            def on_subscribe(status, err=None):
                if status == 'SUBSCRIBED':
                    # Registramos nuestra presencia inicial
                    initial_presence = {
                        'shard': self.shard,
                        'version': self.version,
                        'status': 'online',
                        'last_active': datetime.now().isoformat(),
                        'metadata': {}
                    }
                    
                    try:
                        # Don't use run_async here - this is already in an async context
                        asyncio.create_task(presence_channel.track(initial_presence))
                        
                        message_bus.publish(
                            content="Connected to Presence channel",
                            level=MessageLevel.INFO,
                            metadata={"source": "realtime_bridge"}
                        )
                    except Exception as e:
                        message_bus.publish(
                            content=f"Error tracking initial presence: {e}",
                            level=MessageLevel.ERROR,
                            metadata={"source": "realtime_bridge"}
                        )
            
            # Configurar manejadores de eventos de presencia usando los métodos específicos
            presence_channel.on_presence_sync(
                callback=lambda: self._handle_presence_sync(presence_channel)
            )
            presence_channel.on_presence_join(
                callback=lambda key, current, new: self._handle_presence_join({'newPresences': new})
            )
            presence_channel.on_presence_leave(
                callback=lambda key, current, left: self._handle_presence_leave({'leftPresences': left})
            )
            
            # Suscribirse al canal - usar run_async para manejar la coroutine
            run_async(presence_channel.subscribe(on_subscribe))
            
            self.channels['presence'] = presence_channel
            
            message_bus.publish(
                content="Initialized presence channel",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error initializing presence channel: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
        
    def _init_broadcast_channel(self):
        """Inicializa el canal de broadcast para mensajes generales"""
        try:
            broadcast_channel = self.supabase.channel('broadcast')
            
            # Define the subscription status callback
            def on_subscribe(status, err=None):
                if status == 'SUBSCRIBED':
                    message_bus.publish(
                        content="Connected to Broadcast channel",
                        level=MessageLevel.INFO,
                        metadata={"source": "realtime_bridge"}
                    )
            
            # Configurar manejadores de eventos de broadcast usando el método específico
            broadcast_channel.on_broadcast(
                event="realtime-event",
                callback=self._handle_realtime_event_broadcast
            )
            
            # Suscribirse al canal - usar run_async para manejar la coroutine
            run_async(broadcast_channel.subscribe(on_subscribe))
            
            self.channels['broadcast'] = broadcast_channel
            
            message_bus.publish(
                content="Initialized broadcast channel",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error initializing broadcast channel: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
        
    def _handle_shard_version_update(self, shard, version, username, mode=None):
        """Maneja actualizaciones de shard y versión para sincronizarlas con Realtime"""
        self.shard = shard
        self.version = version
        
        # Si ya estamos conectados a un canal de presencia, actualizar nuestro estado
        if 'presence' in self.channels and self.channels['presence']:
            presence_data = {
                'shard': shard,
                'version': version,
                'status': 'online',
                'last_active': datetime.now().isoformat(),
                'metadata': {'mode': mode}
            }
            
            try:
                # Actualizar nuestro estado en el canal de presencia
                run_async(self.channels['presence'].track(presence_data))
                
                message_bus.publish(
                    content=f"Updated presence status with shard: {shard}, version: {version}",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error updating presence status: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
            
    def _handle_presence_subscription(self, status, channel):
        """Maneja el estado de suscripción al canal de presencia"""
        if status == 'SUBSCRIBED':
            # Registramos nuestra presencia inicial
            initial_presence = {
                'shard': self.shard,
                'version': self.version,
                'status': 'online',
                'last_active': datetime.now().isoformat(),
                'metadata': {}
            }
            
            try:
                channel.track(initial_presence)
                
                message_bus.publish(
                    content="Connected to Presence channel",
                    level=MessageLevel.INFO,
                    metadata={"source": "realtime_bridge"}
                )
            except Exception as e:
                message_bus.publish(
                    content=f"Error tracking initial presence: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "realtime_bridge"}
                )
                
    def _handle_presence_sync(self, channel):
        """Maneja la sincronización de estados de presencia"""
        try:
            presence_state = channel.presence.state
            
            # Emitir evento con la lista actualizada de usuarios en línea
            users_online = []
            for user_id, presences in presence_state.items():
                for presence in presences:
                    users_online.append({
                        'user_id': user_id,
                        'shard': presence.get('shard'),
                        'version': presence.get('version'),
                        'status': presence.get('status'),
                        'last_active': presence.get('last_active'),
                        'metadata': presence.get('metadata', {})
                    })
            
            # Emitir un evento en el MessageBus local con la lista de usuarios conectados
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
        
    def _handle_presence_join(self, payload):
        """Maneja cuando un nuevo usuario se une al canal de presencia"""
        try:
            new_presences = payload.get('newPresences', [])
            
            for presence in new_presences:
                user_id = presence.get('key')
                message_bus.publish(
                    content=f"User '{user_id}' is now online",
                    level=MessageLevel.INFO,
                    metadata={"source": "realtime_bridge", "event": "user_joined"}
                )
            
            # También actualizamos la lista completa
            if 'presence' in self.channels:
                self._handle_presence_sync(self.channels['presence'])
                
        except Exception as e:
            message_bus.publish(
                content=f"Error handling presence join: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            
    def _handle_presence_leave(self, payload):
        """Maneja cuando un usuario deja el canal de presencia"""
        try:
            left_presences = payload.get('leftPresences', [])
            
            for presence in left_presences:
                user_id = presence.get('key')
                message_bus.publish(
                    content=f"User '{user_id}' went offline",
                    level=MessageLevel.INFO,
                    metadata={"source": "realtime_bridge", "event": "user_left"}
                )
            
            # También actualizamos la lista completa
            if 'presence' in self.channels:
                self._handle_presence_sync(self.channels['presence'])
                
        except Exception as e:
            message_bus.publish(
                content=f"Error handling presence leave: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
            
    def _handle_realtime_event(self, event_data):
        """Maneja el evento de realtime_event para transmitirlo a otros usuarios"""
        if not self.shard:  # No transmitimos si no sabemos nuestro shard
            return
            
        try:
            # Crear un canal específico para este shard si no existe
            shard_channel_name = f"shard:{self.shard}"
            if shard_channel_name not in self.channels:
                shard_channel = self.supabase.channel(shard_channel_name)
                shard_channel.subscribe()
                self.channels[shard_channel_name] = shard_channel
                
            # Transmitir el evento en tiempo real a otros usuarios en el mismo shard
            broadcast_data = {
                'user_id': self.username,
                'timestamp': datetime.now().isoformat(),
                'event_data': event_data
            }
            
            self.channels[shard_channel_name].send({
                'type': 'broadcast',
                'event': 'realtime-event',
                'payload': broadcast_data
            })
            
            message_bus.publish(
                content=f"Broadcasted realtime event to users in shard {self.shard}",
                level=MessageLevel.DEBUG,
                metadata={"source": "realtime_bridge"}
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error broadcasting realtime event: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "realtime_bridge"}
            )
        
    def _handle_realtime_event_broadcast(self, payload):
        """Maneja los mensajes broadcast de eventos en tiempo real recibidos de otros usuarios"""
        try:
            # Extraer datos del mensaje
            broadcast_data = payload.get('payload', {})
            user_id = broadcast_data.get('user_id')
            event_data = broadcast_data.get('event_data', {})
            
            # Ignorar los mensajes propios
            if user_id == self.username:
                return
                
            # Emitir el mensaje a través del MessageBus local
            message_bus.publish(
                content=f"Realtime event received from {user_id}: {event_data.get('content', '')}",
                level=MessageLevel.INFO,
                pattern_name="realtime_event_remote",
                metadata={
                    "source": "realtime_bridge",
                    "remote_user": user_id,
                    "event_data": event_data
                }
            )
            
            # También emitir un evento específico que pueda ser capturado por la UI
            message_bus.emit("remote_realtime_event", user_id, event_data)
            
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
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
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
        
    def _heartbeat_worker(self):
        """Worker thread para enviar actualizaciones periódicas de estado"""
        while self.heartbeat_active:
            try:
                # Solo actualizar si tenemos información de shard e información de presencia
                if self.shard and 'presence' in self.channels and self.channels['presence']:
                    presence_data = {
                        'shard': self.shard,
                        'version': self.version,
                        'status': 'online',
                        'last_active': datetime.now().isoformat(),
                        'metadata': {}
                    }
                    
                    # Actualizar estado de presencia
                    self.channels['presence'].track(presence_data)
                    
                    message_bus.publish(
                        content="Heartbeat presence update sent",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "realtime_bridge"}
                    )
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