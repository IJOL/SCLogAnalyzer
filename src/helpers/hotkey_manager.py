#!/usr/bin/env python3
"""
HotkeyManager - Sistema genérico de registro dinámico de hotkeys

Sistema config-first, descentralizado que permite a cualquier componente
registrar sus propios hotkeys con configuración personalizable.

Integración con MessageBus para eventos y GameFocusDetector para 
restricción de foco del juego.
"""

import threading
from typing import Dict, Callable, Optional, List
from pynput import keyboard

from .message_bus import message_bus, MessageLevel
from .game_focus_detector import GameFocusDetector


class HotkeyManager:
    """Sistema genérico de registro dinámico de hotkeys - config-first, descentralizado"""
    
    def __init__(self, config_manager):
        self.hotkeys: Dict[str, str] = {}  # combination -> event_name (vacío al inicio)
        self.config_manager = config_manager
        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self.listener_lock = threading.Lock()
        self._shutdown_event = threading.Event()
        
        # GameFocusDetector para restricción opcional de foco
        self.game_focus_detector: Optional[GameFocusDetector] = None
        self.game_focus_required = True
        self.is_game_focused = False
        
        # Statistics
        self.stats = {
            'registered_hotkeys': 0,
            'total_presses': 0,
            'blocked_presses': 0,
            'successful_presses': 0
        }
        
        # Inicializar GameFocusDetector si está habilitado
        self._initialize_focus_detector()
    
    def _initialize_focus_detector(self):
        """Inicializar detector de foco del juego si está configurado"""
        try:
            hotkey_config = self.config_manager.get('hotkey_system', {})
            self.game_focus_required = hotkey_config.get('game_focus_required', True)
            
            if self.game_focus_required:
                target_windows = hotkey_config.get('target_windows', ["Star Citizen", "Stanton"])
                self.game_focus_detector = GameFocusDetector(target_windows)
                self.game_focus_detector.add_focus_callback(self._on_focus_change)
                self.game_focus_detector.start_monitoring()
                
                message_bus.publish(
                    "GameFocusDetector initialized for hotkey restriction",
                    MessageLevel.DEBUG
                )
        except Exception as e:
            message_bus.publish(
                f"Error initializing GameFocusDetector: {e}",
                MessageLevel.WARNING
            )
            self.game_focus_required = False
    
    def _on_focus_change(self, focused: bool, window_info: str):
        """Callback para cambios de foco del juego"""
        self.is_game_focused = focused
        if focused:
            message_bus.publish(
                f"Game focused - hotkeys enabled: {window_info}",
                MessageLevel.DEBUG
            )
        else:
            message_bus.publish(
                f"Game not focused - hotkeys restricted: {window_info}",
                MessageLevel.DEBUG
            )
    
    def register_hotkey(self, default_combination: str, event_name: str, description: str = ""):
        """
        Registrar hotkey con configuración config-first
        
        Args:
            default_combination: Combinación por defecto (ej: "ctrl+alt+1")
            event_name: Nombre del evento a emitir en MessageBus
            description: Descripción del hotkey para UI
        """
        try:
            # Config-first: usar config si existe, fallback a default
            config_combination = self.config_manager.get(f'hotkeys.{event_name}', default_combination)
            actual_combination = self._validate_combination(config_combination, default_combination, event_name)
            
            # Verificar conflictos
            if actual_combination in self.hotkeys:
                existing_event = self.hotkeys[actual_combination]
                message_bus.publish(
                    f"Hotkey conflict: '{actual_combination}' already registered for '{existing_event}', overwriting with '{event_name}'",
                    MessageLevel.WARNING
                )
            
            # Registrar
            self.hotkeys[actual_combination] = event_name
            self.stats['registered_hotkeys'] = len(self.hotkeys)
            
            message_bus.publish(
                f"Hotkey registered: {actual_combination} -> {event_name} ({description})",
                MessageLevel.DEBUG
            )
            
            # Reiniciar listener con nuevos hotkeys
            self._restart_listener()
            
        except Exception as e:
            message_bus.publish(
                f"Error registering hotkey {default_combination} -> {event_name}: {e}",
                MessageLevel.ERROR
            )
    
    def _validate_combination(self, combo: str, fallback: str, event_name: str) -> str:
        """Validar combinación de hotkey, usar fallback si inválida"""
        if not combo or not self._is_valid_combo_format(combo):
            message_bus.publish(
                f"Invalid hotkey '{combo}' for event '{event_name}', using default '{fallback}'",
                MessageLevel.WARNING
            )
            return fallback
        return combo
    
    def _is_valid_combo_format(self, combo: str) -> bool:
        """Validación básica del formato de combinación"""
        if not combo or not isinstance(combo, str):
            return False
        
        # Verificar formato básico: debe tener al menos una tecla
        parts = combo.lower().split('+')
        if not parts:
            return False
        
        # Verificar que no esté vacío y tenga contenido válido
        valid_modifiers = {'ctrl', 'alt', 'shift', 'cmd', 'win'}
        valid_keys = set('abcdefghijklmnopqrstuvwxyz0123456789') | {'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12', 'space', 'tab', 'enter', 'escape'}
        
        for part in parts:
            part = part.strip()
            if not part:
                return False
            if part not in valid_modifiers and part not in valid_keys:
                # Permitir caracteres individuales que pynput puede manejar
                if len(part) == 1:
                    continue
                return False
        
        return True
    
    def start_listening(self):
        """Iniciar escucha de hotkeys globales"""
        try:
            if not self.config_manager.get('hotkey_system.enabled', True):
                message_bus.publish(
                    "Hotkey system disabled in configuration",
                    MessageLevel.INFO
                )
                return
            
            self._restart_listener()
            message_bus.publish(
                f"Hotkey system started with {len(self.hotkeys)} registered hotkeys",
                MessageLevel.INFO
            )
            
        except Exception as e:
            message_bus.publish(
                f"Error starting hotkey listener: {e}",
                MessageLevel.ERROR
            )
    
    def stop_listening(self):
        """Detener escucha de hotkeys globales"""
        with self.listener_lock:
            if self.listener:
                try:
                    self.listener.stop()
                    self.listener = None
                    message_bus.publish(
                        "Hotkey listener stopped",
                        MessageLevel.DEBUG
                    )
                except Exception as e:
                    message_bus.publish(
                        f"Error stopping hotkey listener: {e}",
                        MessageLevel.WARNING
                    )
    
    def shutdown(self):
        """Cleanup completo al cerrar aplicación"""
        try:
            self._shutdown_event.set()
            self.stop_listening()
            
            if self.game_focus_detector:
                self.game_focus_detector.stop_monitoring()
            
            message_bus.publish(
                "HotkeyManager shutdown completed",
                MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                f"Error during HotkeyManager shutdown: {e}",
                MessageLevel.ERROR
            )
    
    def _restart_listener(self):
        """Thread-safe restart de pynput listener"""
        if self._shutdown_event.is_set():
            return
        
        with self.listener_lock:
            # Detener listener actual
            if self.listener:
                try:
                    self.listener.stop()
                except:
                    pass
            
            # Si no hay hotkeys, no crear listener
            if not self.hotkeys:
                self.listener = None
                return
            
            try:
                # Crear mapping para pynput
                hotkey_mapping = {}
                for combination, event_name in self.hotkeys.items():
                    # Convertir formato a pynput
                    pynput_combo = self._convert_to_pynput_format(combination)
                    if pynput_combo:
                        hotkey_mapping[pynput_combo] = lambda e=event_name: self._on_hotkey_pressed(e)
                
                # Crear nuevo listener
                if hotkey_mapping:
                    self.listener = keyboard.GlobalHotKeys(hotkey_mapping)
                    self.listener.start()
                    
                    message_bus.publish(
                        f"Hotkey listener restarted with {len(hotkey_mapping)} combinations",
                        MessageLevel.DEBUG
                    )
                
            except Exception as e:
                message_bus.publish(
                    f"Error creating hotkey listener: {e}",
                    MessageLevel.ERROR
                )
                self.listener = None
    
    def _convert_to_pynput_format(self, combination: str) -> Optional[str]:
        """Convertir formato config a formato pynput"""
        try:
            # Formato config: "ctrl+alt+1" -> Formato pynput: "<ctrl>+<alt>+1"
            parts = combination.lower().split('+')
            pynput_parts = []
            
            for part in parts:
                part = part.strip()
                if part in {'ctrl', 'alt', 'shift', 'cmd', 'win'}:
                    pynput_parts.append(f'<{part}>')
                else:
                    pynput_parts.append(part)
            
            return '+'.join(pynput_parts)
        except Exception:
            return None
    
    def _on_hotkey_pressed(self, event_name: str):
        """Callback cuando se presiona un hotkey"""
        try:
            self.stats['total_presses'] += 1
            
            # Verificar si el juego debe tener foco
            if self.game_focus_required and not self.is_game_focused:
                self.stats['blocked_presses'] += 1
                message_bus.publish(
                    f"Hotkey blocked (game not focused): {event_name}",
                    MessageLevel.DEBUG
                )
                return
            
            # Emitir evento en MessageBus
            self.stats['successful_presses'] += 1
            message_bus.emit(event_name)
            
            message_bus.publish(
                f"Hotkey executed: {event_name}",
                MessageLevel.DEBUG
            )
            
        except Exception as e:
            message_bus.publish(
                f"Error processing hotkey event {event_name}: {e}",
                MessageLevel.ERROR
            )
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """Obtener diccionario de hotkeys registrados"""
        return self.hotkeys.copy()
    
    def get_stats(self) -> Dict[str, int]:
        """Obtener estadísticas del sistema de hotkeys"""
        return self.stats.copy()


def main():
    """Testing standalone del HotkeyManager"""
    print("=== HotkeyManager Testing ===")
    
    # Mock config manager para testing
    class MockConfigManager:
        def __init__(self):
            self.config = {
                'hotkey_system': {
                    'enabled': True,
                    'game_focus_required': False,  # Disable for testing
                    'target_windows': ["Star Citizen"]
                },
                'hotkeys': {
                    'test_event': 'ctrl+alt+t'
                }
            }
        
        def get(self, key, default=None):
            keys = key.split('.')
            value = self.config
            for k in keys:
                if isinstance(value, dict) and k in value:
                    value = value[k]
                else:
                    return default
            return value
    
    # Mock message bus
    class MockMessageBus:
        def publish(self, content, level=None):
            print(f"[{level}] {content}")
        
        def emit(self, event_name):
            print(f"EVENT EMITTED: {event_name}")
    
    # Replace imports
    import sys
    sys.modules[__name__].message_bus = MockMessageBus()
    
    config_manager = MockConfigManager()
    hotkey_manager = HotkeyManager(config_manager)
    
    # Registrar hotkey de testing
    hotkey_manager.register_hotkey("ctrl+shift+t", "test_hotkey", "Test hotkey")
    
    # Iniciar sistema
    hotkey_manager.start_listening()
    
    print("HotkeyManager started. Press Ctrl+Shift+T to test. Press Ctrl+C to exit.")
    print(f"Registered hotkeys: {hotkey_manager.get_registered_hotkeys()}")
    
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        hotkey_manager.shutdown()


if __name__ == "__main__":
    main()