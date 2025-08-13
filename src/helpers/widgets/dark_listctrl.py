#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import wx
import ctypes
import re
from datetime import datetime

class DarkListCtrl(wx.ListCtrl):
    """
    ListCtrl personalizado basado en wx.ListCtrl nativo con:
    - Tema visual deshabilitado
    - Colores oscuros por defecto
    - API compatible con wx.ListCtrl
    - Ordenación transparente de columnas
    - Auto-sizing inteligente de columnas
    """
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=wx.LC_REPORT,
                 validator=wx.DefaultValidator, name="DarkListCtrl", **kwargs):
        
        # Extraer parámetros específicos de auto-sizing de kwargs
        self.auto_sizing_enabled = kwargs.pop('auto_sizing', True)  # Por defecto: True
        self.max_width_percent = kwargs.pop('max_width_percent', 0.4)  # 40% máximo
        self.min_width = kwargs.pop('min_width', 50)  # Mínimo absoluto

        # Flag para evitar acumulación de wx.CallAfter
        self._autosize_pending = False
        
        # Crear el ListCtrl base con kwargs restantes (API intacta)
        super().__init__(parent, id, pos, size, style, validator, name)
        
        # Variables de ordenación
        self._sort_column = -1
        self._sort_direction = 'asc'
        self._sorting_enabled = True
        self._original_data = []  # Para preservar datos originales
        self._original_headers = []  # Para preservar headers originales
        
        # Aplicar configuración personalizada
        self._apply_custom_theme()
        self._disable_visual_theme()
        
        # Habilitar ordenación por defecto
        self._setup_sorting()
    
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
    
    def _setup_sorting(self):
        """Configurar funcionalidad de ordenación"""
        if self._sorting_enabled:
            self.Bind(wx.EVT_LIST_COL_CLICK, self._on_column_header_click)
    
    def _on_column_header_click(self, event):
        """Maneja clicks en headers de columnas para ordenación"""
        if not self._sorting_enabled:
            event.Skip()
            return
            
        column = event.GetColumn()
        
        if column == self._sort_column:
            # Alternar dirección si es la misma columna
            self._sort_direction = 'desc' if self._sort_direction == 'asc' else 'asc'
        else:
            # Nueva columna, ordenar ascendente
            self._sort_column = column
            self._sort_direction = 'asc'
        
        self._sort_data(column, self._sort_direction)
        self._update_sort_indicator()
        event.Skip()
    
    def _sort_data(self, column, direction):
        """Ordena los datos de la columna especificada"""
        if self.GetItemCount() == 0:
            return
        
        # Obtener todos los datos
        data = []
        for i in range(self.GetItemCount()):
            item_data = []
            for col in range(self.GetColumnCount()):
                item_data.append(self.GetItem(i, col).GetText())
            data.append((item_data, self.GetItemData(i)))
        
        # Ordenar por la columna especificada
        data_type = self._detect_column_data_type(column, data)
        reverse = direction == 'desc'
        
        data.sort(key=lambda x: self._convert_for_sort(x[0][column], data_type), reverse=reverse)
        
        # Reconstruir la lista
        super().DeleteAllItems()
        for item_data, item_id in data:
            index = self.InsertItem(self.GetItemCount(), item_data[0])
            for col, text in enumerate(item_data[1:], 1):
                self.SetItem(index, col, text)
            self.SetItemData(index, item_id)
    
    def _detect_column_data_type(self, column, data):
        """Detecta el tipo de datos de una columna"""
        if not data:
            return 'string'
        
        # Analizar muestras de datos
        samples = [row[0][column] for row in data[:10] if row[0][column]]
        
        if not samples:
            return 'string'
        
        # Detectar fechas (formato HH:MM o similar)
        if all(re.match(r'\d{1,2}:\d{2}', str(s)) for s in samples):
            return 'time'
        
        # Detectar números
        try:
            [float(s) for s in samples]
            return 'numeric'
        except (ValueError, TypeError):
            pass
        
        return 'string'
    
    def _convert_for_sort(self, value, data_type):
        """Convierte valor para ordenación según el tipo de datos"""
        if not value:
            return '' if data_type == 'string' else 0
        
        if data_type == 'numeric':
            try:
                return float(value)
            except (ValueError, TypeError):
                return 0
        elif data_type == 'time':
            try:
                # Convertir HH:MM a minutos para ordenación numérica
                hours, minutes = map(int, value.split(':'))
                return hours * 60 + minutes
            except (ValueError, TypeError):
                return 0
        else:
            return str(value).lower()
    
    def _update_sort_indicator(self):
        """Actualiza los indicadores visuales de ordenación"""
        for col in range(self.GetColumnCount()):
            # Obtener el texto original del header sin indicadores
            original_text = self._get_original_header_text(col)
            
            if col == self._sort_column:
                # Añadir flecha según la dirección
                arrow = " ⬇️" if self._sort_direction == 'desc' else " ⬆️"
                new_text = original_text + arrow
            else:
                new_text = original_text
            
            # Actualizar el texto del header
            self._set_column_header_text(col, new_text)
    
    def _get_original_header_text(self, column):
        """Obtiene el texto original del header sin indicadores de ordenación"""
        header_text = self.GetColumn(column).GetText()
        # Remover cualquier indicador de ordenación existente
        return header_text.replace(" ⬆️", "").replace(" ⬇️", "")
    
    def _set_column_header_text(self, column, text):
        """Establece el texto del header de manera segura"""
        try:
            # Usar el método correcto de wx.ListCtrl
            column_item = wx.ListItem()
            column_item.SetText(text)
            self.SetColumn(column, column_item)
        except Exception as e:
            # Si falla, no hacer nada para evitar errores
            pass
    
    def _clear_sort_indicators(self):
        """Limpia todos los indicadores de ordenación"""
        for col in range(self.GetColumnCount()):
            original_text = self._get_original_header_text(col)
            self._set_column_header_text(col, original_text)
    
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
    
    # Métodos de ordenación para API pública
    def enable_sorting(self, enable=True):
        """Habilita o deshabilita la ordenación de columnas"""
        self._sorting_enabled = enable
        if not enable:
            self._clear_sort_indicators()
            self._sort_column = -1
            self._sort_direction = 'asc'
    
    def set_sort_column(self, column, direction='asc'):
        """Establece la ordenación programáticamente"""
        if 0 <= column < self.GetColumnCount():
            self._sort_column = column
            self._sort_direction = direction
            self._sort_data(column, direction)
            self._update_sort_indicator()
    
    def get_sort_state(self):
        """Obtiene el estado actual de ordenación"""
        return {
            'column': self._sort_column,
            'direction': self._sort_direction,
            'enabled': self._sorting_enabled
        }
    
    def clear_sort(self):
        """Limpia la ordenación actual"""
        self._sort_column = -1
        self._sort_direction = 'asc'
        self._clear_sort_indicators()
    
    # Override de métodos para preservar ordenación
    def DeleteAllItems(self):
        """Override para limpiar estado de ordenación y auto-sizing"""
        result = super().DeleteAllItems()
        self._sort_column = -1
        self._sort_direction = 'asc'
        self._trigger_auto_sizing()
        return result

    def InsertItem(self, *args, **kwargs):
        """Override para auto-sizing tras insertar item"""
        result = super().InsertItem(*args, **kwargs)
        self._trigger_auto_sizing()
        return result

    def SetItem(self, *args, **kwargs):
        """Override para auto-sizing tras modificar item"""
        result = super().SetItem(*args, **kwargs)
        self._trigger_auto_sizing()
        return result

    def DeleteItem(self, *args, **kwargs):
        """Override para auto-sizing tras eliminar item"""
        result = super().DeleteItem(*args, **kwargs)
        self._trigger_auto_sizing()
        return result

    def calculate_column_width(self, col_index):
        """Calcular ancho óptimo basado en contenido y header"""
        try:
            header_width = self.GetTextExtent(self.GetColumn(col_index).GetText())[0]
            
            max_content_width = 0
            for row in range(self.GetItemCount()):
                content = self.GetItemText(row, col_index)
                content_width = self.GetTextExtent(content)[0]
                max_content_width = max(max_content_width, content_width)
            
            # Ancho óptimo = max(header, contenido) + padding
            return max(header_width, max_content_width) + 20
        except Exception:
            return self.min_width
    
    def auto_size_columns(self):
        """Auto-sizing con límite basado en ancho total del componente"""
        if not self.auto_sizing_enabled:
            return
            
        try:
            # Obtener ancho total disponible
            total_width = self.GetSize()[0]
            if total_width <= 0:
                return  # No auto-sizing si el widget no está dimensionado
                
            max_column_width = int(total_width * self.max_width_percent)
            
            for col in range(self.GetColumnCount()):
                # Calcular ancho óptimo
                optimal_width = self.calculate_column_width(col)
                
                # Aplicar límites: mínimo y máximo
                final_width = max(self.min_width, min(optimal_width, max_column_width))
                self.SetColumnWidth(col, final_width)
        except Exception:
            # Si hay error en auto-sizing, no hacer nada (silent fail)
            pass
    
    def enable_auto_sizing(self, enabled=True):
        """Habilitar/deshabilitar auto-sizing"""
        self.auto_sizing_enabled = enabled
        if enabled:
            self.auto_size_columns()
    
    def set_max_width_percent(self, percent):
        """Configurar porcentaje máximo por columna"""
        self.max_width_percent = percent
        if self.auto_sizing_enabled:
            self.auto_size_columns()
    
    def _trigger_auto_sizing(self):
        """Hook thread-safe para updates automáticos"""
        if self.auto_sizing_enabled and not self._autosize_pending:
            self._autosize_pending = True
            wx.CallAfter(self._safe_auto_size_columns)

    def _safe_auto_size_columns(self):
            """Llama a auto_size_columns y limpia el flag de pendiente"""
            try:
                self.auto_size_columns()
            finally:
                self._autosize_pending = False


# Alias para compatibilidad (actualizado)
ListCtrlAdapter = DarkListCtrl


def create_custom_listctrl(parent, **kwargs):
    """
    Factory function para crear DarkListCtrl con configuración estándar
    """
    # Configuración por defecto
    default_kwargs = {
        'style': wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES,
    }
    default_kwargs.update(kwargs)
    
    listctrl = DarkListCtrl(parent, **default_kwargs)
    return listctrl 