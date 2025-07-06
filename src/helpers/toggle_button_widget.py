#!/usr/bin/env python
import wx
from wx.lib import buttons

class ToggleButtonWidget(wx.Panel):
    """
    Widget genérico de botón bi-estado configurable.
    Usa el mismo estilo visual que DarkThemeButton pero con colores rojo/verde.
    """
    
    def __init__(self, parent, on_text="ON", off_text="OFF", 
                 on_color=None, off_color=None, tooltip=""):
        super().__init__(parent)
        self.on_text = on_text
        self.off_text = off_text
        self.on_color = on_color or wx.Colour(0, 128, 0)  # Verde por defecto
        self.off_color = off_color or wx.Colour(128, 0, 0)  # Rojo por defecto
        self.tooltip = tooltip
        
        self._init_ui()
    
    def _init_ui(self):
        # Crear sizer horizontal
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botón con estilo DarkThemeButton pero colores personalizados
        self.toggle_button = buttons.GenButton(
            self, 
            label=self.off_text,  # Empezar con OFF
            size=(60, 25),
            style=wx.BORDER_NONE
        )
        self._button_state = False  # Estado interno
        self.toggle_button.SetToolTip(self.tooltip)
        self.toggle_button.Bind(wx.EVT_BUTTON, self._on_click)
        
        # Configurar estilo visual igual que DarkThemeButton
        self.toggle_button.SetBezelWidth(1)  # Borde más fino
        
        # Añadir solo el botón al sizer
        sizer.Add(self.toggle_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.SetSizer(sizer)
        self._update_ui_state()
    
    def _on_click(self, event):
        # Cambiar estado interno
        self._button_state = not self._button_state
        
        # Actualizar UI
        self._update_ui_state()
        
        # Propagar el evento wxPython estándar
        event.Skip()
    
    def _update_ui_state(self):
        # Usar el estado interno
        is_enabled = self._button_state
        self._update_ui_state_with_value(is_enabled)
    
    def _update_ui_state_with_value(self, is_enabled):
        # Actualizar etiqueta y colores
        self.toggle_button.SetLabel(self.on_text if is_enabled else self.off_text)
        
        # Aplicar colores según estado (mismo estilo que DarkThemeButton)
        if is_enabled:
            self.toggle_button.SetBackgroundColour(self.on_color)
            self.toggle_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
        else:
            self.toggle_button.SetBackgroundColour(self.off_color)
            self.toggle_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
        
        # Forzar refresco
        self.toggle_button.Refresh()
        self.toggle_button.Update()
        self.Refresh()
        self.Update()
    
    def GetValue(self):
        """Obtener el valor actual del widget."""
        return self._button_state
    
    def SetValue(self, value):
        """Establecer el valor del widget programáticamente."""
        self._button_state = bool(value)
        self._update_ui_state()
    
    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """Delegar el Bind al botón interno."""
        return self.toggle_button.Bind(event, handler, source, id, id2) 