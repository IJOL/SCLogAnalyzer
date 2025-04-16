#!/usr/bin/env python
import wx
import wx.grid
import json
import threading
import time
from typing import Dict, Any, Callable, Tuple, List, Optional, Union
from .message_bus import message_bus, MessageLevel
from .config_utils import get_config_manager

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
        
    def _add_tab(self, notebook, tab_title, url, params=None):
        """
        Create a new tab with a grid and a refresh button.

        Args:
            notebook (wx.Notebook): The notebook to add the tab to.
            tab_title (str): The title of the new tab.
            url (str): The URL to fetch JSON data from.
            params (dict, optional): Parameters to pass to the request.
            
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

        # Add a refresh button
        refresh_button = wx.Button(new_tab, label="Refresh")
        tab_sizer.Add(refresh_button, 0, wx.ALL | wx.ALIGN_LEFT, 5)

        # Add a grid to display the JSON data
        grid = wx.grid.Grid(new_tab)
        grid.CreateGrid(0, 0)  # Start with an empty grid
        tab_sizer.Add(grid, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the tab
        new_tab.SetSizer(tab_sizer)

        # Add the new tab to the notebook
        notebook.AddPage(new_tab, tab_title)

        # Store the URL and params directly on objects
        refresh_button.url = url
        refresh_button.params = params
        refresh_button.grid = grid

        # Bind the refresh button to fetch and update the grid
        refresh_button.Bind(wx.EVT_BUTTON, self.parent.on_refresh_tab)

        # Store the tab reference in the dictionary
        self.tab_references[tab_title] = (grid, refresh_button)

        return grid, refresh_button  # Return the grid for further updates

    def add_tab(self, url, tab_title, params=None, top_panel=None):
        """
        Add a new tab to the notebook with a grid and optional top panel.

        Args:
            url (str): The URL to fetch JSON data from.
            tab_title (str): The title of the new tab.
            params (dict, optional): A dictionary of parameters to pass to the request.
            top_panel (wx.Panel, optional): A panel to place above the grid (e.g., a form).
            
        Returns:
            Tuple: (grid, refresh_button)
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            # Tab exists, just return the existing grid
            grid, refresh_button = self.tab_references[tab_title]            
            return grid, refresh_button
        
        # If tab doesn't exist, use _add_tab to create it
        grid, refresh_button = self._add_tab(self.parent.notebook, tab_title, url, params)

        if grid and top_panel:
            # Add the top panel to the tab's sizer
            parent_panel = grid.GetParent()
            parent_sizer = parent_panel.GetSizer()
            parent_sizer.Insert(0, top_panel, 0, wx.EXPAND | wx.ALL, 5)
            parent_panel.Layout()

        # Trigger initial refresh if the grid was created
        return grid, refresh_button
        
    def add_form_tab(self, url, tab_title, form_fields={}, params=None):
        """
        Add a new tab with a form at the top and a grid at the bottom.

        Args:
            url (str): The URL to fetch data for the grid.
            tab_title (str): The title of the new tab.
            form_fields (dict): A dictionary where keys are field names and values are input types.
            params (dict, optional): Parameters to pass to the request.
            
        Returns:
            Tuple: (grid, refresh_button)
        """
        # Check if tab already exists
        if tab_title in self.tab_references:
            # Tab exists, just return the existing grid
            grid, refresh_button = self.tab_references[tab_title]            
            return grid, refresh_button
                
        # Create the base tab if it doesn't exist
        grid, refresh_button = self._add_tab(self.parent.notebook, tab_title, url, params)

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
            submit_button = wx.Button(form_panel, label="Submit")
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

            # Bind the submit button
            submit_button.Bind(wx.EVT_BUTTON, lambda event: self.parent.on_form_submit(
                event, url, refresh_button, form_controls, params.get("sheet", "")))
                
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
        headers = list(json_data[0].keys())

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
        bold_font = wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
        
        # Create the labels
        self.username_label = wx.StaticText(panel, label="Username: Loading...")
        self.username_label.SetFont(bold_font)
        
        self.shard_label = wx.StaticText(panel, label="Shard: Loading...")
        self.shard_label.SetFont(bold_font)
        
        self.version_label = wx.StaticText(panel, label="Version: Loading...")
        self.version_label.SetFont(bold_font)
        
        self.mode_label = wx.StaticText(panel, label="Mode: Loading...")
        self.mode_label.SetFont(bold_font)
        
        # Create and populate the label sizer
        label_sizer = wx.BoxSizer(wx.HORIZONTAL)
        label_sizer.Add(self.username_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.shard_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.version_label, 1, wx.ALL | wx.EXPAND, 5)
        label_sizer.Add(self.mode_label, 1, wx.ALL | wx.EXPAND, 5)
        
        # Add label sizer to the provided sizer
        sizer.Add(label_sizer, 0, wx.EXPAND)
        
        return label_sizer
    
    def update_labels(self, username="Unknown", shard="Unknown", version="Unknown", mode="None"):
        """
        Update the dynamic labels with new values.
        
        Args:
            username (str): The username to display
            shard (str): The shard to display
            version (str): The version to display
            mode (str): The game mode to display
        """
        if self.username_label:
            self.username_label.SetLabel(f"Username: {username}")
        
        if self.shard_label:
            self.shard_label.SetLabel(f"Shard: {shard}")
            
        if self.version_label:
            self.version_label.SetLabel(f"Version: {version}")
            
        if self.mode_label:
            self.mode_label.SetLabel(f"Mode: {mode or 'None'}")


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
        submit_button = wx.Button(form_panel, label="Submit")
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