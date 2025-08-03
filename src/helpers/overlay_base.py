#!/usr/bin/env python3
"""
Dynamic Overlay System - Base Implementation

Universal overlay system that can work with any widget in the SC Log Analyzer.
Uses hybrid efficient polling for maximum performance in gaming environments.

Key Features:
- Hybrid polling: lightweight key detection (100ms) + mouse polling only when needed (25ms)
- Ctrl+Alt+Right-click activation for gaming compatibility
- Windows API transparency and click-through support
- Manual hit testing for precise mouse detection
- ConfigManager integration for persistent settings
- MessageBus integration for automatic data synchronization
- Universal widget support through factory pattern
"""

import wx
import win32gui
import win32con
import win32api
import time
import threading
from typing import Optional, Callable, Any, Dict, Tuple

from .config_utils import ConfigManager
from .message_bus import message_bus, MessageLevel


class DynamicOverlay(wx.Frame):
    """
    Universal dynamic overlay that can display any widget with click-through gaming support.
    
    Features:
    - Hybrid efficient polling system
    - Ctrl+Alt+Right-click activation
    - Automatic data synchronization
    - Persistent settings through ConfigManager
    - Thread-safe operation
    """
    
    def __init__(self, widget_class, widget_args=None, widget_kwargs=None, 
                 overlay_id=None, title="Dynamic Overlay", size=(600, 400), pos=(200, 200)):
        """
        Initialize dynamic overlay with any widget.
        
        Args:
            widget_class: The widget class to display in overlay
            widget_args: Arguments to pass to widget constructor
            widget_kwargs: Keyword arguments to pass to widget constructor
            overlay_id: Unique identifier for this overlay (for settings persistence)
            title: Window title
            size: Initial window size
            pos: Initial window position
        """
        super().__init__(
            None,
            title=title,
            style=wx.STAY_ON_TOP | wx.FRAME_NO_TASKBAR | wx.BORDER_NONE,
            size=size,
            pos=pos
        )
        
        # Core properties
        self.widget_class = widget_class
        self.widget_args = widget_args or []
        self.widget_kwargs = widget_kwargs or {}
        self.overlay_id = overlay_id or f"overlay_{widget_class.__name__}_{int(time.time())}"
        
        # Window properties
        self.hwnd = None
        self.opacity_level = 200
        self.click_through_enabled = False
        
        # Hybrid polling management
        self.key_polling_timer = None      # Lightweight key polling (100ms)
        self.mouse_polling_timer = None    # Heavy mouse polling (25ms, only when needed)
        self.polling_lock = threading.Lock()
        
        # Key state tracking
        self.ctrl_pressed = False
        self.alt_pressed = False
        self.key_combination_active = False
        self.last_key_combination_state = False
        
        # Performance tracking
        self.key_polls = 0
        self.mouse_polls = 0
        self.menu_activations = 0
        self.start_time = time.time()
        
        # Widget instance
        self.widget_instance = None
        
        # External systems
        self.config_manager = ConfigManager.get_instance()
        
        # Initialize overlay
        self._load_overlay_settings()
        self._create_overlay_ui()
        wx.CallAfter(self._setup_transparency)
    
    def _create_overlay_ui(self):
        """Create the overlay UI with the embedded widget."""
        # Create main panel
        self.main_panel = wx.Panel(self)
        self.main_panel.SetBackgroundColour(wx.Colour(25, 30, 35))
        
        # Create main sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Create title bar (minimal, for dragging)
        self.title_panel = wx.Panel(self.main_panel)
        self.title_panel.SetBackgroundColour(wx.Colour(35, 40, 45))
        self.title_panel.SetMinSize((-1, 25))
        
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Title text
        self.title_text = wx.StaticText(self.title_panel, label=self.GetTitle())
        self.title_text.SetForegroundColour(wx.Colour(180, 190, 200))
        title_font = wx.Font(8, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.title_text.SetFont(title_font)
        
        # Status indicator
        self.status_indicator = wx.StaticText(self.title_panel, label="●")
        self.status_indicator.SetForegroundColour(wx.Colour(100, 150, 100))
        self.status_indicator.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        title_sizer.Add(self.title_text, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        title_sizer.Add(self.status_indicator, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.title_panel.SetSizer(title_sizer)
        
        # Create widget container
        widget_panel = wx.Panel(self.main_panel)
        widget_panel.SetBackgroundColour(wx.Colour(25, 30, 35))
        widget_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Instantiate the embedded widget
        try:
            # Create widget with widget_panel as parent
            self.widget_instance = self.widget_class(widget_panel, *self.widget_args, **self.widget_kwargs)
            widget_sizer.Add(self.widget_instance, 1, wx.EXPAND | wx.ALL, 2)
            self._log_message(f"Successfully created widget: {self.widget_class.__name__}", MessageLevel.DEBUG)
        except Exception as e:
            # Fallback: show error message with detailed error info
            error_msg = f"Error loading {self.widget_class.__name__}: {str(e)}"
            error_text = wx.StaticText(widget_panel, label=error_msg)
            error_text.SetForegroundColour(wx.Colour(255, 100, 100))
            error_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            widget_sizer.Add(error_text, 1, wx.EXPAND | wx.ALL, 10)
            self._log_message(f"Failed to create widget {self.widget_class.__name__}: {str(e)}", MessageLevel.ERROR)
            
            # Debug info
            debug_info = wx.StaticText(widget_panel, label=f"Args: {self.widget_args}\nKwargs: {self.widget_kwargs}")
            debug_info.SetForegroundColour(wx.Colour(180, 180, 180))
            widget_sizer.Add(debug_info, 0, wx.EXPAND | wx.ALL, 5)
        
        widget_panel.SetSizer(widget_sizer)
        
        # Add to main sizer
        main_sizer.Add(self.title_panel, 0, wx.EXPAND)
        main_sizer.Add(widget_panel, 1, wx.EXPAND)
        
        # Set main sizer
        self.main_panel.SetSizer(main_sizer)
        
        # Force layout update
        self.main_panel.Layout()
        self.Layout()
        
        # Event bindings
        self._bind_overlay_events()
    
    def _bind_overlay_events(self):
        """Bind overlay-specific events."""
        # Window events
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Bind(wx.EVT_CHAR_HOOK, self._on_key_press)
        self.Bind(wx.EVT_RIGHT_UP, self._on_normal_right_click)
        
        # Dragging events (title bar only)
        self.title_panel.Bind(wx.EVT_LEFT_DOWN, self._on_drag_start)
        self.title_text.Bind(wx.EVT_LEFT_DOWN, self._on_drag_start)
        
        # Context menu events (title bar only)
        self.title_panel.Bind(wx.EVT_RIGHT_UP, self._on_title_right_click)
        self.title_text.Bind(wx.EVT_RIGHT_UP, self._on_title_right_click)
        self.status_indicator.Bind(wx.EVT_RIGHT_UP, self._on_title_right_click)
    
    def _setup_transparency(self):
        """Setup initial transparency and window properties."""
        try:
            self.hwnd = self.GetHandle()
            self._apply_opacity(self.opacity_level)
            self._update_status_indicator("ready")
            self._log_message("Overlay transparency setup complete", MessageLevel.INFO)
        except Exception as e:
            self._log_message(f"Transparency setup error: {str(e)}", MessageLevel.ERROR)
    
    
    def _load_overlay_settings(self):
        """Load overlay settings from ConfigManager."""
        try:
            overlay_config = self.config_manager.get(f'overlays.{self.overlay_id}', {})
            
            # Load position
            if 'position' in overlay_config:
                pos = overlay_config['position']
                self.SetPosition((pos['x'], pos['y']))
            
            # Load size
            if 'size' in overlay_config:
                size = overlay_config['size']
                self.SetSize((size['width'], size['height']))
            
            # Load opacity
            self.opacity_level = overlay_config.get('opacity', 200)
            
            # Load click-through state
            self.click_through_enabled = overlay_config.get('click_through', False)
            
            self._log_message(f"Loaded settings for overlay: {self.overlay_id}", MessageLevel.INFO)
        except Exception as e:
            self._log_message(f"Failed to load overlay settings: {str(e)}", MessageLevel.WARNING)
    
    def _save_overlay_settings(self):
        """Save current overlay settings to ConfigManager."""
        try:
            overlay_config = {
                'position': {
                    'x': self.GetPosition().x,
                    'y': self.GetPosition().y
                },
                'size': {
                    'width': self.GetSize().width,
                    'height': self.GetSize().height
                },
                'opacity': self.opacity_level,
                'click_through': self.click_through_enabled
            }
            
            self.config_manager.set(f'overlays.{self.overlay_id}', overlay_config)
            self._log_message(f"Saved settings for overlay: {self.overlay_id}", MessageLevel.INFO)
        except Exception as e:
            self._log_message(f"Failed to save overlay settings: {str(e)}", MessageLevel.WARNING)
    
    # Hybrid Polling System Implementation
    
    def _start_key_polling(self):
        """Start lightweight key polling (always running when click-through enabled)."""
        with self.polling_lock:
            if not self.key_polling_timer and self.click_through_enabled:
                self.key_polling_timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self._check_key_combination, self.key_polling_timer)
                self.key_polling_timer.Start(100)  # Lightweight 100ms polling for keys only
                self._update_status_indicator("key_polling")
                self._log_message("Key polling started (100ms)", MessageLevel.DEBUG)
    
    def _stop_key_polling(self):
        """Stop key polling."""
        with self.polling_lock:
            if self.key_polling_timer:
                self.key_polling_timer.Stop()
                self.key_polling_timer = None
                self._log_message("Key polling stopped", MessageLevel.DEBUG)
    
    def _start_mouse_polling(self):
        """Start intensive mouse polling (only when Ctrl+Alt held)."""
        with self.polling_lock:
            if not self.mouse_polling_timer and self.click_through_enabled:
                self.mouse_polling_timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self._check_mouse_and_right_click, self.mouse_polling_timer)
                self.mouse_polling_timer.Start(25)  # Fast mouse polling when keys held
                self._update_status_indicator("active_polling")
                self._log_message("Mouse polling started (25ms)", MessageLevel.DEBUG)
    
    def _stop_mouse_polling(self):
        """Stop mouse polling."""
        with self.polling_lock:
            if self.mouse_polling_timer:
                self.mouse_polling_timer.Stop()
                self.mouse_polling_timer = None
                self._update_status_indicator("key_polling")
                self._log_message("Mouse polling stopped", MessageLevel.DEBUG)
    
    def _check_key_combination(self, event):
        """Lightweight key combination check (Ctrl+Alt only)."""
        if not self.click_through_enabled:
            return
        
        self.key_polls += 1
        
        try:
            # Check key states (very lightweight operation)
            ctrl_state = win32api.GetAsyncKeyState(0x11) & 0x8000  # VK_CONTROL
            alt_state = win32api.GetAsyncKeyState(0x12) & 0x8000   # VK_MENU (Alt)
            
            # Update key states
            self.ctrl_pressed = bool(ctrl_state)
            self.alt_pressed = bool(alt_state)
            
            # Check if combination is active
            new_combination_state = self.ctrl_pressed and self.alt_pressed
            
            # State change detection
            if new_combination_state != self.last_key_combination_state:
                self.last_key_combination_state = new_combination_state
                self.key_combination_active = new_combination_state
                
                if new_combination_state:
                    # Keys pressed: start mouse polling
                    self._start_mouse_polling()
                    self._log_message("Ctrl+Alt detected - Mouse polling activated", MessageLevel.DEBUG)
                else:
                    # Keys released: stop mouse polling
                    self._stop_mouse_polling()
                    self._log_message("Keys released - Mouse polling deactivated", MessageLevel.DEBUG)
                    
        except Exception as e:
            self._log_message(f"Key polling error: {str(e)}", MessageLevel.ERROR)
    
    def _check_mouse_and_right_click(self, event):
        """Intensive mouse+click check (only called when Ctrl+Alt held)."""
        if not self.key_combination_active:
            self._stop_mouse_polling()
            return
        
        self.mouse_polls += 1
        
        try:
            # Get mouse position
            mouse_pos = win32gui.GetCursorPos()
            
            # Check if mouse is over our overlay
            if self._is_mouse_over_overlay(mouse_pos):
                # Check for right-click
                right_pressed = win32api.GetAsyncKeyState(0x02) & 0x8000  # VK_RBUTTON
                
                if right_pressed:
                    self.menu_activations += 1
                    wx.CallAfter(self._trigger_overlay_menu, mouse_pos)
                    # Stop mouse polling temporarily
                    self._stop_mouse_polling()
                    wx.CallLater(1000, self._maybe_restart_mouse_polling)
                    
        except Exception as e:
            self._log_message(f"Mouse polling error: {str(e)}", MessageLevel.ERROR)
    
    def _maybe_restart_mouse_polling(self):
        """Restart mouse polling if keys still held."""
        if self.key_combination_active and self.click_through_enabled:
            self._start_mouse_polling()
    
    def _is_mouse_over_overlay(self, mouse_pos: Tuple[int, int]) -> bool:
        """Manual hit testing - check if mouse is over overlay."""
        try:
            if not self.hwnd:
                return False
            
            rect = win32gui.GetWindowRect(self.hwnd)
            left, top, right, bottom = rect
            mx, my = mouse_pos
            return left <= mx <= right and top <= my <= bottom
            
        except:
            return False
    
    def _trigger_overlay_menu(self, mouse_pos: Tuple[int, int]):
        """Trigger context menu from hybrid detection."""
        try:
            # Temporarily disable click-through
            if self.click_through_enabled:
                ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
                new_ex_style = ex_style & ~win32con.WS_EX_TRANSPARENT
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, new_ex_style)
            
            # Convert to window coordinates
            window_pos = self.ScreenToClient(mouse_pos)
            
            # Show context menu
            self._show_overlay_context_menu(window_pos, from_hybrid=True)
            
        except Exception as e:
            self._log_message(f"Menu trigger error: {str(e)}", MessageLevel.ERROR)
    
    # Windows API and Transparency Management
    
    def _apply_opacity(self, opacity: int) -> bool:
        """Apply opacity using Windows API."""
        try:
            if self.CanSetTransparent():
                self.SetTransparent(opacity)
            
            if self.hwnd:
                ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
                if not (ex_style & win32con.WS_EX_LAYERED):
                    win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, ex_style | win32con.WS_EX_LAYERED)
                win32gui.SetLayeredWindowAttributes(self.hwnd, 0, opacity, win32con.LWA_ALPHA)
            
            self.opacity_level = opacity
            self._save_overlay_settings()
            return True
        except Exception as e:
            self._log_message(f"Opacity error: {str(e)}", MessageLevel.ERROR)
            return False
    
    def toggle_click_through(self) -> bool:
        """Toggle click-through mode."""
        if not self.hwnd:
            self._log_message("No window handle for click-through toggle", MessageLevel.WARNING)
            return False
        
        try:
            ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
            
            if self.click_through_enabled:
                # Disable click-through
                new_ex_style = ex_style & ~win32con.WS_EX_TRANSPARENT
                self.click_through_enabled = False
                self._stop_key_polling()
                self._stop_mouse_polling()
                self._update_status_indicator("ready")
                self._log_message("Click-through disabled", MessageLevel.DEBUG)
            else:
                # Enable click-through
                new_ex_style = ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                self.click_through_enabled = True
                self._start_key_polling()
                self._update_status_indicator("key_polling")
                self._log_message("Click-through enabled - Hybrid polling active", MessageLevel.DEBUG)

            win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, new_ex_style)
            win32gui.SetLayeredWindowAttributes(self.hwnd, 0, self.opacity_level, win32con.LWA_ALPHA)
            
            self._save_overlay_settings()
            return True
            
        except Exception as e:
            self._log_message(f"Click-through toggle error: {str(e)}", MessageLevel.ERROR)
            return False
    
    def cycle_opacity(self):
        """Cycle through opacity levels."""
        opacity_steps = [255, 200, 150, 100, 60]
        
        try:
            current_index = opacity_steps.index(self.opacity_level) if self.opacity_level in opacity_steps else -1
            next_index = (current_index + 1) % len(opacity_steps)
            new_opacity = opacity_steps[next_index]
            
            if self._apply_opacity(new_opacity):
                pct = int((new_opacity/255)*100)
                self._log_message(f"Opacity changed to {pct}%", MessageLevel.INFO)
                return True
                
        except Exception as e:
            self._log_message(f"Opacity cycle failed: {str(e)}", MessageLevel.ERROR)
        
        return False
    
    # Event Handlers
    
    def _on_close(self, event):
        """Handle window close."""
        self._cleanup_overlay()
        event.Skip()
    
    def _on_key_press(self, event):
        """Handle key press events."""
        if event.GetKeyCode() == wx.WXK_ESCAPE:
            self._cleanup_overlay()
            self.Close()
        else:
            event.Skip()
    
    def _on_normal_right_click(self, event):
        """Handle normal right-click (when not in click-through mode)."""
        if not self.click_through_enabled:
            self._show_overlay_context_menu(event.GetPosition(), from_hybrid=False)
    
    def _on_title_right_click(self, event):
        """Handle right-click specifically on title bar - show control menu."""
        self._show_title_control_menu(event.GetPosition())
    
    def _on_drag_start(self, event):
        """Handle window dragging."""
        if self.click_through_enabled:
            return
        
        self.CaptureMouse()
        pos = event.GetPosition()
        self.delta_x = pos.x
        self.delta_y = pos.y
        
        def on_move(evt):
            if evt.Dragging() and evt.LeftIsDown():
                mouse_pos = wx.GetMousePosition()
                new_pos = (mouse_pos.x - self.delta_x, mouse_pos.y - self.delta_y)
                self.SetPosition(new_pos)
        
        def on_up(evt):
            if self.HasCapture():
                self.ReleaseMouse()
                self.Unbind(wx.EVT_MOTION)
                self.Unbind(wx.EVT_LEFT_UP)
                self._save_overlay_settings()  # Save new position
        
        self.Bind(wx.EVT_MOTION, on_move)
        self.Bind(wx.EVT_LEFT_UP, on_up)
    
    def _show_overlay_context_menu(self, position, from_hybrid=False):
        """Show overlay context menu."""
        try:
            menu = wx.Menu()
            
            if from_hybrid:
                # Success indicator for hybrid detection
                success_item = menu.Append(wx.ID_ANY, "✓ Hybrid Overlay Menu (Ctrl+Alt+Right)")
                menu.AppendSeparator()
            
            # Opacity control
            opacity_item = menu.Append(wx.ID_ANY, "Change Opacity")
            self.Bind(wx.EVT_MENU, lambda evt: self.cycle_opacity(), opacity_item)
            
            # Click-through toggle
            ct_label = "Disable Click-Through" if self.click_through_enabled else "Enable Click-Through"
            ct_item = menu.Append(wx.ID_ANY, ct_label)
            self.Bind(wx.EVT_MENU, lambda evt: self.toggle_click_through(), ct_item)
            
            menu.AppendSeparator()
            
            
            # Performance info
            perf_item = menu.Append(wx.ID_ANY, f"Stats: {self.key_polls} keys, {self.mouse_polls} mouse")
            
            # Close
            close_item = menu.Append(wx.ID_ANY, "Close Overlay")
            self.Bind(wx.EVT_MENU, lambda evt: self.Close(), close_item)
            
            # Show menu
            self.PopupMenu(menu, position)
            menu.Destroy()
            
            # Re-enable click-through if it was enabled
            if self.click_through_enabled:
                wx.CallAfter(self._re_enable_click_through)
                
        except Exception as e:
            self._log_message(f"Context menu error: {str(e)}", MessageLevel.ERROR)
    
    def _re_enable_click_through(self):
        """Re-enable click-through after menu interaction."""
        if self.click_through_enabled and self.hwnd:
            try:
                ex_style = win32gui.GetWindowLong(self.hwnd, win32con.GWL_EXSTYLE)
                new_ex_style = ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT
                win32gui.SetWindowLong(self.hwnd, win32con.GWL_EXSTYLE, new_ex_style)
                win32gui.SetLayeredWindowAttributes(self.hwnd, 0, self.opacity_level, win32con.LWA_ALPHA)
            except Exception as e:
                self._log_message(f"Re-enable click-through error: {str(e)}", MessageLevel.ERROR)
    
    def _show_title_control_menu(self, position):
        """Show title bar control menu with overlay-specific options."""
        try:
            menu = wx.Menu()
            
            # Header con nombre del widget
            header_item = menu.Append(wx.ID_ANY, f"📋 {self.widget_class.__name__} Overlay")
            header_item.Enable(False)
            menu.AppendSeparator()
            
            # Opacity control con indicador actual
            opacity_pct = int((self.opacity_level/255)*100)
            opacity_item = menu.Append(wx.ID_ANY, f"🔅 Opacidad ({opacity_pct}%) - Click para cambiar")
            self.Bind(wx.EVT_MENU, lambda evt: self.cycle_opacity(), opacity_item)
            
            # Click-through toggle con indicador de estado
            if self.click_through_enabled:
                ct_item = menu.Append(wx.ID_ANY, "🖱️ Deshabilitar Click-Through")
                ct_icon = "🔴"
            else:
                ct_item = menu.Append(wx.ID_ANY, "🖱️ Habilitar Click-Through")
                ct_icon = "🟢"
            
            self.Bind(wx.EVT_MENU, lambda evt: self.toggle_click_through(), ct_item)
            
            menu.AppendSeparator()
            
            # Size presets
            size_submenu = wx.Menu()
            
            # Current size
            current_size = self.GetSize()
            current_item = size_submenu.Append(wx.ID_ANY, f"📐 Actual: {current_size.width}x{current_size.height}")
            current_item.Enable(False)
            size_submenu.AppendSeparator()
            
            # Preset sizes
            size_presets = [
                ("Pequeño", (400, 300)),
                ("Mediano", (600, 400)), 
                ("Grande", (800, 500)),
                ("Muy Grande", (1000, 600))
            ]
            
            for name, size in size_presets:
                size_item = size_submenu.Append(wx.ID_ANY, f"{name} ({size[0]}x{size[1]})")
                self.Bind(wx.EVT_MENU, lambda evt, s=size: self._resize_overlay(s), size_item)
            
            menu.AppendSubMenu(size_submenu, "📏 Cambiar Tamaño")
            
            # Position presets
            pos_submenu = wx.Menu()
            
            # Current position
            current_pos = self.GetPosition()
            current_pos_item = pos_submenu.Append(wx.ID_ANY, f"📍 Actual: {current_pos.x}, {current_pos.y}")
            current_pos_item.Enable(False)
            pos_submenu.AppendSeparator()
            
            # Preset positions
            pos_presets = [
                ("🔝 Arriba Izquierda", (50, 50)),
                ("🔝 Arriba Derecha", (800, 50)),
                ("🔽 Abajo Izquierda", (50, 400)),
                ("🔽 Abajo Derecha", (800, 400)),
                ("🎯 Centro", (400, 300))
            ]
            
            for name, pos in pos_presets:
                pos_item = pos_submenu.Append(wx.ID_ANY, name)
                self.Bind(wx.EVT_MENU, lambda evt, p=pos: self._move_overlay(p), pos_item)
            
            menu.AppendSubMenu(pos_submenu, "📍 Mover a...")
            
            menu.AppendSeparator()
            
            # Performance info
            stats = self.get_performance_stats()
            if self.click_through_enabled:
                perf_text = f"📊 Rendimiento: {stats['key_polls']} keys, {stats['mouse_polls']} mouse"
            else:
                perf_text = f"📊 Tiempo activo: {int(stats['uptime_seconds'])}s"
            
            perf_item = menu.Append(wx.ID_ANY, perf_text)
            perf_item.Enable(False)
            
            # Reset settings
            reset_item = menu.Append(wx.ID_ANY, "🔄 Restaurar Configuración")
            self.Bind(wx.EVT_MENU, lambda evt: self._reset_overlay_settings(), reset_item)
            
            menu.AppendSeparator()
            
            # Close
            close_item = menu.Append(wx.ID_ANY, "❌ Cerrar Overlay")
            self.Bind(wx.EVT_MENU, lambda evt: self.Close(), close_item)
            
            # Show menu at title bar position
            self.title_panel.PopupMenu(menu, position)
            menu.Destroy()
            
        except Exception as e:
            self._log_message(f"Title control menu error: {str(e)}", MessageLevel.ERROR)
    
    def _resize_overlay(self, new_size):
        """Resize overlay to specific size."""
        try:
            self.SetSize(new_size)
            self._save_overlay_settings()
        except Exception as e:
            self._log_message(f"Resize error: {str(e)}", MessageLevel.ERROR)
    
    def _move_overlay(self, new_position):
        """Move overlay to specific position."""
        try:
            self.SetPosition(new_position)
            self._save_overlay_settings()
        except Exception as e:
            self._log_message(f"Move error: {str(e)}", MessageLevel.ERROR)
    
    def _reset_overlay_settings(self):
        """Reset overlay settings to defaults."""
        try:
            # Reset to default size and position
            self.SetSize((600, 400))
            self.SetPosition((200, 200))
            self._apply_opacity(200)  # Default opacity
            
            # Disable click-through if enabled
            if self.click_through_enabled:
                self.toggle_click_through()
            
            self._save_overlay_settings()
        except Exception as e:
            self._log_message(f"Reset settings error: {str(e)}", MessageLevel.ERROR)
    
    
    # Utility Methods
    
    def _update_status_indicator(self, status: str):
        """Update visual status indicator."""
        try:
            status_colors = {
                'ready': wx.Colour(100, 150, 100),      # Green
                'key_polling': wx.Colour(150, 150, 100),  # Yellow
                'active_polling': wx.Colour(150, 100, 100), # Red
                'error': wx.Colour(200, 100, 100)       # Bright red
            }
            
            color = status_colors.get(status, wx.Colour(100, 100, 100))
            self.status_indicator.SetForegroundColour(color)
        except:
            pass
    
    def _log_message(self, message: str, level: MessageLevel = MessageLevel.INFO):
        """Log message through MessageBus."""
        try:
            message_bus.publish(content=f"[Overlay:{self.overlay_id}] {message}", level=level)
        except:
            print(f"[Overlay:{self.overlay_id}] {message}")
    
    def _cleanup_overlay(self):
        """Clean up overlay resources."""
        try:
            self._stop_key_polling()
            self._stop_mouse_polling()
            self._save_overlay_settings()
        except Exception as e:
            self._log_message(f"Cleanup error: {str(e)}", MessageLevel.ERROR)
    
    # Public API
    
    def get_widget_instance(self):
        """Get the embedded widget instance."""
        return self.widget_instance
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        elapsed = time.time() - self.start_time
        return {
            'key_polls': self.key_polls,
            'mouse_polls': self.mouse_polls,
            'menu_activations': self.menu_activations,
            'key_polls_per_second': self.key_polls / elapsed if elapsed > 0 else 0,
            'mouse_polls_per_second': self.mouse_polls / elapsed if elapsed > 0 else 0,
            'uptime_seconds': elapsed
        }
    
