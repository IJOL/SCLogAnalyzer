#!/usr/bin/env python3
"""
Overlay Manager - Factory Pattern para Dynamic Overlays

Este módulo proporciona un factory pattern para crear overlays dinámicos
de cualquier widget de la aplicación de manera uniforme y consistente.

Integración con sistema de menú contextual existente siguiendo el patrón
establecido en ProfileCacheWidget con _extend_context_menu_with_vip().
"""

import wx
import time
from typing import Type, Dict, Any, Optional

from .overlay_base import DynamicOverlay
from .message_bus import message_bus, MessageLevel


class OverlayManager:
    """Factory y gestor de overlays dinámicos con integración MessageBus"""
    
    # Registry de overlays activos
    _active_overlays: Dict[str, DynamicOverlay] = {}
    
    @classmethod
    def create_overlay(cls, 
                      widget_class: Type[wx.Panel], 
                      widget_args: Optional[list] = None,
                      widget_kwargs: Optional[Dict[str, Any]] = None,
                      overlay_id: Optional[str] = None,
                      size: Optional[tuple] = None,
                      position: Optional[tuple] = None,
                      title: Optional[str] = None) -> DynamicOverlay:
        """
        Factory method para crear overlay de cualquier widget
        
        Args:
            widget_class: Clase del widget a mostrar en overlay
            widget_args: Lista de argumentos para el constructor del widget
            widget_kwargs: Argumentos keyword para el constructor del widget  
            overlay_id: ID único del overlay (auto-generado si no se especifica)
            size: Tamaño inicial del overlay (width, height)
            position: Posición inicial del overlay (x, y)
            title: Título personalizado del overlay
            
        Returns:
            DynamicOverlay: Instancia del overlay creado
            
        Raises:
            Exception: Si hay error en la creación del overlay
        """
        try:
            # Generar ID único si no se proporciona
            if not overlay_id:
                timestamp = int(time.time() * 1000)  # milliseconds para unicidad
                overlay_id = f"{widget_class.__name__}_overlay_{timestamp}"
            
            # Verificar si ya existe un overlay con este ID
            if overlay_id in cls._active_overlays:
                existing_overlay = cls._active_overlays[overlay_id]
                if existing_overlay and not existing_overlay.IsBeingDeleted():
                    # Si ya existe, traerlo al frente
                    existing_overlay.Raise()
                    existing_overlay.RequestUserAttention()
                    cls._log_message(f"Overlay existente traído al frente: {overlay_id}", MessageLevel.INFO)
                    return existing_overlay
                else:
                    # Si existe pero está siendo eliminado, limpiar referencia
                    del cls._active_overlays[overlay_id]
            
            # Preparar argumentos para DynamicOverlay
            overlay_kwargs = {
                'widget_class': widget_class,
                'widget_args': widget_args or [],
                'widget_kwargs': widget_kwargs or {},
                'overlay_id': overlay_id
            }
            
            # Añadir parámetros opcionales
            if size:
                overlay_kwargs['size'] = size
            if position:
                overlay_kwargs['pos'] = position
            if title:
                overlay_kwargs['title'] = title
            else:
                overlay_kwargs['title'] = f"{widget_class.__name__} Overlay"
            
            # Crear nuevo overlay usando overlay_base.py existente
            overlay = DynamicOverlay(**overlay_kwargs)
            
            # Registrar overlay activo
            cls._active_overlays[overlay_id] = overlay
            
            # Configurar cleanup automático cuando se cierre
            overlay.Bind(wx.EVT_CLOSE, lambda evt: cls._on_overlay_close(overlay_id, evt))
            
            
            return overlay
            
        except Exception as e:
            # Log de error
            cls._log_message(
                f"Error creando overlay {overlay_id or 'unknown'}: {str(e)}",
                MessageLevel.ERROR
            )
            raise
    
    @classmethod
    def get_active_overlays(cls) -> Dict[str, DynamicOverlay]:
        """
        Obtener todos los overlays activos
        
        Returns:
            Dict[str, DynamicOverlay]: Diccionario de overlays activos {id: overlay}
        """
        # Limpiar referencias a overlays eliminados
        to_remove = []
        for overlay_id, overlay in cls._active_overlays.items():
            if not overlay or overlay.IsBeingDeleted():
                to_remove.append(overlay_id)
        
        for overlay_id in to_remove:
            del cls._active_overlays[overlay_id]
        
        return cls._active_overlays.copy()
    
    @classmethod
    def close_overlay(cls, overlay_id: str) -> bool:
        """
        Cerrar overlay específico por ID
        
        Args:
            overlay_id: ID del overlay a cerrar
            
        Returns:
            bool: True si el overlay fue cerrado exitosamente
        """
        if overlay_id in cls._active_overlays:
            overlay = cls._active_overlays[overlay_id]
            if overlay and not overlay.IsBeingDeleted():
                # Eliminar del registry ANTES de cerrar para evitar race condition
                del cls._active_overlays[overlay_id]
                overlay.Close()
                return True
        return False
    
    @classmethod
    def close_all_overlays(cls):
        """Cerrar todos los overlays activos"""
        overlays_to_close = list(cls._active_overlays.values())
        closed_count = 0
        
        for overlay in overlays_to_close:
            if overlay and not overlay.IsBeingDeleted():
                overlay.Close()
                closed_count += 1
        
        cls._active_overlays.clear()
        cls._log_message(f"Cerrados {closed_count} overlays", MessageLevel.INFO)
    
    @classmethod
    def toggle_overlay(cls, widget_class: Type[wx.Panel], 
                      widget_args: Optional[list] = None,
                      widget_kwargs: Optional[Dict[str, Any]] = None,
                      **kwargs) -> DynamicOverlay:
        """
        Toggle overlay - si existe lo cierra, si no existe lo crea
        
        Útil para menús contextuales que quieren comportamiento toggle.
        
        Args:
            widget_class: Clase del widget
            widget_args: Argumentos para el widget
            widget_kwargs: Argumentos keyword para el widget
            **kwargs: Argumentos adicionales para create_overlay()
            
        Returns:
            DynamicOverlay: El overlay creado, o None si se cerró uno existente
        """
        # Generar ID basado en la clase del widget para toggle behavior
        base_overlay_id = f"{widget_class.__name__}_overlay"
        
        # Buscar si existe un overlay de esta clase
        existing_overlay_id = None
        for overlay_id, overlay in cls._active_overlays.items():
            if (overlay and not overlay.IsBeingDeleted() and 
                overlay_id.startswith(base_overlay_id)):
                existing_overlay_id = overlay_id
                break
        
        if existing_overlay_id:
            # Si existe, cerrarlo
            cls.close_overlay(existing_overlay_id)
            return None
        else:
            # Si no existe, crearlo
            overlay = cls.create_overlay(
                widget_class=widget_class,
                widget_args=widget_args,
                widget_kwargs=widget_kwargs,
                overlay_id=kwargs.get('overlay_id', base_overlay_id),
                **{k: v for k, v in kwargs.items() if k != 'overlay_id'}
            )
            # Mostrar el overlay si se creó exitosamente
            if overlay:
                overlay.Show()
            return overlay
    
    @classmethod
    def _on_overlay_close(cls, overlay_id: str, event):
        """
        Callback para cleanup cuando se cierra un overlay
        
        Args:
            overlay_id: ID del overlay que se está cerrando
            event: Evento de cierre
        """
        if overlay_id in cls._active_overlays:
            del cls._active_overlays[overlay_id]
        
        cls._log_message(f"Overlay limpiado del registry: {overlay_id}", MessageLevel.DEBUG)
        event.Skip()  # Permitir que el evento continúe
    
    @classmethod
    def get_overlay_count(cls) -> int:
        """
        Obtener número de overlays activos
        
        Returns:
            int: Número de overlays actualmente activos
        """
        return len(cls.get_active_overlays())
    
    @classmethod
    def has_overlay(cls, overlay_id: str) -> bool:
        """
        Verificar si existe un overlay específico
        
        Args:
            overlay_id: ID del overlay a verificar
            
        Returns:
            bool: True si el overlay existe y está activo
        """
        return overlay_id in cls.get_active_overlays()
    
    @classmethod
    def has_overlay_for_widget(cls, widget_class: Type[wx.Panel]) -> bool:
        """
        Verificar si existe un overlay para una clase de widget específica
        
        Args:
            widget_class: Clase del widget a verificar
            
        Returns:
            bool: True si existe al menos un overlay de esta clase de widget
        """
        base_overlay_id = f"{widget_class.__name__}_overlay"
        for overlay_id in cls.get_active_overlays():
            if overlay_id.startswith(base_overlay_id):
                return True
        return False
    
    @classmethod
    def initialize_hotkeys(cls):
        """
        Registrar hotkeys para gestión de overlays - se llama desde main_frame
        
        Método descentralizado que auto-registra los hotkeys de overlay
        usando lazy imports para evitar dependencias circulares.
        """
        try:
            # Importar hotkey_utils aquí para evitar import circular
            from .hotkey_manager import get_hotkey_manager
            
            hotkey_manager = get_hotkey_manager()
            
            # WIDGETS CON OVERLAYMIXIN (funcionalidad overlay ya integrada):
            hotkey_manager.register_hotkey("ctrl+alt+1", "overlay_toggle_stalled", "Toggle Stalled Widget Overlay", "Overlay")
            hotkey_manager.register_hotkey("ctrl+alt+2", "overlay_toggle_shared_logs", "Toggle Shared Logs Overlay", "Overlay")
            
            # Hotkeys globales de overlay
            hotkey_manager.register_hotkey("ctrl+alt+0", "overlay_toggle_all", "Toggle All Overlays", "Overlay")
            hotkey_manager.register_hotkey("ctrl+alt+escape", "overlay_close_all", "Emergency Close All", "Overlay")
            
            # Registrar handlers para widgets con OverlayMixin - thread safe
            import wx
            message_bus.on("overlay_toggle_stalled", lambda: wx.CallAfter(cls._toggle_widget_overlay, "StalledWidget"))
            message_bus.on("overlay_toggle_shared_logs", lambda: wx.CallAfter(cls._toggle_shared_logs_overlay))
            message_bus.on("overlay_toggle_all", lambda: wx.CallAfter(cls._toggle_all_overlays))
            message_bus.on("overlay_close_all", lambda: wx.CallAfter(cls.close_all_overlays))
            
            cls._log_message("Overlay hotkeys registered successfully")
            
        except Exception as e:
            cls._log_message(f"Error registering overlay hotkeys: {e}", MessageLevel.ERROR)
    
    @classmethod
    def _toggle_widget_overlay(cls, widget_class_name: str):
        """Toggle overlay usando lazy import para evitar circular imports"""
        try:
            if widget_class_name == "StalledWidget":
                from .stalled_widget import StalledWidget
                cls.toggle_overlay(StalledWidget)
            elif widget_class_name == "SharedLogsWidget": 
                from .shared_logs_widget import SharedLogsWidget
                cls.toggle_overlay(SharedLogsWidget)
            else:
                cls._log_message(f"Unknown widget class for overlay: {widget_class_name}", MessageLevel.WARNING)
        except ImportError as e:
            cls._log_message(f"Error importing {widget_class_name}: {e}", MessageLevel.ERROR)
        except Exception as e:
            cls._log_message(f"Error toggling {widget_class_name} overlay: {e}", MessageLevel.ERROR)
    
    @classmethod
    def _toggle_shared_logs_overlay(cls):
        """Toggle SharedLogsWidget overlay usando instancia controladora"""
        try:
            from .shared_logs_widget import SharedLogsWidget
            
            # Usar la instancia controladora si existe
            if SharedLogsWidget._controller_instance:
                SharedLogsWidget._controller_instance._toggle_widget_overlay()
            else:
                cls._log_message("No SharedLogsWidget controller instance found", MessageLevel.WARNING)
                # Fallback al método estático
                cls._toggle_widget_overlay("SharedLogsWidget")
        except ImportError as e:
            cls._log_message(f"Error importing SharedLogsWidget: {e}", MessageLevel.ERROR)
        except Exception as e:
            cls._log_message(f"Error toggling SharedLogsWidget overlay: {e}", MessageLevel.ERROR)
    
    @classmethod
    def _toggle_all_overlays(cls):
        """Toggle todos los overlays activos"""
        try:
            active_overlays = cls.get_active_overlays()
            if not active_overlays:
                # No hay overlays activos, crear overlays por defecto
                cls._log_message("No active overlays found, creating default overlays", MessageLevel.INFO)
                cls._toggle_widget_overlay("StalledWidget")
                cls._toggle_shared_logs_overlay()
            else:
                # Hay overlays activos, ocultarlos/mostrarlos
                hidden_count = 0
                shown_count = 0
                
                for overlay_id, overlay in active_overlays.items():
                    try:
                        if overlay and not overlay.IsBeingDeleted():
                            if overlay.IsShown():
                                overlay.Hide()
                                hidden_count += 1
                            else:
                                overlay.Show()
                                shown_count += 1
                    except Exception as e:
                        cls._log_message(f"Error toggling overlay {overlay_id}: {e}", MessageLevel.WARNING)
                
                cls._log_message(f"Toggle all overlays: {shown_count} shown, {hidden_count} hidden", MessageLevel.INFO)
                        
        except Exception as e:
            cls._log_message(f"Error in toggle all overlays: {e}", MessageLevel.ERROR)
    
    @classmethod
    def _log_message(cls, message: str, level: MessageLevel = MessageLevel.INFO):
        """
        Log message a través del MessageBus
        
        Args:
            message: Mensaje a loggear
            level: Nivel del mensaje
        """
        try:
            message_bus.publish(content=f"[OverlayManager] {message}", level=level)
        except:
            # Fallback a print si MessageBus no está disponible
            print(f"[OverlayManager] {message}")


# Funciones de conveniencia para fácil importación
def create_widget_overlay(widget_class: Type[wx.Panel], 
                         widget_args: Optional[list] = None,
                         widget_kwargs: Optional[Dict[str, Any]] = None,
                         **kwargs) -> DynamicOverlay:
    """
    Función de conveniencia para crear overlay de widget
    
    Args:
        widget_class: Clase del widget a mostrar en overlay
        widget_args: Argumentos para el constructor del widget
        widget_kwargs: Argumentos keyword para el constructor del widget
        **kwargs: Argumentos adicionales para OverlayManager.create_overlay()
        
    Returns:
        DynamicOverlay: Instancia del overlay creado
    """
    return OverlayManager.create_overlay(
        widget_class=widget_class,
        widget_args=widget_args,
        widget_kwargs=widget_kwargs,
        **kwargs
    )


def toggle_widget_overlay(widget_class: Type[wx.Panel],
                         widget_args: Optional[list] = None,
                         widget_kwargs: Optional[Dict[str, Any]] = None,
                         **kwargs) -> Optional[DynamicOverlay]:
    """
    Función de conveniencia para toggle overlay de widget
    
    Args:
        widget_class: Clase del widget
        widget_args: Argumentos para el constructor del widget
        widget_kwargs: Argumentos keyword para el constructor del widget
        **kwargs: Argumentos adicionales para OverlayManager.toggle_overlay()
        
    Returns:
        Optional[DynamicOverlay]: El overlay creado, o None si se cerró uno existente
    """
    return OverlayManager.toggle_overlay(
        widget_class=widget_class,
        widget_args=widget_args,
        widget_kwargs=widget_kwargs,
        **kwargs
    )


def get_active_overlay_count() -> int:
    """
    Función de conveniencia para obtener número de overlays activos
    
    Returns:
        int: Número de overlays actualmente activos
    """
    return OverlayManager.get_overlay_count()


def close_all_overlays():
    """Función de conveniencia para cerrar todos los overlays"""
    OverlayManager.close_all_overlays()


# Validación del sistema para testing
def validate_overlay_system() -> bool:
    """
    Validación básica del sistema de overlays
    
    Returns:
        bool: True si la validación pasa exitosamente
    """
    try:
        print("=== Overlay System Validation ===")
        
        # Verificar que se puede importar DynamicOverlay
        print("Test 1: Importing DynamicOverlay...")
        from .overlay_base import DynamicOverlay
        print("✓ DynamicOverlay imported successfully")
        
        # Verificar que OverlayManager funciona
        print("Test 2: OverlayManager functionality...")
        initial_count = OverlayManager.get_overlay_count()
        print(f"✓ OverlayManager working, {initial_count} overlays active")
        
        # Test registry functions
        print("Test 3: Registry functions...")
        active_overlays = OverlayManager.get_active_overlays()
        has_test = OverlayManager.has_overlay("test_overlay_id")
        print(f"✓ Registry functions working: {len(active_overlays)} active, has_test={has_test}")
        
        print("=== All tests passed ===")
        return True
        
    except Exception as e:
        print(f"✗ Validation failed: {e}")
        return False


# Ejecutar validación si se importa el módulo directamente
if __name__ == "__main__":
    import wx
    app = wx.App()
    validate_overlay_system()