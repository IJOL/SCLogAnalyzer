#!/usr/bin/env python
import uuid
import json
from datetime import datetime
import threading
import time

# Import Supabase manager
from .supabase_manager import supabase_manager
from .message_bus import message_bus, MessageLevel

class RealtimeBridge:
    """
    Clase puente que conecta el MessageBus local con Supabase Realtime para
    permitir la comunicación entre diferentes instancias de SCLogAnalyzer.
    """
    def __init__(self, supabase_client, config_manager):
        self.supabase = supabase_client
        self.config_manager = config_manager
        self.username = config_manager.get('username', 'Unknown')
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
        
    def connect(self):
        """Inicializa la conexión con Supabase Realtime"""
        try:
            # Conectarse al canal de usuarios activos
            self._init_presence_channel()
            # Conectarse al canal de broadcast general
            self._init_broadcast_channel()
            self.is_connected = True
            
            # Iniciar el heartbeat para mantener actualizado el estado en la base de datos
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
            
            # Configurar manejadores de eventos de presencia
            presence_channel.on('presence', {'event': 'sync'}, lambda payload: self._handle_presence_sync(presence_channel))
            presence_channel.on('presence', {'event': 'join'}, lambda payload: self._handle_presence_join(payload))
            presence_channel.on('presence', {'event': 'leave'}, lambda payload: self._handle_presence_leave(payload))
            
            # Suscribirse al canal
            presence_channel.subscribe(lambda status: self._handle_presence_subscription(status, presence_channel))
            
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
            
            # Configurar manejadores de eventos de broadcast
            broadcast_channel.on('broadcast', {'event': 'realtime-event'}, lambda payload: self._handle_realtime_event_broadcast(payload))
            
            # Suscribirse al canal
            broadcast_channel.subscribe()
            
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
                self.channels['presence'].track(presence_data)
                
                # También actualizar nuestro registro en la base de datos
                self._update_user_in_db(presence_data)
                
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
            
    def _update_user_in_db(self, presence_data):
        """Actualiza o crea el registro del usuario en la base de datos"""
        try:
            # Intentar actualizar primero por username (único identificador)
            result = self.supabase.table('active_users').update({
                'shard': presence_data['shard'],
                'version': presence_data['version'],
                'status': presence_data['status'],
                'last_seen': presence_data['last_active'],
                'user_mode': presence_data.get('metadata', {}).get('mode'),
                'metadata': presence_data['metadata']
            }).eq('username', self.username).execute()
            
            # Si no hay filas afectadas, insertar un nuevo registro
            if not result.data or len(result.data) == 0:
                self.supabase.table('active_users').insert({
                    'username': self.username,
                    'shard': presence_data['shard'],
                    'version': presence_data['version'],
                    'status': presence_data['status'],
                    'last_seen': presence_data['last_active'],
                    'user_mode': presence_data.get('metadata', {}).get('mode'),
                    'metadata': presence_data['metadata']
                }).execute()
                
                message_bus.publish(
                    content="Created new active user record in database",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
            else:
                message_bus.publish(
                    content="Updated existing active user record in database",
                    level=MessageLevel.DEBUG,
                    metadata={"source": "realtime_bridge"}
                )
                
        except Exception as e:
            message_bus.publish(
                content=f"Error updating user in database: {e}",
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
                
                # También añadir a la base de datos
                self._update_user_in_db(initial_presence)
                
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
            presence_state = channel.presenceState()
            
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
        """Inicia el heartbeat para mantener actualizada la información de usuario activo"""
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
                # Solo actualizar si tenemos información de shard
                if self.shard:
                    presence_data = {
                        'shard': self.shard,
                        'version': self.version,
                        'status': 'online',
                        'last_active': datetime.now().isoformat(),
                        'metadata': {}
                    }
                    
                    # Actualizar en la base de datos
                    self._update_user_in_db(presence_data)
                    
                    message_bus.publish(
                        content="Heartbeat update sent",
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