#!/usr/bin/env python3
"""
HotkeyCapture Widget - Widget para capturar combinaciones de hotkeys

Widget especializado que permite al usuario definir combinaciones de hotkeys
de manera interactiva. Migrado del POC funcional con mejoras para integración
en el sistema de configuración de SC Log Analyzer.
"""

import wx
import wx.lib.scrolledpanel
from typing import Callable, Optional, Set


class HotkeyCapture(wx.Panel):
    """Widget para capturar hotkeys directamente"""
    
    def __init__(self, parent, label: str, current_hotkey: str = "", callback: Optional[Callable[[str], None]] = None):
        """
        Inicializar widget de captura de hotkeys
        
        Args:
            parent: Ventana padre
            label: Etiqueta descriptiva del hotkey
            current_hotkey: Hotkey actual configurado (formato: "ctrl+alt+1")
            callback: Función a llamar cuando se configura un nuevo hotkey
        """
        super().__init__(parent)
        self.current_hotkey = current_hotkey
        self.callback = callback
        self.capturing = False
        self.pressed_keys: Set[str] = set()
        
        self._create_ui(label)
        self._apply_dark_theme()
    
    def _create_ui(self, label: str):
        """Crear interfaz del widget más compacta"""
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Label descriptivo más corto
        label_text = wx.StaticText(self, label=f"{label}:")
        label_text.SetMinSize((180, -1))
        sizer.Add(label_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 2)
        
        # Display del hotkey actual - MOSTRAR VALOR INICIAL
        self.hotkey_display = wx.TextCtrl(self, value=self.current_hotkey, style=wx.TE_READONLY)
        self.hotkey_display.SetMinSize((120, -1))  # Tamaño fijo más pequeño
        sizer.Add(self.hotkey_display, 0, wx.EXPAND | wx.ALL, 2)
        
        # Botones más pequeños
        self.capture_btn = wx.Button(self, label="Capturar")
        self.capture_btn.SetMinSize((65, -1))
        self.capture_btn.Bind(wx.EVT_BUTTON, self._on_capture_click)
        sizer.Add(self.capture_btn, 0, wx.ALL, 2)
        
        clear_btn = wx.Button(self, label="Limpiar")  
        clear_btn.SetMinSize((55, -1))
        clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_click)
        sizer.Add(clear_btn, 0, wx.ALL, 2)
        
        self.SetSizer(sizer)
    
    def _apply_dark_theme(self):
        """Aplicar tema legible - fondo claro con texto oscuro"""
        # Colores legibles para el display
        self.hotkey_display.SetBackgroundColour(wx.Colour(240, 240, 240))
        self.hotkey_display.SetForegroundColour(wx.Colour(0, 0, 0))
        
        # Color de fondo del panel - usar default del sistema
        # self.SetBackgroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW))
    
    def _on_capture_click(self, event):
        """Manejar click del botón de captura"""
        if not self.capturing:
            self._start_capture()
        else:
            self._stop_capture()
    
    def _on_clear_click(self, event):
        """Manejar click del botón de limpiar"""
        self.set_hotkey("")
    
    def _start_capture(self):
        """Iniciar captura de hotkey"""
        self.capturing = True
        self.pressed_keys.clear()
        self.capture_btn.SetLabel("⏹️ Parar")
        self.hotkey_display.SetValue("Presiona teclas... (ESC para cancelar)")
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key_hook)
        self.SetFocus()
    
    def _stop_capture(self):
        """Detener captura de hotkey"""
        self.capturing = False
        self.capture_btn.SetLabel("🎯 Capturar")
        self.Unbind(wx.EVT_CHAR_HOOK)
        
        if self.pressed_keys:
            # Convertir teclas presionadas a string
            hotkey_str = self._keys_to_string(self.pressed_keys)
            self.set_hotkey(hotkey_str)
        else:
            # Restaurar hotkey anterior si no se presionó nada
            self.hotkey_display.SetValue(self.current_hotkey)
    
    def _on_key_hook(self, event):
        """Manejar teclas presionadas durante captura"""
        key_code = event.GetKeyCode()
        
        # ESC cancela la captura
        if key_code == wx.WXK_ESCAPE:
            self._cancel_capture()
            return
        
        # Convertir keycode a nombre
        key_name = self._keycode_to_name(key_code)
        if key_name:
            self.pressed_keys.add(key_name)
            current_combo = self._keys_to_string(self.pressed_keys)
            self.hotkey_display.SetValue(f"Capturando: {current_combo}")
    
    def _cancel_capture(self):
        """Cancelar captura y restaurar estado anterior"""
        self.capturing = False
        self.capture_btn.SetLabel("🎯 Capturar")
        self.hotkey_display.SetValue(self.current_hotkey)
        self.Unbind(wx.EVT_CHAR_HOOK)
    
    def _keycode_to_name(self, keycode: int) -> Optional[str]:
        """Convertir código de tecla wx a nombre string"""
        key_map = {
            wx.WXK_CONTROL: "ctrl",
            wx.WXK_ALT: "alt", 
            wx.WXK_SHIFT: "shift",
            wx.WXK_WINDOWS_LEFT: "cmd",
            wx.WXK_WINDOWS_RIGHT: "cmd",
            wx.WXK_SPACE: "space",
            wx.WXK_RETURN: "enter",
            wx.WXK_ESCAPE: "escape",
            wx.WXK_TAB: "tab",
            wx.WXK_BACK: "backspace",
            wx.WXK_DELETE: "delete",
            wx.WXK_HOME: "home",
            wx.WXK_END: "end",
            wx.WXK_PAGEUP: "page_up",
            wx.WXK_PAGEDOWN: "page_down",
            wx.WXK_UP: "up",
            wx.WXK_DOWN: "down", 
            wx.WXK_LEFT: "left",
            wx.WXK_RIGHT: "right",
            wx.WXK_INSERT: "insert"
        }
        
        # Teclas especiales
        if keycode in key_map:
            return key_map[keycode]
        
        # Caracteres ASCII
        elif 32 <= keycode <= 126:
            char = chr(keycode).lower()
            if char.isalnum():
                return char
        
        # Teclas de función
        elif wx.WXK_F1 <= keycode <= wx.WXK_F24:
            return f"f{keycode - wx.WXK_F1 + 1}"
        
        # Teclado numérico
        elif wx.WXK_NUMPAD0 <= keycode <= wx.WXK_NUMPAD9:
            return f"num{keycode - wx.WXK_NUMPAD0}"
        
        return None
    
    def _keys_to_string(self, keys: Set[str]) -> str:
        """Convertir conjunto de teclas a string ordenado"""
        if not keys:
            return ""
        
        # Orden de modificadores
        modifiers = ["ctrl", "alt", "shift", "cmd"]
        ordered_keys = []
        
        # Añadir modificadores en orden
        for mod in modifiers:
            if mod in keys:
                ordered_keys.append(mod)
        
        # Añadir teclas regulares ordenadas
        for key in sorted(keys):
            if key not in modifiers:
                ordered_keys.append(key)
        
        return "+".join(ordered_keys)
    
    def set_hotkey(self, hotkey: str):
        """
        Establecer hotkey programáticamente
        
        Args:
            hotkey: Nueva combinación de hotkey (formato: "ctrl+alt+1")
        """
        self.current_hotkey = hotkey
        
        # Mostrar el valor actual o placeholder si está vacío
        display_value = hotkey if hotkey else "(sin configurar)"
        self.hotkey_display.SetValue(display_value)
        
        # Notificar callback si existe
        if self.callback:
            try:
                self.callback(hotkey)
            except Exception as e:
                # No propagar errores del callback
                print(f"Error in hotkey callback: {e}")
    
    def get_hotkey(self) -> str:
        """
        Obtener hotkey actual
        
        Returns:
            str: Combinación actual de hotkey
        """
        return self.current_hotkey
    
    def validate_hotkey(self, hotkey: str) -> bool:
        """
        Validar formato de hotkey
        
        Args:
            hotkey: Combinación a validar
            
        Returns:
            bool: True si el formato es válido
        """
        if not hotkey or not isinstance(hotkey, str):
            return False
        
        parts = hotkey.lower().split('+')
        if not parts:
            return False
        
        valid_modifiers = {'ctrl', 'alt', 'shift', 'cmd'}
        valid_keys = set('abcdefghijklmnopqrstuvwxyz0123456789')
        valid_keys.update([f'f{i}' for i in range(1, 25)])  # F1-F24
        valid_keys.update(['space', 'enter', 'tab', 'escape', 'esc', 'backspace', 'delete', 
                          'home', 'end', 'page_up', 'page_down', 'up', 'down', 'left', 'right',
                          'insert', 'caps_lock', 'scroll_lock', 'num_lock', 'print_screen', 'pause', 'menu'])
        
        for part in parts:
            part = part.strip()
            if not part:
                return False
            if part not in valid_modifiers and part not in valid_keys:
                # Permitir caracteres individuales
                if len(part) != 1:
                    return False
        
        return True
    
    def is_capturing(self) -> bool:
        """
        Verificar si está en modo captura
        
        Returns:
            bool: True si está capturando
        """
        return self.capturing


class HotkeyConfigPanel(wx.Panel):
    """Panel completo de configuración de hotkeys - sin botones propios"""
    
    def __init__(self, parent, config_manager):
        """
        Inicializar panel de configuración de hotkeys
        
        Args:
            parent: Ventana padre
            config_manager: Instancia del ConfigManager
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.hotkey_widgets = {}
        
        self._create_ui()
        self._load_current_hotkeys()
    
    def _create_ui(self):
        """Crear interfaz del panel compacta"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título más pequeño
        title = wx.StaticText(self, label="⌨️ Hotkeys")
        title_font = title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 5)
        
        # Panel scrollable para el contenido
        scrolled_panel = wx.lib.scrolledpanel.ScrolledPanel(self)
        scrolled_panel.SetupScrolling(scroll_x=False, scroll_y=True)
        scrolled_panel.SetBackgroundColour(wx.Colour(240, 240, 240))
        config_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Sección de Overlays - más compacta
        # Crear widgets dinámicamente basado en hotkeys registrados
        try:
            from .hotkey_manager import get_hotkey_manager
            hotkey_manager = get_hotkey_manager()
            hotkeys_by_category = hotkey_manager.get_hotkeys_by_category()
            
            # Mapeo de iconos por categoría
            category_icons = {
                'Overlay': '🖼️',
                'System': '🛠️',
                'General': '⚙️'
            }
            
            first_category = True
            for category_name in sorted(hotkeys_by_category.keys()):
                # Spacer entre categorías (excepto la primera)
                if not first_category:
                    config_sizer.Add(wx.StaticLine(scrolled_panel), 0, wx.EXPAND | wx.ALL, 5)
                first_category = False
                
                # Añadir label de categoría
                icon = category_icons.get(category_name, '📋')
                category_label = wx.StaticText(scrolled_panel, label=f"{icon} {category_name}:")
                category_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                config_sizer.Add(category_label, 0, wx.ALL, 3)
                
                # Añadir widgets de hotkeys de esta categoría
                category_hotkeys = hotkeys_by_category[category_name]
                for event_name, metadata in category_hotkeys.items():
                    description = metadata['description']
                    widget = HotkeyCapture(scrolled_panel, description, callback=lambda hk, en=event_name: self._on_hotkey_changed(en, hk))
                    self.hotkey_widgets[event_name] = widget
                    config_sizer.Add(widget, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 5)
                    
        except Exception as e:
            # Fallback si hay algún problema - mostrar mensaje de error
            error_label = wx.StaticText(scrolled_panel, label="Error loading hotkeys dynamically")
            config_sizer.Add(error_label, 0, wx.ALL, 5)
        
        # Info más corta
        config_sizer.Add(wx.StaticLine(scrolled_panel), 0, wx.EXPAND | wx.ALL, 5)
        info_text = wx.StaticText(scrolled_panel, 
            label="💡 Usa 'Capturar' para cambiar hotkey. Cambios se guardan con 'Accept'.")
        info_text.SetFont(wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        config_sizer.Add(info_text, 0, wx.ALL, 5)
        
        scrolled_panel.SetSizer(config_sizer)
        main_sizer.Add(scrolled_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        self.SetSizer(main_sizer)
    
    def _load_current_hotkeys(self):
        """Cargar hotkeys actuales dinámicamente desde HotkeyManager registrados"""
        try:
            from .hotkey_manager import get_hotkey_manager
            hotkey_manager = get_hotkey_manager()
            
            # Obtener hotkeys registrados dinámicamente 
            registered_hotkeys = hotkey_manager.get_registered_hotkeys_info()
            
            for event_name, metadata in registered_hotkeys.items():
                if event_name in self.hotkey_widgets:
                    # Usar combinación actual (ya procesada por ConfigManager)
                    current_combination = metadata.get('current_combination', '')
                    # Convertir de formato pynput a formato config para mostrar
                    display_combination = self._convert_from_pynput_format(current_combination)
                    self.hotkey_widgets[event_name].set_hotkey(display_combination)
                    
        except Exception as e:
            # Fallback si hay algún problema
            pass
        
        # Guardar estado inicial DESPUÉS de cargar valores
        self.initial_state = {}
        for event_name, widget in self.hotkey_widgets.items():
            self.initial_state[event_name] = widget.get_hotkey()
    
    def get_modified_hotkeys(self):
        """Solo devuelve lo que cambió respecto al estado inicial"""
        modified = {}
        for event_name, widget in self.hotkey_widgets.items():
            current = widget.get_hotkey()
            initial = self.initial_state.get(event_name, '')
            
            if current != initial:
                modified[f'hotkeys.{event_name}'] = current
        
        return modified
    
    def _convert_from_pynput_format(self, pynput_combination: str) -> str:
        """Convertir de formato pynput a formato config para mostrar"""
        if not pynput_combination:
            return ''
        
        # Mapeo inverso de pynput a config
        reverse_mapping = {
            '<ctrl>': 'ctrl',
            '<alt>': 'alt', 
            '<shift>': 'shift',
            '<cmd>': 'cmd',
            '<esc>': 'escape',
            '<enter>': 'enter',
            '<space>': 'space',
            '<tab>': 'tab'
        }
        
        result = pynput_combination
        for pynput_key, config_key in reverse_mapping.items():
            result = result.replace(pynput_key, config_key)
        
        return result
    
    def _on_hotkey_changed(self, event_name: str, hotkey: str):
        """Callback cuando se cambia un hotkey - solo actualizar en memoria, no guardar"""
        # Validar hotkey
        if hotkey and not self.hotkey_widgets[event_name].validate_hotkey(hotkey):
            wx.MessageBox(
                f"Formato de hotkey inválido: '{hotkey}'",
                "Error de Validación", 
                wx.OK | wx.ICON_ERROR
            )
            return
        
        # Solo actualizar en memoria - no guardar hasta que user presione Accept
        self.config_manager.set(f'hotkeys.{event_name}', hotkey)
    
    def get_current_hotkeys(self):
        """Obtener configuración actual de hotkeys desde los widgets"""
        current_config = {}
        for event_name, widget in self.hotkey_widgets.items():
            current_config[f'hotkeys.{event_name}'] = widget.get_hotkey()
        return current_config


def main():
    """Testing del widget de captura de hotkeys"""
    app = wx.App()
    
    frame = wx.Frame(None, title="HotkeyCapture Widget Test", size=(600, 400))
    panel = wx.Panel(frame)
    sizer = wx.BoxSizer(wx.VERTICAL)
    
    # Widget de prueba
    def on_hotkey_captured(hotkey):
        print(f"Hotkey captured: '{hotkey}'")
    
    hotkey_widget = HotkeyCapture(panel, "Test Hotkey", "ctrl+alt+t", on_hotkey_captured)
    sizer.Add(hotkey_widget, 0, wx.EXPAND | wx.ALL, 10)
    
    panel.SetSizer(sizer)
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()