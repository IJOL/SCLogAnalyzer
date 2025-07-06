#!/usr/bin/env python
import wx

class ToggleButtonWidget(wx.Panel):
    """
    Widget genérico de botón bi-estado configurable.
    Usa el estilo darkbutton con textos configurables.
    """
    
    def __init__(self, parent, on_text="ON", off_text="OFF", 
                 on_color=None, off_color=None, tooltip=""):
        super().__init__(parent)
        self.on_text = on_text
        self.off_text = off_text
        self.on_color = on_color or wx.Colour(0, 128, 0)  # Verde por defecto
        self.off_color = off_color or wx.Colour(128, 0, 0)  # Rojo por defecto
        self.tooltip = tooltip
        self.enabled = False  # Por defecto deshabilitado
        
        self._init_ui()
        self._update_ui_state()
    
    def _init_ui(self):
        # Crear sizer horizontal
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botón bi-estado (usar wx.ToggleButton)
        self.toggle_button = wx.ToggleButton(
            self, 
            label=self.on_text if self.enabled else self.off_text,
            size=(60, 25)
        )
        self.toggle_button.SetValue(self.enabled)
        self.toggle_button.SetToolTip(self.tooltip)
        self.toggle_button.Bind(wx.EVT_TOGGLEBUTTON, self._on_toggle)
        
        # Añadir solo el botón al sizer
        sizer.Add(self.toggle_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.SetSizer(sizer)
        self._update_ui_state()
    
    def _on_toggle(self, event):
        # Aplicar cambio inmediatamente
        self.enabled = self.toggle_button.GetValue()
        
        # Actualizar UI
        self.toggle_button.SetLabel(self.on_text if self.enabled else self.off_text)
        self._update_ui_state()
        
        # Propagar el evento wxPython estándar
        event.Skip()
    
    def _update_ui_state(self):
        # Aplicar colores según estado
        if self.enabled:
            self.toggle_button.SetBackgroundColour(self.on_color)
            self.toggle_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
        else:
            self.toggle_button.SetBackgroundColour(self.off_color)
            self.toggle_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
    
    def GetValue(self):
        """Obtener el valor actual del widget."""
        return self.enabled
    
    def SetValue(self, value):
        """Establecer el valor del widget programáticamente."""
        self.enabled = bool(value)
        self.toggle_button.SetValue(self.enabled)
        self.toggle_button.SetLabel(self.on_text if self.enabled else self.off_text)
        self._update_ui_state()
    
    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """Delegar el Bind al botón interno."""
        return self.toggle_button.Bind(event, handler, source, id, id2) 