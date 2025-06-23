#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import wx
import ctypes

class CustomListCtrl(wx.ListCtrl):
    """
    ListCtrl personalizado basado en wx.ListCtrl nativo con:
    - Tema visual deshabilitado
    - Colores oscuros por defecto
    - API compatible con wx.ListCtrl
    """
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition, 
                 size=wx.DefaultSize, style=wx.LC_REPORT, 
                 validator=wx.DefaultValidator, name="CustomListCtrl"):
        
        # Crear el ListCtrl base
        super().__init__(parent, id, pos, size, style, validator, name)
        
        # Aplicar configuración personalizada
        self._apply_custom_theme()
        self._disable_visual_theme()
    
    def _apply_custom_theme(self):
        """Aplicar tema oscuro personalizado"""
        # Colores de fondo y texto
        self.SetBackgroundColour(wx.Colour(80, 80, 80))  # Gris oscuro
        self.SetForegroundColour(wx.Colour(230, 230, 230))  # Texto claro
        
    def _disable_visual_theme(self):
        """Deshabilitar tema visual de Windows para personalización completa"""
        try:
            # Deshabilitar tema del ListCtrl principal
            uxtheme = ctypes.windll.uxtheme
            hwnd = self.GetHandle()
            uxtheme.SetWindowTheme(hwnd, "", "")
            
            # Buscar y deshabilitar tema del header también
            import win32gui
            header_hwnd = win32gui.FindWindowEx(hwnd, 0, "SysHeader32", None)
            if header_hwnd:
                uxtheme.SetWindowTheme(header_hwnd, "", "")
                
        except Exception:
            # Si falla, no es crítico
            pass
    
    # Métodos de conveniencia para temas
    def apply_dark_theme(self):
        """Aplicar tema oscuro"""
        self.SetBackgroundColour(wx.Colour(80, 80, 80))
        self.SetForegroundColour(wx.Colour(230, 230, 230))
        self.Refresh()
    
    def apply_light_theme(self):
        """Aplicar tema claro"""
        self.SetBackgroundColour(wx.Colour(255, 255, 255))
        self.SetForegroundColour(wx.Colour(0, 0, 0))
        self.Refresh()


# Alias para compatibilidad
ListCtrlAdapter = CustomListCtrl


def create_custom_listctrl(parent, **kwargs):
    """
    Factory function para crear CustomListCtrl con configuración estándar
    """
    # Configuración por defecto
    default_kwargs = {
        'style': wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES,
    }
    default_kwargs.update(kwargs)
    
    listctrl = CustomListCtrl(parent, **default_kwargs)
    return listctrl 