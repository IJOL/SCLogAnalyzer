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

from helpers.core.message_bus import message_bus, MessageLevel
from helpers.services.game_focus_detector import GameFocusDetector


class HotkeyManager:
    """Sistema genérico de registro dinámico de hotkeys - config-first, descentralizado"""
    
    def __init__(self, config_manager):
        self.hotkeys: Dict[str, str] = {}  # combination -> event_name (vacío al inicio)
        self.hotkey_metadata: Dict[str, dict] = {}  # event_name -> {description, category, default_combination}
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
                target_windows = hotkey_config.get('target_windows', ["Star Citizen"])
                # Añadir la propia aplicación a las ventanas objetivo
                target_windows = list(target_windows)  # Hacer copia para no modificar el original
                target_windows.append('SC Log Analyzer')
                self.game_focus_detector = GameFocusDetector(target_windows)
                self.game_focus_detector.add_focus_callback(self._on_focus_change)
                self.game_focus_detector.start_monitoring()
                
                message_bus.publish(
                    content="GameFocusDetector initialized for hotkey restriction",
                    level=MessageLevel.INFO
                )
        except Exception as e:
            message_bus.publish(
                content=f"Error initializing GameFocusDetector: {e}",
                level=MessageLevel.WARNING
            )
            self.game_focus_required = False
    
    def _on_focus_change(self, focused: bool, window_info: str):
        """Callback para cambios de foco del juego"""
        old_focused = self.is_game_focused
        self.is_game_focused = focused
            
    def register_hotkey(self, default_combination: str, event_name: str, description: str = "", category: str = "General"):
        """
        Registrar hotkey con configuración config-first
        
        Args:
            default_combination: Combinación por defecto (ej: "ctrl+alt+1")
            event_name: Nombre del evento a emitir en MessageBus
            description: Descripción del hotkey para UI
            category: Categoría para organizar en UI (System, Overlay, etc.)
        """
        try:
            # Config-first: usar config si existe, fallback a default
            config_combination = self.config_manager.get(f'hotkeys.{event_name}', default_combination)
            actual_combination = self._validate_combination(config_combination, default_combination, event_name)
            
            # Verificar conflictos
            if actual_combination in self.hotkeys:
                existing_event = self.hotkeys[actual_combination]
                message_bus.publish(
                    content=f"Hotkey conflict: '{actual_combination}' overwritten {existing_event} -> {event_name}",
                    level=MessageLevel.WARNING
                )
            
            # Registrar hotkey y metadata
            self.hotkeys[actual_combination] = event_name
            self.hotkey_metadata[event_name] = {
                'description': description,
                'category': category, 
                'default_combination': default_combination,
                'current_combination': actual_combination
            }
            self.stats['registered_hotkeys'] = len(self.hotkeys)
            
            # Reiniciar listener con nuevos hotkeys
            self._restart_listener()
            
        except Exception as e:
            message_bus.publish(
                content=f"Error registering hotkey {default_combination} -> {event_name}: {e}",
                level=MessageLevel.ERROR
            )
    
    def _validate_combination(self, combo: str, fallback: str, event_name: str) -> str:
        """Validar combinación de hotkey, usar fallback si inválida"""
        if not combo or not self._is_valid_combo_format(combo):
            message_bus.publish(
                content=f"Invalid hotkey '{combo}' for {event_name}, using default '{fallback}'",
                level=MessageLevel.WARNING
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
                    content="Hotkey system disabled in configuration",
                    level=MessageLevel.INFO
                )
                return
            
            self._restart_listener()
            message_bus.publish(
                content=f"Hotkey system started with {len(self.hotkeys)} hotkeys",
                level=MessageLevel.INFO
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error starting hotkey listener: {e}",
                level=MessageLevel.ERROR
            )
    
    def stop_listening(self):
        """Detener escucha de hotkeys globales"""
        with self.listener_lock:
            if self.listener:
                try:
                    self.listener.stop()
                    self.listener = None
                except Exception as e:
                    message_bus.publish(
                        content=f"Error stopping hotkey listener: {e}",
                        level=MessageLevel.WARNING
                    )
    
    def shutdown(self):
        """Cleanup completo al cerrar aplicación"""
        try:
            self._shutdown_event.set()
            self.stop_listening()
            
            if self.game_focus_detector:
                self.game_focus_detector.stop_monitoring()
            
            message_bus.publish(
                content="HotkeyManager shutdown completed",
                level=MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error during HotkeyManager shutdown: {e}",
                level=MessageLevel.ERROR
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
                
            except Exception as e:
                message_bus.publish(
                    content=f"Error creating hotkey listener: {e}",
                    level=MessageLevel.ERROR
                )
                self.listener = None
    
    def _convert_to_pynput_format(self, combination: str) -> Optional[str]:
        """Convertir formato config a formato pynput"""
        try:
            # Formato config: "ctrl+alt+1" -> Formato pynput: "<ctrl>+<alt>+1"
            parts = combination.lower().split('+')
            pynput_parts = []
            
            # Mapping de teclas especiales que requieren formato <key> en pynput
            special_keys = {
                'ctrl': '<ctrl>',
                'alt': '<alt>', 
                'shift': '<shift>',
                'cmd': '<cmd>',
                'win': '<cmd>',  # Windows key maps to cmd in pynput
                'escape': '<esc>',
                'esc': '<esc>',
                'enter': '<enter>',
                'return': '<enter>',
                'space': '<space>',
                'tab': '<tab>',
                'backspace': '<backspace>',
                'delete': '<delete>',
                'home': '<home>',
                'end': '<end>',
                'page_up': '<page_up>',
                'page_down': '<page_down>',
                'up': '<up>',
                'down': '<down>',
                'left': '<left>',
                'right': '<right>',
                'insert': '<insert>',
                'caps_lock': '<caps_lock>',
                'scroll_lock': '<scroll_lock>',
                'num_lock': '<num_lock>',
                'print_screen': '<print_screen>',
                'pause': '<pause>',
                'menu': '<menu>'
            }
            
            for part in parts:
                part = part.strip()
                if part in special_keys:
                    pynput_parts.append(special_keys[part])
                elif part.startswith('f') and len(part) > 1 and part[1:].isdigit():
                    # Teclas de función F1-F24
                    pynput_parts.append(f'<{part}>')
                else:
                    # Teclas regulares (letras, números)
                    pynput_parts.append(part)
            
            return '+'.join(pynput_parts)
        except Exception as e:
            message_bus.publish(
                content=f"Error converting hotkey format '{combination}': {e}",
                level=MessageLevel.ERROR
            )
            return None
    
    def _on_hotkey_pressed(self, event_name: str):
        """Callback cuando se presiona un hotkey"""
        try:
            self.stats['total_presses'] += 1
            
            # Verificar si el juego debe tener foco
            if self.game_focus_required and not self.is_game_focused:
                self.stats['blocked_presses'] += 1
                return
            
            # Emitir evento en MessageBus
            self.stats['successful_presses'] += 1
            message_bus.emit(event_name)
            
        except Exception as e:
            message_bus.publish(
                content=f"Error processing hotkey event {event_name}: {e}",
                level=MessageLevel.ERROR
            )
    
    def get_registered_hotkeys(self) -> Dict[str, str]:
        """Obtener diccionario de hotkeys registrados"""
        return self.hotkeys.copy()
    
    def get_stats(self) -> Dict[str, int]:
        """Obtener estadísticas del sistema de hotkeys"""
        return self.stats.copy()
    
    def get_registered_hotkeys_info(self) -> Dict[str, dict]:
        """
        Obtener información completa de hotkeys registrados
        
        Returns:
            Dict con event_name -> {description, category, default_combination, current_combination}
        """
        return self.hotkey_metadata.copy()
    
    def get_hotkeys_by_category(self) -> Dict[str, Dict[str, dict]]:
        """
        Obtener hotkeys organizados por categoría
        
        Returns:
            Dict con category -> {event_name -> {description, default_combination, current_combination}}
        """
        by_category = {}
        for event_name, metadata in self.hotkey_metadata.items():
            category = metadata['category']
            if category not in by_category:
                by_category[category] = {}
            by_category[category][event_name] = metadata
        return by_category


# === Singleton Management - trasladado de hotkey_utils.py ===
import threading
from typing import Optional

# Variables globales para singleton thread-safe
_hotkey_manager_instance: Optional[HotkeyManager] = None
_hotkey_manager_lock = threading.Lock()


def get_hotkey_manager() -> HotkeyManager:
    """
    Obtener instancia singleton del HotkeyManager de forma thread-safe.
    
    Sigue el mismo patrón que get_config_manager() para consistencia
    con el resto del codebase.
    
    Returns:
        HotkeyManager: Instancia única del gestor de hotkeys
    """
    global _hotkey_manager_instance
    
    with _hotkey_manager_lock:
        if _hotkey_manager_instance is None:
            # Obtener ConfigManager usando la función existente
            from ..core.config_utils import get_config_manager
            config_manager = get_config_manager()
            
            # Crear instancia única de HotkeyManager
            _hotkey_manager_instance = HotkeyManager(config_manager)
            
            # Log de inicialización usando el sistema de logging del proyecto
            try:
                from ..core.message_bus import message_bus, MessageLevel
                message_bus.publish(
                    content="HotkeyManager singleton instance created",
                    level=MessageLevel.INFO
                )
            except ImportError:
                # Fallback si MessageBus no está disponible
                print("HotkeyManager singleton instance created")
        
        return _hotkey_manager_instance


def reset_hotkey_manager():
    """
    Reset del singleton para testing.
    
    SOLO para uso en tests - no usar en código de producción.
    """
    global _hotkey_manager_instance
    
    with _hotkey_manager_lock:
        if _hotkey_manager_instance is not None:
            try:
                _hotkey_manager_instance.shutdown()
            except:
                pass
            _hotkey_manager_instance = None


def is_hotkey_manager_initialized() -> bool:
    """
    Verificar si el HotkeyManager ya está inicializado.
    
    Returns:
        bool: True si la instancia existe
    """
    global _hotkey_manager_instance
    return _hotkey_manager_instance is not None


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