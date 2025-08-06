#!/usr/bin/env python3
"""
HotkeyCapture Widget - Widget para capturar combinaciones de hotkeys

Widget especializado que permite al usuario definir combinaciones de hotkeys
de manera interactiva. Migrado del POC funcional con mejoras para integración
en el sistema de configuración de SC Log Analyzer.
"""

import wx
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
        """Crear interfaz del widget"""
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Label descriptivo
        label_text = wx.StaticText(self, label=f"{label}:")
        label_text.SetMinSize((200, -1))
        sizer.Add(label_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        
        # Display del hotkey actual
        self.hotkey_display = wx.TextCtrl(self, value=self.current_hotkey, style=wx.TE_READONLY)
        sizer.Add(self.hotkey_display, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botón de captura
        self.capture_btn = wx.Button(self, label="🎯 Capturar")
        self.capture_btn.Bind(wx.EVT_BUTTON, self._on_capture_click)
        sizer.Add(self.capture_btn, 0, wx.ALL, 5)
        
        # Botón de limpiar
        clear_btn = wx.Button(self, label="🗑️ Limpiar")
        clear_btn.Bind(wx.EVT_BUTTON, self._on_clear_click)
        sizer.Add(clear_btn, 0, wx.ALL, 5)
        
        self.SetSizer(sizer)
    
    def _apply_dark_theme(self):
        """Aplicar tema oscuro al widget"""
        # Colores oscuros para el display
        self.hotkey_display.SetBackgroundColour(wx.Colour(45, 45, 45))
        self.hotkey_display.SetForegroundColour(wx.Colour(255, 255, 255))
        
        # Color de fondo del panel
        self.SetBackgroundColour(wx.Colour(32, 32, 32))
    
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
            wx.WXK_BACK: "backspace"
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
        self.hotkey_display.SetValue(hotkey)
        
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
        valid_keys.update(['space', 'enter', 'tab', 'escape', 'backspace'])
        
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
    """Panel completo de configuración de hotkeys"""
    
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
        """Crear interfaz del panel"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(self, label="⌨️ Configuración de Hotkeys")
        title_font = title.GetFont()
        title_font.SetPointSize(14)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL | wx.CENTER, 10)
        
        # Scroll panel para las configuraciones
        scroll_panel = wx.ScrolledWindow(self)
        scroll_panel.SetScrollRate(5, 5)
        scroll_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Sección de Overlays
        overlay_box = wx.StaticBox(scroll_panel, label="🖼️ Hotkeys de Overlays")
        overlay_sizer = wx.StaticBoxSizer(overlay_box, wx.VERTICAL)
        
        overlay_hotkeys = [
            ("overlay_toggle_stalled", "Toggle Stalled Widget"),
            ("overlay_toggle_shared_logs", "Toggle Shared Logs"),
            ("overlay_toggle_all", "Toggle All Overlays"),
            ("overlay_close_all", "Emergency Close All")
        ]
        
        for event_name, description in overlay_hotkeys:
            widget = HotkeyCapture(scroll_panel, description, callback=lambda hk, en=event_name: self._on_hotkey_changed(en, hk))
            self.hotkey_widgets[event_name] = widget
            overlay_sizer.Add(widget, 0, wx.EXPAND | wx.ALL, 5)
        
        scroll_sizer.Add(overlay_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        # Sección de Sistema
        system_box = wx.StaticBox(scroll_panel, label="🛠️ Hotkeys de Sistema")
        system_sizer = wx.StaticBoxSizer(system_box, wx.VERTICAL)
        
        system_hotkeys = [
            ("system_toggle_monitoring", "Toggle Monitoring"),
            ("system_auto_shard", "Auto Shard"),
            ("system_open_config", "Open Config"),
            ("system_toggle_recording", "Toggle Recording")
        ]
        
        for event_name, description in system_hotkeys:
            widget = HotkeyCapture(scroll_panel, description, callback=lambda hk, en=event_name: self._on_hotkey_changed(en, hk))
            self.hotkey_widgets[event_name] = widget
            system_sizer.Add(widget, 0, wx.EXPAND | wx.ALL, 5)
        
        scroll_sizer.Add(system_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        scroll_panel.SetSizer(scroll_sizer)
        main_sizer.Add(scroll_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Botones de acción
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        reset_btn = wx.Button(self, label="↺ Restaurar Defaults")
        reset_btn.Bind(wx.EVT_BUTTON, self._on_reset_defaults)
        button_sizer.Add(reset_btn, 0, wx.ALL, 5)
        
        button_sizer.AddStretchSpacer()
        
        apply_btn = wx.Button(self, label="✓ Aplicar")
        apply_btn.Bind(wx.EVT_BUTTON, self._on_apply_changes)
        button_sizer.Add(apply_btn, 0, wx.ALL, 5)
        
        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    
    def _load_current_hotkeys(self):
        """Cargar hotkeys actuales desde configuración"""
        for event_name, widget in self.hotkey_widgets.items():
            current_hotkey = self.config_manager.get(f'hotkeys.{event_name}', '')
            widget.set_hotkey(current_hotkey)
    
    def _on_hotkey_changed(self, event_name: str, hotkey: str):
        """Callback cuando se cambia un hotkey"""
        # Validar hotkey
        if hotkey and not self.hotkey_widgets[event_name].validate_hotkey(hotkey):
            wx.MessageBox(
                f"Formato de hotkey inválido: '{hotkey}'",
                "Error de Validación",
                wx.OK | wx.ICON_ERROR
            )
            return
        
        # Actualizar configuración
        self.config_manager.set(f'hotkeys.{event_name}', hotkey)
        
        # Log del cambio
        try:
            from .message_bus import message_bus, MessageLevel
            message_bus.publish(
                f"Hotkey changed: {event_name} = '{hotkey}'",
                MessageLevel.DEBUG
            )
        except ImportError:
            print(f"Hotkey changed: {event_name} = '{hotkey}'")
    
    def _on_reset_defaults(self, event):
        """Restaurar hotkeys a valores por defecto"""
        defaults = {
            "overlay_toggle_stalled": "ctrl+alt+1",
            "overlay_toggle_shared_logs": "ctrl+alt+2",
            "overlay_toggle_all": "ctrl+alt+0",
            "overlay_close_all": "ctrl+alt+escape",
            "system_toggle_monitoring": "ctrl+alt+m",
            "system_auto_shard": "ctrl+alt+s",
            "system_open_config": "ctrl+alt+c",
            "system_toggle_recording": "ctrl+alt+r"
        }
        
        for event_name, default_hotkey in defaults.items():
            if event_name in self.hotkey_widgets:
                self.hotkey_widgets[event_name].set_hotkey(default_hotkey)
    
    def _on_apply_changes(self, event):
        """Aplicar cambios de configuración"""
        try:
            # Guardar configuración
            self.config_manager.save_config()
            
            wx.MessageBox(
                "Configuración de hotkeys aplicada correctamente.\n\nLos cambios serán efectivos inmediatamente.",
                "Configuración Aplicada",
                wx.OK | wx.ICON_INFORMATION
            )
            
        except Exception as e:
            wx.MessageBox(
                f"Error aplicando configuración: {e}",
                "Error",
                wx.OK | wx.ICON_ERROR
            )


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