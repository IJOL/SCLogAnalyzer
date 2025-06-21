#!/usr/bin/env python
"""
UltimateListCtrlAdapter - Adapter drop-in para wx.ListCtrl con soporte de colores de cabecera y alineación usando UltimateListCtrl.
"""

import wx
import wx.lib.agw.ultimatelistctrl as ULC

class CustomHeaderRenderer:
    """
    Renderer personalizado para las cabeceras de UltimateListCtrl
    que permite controlar colores de fondo, texto y alineación por columna.
    """
    def __init__(self, listctrl, col):
        self.listctrl = listctrl
        self.col = col
        self.bg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
        self.fg = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)
        # Siempre negrita para cabecera
        font = wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        self.font = font
        self.align = wx.ALIGN_LEFT

    def set_colors(self, bg=None, fg=None):
        if bg is not None:
            self.bg = bg
        if fg is not None:
            self.fg = fg

    def set_font(self, font):
        self.font = font

    def set_align(self, align):
        self.align = align

    def DrawHeaderButton(self, dc, rect, flags):
        bg = self.bg
        fg = self.fg
        font = self.font
        align = self.align
        
        # Fondo principal
        dc.SetBrush(wx.Brush(bg))
        dc.SetPen(wx.Pen(bg))
        dc.DrawRectangle(rect)
        
        # Separador derecho (línea vertical clara) - versión original
        separator_color = wx.Colour(160, 160, 160)  # Gris claro para separador
        dc.SetPen(wx.Pen(separator_color, 1))
        dc.DrawLine(rect.x + rect.width - 1, rect.y, 
                   rect.x + rect.width - 1, rect.y + rect.height)
        
        # Texto
        dc.SetTextForeground(fg)
        dc.SetFont(font)
        dc.SetBackgroundMode(wx.TRANSPARENT)
        text = self._get_column_text()
        w, h = dc.GetTextExtent(text)
        x = rect.x + 6
        if align == wx.ALIGN_CENTER:
            x = rect.x + (rect.width - w) // 2
        elif align == wx.ALIGN_RIGHT:
            x = rect.x + rect.width - w - 6
        y = rect.y + (rect.height - h) // 2
        dc.DrawText(text, x, y)
        return True

    def GetForegroundColour(self):
        return self.fg

    def _get_column_text(self):
        try:
            return self.listctrl.GetColumn(self.col).GetText()
        except Exception:
            return ""

class UltimateListCtrlAdapter(ULC.UltimateListCtrl):
    """
    Adapter drop-in para wx.ListCtrl con soporte de colores de cabecera y alineación usando UltimateListCtrl.
    """
    
    # FLAG para controlar el workaround de inserción en posición 0
    # True = usar workaround brutal (seguro pero lento)
    # False = usar fix nativo en UltimateListCtrl (rápido pero experimental)
    USE_INSERT_ZERO_WORKAROUND = False  # Cambiado a False para probar el fix nativo
    
    def __init__(self, parent, id=wx.ID_ANY, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0, validator=wx.DefaultValidator,
                 name="listCtrl"):
        ulc_style = self._map_style(style)
        super().__init__(parent, id, pos, size, agwStyle=ulc_style, validator=validator, name=name)
        self._renderers = []
        
        # Configurar colores de selección por defecto (verde con texto blanco)
        self.SetHighlightColour(wx.Colour(76, 175, 80))  # Verde moderno
        self.SetHighlightTextColour(wx.Colour(255, 255, 255))  # Texto blanco
        
        # Aplicar tema dark automáticamente después de la inicialización completa
        wx.CallAfter(self._apply_default_dark_theme)

    def _apply_default_dark_theme(self):
        """Aplicar tema dark por defecto automáticamente"""
        # Colores del tema dark (igual que en el tester)
        dark_header_bg = wx.Colour(64, 64, 64)
        dark_header_fg = wx.Colour(240, 240, 240)
        dark_row_bg = wx.Colour(80, 80, 80)
        dark_row_fg = wx.Colour(230, 230, 230)
        
        # Configurar tema dark
        self.SetAllColumnHeaderColors(dark_header_bg, dark_header_fg)
        self.SetRowColors(dark_row_bg, dark_row_fg)
        
        # Aplicar parche de cabecera automáticamente
        self._apply_header_patch()
        
        # Refresh final
        self.Refresh()

    def _apply_header_patch(self):
        """Aplicar parche de cabecera automáticamente"""
        header = getattr(self, '_headerWin', None)
        if header:
            def on_paint(evt):
                dc = wx.PaintDC(header)
                size = header.GetClientSize()
                bg = self._renderers[0].bg if self._renderers else wx.Colour(64, 64, 64)
                dc.SetBrush(wx.Brush(bg))
                dc.SetPen(wx.Pen(bg))
                dc.DrawRectangle(0, 0, size.x, size.y)
                last_right = 0
                for col, renderer in enumerate(getattr(self, '_renderers', [])):
                    rect = self.GetHeaderRect(col)
                    renderer.DrawHeaderButton(dc, rect, 0)
                    last_right = max(last_right, rect.x + rect.width)
                if last_right < size.x:
                    dc.SetBrush(wx.Brush(bg))
                    dc.SetPen(wx.Pen(bg))
                    dc.DrawRectangle(last_right, 0, size.x - last_right, size.y)
            header.Bind(wx.EVT_PAINT, on_paint)

    def InsertColumn(self, col, heading, format=wx.LIST_FORMAT_LEFT, width=-1):
        res = super().InsertColumn(col, heading, format, width)
        renderer = CustomHeaderRenderer(self, col)
        self._mainWin.SetColumnCustomRenderer(col, renderer)
        self._renderers.insert(col, renderer)
        return res

    def SetColumnHeaderColors(self, col, bg_color=None, fg_color=None):
        if 0 <= col < len(self._renderers):
            self._renderers[col].set_colors(bg_color, fg_color)
            self.Refresh()

    def SetAllColumnHeaderColors(self, bg_color=None, fg_color=None):
        for renderer in self._renderers:
            renderer.set_colors(bg_color, fg_color)
        if bg_color is not None:
            self.SetBackgroundColour(bg_color)
        if fg_color is not None:
            self.SetForegroundColour(fg_color)
        self.Refresh()

    def SetColumnHeaderFont(self, col, font):
        if 0 <= col < len(self._renderers):
            self._renderers[col].set_font(font)
            self.Refresh()

    def SetColumnHeaderAlignment(self, col, alignment):
        if 0 <= col < len(self._renderers):
            self._renderers[col].set_align(alignment)
            self.Refresh()

    # Métodos para filas (contenido)
    def SetRowColors(self, bg_color=None, fg_color=None):
        for i in range(self.GetItemCount()):
            if bg_color is not None:
                self.SetItemBackgroundColour(i, bg_color)
            if fg_color is not None:
                self.SetItemTextColour(i, fg_color)
        self.Refresh()

    def _map_style(self, wx_style):
        ulc_style = ULC.ULC_REPORT | ULC.ULC_HRULES | ULC.ULC_VRULES
        style_map = {
            wx.LC_REPORT: ULC.ULC_REPORT,
            wx.LC_LIST: ULC.ULC_LIST,
            wx.LC_ICON: ULC.ULC_ICON,
            wx.LC_SMALL_ICON: ULC.ULC_SMALL_ICON,
            wx.LC_ALIGN_TOP: ULC.ULC_ALIGN_TOP,
            wx.LC_ALIGN_LEFT: ULC.ULC_ALIGN_LEFT,
            wx.LC_AUTOARRANGE: ULC.ULC_AUTOARRANGE,
            wx.LC_VIRTUAL: ULC.ULC_VIRTUAL,
            wx.LC_EDIT_LABELS: ULC.ULC_EDIT_LABELS,
            wx.LC_NO_HEADER: ULC.ULC_NO_HEADER,
            wx.LC_SINGLE_SEL: ULC.ULC_SINGLE_SEL,
            wx.LC_SORT_ASCENDING: ULC.ULC_SORT_ASCENDING,
            wx.LC_SORT_DESCENDING: ULC.ULC_SORT_DESCENDING,
        }
        for wx_style_flag, ulc_style_flag in style_map.items():
            if wx_style & wx_style_flag:
                ulc_style |= ulc_style_flag
        return ulc_style

    # Métodos de compatibilidad wx.ListCtrl
    def SetItem(self, index, col, label, imageId=-1):
        return self.SetStringItem(index, col, label)
    
    def InsertItem(self, *args, **kwargs):
        """Override para compatibilidad EXACTA con wx.ListCtrl.InsertItem()
        
        Soporta:
        - InsertItem(index, text) - insertar en posición específica
        - InsertItem(index, text, imageId) - insertar con imagen
        - InsertItem(ListItem) - modo original UltimateListCtrl
        """
        # Caso 1: InsertItem(UltimateListItem) - modo original
        if len(args) == 1 and isinstance(args[0], (ULC.UltimateListItem, wx.ListItem)):
            return ULC.UltimateListCtrl.InsertItem(self, args[0])
        
        # Caso 2: InsertItem(index, text) - más común en producción
        elif len(args) == 2:
            index, text = args
            return self.InsertStringItem(index, text)
        
        # Caso 3: InsertItem(index, text, imageId) - con imagen
        elif len(args) == 3:
            index, text, imageId = args
            if imageId >= 0:
                # Con imagen: crear UltimateListItem CORRECTAMENTE
                info = ULC.UltimateListItem()
                info.SetText(text)
                info.SetImage(imageId)  # Usar SetImage() en lugar de _image
                info.SetMask(ULC.ULC_MASK_TEXT | ULC.ULC_MASK_IMAGE)
                # Insertar usando índice correcto
                info.SetId(index)
                return ULC.UltimateListCtrl.InsertItem(self, info)
            else:
                # Sin imagen válida: usar InsertStringItem
                return self.InsertStringItem(index, text)
        
        # Caso legacy con kwargs
        elif 'label' in kwargs or 'imageId' in kwargs:
            index = args[0] if args else 0
            label = kwargs.get('label', '')
            imageId = kwargs.get('imageId', -1)
            if imageId >= 0:
                info = ULC.UltimateListItem()
                info.SetText(label)
                info.SetImage(imageId)  # Usar SetImage() correctamente
                info.SetMask(ULC.ULC_MASK_TEXT | ULC.ULC_MASK_IMAGE)
                info.SetId(index)
                return ULC.UltimateListCtrl.InsertItem(self, info)
            else:
                return self.InsertStringItem(index, label)
        
        else:
            raise TypeError(f"InsertItem() invalid arguments: args={args}, kwargs={kwargs}")
        
    def GetItemText(self, item, col=0, **kwargs):
        """Override para compatibilidad EXACTA con wx.ListCtrl.GetItemText()
        
        Soporta:
        - GetItemText(index, column) - posicional
        - GetItemText(index, col=N) - con nombre
        - GetItemText(index) - columna 0 por defecto
        """
        # Manejar caso col=N en kwargs (usado en freezer_panel)
        if 'col' in kwargs:
            col = kwargs['col']
        
        # Si es columna 0, usar método padre directo
        if col == 0:
            return super().GetItemText(item)
        else:
            # Para otras columnas, obtener el item y extraer texto
            try:
                listItem = self.GetItem(item, col)
                return listItem.GetText()
            except Exception:
                # Fallback si falla
                return ""
            
    def AssignImageList(self, imageList, which):
        return super().AssignImageList(imageList, which)
        
    def GetHeaderRect(self, col):
        x = 0
        for c in range(col):
            x += self.GetColumnWidth(c)
        w = self.GetColumnWidth(col)
        return wx.Rect(x, 0, w, 24)
    
    def GetFirstSelected(self):
        """Obtener el índice del primer item seleccionado"""
        for i in range(self.GetItemCount()):
            if self.IsSelected(i):
                return i
        return -1  # No hay selección
    
    def GetItemCount(self):
        """Obtener el número total de items - compatibilidad EXACTA con wx.ListCtrl"""
        return super().GetItemCount()
    
    def InsertStringItem(self, index, label):
        """Override - ahora usa el fix nativo en UltimateListCtrl"""
        return super().InsertStringItem(index, label)
    

    
    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        """Override para interceptar y adaptar eventos de clic derecho"""
        if event == wx.EVT_LIST_ITEM_RIGHT_CLICK:
            # Adaptar evento de clic derecho para compatibilidad
            return self._bind_right_click_event(handler)
        else:
            return super().Bind(event, handler, source, id, id2)
    
    def _bind_right_click_event(self, handler):
        """Adaptador para eventos de clic derecho"""
        def adapted_handler(event):
            # Normalizar el evento para compatibilidad con wx.ListCtrl
            normalized_event = self._normalize_event_data(event)
            return handler(normalized_event)
        
        # Bind al evento apropiado de UltimateListCtrl
        return super().Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, adapted_handler)
    
    def _normalize_event_data(self, event):
        """Normalizar datos del evento para compatibilidad"""
        # Asegurar que GetIndex() funcione correctamente
        if hasattr(event, 'GetIndex'):
            return event
        
        # Si no tiene GetIndex, crear un wrapper
        class EventWrapper:
            def __init__(self, original_event, listctrl):
                self.original_event = original_event
                self.listctrl = listctrl
                # Copiar todos los atributos del evento original
                for attr in dir(original_event):
                    if not attr.startswith('_'):
                        try:
                            setattr(self, attr, getattr(original_event, attr))
                        except:
                            pass
            
            def GetIndex(self):
                # Implementar GetIndex si no existe
                return getattr(self.original_event, 'm_itemIndex', -1)
            
            def GetEventObject(self):
                return self.listctrl
        
        return EventWrapper(event, self)

def patch_header_empty_bg(ulc):
    """Rellenar el fondo de la cabecera vacía (sin columnas)"""
    header = getattr(ulc, '_headerWin', None)
    if header:
        def on_paint(evt):
            dc = wx.PaintDC(header)
            size = header.GetClientSize()
            bg = ulc._renderers[0].bg if ulc._renderers else wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
            dc.SetBrush(wx.Brush(bg))
            dc.SetPen(wx.Pen(bg))
            dc.DrawRectangle(0, 0, size.x, size.y)
            last_right = 0
            for col, renderer in enumerate(getattr(ulc, '_renderers', [])):
                rect = ulc.GetHeaderRect(col)
                renderer.DrawHeaderButton(dc, rect, 0)
                last_right = max(last_right, rect.x + rect.width)
            if last_right < size.x:
                dc.SetBrush(wx.Brush(bg))
                dc.SetPen(wx.Pen(bg))
                dc.DrawRectangle(last_right, 0, size.x - last_right, size.y)
        header.Bind(wx.EVT_PAINT, on_paint) 