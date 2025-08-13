#!/usr/bin/env python
import wx
import wx.grid
import json
import threading
import time
import os
from typing import Dict, Any, Callable, Tuple, List, Optional, Union
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_application_path, get_config_manager, get_template_base_dir, get_template_path
import wx.lib.buttons as buttons
class TabCreator:
    """Manages creation and configuration of tabs in the notebook."""
    
    def __init__(self, parent_frame):
        """
        Initialize the TabCreator.
        
        Args:
            parent_frame: The parent frame that contains the notebook
        """
        self.parent = parent_frame
        self.tab_references = {}
        
    def _add_tab(self, notebook, tab_title, params=None, tab_info=None):
        """
        Create a new tab with a grid and a refresh button.

        Args:
            notebook (wx.Notebook): The notebook to add the tab to.
            tab_title (str): The title of the new tab.
            params (dict, optional): Parameters to pass to the request.
            tab_info (dict, optional): Complete tab configuration information.
            
        Returns:
            Tuple: (grid, refresh_button) or None if the tab already exists
        """
        # Check if a tab with the same title already exists
        if tab_title in self.tab_references:
            return self.tab_references[tab_title]  # Return existing tab components

        # Create a new panel for the tab
        new_tab = wx.Panel(notebook)

        # Create a vertical sizer for the tab
        tab_sizer = wx.BoxSizer(wx.VERTICAL)

        # Obtener DPI y calcular escala para fuentes
        dpi = wx.ScreenDC().GetPPI()
        scale = dpi[0] / 96  # 96 = DPI estándar
        base_font_size = 10
        font = wx.Font(int(base_font_size * scale), wx.FONTFAMILY_SWISS, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)

        # Create a flat button with only a refresh icon
        refresh_button = wx.BitmapButton(
            new_tab,
            bitmap=wx.ArtProvider.GetBitmap(wx.ART_REDO, wx.ART_BUTTON, (int(16*scale), int(16*scale))),
            style=wx.BORDER_NONE
        )
        refresh_button.SetToolTip("Refresh")
        refresh_button.SetFont(font)
        tab_sizer.Add(refresh_button, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        # Add a grid to display the JSON data
        grid = wx.grid.Grid(new_tab)
        grid.CreateGrid(0, 0)
        grid.SetFont(font)

        # Store tab_info directly on the grid
        if tab_info:
            grid.tab_info = tab_info
            
        tab_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the tab
        new_tab.SetSizer(tab_sizer)

        # Add the new tab to the notebook
        notebook.AddPage(new_tab, tab_title)

        # Store only the params directly on the button object
        refresh_button.params = params
        refresh_button.grid = grid

        # Bind the refresh button directly to the data manager's on_refresh_tab method
        refresh_button.Bind(wx.EVT_BUTTON, self.parent.data_manager.on_refresh_tab)

        # Store the tab reference in the dictionary
        self.tab_references[tab_title] = (grid, refresh_button)

        # Aplicar fuente escalada a todos los hijos del panel
        for child in new_tab.GetChildren():
            if hasattr(child, 'SetFont'):
                child.SetFont(font)

        return grid, refresh_button  # Return the grid for further updates

    def add_tab(self, tab_title, params=None, top_panel=None, tab_info=None):
        """
        Add a new tab to the notebook with a grid and optional top panel.

        Args:
            tab_title (str): The title of the new tab.
            params (dict, optional): A dictionary of parameters to pass to the request.
            top_panel (wx.Panel, optional): A panel to place above the grid (e.g., a form).
            tab_info (dict, optional): Complete tab configuration information.
            
        Returns:
            Tuple: (grid, refresh_button)
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            grid, refresh_button = self.tab_references[tab_title]
            return grid, refresh_button
        # Usa _add_tab para crear el tab base
        grid, refresh_button = self._add_tab(self.parent.notebook, tab_title, params, tab_info)

        # Si se pasa un top_panel, lo añade arriba del grid
        if grid and top_panel:
            parent_panel = grid.GetParent()
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, top_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

        return grid, refresh_button
        
    def add_form_tab(self, tab_title, form_fields={}, params=None, tab_info=None):
        """
        Add a new tab with a form at the top and a grid at the bottom.

        Args:
            tab_title (str): The title of the new tab.
            form_fields (dict): A dictionary where keys are field names and values are input types.
            params (dict, optional): Parameters to pass to the request.
            tab_info (dict, optional): Complete tab configuration information.
            
        Returns:
            Tuple: (grid, refresh_button)
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            # Tab exists, just return the existing grid
            grid, refresh_button = self.tab_references[tab_title]            
            return grid, refresh_button
                
        # Create the base tab if it doesn't exist
        grid, refresh_button = self._add_tab(self.parent.notebook, tab_title, params, tab_info)

        if grid:
            # Use the grid's parent as the correct parent for the form panel
            parent_panel = grid.GetParent()
            form_panel = wx.Panel(parent_panel)  # Correct parent assignment

            form_sizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
            form_sizer.AddGrowableCol(1, 1)

            form_controls = {}

            for field_name, field_type in form_fields.items():
                label = wx.StaticText(form_panel, label=field_name)
                if field_type == 'text':
                    control = wx.TextCtrl(form_panel)
                elif field_type == 'dropdown':
                    control = wx.Choice(form_panel, choices=form_fields.get('choices', []))
                elif field_type == 'check':
                    control = wx.CheckBox(form_panel)
                elif field_type == 'number':
                    control = wx.TextCtrl(form_panel)
                    control.SetValidator(NumericValidator(allow_float=True))
                    control.field_type = 'number'  # Store field type for validation
                else:
                    raise ValueError(f"Unsupported field type: {field_type}")
                form_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
                form_sizer.Add(control, 1, wx.EXPAND)
                form_controls[field_name] = control

            # Add the submit button aligned to the right
            submit_button = DarkThemeButton(form_panel, label="📤 Submit")
            button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            button_sizer.AddStretchSpacer()
            button_sizer.Add(submit_button, 0, wx.ALL, 5)

            # Wrap the form and button sizer in a vertical sizer
            vertical_sizer = wx.BoxSizer(wx.VERTICAL)
            vertical_sizer.Add(form_sizer, 0, wx.EXPAND | wx.ALL, 5)
            vertical_sizer.Add(button_sizer, 0, wx.EXPAND)

            # Set the maximum width of the form to half of the parent
            max_width = parent_panel.GetSize().GetWidth() // 2
            form_panel.SetMaxSize(wx.Size(max_width, -1))

            form_panel.SetSizer(vertical_sizer)

            # Add the form panel to the tab's sizer
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, form_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

            # Bind the submit button - pass None instead of URL
            submit_button.Bind(wx.EVT_BUTTON, lambda event: self.parent.data_manager.on_form_submit(
                event, None, refresh_button, form_controls, params.get("sheet", "")))
                
            self.tab_references[tab_title] = (grid, refresh_button)
        return grid, refresh_button


class GridManager:
    """Manages grid creation, population, and updates."""
    
    @staticmethod
    def set_grid_loading(grid, is_loading):
        """
        Set the visual state of a grid to indicate loading.
        
        Args:
            grid (wx.grid.Grid): The grid to update
            is_loading (bool): Whether the grid is loading data
        """
        if is_loading:
            # Clear existing data and show "Loading..." in the first cell
            if grid.GetNumberRows() > 0:
                grid.DeleteRows(0, grid.GetNumberRows())
            grid.AppendRows(1)
            if grid.GetNumberCols() == 0:
                grid.AppendCols(1)
            grid.SetCellValue(0, 0, "Loading data...")
            grid.SetCellAlignment(0, 0, wx.ALIGN_CENTER, wx.ALIGN_CENTER)
            grid.Enable(False)
        else:
            grid.Enable(True)
            # Make all cells read-only without disabling the grid
            grid.EnableEditing(False)
    
    @staticmethod
    def update_sheets_grid(json_data, grid):
        """
        Update the given grid with the provided JSON data.

        Args:
            json_data (list): The JSON data to display.
            grid (wx.grid.Grid): The grid to update.
        """
        if not json_data:
            grid.ClearGrid()
            return

        # Get the keys from the first dictionary as column headers
        headers = [h for h in list(json_data[0].keys()) if h not in ["id", "created_at"]]
        
        # Check if this is a dynamic tab with username filtering using the stored tab_info
        if (hasattr(grid, "tab_info") and 
            "params" in grid.tab_info and 
            "username" in grid.tab_info["params"] and
            grid.tab_info["title"] != "Stats" and
            "username" in headers):
            # Hide username column in dynamic tabs with username filtering
            headers = [h for h in headers if h != "username"]

        # Resize the grid to fit the data
        grid.ClearGrid()
        if grid.GetNumberRows() > 0:
            grid.DeleteRows(0, grid.GetNumberRows())
        if grid.GetNumberCols() > 0:
            grid.DeleteCols(0, grid.GetNumberCols())
        grid.AppendCols(len(headers))
        grid.AppendRows(len(json_data))

        # Set column headers
        for col, header in enumerate(headers):
            grid.SetColLabelValue(col, header)

        # Populate the grid with data
        for row, entry in enumerate(json_data):
            for col, header in enumerate(headers):
                grid.SetCellValue(row, col, str(entry[header]))

        # Auto-size columns only if there are valid rows and columns
        if grid.GetNumberCols() > 0 and grid.GetNumberRows() > 0:
            grid.AutoSizeColumns()
            
        # Disable column and row resizing
        grid.EnableDragColSize(False)
        grid.EnableDragRowSize(False)
        grid.EnableDragGridSize(False)


class DynamicLabels:
    """Handles updating of dynamic labels in the UI."""
    
    def __init__(self, parent_frame):
        """
        Initialize the DynamicLabels manager.
        
        Args:
            parent_frame: The parent frame containing the labels
        """
        self.parent = parent_frame
        self.username_label = None
        self.shard_label = None
        self.version_label = None
        self.mode_label = None
        self.connection_icon = None  # wx.StaticBitmap for connection status
        self._connected = True  # Internal state
        
    def create_labels(self, panel, sizer):
        """
        Create the dynamic labels for displaying game information.
        
        Args:
            panel: The panel to create labels on
            sizer: The sizer to add labels to
            
        Returns:
            wx.BoxSizer: The sizer containing the labels
        """
        # Create bold font for labels
        bold_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        
        # Create the labels
        self.username_label = wx.StaticText(panel, label="Username: Loading...")
        self.username_label.SetFont(bold_font)
        
        self.shard_label = wx.StaticText(panel, label="Shard: Loading...")
        self.shard_label.SetFont(bold_font)
        
        self.version_label = wx.StaticText(panel, label="Version: Loading...")
        self.version_label.SetFont(bold_font)
        
        self.mode_label = wx.StaticText(panel, label="Mode: Loading...")
        self.mode_label.SetFont(bold_font)

        self.private_label = wx.StaticText(panel, label="Private")
        self.private_label.SetFont(bold_font)
        self.private_label.Hide()  # Hide by default
        # Set the label colors  
        self.private_label.SetForegroundColour(wx.Colour(0, 255, 0))  # Green

        
        # Create and populate the label sizer
        label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label_sizer.Add(self.username_label, 1, wx.ALL | wx.LEFT, 5)
        label_sizer.AddStretchSpacer()
        label_sizer.Add(self.shard_label, 1, wx.ALL | wx.LEFT, 5)
        label_sizer.AddStretchSpacer()
        label_sizer.Add(self.version_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.AddStretchSpacer()
        label_sizer.Add(self.mode_label, 1, wx.ALL | wx.RIGHT, 5)
        label_sizer.AddStretchSpacer()
        label_sizer.Add(self.private_label, 1, wx.ALL | wx.RIGHT, 5)
        label_sizer.AddStretchSpacer()
        # --- Custom icon loading (PNG) ---
        # Iconos descargados de https://icons8.com/icon/124377/green-circle y https://icons8.com/icon/124376/red-circle
        # Licencia: uso libre con atribución (icons8)
        green_icon_path = os.path.join(get_template_base_dir(), 'assets', 'icon_connection_green.png')
        red_icon_path = os.path.join(get_template_base_dir(), 'assets', 'icon_connection_red.png')
        self._icon_paths = {
            True: green_icon_path,
            False: red_icon_path
        }
        # Cargar el icono ya escalado (por ejemplo, 8x8 px) sin escalar en runtime
        bmp = wx.Bitmap(green_icon_path, wx.BITMAP_TYPE_PNG)
        self.connection_icon = wx.StaticBitmap(panel, bitmap=bmp)
        self.connection_icon.SetToolTip("Estado de conexión: conectado")
        label_sizer.Add(self.connection_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        sizer.Add(label_sizer, 0, wx.EXPAND)
        message_bus.on("broadcast_ping_missing", lambda *a, **k: wx.CallAfter(self._on_ping_missing))
        message_bus.on("realtime_reconnected", lambda *a, **k: wx.CallAfter(self._on_reconnected))
        return label_sizer

    def set_connection_status(self, connected: bool):
        """
        Cambia el icono de estado de conexión (verde: conectado, rojo: desconectado).
        """
        if self.connection_icon:
            icon_path = self._icon_paths[connected]
            bmp = wx.Bitmap(icon_path, wx.BITMAP_TYPE_PNG)
            if connected:
                self.connection_icon.SetToolTip("Estado de conexión: conectado")
            else:
                self.connection_icon.SetToolTip("Estado de conexión: desconectado (ping missing)")
            self.connection_icon.SetBitmap(bmp)
            self._connected = connected

    def _on_ping_missing(self, *args, **kwargs):
        """Callback para evento de ping perdido: pone el icono en rojo."""
        self.set_connection_status(False)

    def _on_reconnected(self, *args, **kwargs):
        """Callback para evento de reconexión: pone el icono en verde."""
        self.set_connection_status(True)

    def update_labels(self, username="Unknown", shard="Unknown", version="Unknown", mode="None", private=False):
        """
        Update the dynamic labels with new values.
        
        Args:
            username (str): The username to display
            shard (str): The shard to display
            version (str): The version to display
            mode (str): The game mode to display
        """
        if self.username_label:
            self.username_label.SetLabel(f"{username}")
        
        if self.shard_label:
            self.shard_label.SetLabel(f"{shard}")
            
        if self.version_label:
            self.version_label.SetLabel(f"{version}")
            # Colorear versión en rojo si NO es pub (modo test: PTU/EPTU/otros)
            is_test_mode = (version and 
                           version.split('-')[0].lower() != 'pub')
            if is_test_mode:
                self.version_label.SetForegroundColour(wx.Colour(255, 0, 0))  # Red
            else:
                self.version_label.SetForegroundColour(wx.Colour(0, 0, 0))    # Black (default)
            
        if self.mode_label:
            self.mode_label.SetLabel(f"Mode: {mode or 'None'}")
        if self.private_label:
            if private:
                self.private_label.Show()
            else:
                self.private_label.Hide()


class FormPanel:
    """Creates and manages form inputs and submission."""
    
    @staticmethod
    def create_form_panel(parent, fields, on_submit):
        """
        Create a form panel with the specified fields.
        
        Args:
            parent: The parent panel
            fields (dict): Dictionary of field names and types
            on_submit: Callback function when the form is submitted
            
        Returns:
            Tuple: (panel, form_controls)
        """
        form_panel = wx.Panel(parent)
        form_sizer = wx.FlexGridSizer(cols=2, hgap=5, vgap=5)
        form_sizer.AddGrowableCol(1, 1)
        
        form_controls = {}
        
        for field_name, field_type in fields.items():
            label = wx.StaticText(form_panel, label=field_name)
            
            if field_type == 'text':
                control = wx.TextCtrl(form_panel)
            elif field_type == 'dropdown':
                control = wx.Choice(form_panel, choices=fields.get('choices', []))
            elif field_type == 'check':
                control = wx.CheckBox(form_panel)
            elif field_type == 'number':
                control = wx.TextCtrl(form_panel)
                control.field_type = 'number'  # For validation
            else:
                control = wx.TextCtrl(form_panel)  # Default to text input
                
            form_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL)
            form_sizer.Add(control, 1, wx.EXPAND)
            form_controls[field_name] = control
            
        # Add submit button
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        submit_button = DarkThemeButton(form_panel, label="📤 Submit")
        button_sizer.AddStretchSpacer()
        button_sizer.Add(submit_button, 0, wx.ALL, 5)
        
        # Create main sizer and add components
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(form_sizer, 1, wx.EXPAND | wx.ALL, 5)
        main_sizer.Add(button_sizer, 0, wx.EXPAND)
        
        form_panel.SetSizer(main_sizer)
        
        # Bind submit button
        submit_button.Bind(wx.EVT_BUTTON, on_submit)
        
        return form_panel, form_controls


class NumericValidator(wx.Validator):
    """Custom numeric validator for text controls."""
    def __init__(self, allow_float=True):
        wx.Validator.__init__(self)
        self.allow_float = allow_float
        self.Bind(wx.EVT_CHAR, self.on_char)

    def Clone(self):
        return NumericValidator(self.allow_float)

    def Validate(self, win):
        text_ctrl = self.GetWindow()
        text = text_ctrl.GetValue()
        if not text:
            return True  # Empty is valid
        try:
            if self.allow_float:
                float(text)
            else:
                int(text)
            return True
        except ValueError:
            return False

    def on_char(self, event):
        key = event.GetKeyCode()
        text_ctrl = self.GetWindow()
        current_text = text_ctrl.GetValue()

        # Allow control keys (backspace, delete, arrow keys, etc.)
        if key < wx.WXK_SPACE or key == wx.WXK_DELETE or key > 255:
            event.Skip()
            return

        # Allow digits
        if chr(key).isdigit():
            event.Skip()
            return

        # Allow decimal point if float is allowed and not already in the text
        if self.allow_float and chr(key) == '.' and '.' not in current_text:
            event.Skip()
            return

        # Allow minus sign as first character if not already present
        if chr(key) == '-' and current_text == '':
            event.Skip()
            return

        # Block all other characters
        return


def safe_call_after(func, *args, **kwargs):
    """Safely call wx.CallAfter, ensuring wx.App is initialized."""
    if wx.GetApp() is not None:
        wx.CallAfter(func, *args, **kwargs)
    else:
        print(f"wx.App is not initialized. Cannot call {func.__name__}.")

class DarkThemeButton(buttons.GenButton):
    """Botón con tema oscuro por defecto usando GenButton"""
    
    def __init__(self, parent, label="", **kwargs):
        # Configurar estilo con bordes menores
        style = kwargs.get('style', 0) | wx.BORDER_NONE
        kwargs['style'] = style
        
        super().__init__(parent, label=label, **kwargs)
        
        # Configurar colores oscuros por defecto
        self.SetBackgroundColour(wx.Colour(64, 64, 64))  # Fondo gris oscuro
        self.SetForegroundColour(wx.Colour(240, 240, 240))  # Texto blanco
        
        # Configurar bordes menores
        self.SetBezelWidth(1)  # Borde más fino


class MiniDarkThemeButton(buttons.GenButton):
    """Botón mini con tema oscuro que solo muestra el emoji"""
    
    def __init__(self, parent, label="", **kwargs):
        # Configurar estilo con bordes menores
        style = kwargs.get('style', 0) | wx.BORDER_NONE
        kwargs['style'] = style
        
        # Tamaño mini por defecto
        if 'size' not in kwargs:
            kwargs['size'] = (30, 25)  # Tamaño más pequeño
        
        super().__init__(parent, label=label, **kwargs)
        
        # Configurar colores oscuros por defecto
        self.SetBackgroundColour(wx.Colour(64, 64, 64))  # Fondo gris oscuro
        self.SetForegroundColour(wx.Colour(240, 240, 240))  # Texto blanco
        
        # Configurar bordes menores
        self.SetBezelWidth(1)  # Borde más fino
        
        # Configurar fuente más pequeña para el emoji
        font = self.GetFont()
        font.SetPointSize(10)  # Fuente más pequeña
        self.SetFont(font)