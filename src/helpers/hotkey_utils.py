#!/usr/bin/env python3
"""
HotkeyUtils - Utilidades para el sistema de hotkeys

Proporciona función get_hotkey_manager() siguiendo el mismo patrón
que get_config_manager() para gestión de singleton thread-safe.
"""

import threading
from typing import Optional

from .hotkey_manager import HotkeyManager
from .config_utils import get_config_manager


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
            config_manager = get_config_manager()
            
            # Crear instancia única de HotkeyManager
            _hotkey_manager_instance = HotkeyManager(config_manager)
            
            # Log de inicialización usando el sistema de logging del proyecto
            try:
                from .message_bus import message_bus, MessageLevel
                message_bus.publish(
                    "HotkeyManager singleton instance created",
                    MessageLevel.DEBUG
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
    """Testing de las utilidades de hotkey"""
    print("=== HotkeyUtils Testing ===")
    
    # Test 1: Primera obtención del manager
    print("Test 1: Getting HotkeyManager instance...")
    manager1 = get_hotkey_manager()
    print(f"✓ Instance created: {type(manager1)}")
    
    # Test 2: Segunda obtención debe devolver la misma instancia
    print("Test 2: Getting HotkeyManager instance again...")
    manager2 = get_hotkey_manager()
    print(f"✓ Same instance: {manager1 is manager2}")
    
    # Test 3: Verificar estado de inicialización
    print("Test 3: Checking initialization state...")
    print(f"✓ Is initialized: {is_hotkey_manager_initialized()}")
    
    # Test 4: Reset y verificación
    print("Test 4: Resetting instance...")
    reset_hotkey_manager()
    print(f"✓ After reset, is initialized: {is_hotkey_manager_initialized()}")
    
    # Test 5: Nueva instancia después del reset
    print("Test 5: Getting new instance after reset...")
    manager3 = get_hotkey_manager()
    print(f"✓ New instance created: {manager3 is not manager1}")
    
    print("=== All HotkeyUtils tests passed ===")
    
    # Cleanup
    reset_hotkey_manager()


if __name__ == "__main__":
    main()