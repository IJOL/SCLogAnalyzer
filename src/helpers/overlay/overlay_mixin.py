#!/usr/bin/env python3
"""
Overlay Mixin - Funcionalidad overlay universal para widgets

Este mixin proporciona funcionalidad overlay estándar que cualquier
widget puede integrar fácilmente en sus menús contextuales existentes.

Sigue el patrón establecido por _extend_context_menu_with_vip() en 
ProfileCacheWidget para máxima consistencia con el codebase.
"""

import wx
from typing import Optional, Dict, Any, Callable

from ..overlay.overlay_manager import OverlayManager
from ..core.message_bus import message_bus, MessageLevel


class OverlayMixin:
    """
    Mixin para añadir funcionalidad overlay a cualquier widget
    
    Este mixin proporciona métodos estándar para integrar overlays
    en menús contextuales existentes siguiendo el patrón establecido.
    
    Uso típico:
    ```python
    class MiWidget(wx.Panel, OverlayMixin):
        def _on_right_click(self, event):
            menu = wx.Menu()
            # ... opciones existentes ...
            
            # Añadir opción de overlay
            self.add_overlay_context_option(menu, context_data)
            
            self.PopupMenu(menu)
            menu.Destroy()
    ```
    """
    
    def add_overlay_context_option(self, 
                                  menu: wx.Menu,
                                  context_data: Optional[Dict[str, Any]] = None,
                                  option_label: str = "🔲 Abrir en Overlay",
                                  separator_before: bool = True) -> wx.MenuItem:
        """
        Añade opción de overlay al menú contextual existente
        
        Este método sigue el patrón de _extend_context_menu_with_vip()
        para máxima consistencia con el sistema existente.
        
        Args:
            menu: El menú contextual wx.Menu al que añadir la opción
            context_data: Datos contextuales para pasar al overlay (opcional)
            option_label: Texto de la opción de menú (default: "🔲 Abrir en Overlay")
            separator_before: Si añadir separador antes de la opción (default: True)
            
        Returns:
            wx.MenuItem: El item de menú creado
            
        Example:
            ```python
            def _on_right_click(self, event):
                menu = wx.Menu()
                
                # Opciones existentes del widget
                detail_item = menu.Append(wx.ID_ANY, "Ver detalles")
                # ... más opciones ...
                
                # Añadir overlay option (con separador)
                self.add_overlay_context_option(menu, {"selected_item": selection_data})
                
                self.PopupMenu(menu)
                menu.Destroy()
            ```
        """
        try:
            # Añadir separador si se solicita (patrón estándar)
            if separator_before:
                menu.AppendSeparator()
            
            # Crear item de menú para overlay
            overlay_item = menu.Append(wx.ID_ANY, option_label)
            
            # Bind del evento - usar lambda para capturar context_data
            self.Bind(wx.EVT_MENU, 
                     lambda evt: self._create_widget_overlay(context_data), 
                     overlay_item)
            
            return overlay_item
            
        except Exception as e:
            self._log_overlay_message(f"Error añadiendo overlay option al menú: {str(e)}", MessageLevel.ERROR)
            raise
    
    def add_overlay_toggle_option(self,
                                 menu: wx.Menu,
                                 context_data: Optional[Dict[str, Any]] = None,
                                 separator_before: bool = True) -> wx.MenuItem:
        """
        Añade opción de toggle overlay que cambia su texto según el estado
        
        Detecta si ya existe un overlay de este widget y muestra texto apropiado:
        - "🔲 Abrir en Overlay" si no hay overlay activo
        - "🔳 Cerrar Overlay" si ya hay un overlay activo
        
        Args:
            menu: El menú contextual wx.Menu al que añadir la opción
            context_data: Datos contextuales para pasar al overlay (opcional) 
            separator_before: Si añadir separador antes de la opción (default: True)
            
        Returns:
            wx.MenuItem: El item de menú creado
        """
        try:
            # Determinar si ya existe un overlay de este widget
            has_overlay = OverlayManager.get_instance().has_overlay_for_widget(self.__class__)
            
            # Texto dinámico según estado
            if has_overlay:
                option_label = "🔳 Cerrar Overlay"
            else:
                option_label = "🔲 Abrir en Overlay"
            
            # Añadir separador si se solicita
            if separator_before:
                menu.AppendSeparator()
            
            # Crear item de menú
            overlay_item = menu.Append(wx.ID_ANY, option_label)
            
            # Bind del evento para toggle behavior
            self.Bind(wx.EVT_MENU,
                     lambda evt: self._toggle_widget_overlay(context_data),
                     overlay_item)
            
            return overlay_item
            
        except Exception as e:
            self._log_overlay_message(f"Error añadiendo toggle overlay option: {str(e)}", MessageLevel.ERROR)
            raise
    
    def _create_widget_overlay(self, context_data: Optional[Dict[str, Any]] = None):
        """
        Crea overlay dinámico del widget actual
        
        Este método instancia un overlay del mismo tipo de widget que el actual,
        permitiendo que los datos se sincronicen automáticamente vía MessageBus.
        
        Args:
            context_data: Datos contextuales (actualmente para futura expansión)
        """
        try:
            # Obtener argumentos para la instanciación del widget
            widget_args, widget_kwargs = self._get_overlay_widget_args(context_data)
            
            # Crear overlay usando OverlayManager
            overlay = OverlayManager.get_instance().create_overlay(
                widget_class=self.__class__,
                widget_args=widget_args,
                widget_kwargs=widget_kwargs,
                title=f"{self.__class__.__name__} Overlay",
                size=self._get_overlay_default_size(),
                position=self._get_overlay_default_position()
            )
            
            # Mostrar overlay
            overlay.Show()
            
            
        except Exception as e:
            self._log_overlay_message(
                f"Error creando overlay para {self.__class__.__name__}: {str(e)}",
                MessageLevel.ERROR
            )
            
            # Mostrar error al usuario
            wx.MessageBox(
                f"Error creando overlay: {str(e)}",
                "Error de Overlay",
                wx.OK | wx.ICON_ERROR
            )
    
    def _toggle_widget_overlay(self, context_data: Optional[Dict[str, Any]] = None):
        """
        Toggle overlay - crea si no existe, cierra si existe
        
        Args:
            context_data: Datos contextuales para pasar al overlay
        """
        try:
            # Obtener argumentos para la instanciación del widget


            widget_args, widget_kwargs = self._get_overlay_widget_args(context_data)
            
            # Toggle usando OverlayManager
            overlay = OverlayManager.get_instance().toggle_overlay(
                widget_class=self.__class__,
                widget_args=widget_args,
                widget_kwargs=widget_kwargs,
                title=f"{self.__class__.__name__} Overlay",
                size=self._get_overlay_default_size(),
                position=self._get_overlay_default_position()
            )
        except Exception as e:
            self._log_overlay_message(
                f"Error en toggle overlay para {self.__class__.__name__}: {str(e)}",
                MessageLevel.ERROR
            )
            
            # Mostrar error al usuario
            wx.MessageBox(
                f"Error en toggle overlay: {str(e)}",
                "Error de Overlay",
                wx.OK | wx.ICON_ERROR
            )
    
    def _get_overlay_widget_args(self, context_data: Optional[Dict[str, Any]] = None) -> tuple:
        """
        Obtener argumentos para el constructor del widget en overlay
        
        Los widgets específicos pueden override este método si necesitan
        argumentos especiales para la instancia del overlay.
        
        Args:
            context_data: Datos contextuales del menú contextual
            
        Returns:
            tuple: (widget_args: list, widget_kwargs: dict)
        """
        # Default: sin argumentos especiales
        # Los widgets que necesiten argumentos específicos pueden override este método
        return [], {}
    
    def _get_overlay_default_size(self) -> tuple:
        """
        Obtener tamaño por defecto para overlay de este widget
        
        Los widgets pueden override este método para especificar
        un tamaño más apropiado para su contenido.
        
        Returns:
            tuple: (width, height) en píxeles
        """
        # Tamaño por defecto más grande y apropiado para widgets de datos
        widget_name = self.__class__.__name__
        if widget_name == "SharedLogsWidget":
            return (800, 400)  # Más ancho para las columnas de logs
        elif widget_name == "StalledWidget":
            return (500, 300)  # Tamaño apropiado para la tabla stalled
        else:
            return (600, 350)  # Tamaño por defecto razonable
    
    def _get_overlay_default_position(self) -> Optional[tuple]:
        """
        Obtener posición por defecto para overlay de este widget
        
        Returns:
            Optional[tuple]: (x, y) en píxeles, o None para usar default del sistema
        """
        # None para usar posición automática del sistema
        return None
    
    def cleanup_overlays(self):
        """
        Limpiar overlays asociados con este widget
        
        Debe ser llamado en el destructor del widget para cleanup apropiado.
        Los widgets pueden override este método si necesitan cleanup específico.
        """
        try:
            # Cerrar todos los overlays de este tipo de widget
            widget_class_name = self.__class__.__name__
            active_overlays = OverlayManager.get_instance().get_active_overlays()
            
            overlays_to_close = []
            for overlay_id, overlay in active_overlays.items():
                if overlay_id.startswith(f"{widget_class_name}_overlay"):
                    overlays_to_close.append(overlay_id)
            
            for overlay_id in overlays_to_close:
                OverlayManager.get_instance().close_overlay(overlay_id)
                
            if overlays_to_close:
                self._log_overlay_message(
                    f"Limpiados {len(overlays_to_close)} overlays para {widget_class_name}",
                    MessageLevel.DEBUG
                )
                
        except Exception as e:
            self._log_overlay_message(
                f"Error en cleanup de overlays para {self.__class__.__name__}: {str(e)}",
                MessageLevel.ERROR
            )
    
    def _log_overlay_message(self, message: str, level: MessageLevel = MessageLevel.INFO):
        """
        Log message relacionado con overlays
        
        Args:
            message: Mensaje a loggear
            level: Nivel del mensaje
        """
        try:
            message_bus.publish(content=f"[{self.__class__.__name__}] {message}", level=level)
        except:
            # Fallback a print si MessageBus no está disponible
            print(f"[{self.__class__.__name__}] {message}")


# Funciones utilitarias para widgets que no pueden usar herencia múltiple
def add_overlay_option_to_menu(widget_instance,
                              menu: wx.Menu,
                              context_data: Optional[Dict[str, Any]] = None,
                              option_label: str = "🔲 Abrir en Overlay",
                              separator_before: bool = True) -> wx.MenuItem:
    """
    Función standalone para añadir overlay option a menú
    
    Para widgets que no pueden usar OverlayMixin (ej. herencia múltiple compleja).
    
    Args:
        widget_instance: Instancia del widget (debe ser wx.Panel subclass)
        menu: Menú contextual al que añadir la opción
        context_data: Datos contextuales
        option_label: Texto de la opción
        separator_before: Si añadir separador antes
        
    Returns:
        wx.MenuItem: El item de menú creado
    """
    # Añadir separador si se solicita
    if separator_before:
        menu.AppendSeparator()
    
    # Crear item de menú
    overlay_item = menu.Append(wx.ID_ANY, option_label)
    
    # Crear función de callback
    def create_overlay(event):
        try:
            overlay = OverlayManager.get_instance().create_overlay(
                widget_class=widget_instance.__class__,
                widget_args=[],
                widget_kwargs={},
                title=f"{widget_instance.__class__.__name__} Overlay",
                size=(450, 350)
            )
            overlay.Show()
        except Exception as e:
            wx.MessageBox(
                f"Error creando overlay: {str(e)}",
                "Error de Overlay",
                wx.OK | wx.ICON_ERROR
            )
    
    # Bind del evento
    widget_instance.Bind(wx.EVT_MENU, create_overlay, overlay_item)
    
    return overlay_item


# Validación del mixin
def validate_overlay_mixin() -> bool:
    """
    Validación básica del OverlayMixin
    
    Returns:
        bool: True si la validación pasa
    """
    try:
        print("=== OverlayMixin Validation ===")
        
        # Test 1: Import dependencies
        print("Test 1: Importing dependencies...")
        from ..overlay.overlay_manager import OverlayManager
        from ..core.message_bus import message_bus, MessageLevel
        print("✓ Dependencies imported successfully")
        
        # Test 2: Mixin class structure
        print("Test 2: OverlayMixin class structure...")
        mixin = OverlayMixin()
        assert hasattr(mixin, 'add_overlay_context_option')
        assert hasattr(mixin, 'add_overlay_toggle_option')
        assert hasattr(mixin, 'cleanup_overlays')
        print("✓ OverlayMixin methods available")
        
        # Test 3: Utility functions
        print("Test 3: Utility functions...")
        assert callable(add_overlay_option_to_menu)
        print("✓ Utility functions available")
        
        print("=== All OverlayMixin tests passed ===")
        return True
        
    except Exception as e:
        print(f"✗ OverlayMixin validation failed: {e}")
        return False


if __name__ == "__main__":
    validate_overlay_mixin()