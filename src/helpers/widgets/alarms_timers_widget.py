"""
Alarms and Timers Widget for SCLogAnalyzer
Provides stopwatch and countdown timer functionality integrated into the connected users panel.
"""

import uuid
import wx
from datetime import datetime, timedelta
from threading import RLock
from typing import List, Optional, Dict

from helpers.widgets.dark_listctrl import DarkListCtrl
from helpers.ui.ui_components import MiniDarkThemeButton
from helpers.core.message_bus import message_bus, MessageLevel


def format_time(seconds: float) -> str:
    """
    Format time in seconds to MM:SS format.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted time string (MM:SS)
    """
    total_seconds = int(seconds)
    minutes = total_seconds // 60
    secs = total_seconds % 60
    return f"{minutes:02d}:{secs:02d}"


class Timer:
    """
    Stopwatch class with lap functionality.
    Thread-safe implementation for concurrent access.
    """

    def __init__(self, name: str):
        """
        Initialize a new timer.

        Args:
            name: Display name for the timer
        """
        self.id = str(uuid.uuid4())
        self.name = name
        self._lock = RLock()

        # State
        self._state = "stopped"  # "running", "paused", "stopped"

        # Time tracking
        self._elapsed_seconds = 0.0
        self._start_time: Optional[datetime] = None
        self._pause_time: Optional[datetime] = None

        # Laps
        self._laps: List[float] = []

        # Metadata
        self.created_at = datetime.now()

    def start(self) -> None:
        """Start or resume the timer."""
        with self._lock:
            if self._state == "running":
                return

            self._start_time = datetime.now()
            self._state = "running"

    def stop(self) -> None:
        """Stop the timer (pause)."""
        with self._lock:
            if self._state != "running":
                return

            # Update elapsed time
            if self._start_time:
                elapsed = (datetime.now() - self._start_time).total_seconds()
                self._elapsed_seconds += elapsed

            self._pause_time = datetime.now()
            self._state = "paused"
            self._start_time = None

    def pause(self) -> None:
        """Alias for stop()."""
        self.stop()

    def reset(self) -> None:
        """Reset the timer to zero."""
        with self._lock:
            self._elapsed_seconds = 0.0
            self._start_time = None
            self._pause_time = None
            self._laps.clear()
            self._state = "stopped"

    def lap(self) -> float:
        """
        Record a lap time.

        Returns:
            The current elapsed time in seconds
        """
        with self._lock:
            current_time = self.get_elapsed_time()
            self._laps.append(current_time)
            return current_time

    def get_elapsed_time(self) -> float:
        """
        Get the current elapsed time in seconds.

        Returns:
            Total elapsed time in seconds
        """
        with self._lock:
            if self._state == "running" and self._start_time:
                # Add time since last start
                current_elapsed = (datetime.now() - self._start_time).total_seconds()
                return self._elapsed_seconds + current_elapsed
            else:
                return self._elapsed_seconds

    def get_laps(self) -> List[float]:
        """
        Get all recorded lap times.

        Returns:
            List of lap times in seconds
        """
        with self._lock:
            return self._laps.copy()

    def get_state(self) -> str:
        """
        Get the current timer state.

        Returns:
            State string: "running", "paused", or "stopped"
        """
        with self._lock:
            return self._state


class Alarm:
    """
    Countdown timer class with adjustable time.
    Thread-safe implementation for concurrent access.
    """

    def __init__(self, minutes: int, name: Optional[str] = None):
        """
        Initialize a new alarm.

        Args:
            minutes: Initial countdown time in minutes
            name: Optional display name for the alarm
        """
        self.id = str(uuid.uuid4())
        self.name = name or f"{minutes}min Alarm"
        self._lock = RLock()

        # State
        self._state = "paused"  # "running", "paused", "expired"

        # Time tracking
        self._total_minutes = minutes
        self._remaining_seconds = minutes * 60.0
        self._start_time: Optional[datetime] = None
        self._pause_time: Optional[datetime] = None

        # Metadata
        self.created_at = datetime.now()

    def start(self) -> None:
        """Start the countdown."""
        with self._lock:
            if self._state == "running" or self._state == "expired":
                return

            if self._remaining_seconds <= 0:
                self._state = "expired"
                return

            self._start_time = datetime.now()
            self._state = "running"

    def pause(self) -> None:
        """Pause the countdown."""
        with self._lock:
            if self._state != "running":
                return

            # Update remaining time
            if self._start_time:
                elapsed = (datetime.now() - self._start_time).total_seconds()
                self._remaining_seconds -= elapsed

                # Check if expired
                if self._remaining_seconds <= 0:
                    self._remaining_seconds = 0
                    self._state = "expired"
                else:
                    self._state = "paused"

            self._pause_time = datetime.now()
            self._start_time = None

    def adjust_time(self, delta_minutes: int) -> None:
        """
        Adjust the remaining time by adding/subtracting minutes.

        Args:
            delta_minutes: Minutes to add (positive) or subtract (negative)
        """
        with self._lock:
            # If running, pause first to update remaining time
            was_running = self._state == "running"
            if was_running:
                self.pause()

            # Adjust time
            self._remaining_seconds += delta_minutes * 60.0

            # Clamp to valid range (0 to 999 minutes)
            self._remaining_seconds = max(0, min(self._remaining_seconds, 999 * 60))

            # Update state
            if self._remaining_seconds <= 0:
                self._state = "expired"
            elif self._state == "expired":
                self._state = "paused"

            # Resume if was running
            if was_running and self._state != "expired":
                self.start()

    def get_remaining_time(self) -> float:
        """
        Get the remaining time in seconds.

        Returns:
            Remaining time in seconds
        """
        with self._lock:
            if self._state == "running" and self._start_time:
                # Subtract time since start
                elapsed = (datetime.now() - self._start_time).total_seconds()
                remaining = self._remaining_seconds - elapsed
                return max(0, remaining)
            else:
                return self._remaining_seconds

    def is_expired(self) -> bool:
        """
        Check if the alarm has expired.

        Returns:
            True if expired, False otherwise
        """
        with self._lock:
            # Update state if running and time is up
            if self._state == "running":
                remaining = self.get_remaining_time()
                if remaining <= 0:
                    self._remaining_seconds = 0
                    self._state = "expired"

            return self._state == "expired"

    def get_state(self) -> str:
        """
        Get the current alarm state.

        Returns:
            State string: "running", "paused", or "expired"
        """
        with self._lock:
            # Update expired state if needed
            self.is_expired()
            return self._state

    def reset(self, minutes: Optional[int] = None) -> None:
        """
        Reset the alarm to initial or specified time.

        Args:
            minutes: New time in minutes (defaults to original total_minutes)
        """
        with self._lock:
            if minutes is not None:
                self._total_minutes = minutes

            self._remaining_seconds = self._total_minutes * 60.0
            self._start_time = None
            self._pause_time = None
            self._state = "paused"


class AlarmsTimersWidget(wx.Panel):
    """
    Main widget for alarms and timers functionality.
    Displays list of active timers/alarms with controls.
    """

    def __init__(self, parent):
        """
        Initialize the widget.

        Args:
            parent: Parent wxPython window
        """
        super().__init__(parent)

        # Data storage (in-memory only, no persistence)
        self._timers: Dict[str, Timer] = {}
        self._alarms: Dict[str, Alarm] = {}
        self._lock = RLock()
        
        # Current username tracking
        self._current_username = ""

        # UI update timer
        self._update_timer: Optional[wx.Timer] = None

        # Build UI
        self._create_ui()

        # Start update timer (100ms refresh rate)
        self._update_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_update_timer)
        self._update_timer.Start(100)  # 100ms = 10 updates per second

        # Listen for shared alarms from remote_realtime_event
        message_bus.on("remote_realtime_event", self._on_remote_realtime_event)
        # Listen for username changes
        message_bus.on("username_change", self._on_username_change)

    def _create_ui(self):
        """Create the widget UI structure."""
        # Main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title bar
        title = wx.StaticText(self, label="Alarmas y Cronómetros")
        title_font = title.GetFont()
        title_font.PointSize += 2
        title_font = title_font.Bold()
        title.SetFont(title_font)
        title.SetForegroundColour(wx.Colour(230, 230, 230))
        main_sizer.Add(title, 0, wx.ALL | wx.ALIGN_CENTER, 10)

        # Quick Action Panel
        action_panel = self._create_action_panel()
        main_sizer.Add(action_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # List Panel with DarkListCtrl
        self.list_ctrl = DarkListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            auto_sizing=True
        )

        # Define columns (sin columna de Acciones)
        self.list_ctrl.InsertColumn(0, "Nombre", width=200)
        self.list_ctrl.InsertColumn(1, "Tiempo", width=100)
        self.list_ctrl.InsertColumn(2, "Estado", width=100)
        self.list_ctrl.InsertColumn(3, "Laps", width=100)

        # Bind right-click event
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self._on_item_right_click)
        # Bind selection event
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_item_selected)
        self.list_ctrl.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_item_deselected)

        main_sizer.Add(self.list_ctrl, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # Set main sizer
        self.SetSizer(main_sizer)

        # Set dark background
        self.SetBackgroundColour(wx.Colour(60, 60, 60))

    def _create_action_panel(self) -> wx.Panel:
        """
        Create the quick action panel with buttons.

        Returns:
            Panel containing action buttons
        """
        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(70, 70, 70))

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Quick alarm buttons - solo emojis/números
        alarm_label = wx.StaticText(panel, label="⏰")
        alarm_label.SetForegroundColour(wx.Colour(230, 230, 230))
        sizer.Add(alarm_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        btn_1min = MiniDarkThemeButton(panel, label="1")
        btn_1min.SetToolTip("Alarma 1 minuto")
        btn_1min.Bind(wx.EVT_BUTTON, lambda evt: self._on_quick_alarm(1))
        sizer.Add(btn_1min, 0, wx.RIGHT, 3)

        btn_5min = MiniDarkThemeButton(panel, label="5")
        btn_5min.SetToolTip("Alarma 5 minutos")
        btn_5min.Bind(wx.EVT_BUTTON, lambda evt: self._on_quick_alarm(5))
        sizer.Add(btn_5min, 0, wx.RIGHT, 3)

        btn_10min = MiniDarkThemeButton(panel, label="10")
        btn_10min.SetToolTip("Alarma 10 minutos")
        btn_10min.Bind(wx.EVT_BUTTON, lambda evt: self._on_quick_alarm(10))
        sizer.Add(btn_10min, 0, wx.RIGHT, 15)

        # Timer button - solo emoji
        btn_timer = MiniDarkThemeButton(panel, label="⏱️")
        btn_timer.SetToolTip("Añadir cronómetro")
        btn_timer.Bind(wx.EVT_BUTTON, self._on_add_timer)
        sizer.Add(btn_timer, 0, wx.RIGHT, 15)

        # Separator
        separator = wx.StaticText(panel, label="│")
        separator.SetForegroundColour(wx.Colour(150, 150, 150))
        sizer.Add(separator, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Context action buttons (disabled by default)
        self.btn_start = MiniDarkThemeButton(panel, label="▶️")
        self.btn_start.SetToolTip("Iniciar")
        self.btn_start.Bind(wx.EVT_BUTTON, self._on_context_start)
        self.btn_start.Enable(False)
        sizer.Add(self.btn_start, 0, wx.RIGHT, 3)

        self.btn_pause = MiniDarkThemeButton(panel, label="⏸️")
        self.btn_pause.SetToolTip("Pausar")
        self.btn_pause.Bind(wx.EVT_BUTTON, self._on_context_pause)
        self.btn_pause.Enable(False)
        sizer.Add(self.btn_pause, 0, wx.RIGHT, 3)

        self.btn_lap = MiniDarkThemeButton(panel, label="🏁")
        self.btn_lap.SetToolTip("Registrar Lap")
        self.btn_lap.Bind(wx.EVT_BUTTON, self._on_context_lap)
        self.btn_lap.Enable(False)
        sizer.Add(self.btn_lap, 0, wx.RIGHT, 3)

        self.btn_plus = MiniDarkThemeButton(panel, label="➕")
        self.btn_plus.SetToolTip("+1 Minuto")
        self.btn_plus.Bind(wx.EVT_BUTTON, self._on_context_plus)
        self.btn_plus.Enable(False)
        sizer.Add(self.btn_plus, 0, wx.RIGHT, 3)

        self.btn_minus = MiniDarkThemeButton(panel, label="➖")
        self.btn_minus.SetToolTip("-1 Minuto")
        self.btn_minus.Bind(wx.EVT_BUTTON, self._on_context_minus)
        self.btn_minus.Enable(False)
        sizer.Add(self.btn_minus, 0, wx.RIGHT, 3)

        self.btn_delete = MiniDarkThemeButton(panel, label="🗑️")
        self.btn_delete.SetToolTip("Eliminar")
        self.btn_delete.Bind(wx.EVT_BUTTON, self._on_context_delete)
        self.btn_delete.Enable(False)
        sizer.Add(self.btn_delete, 0, wx.RIGHT, 3)

        self.btn_share = MiniDarkThemeButton(panel, label="📢")
        self.btn_share.SetToolTip("Compartir alarma")
        self.btn_share.Bind(wx.EVT_BUTTON, self._on_context_share)
        self.btn_share.Enable(False)
        sizer.Add(self.btn_share, 0, wx.RIGHT, 10)

        # Separator
        separator2 = wx.StaticText(panel, label="│")
        separator2.SetForegroundColour(wx.Colour(150, 150, 150))
        sizer.Add(separator2, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # Clear all button
        self.btn_clear_all = MiniDarkThemeButton(panel, label="🗑️")
        self.btn_clear_all.SetToolTip("Borrar todo")
        self.btn_clear_all.Bind(wx.EVT_BUTTON, self._on_clear_all)
        sizer.Add(self.btn_clear_all, 0)

        panel.SetSizer(sizer)
        return panel

    def _on_quick_alarm(self, minutes: int):
        """
        Handle quick alarm button click.

        Args:
            minutes: Alarm duration in minutes
        """
        # Create alarm
        alarm = Alarm(minutes)
        alarm.start()  # Start immediately

        # Add to storage
        with self._lock:
            self._alarms[alarm.id] = alarm

    def _on_add_timer(self, event):
        """Handle add timer button click."""
        # Generate automatic timer name
        with self._lock:
            timer_count = len([t for t in self._timers.values()]) + 1
            name = f"Timer {timer_count}"
        
        # Create timer
        timer = Timer(name)
        timer.start()  # Start immediately

        # Add to storage
        with self._lock:
            self._timers[timer.id] = timer

    def _on_item_selected(self, event):
        """Handle item selection to enable/disable context buttons."""
        # Skip if we're updating the list
        if hasattr(self, '_updating_list') and self._updating_list:
            return
            
        index = event.GetIndex()
        if index < 0:
            return

        # Get item data
        item_id = self.list_ctrl.GetItemData(index)
        if not hasattr(self, '_item_refs') or item_id not in self._item_refs:
            return

        item_type, item = self._item_refs[item_id]
        self._update_context_buttons(item_type, item)

    def _update_context_buttons(self, item_type, item):
        """Update context buttons based on item type and state."""
        if item_type == 'timer':
            state = item.get_state()
            self.btn_start.Enable(state != "running")
            self.btn_pause.Enable(state == "running")
            self.btn_lap.Enable(state == "running")
            self.btn_plus.Enable(False)
            self.btn_minus.Enable(False)
            self.btn_delete.Enable(True)
            self.btn_share.Enable(False)
        elif item_type == 'alarm':
            state = item.get_state()
            is_active = state != "expired"
            self.btn_start.Enable(is_active and state != "running")
            self.btn_pause.Enable(is_active and state == "running")
            self.btn_lap.Enable(False)
            self.btn_plus.Enable(is_active)
            self.btn_minus.Enable(is_active)
            self.btn_delete.Enable(True)
            self.btn_share.Enable(is_active)

    def _on_item_deselected(self, event):
        """Handle item deselection to disable all context buttons."""
        # Skip if we're updating the list
        if hasattr(self, '_updating_list') and self._updating_list:
            return
            
        self.btn_start.Enable(False)
        self.btn_pause.Enable(False)
        self.btn_lap.Enable(False)
        self.btn_plus.Enable(False)
        self.btn_minus.Enable(False)
        self.btn_delete.Enable(False)
        self.btn_share.Enable(False)
        self.btn_share.Enable(False)

    def _get_selected_item(self):
        """Get the currently selected item from the list."""
        index = self.list_ctrl.GetFirstSelected()
        if index < 0:
            return None, None

        item_id = self.list_ctrl.GetItemData(index)
        if not hasattr(self, '_item_refs') or item_id not in self._item_refs:
            return None, None

        return self._item_refs[item_id]

    def _on_context_start(self, event):
        """Handle start button click for selected item."""
        item_type, item = self._get_selected_item()
        if not item:
            return

        if item_type == 'timer':
            state = item.get_state()
            if state != "running":
                item.start()
        elif item_type == 'alarm':
            state = item.get_state()
            if state != "running" and state != "expired":
                item.start()

    def _on_context_pause(self, event):
        """Handle pause button click for selected item."""
        item_type, item = self._get_selected_item()
        if not item:
            return

        if item_type == 'timer':
            state = item.get_state()
            if state == "running":
                item.pause()
        elif item_type == 'alarm':
            state = item.get_state()
            if state == "running":
                item.pause()

    def _on_context_lap(self, event):
        """Handle lap button click for selected timer."""
        item_type, item = self._get_selected_item()
        if item_type == 'timer' and item:
            self.on_timer_lap(item)

    def _on_context_plus(self, event):
        """Handle +1 minute button click for selected alarm."""
        item_type, item = self._get_selected_item()
        if item_type == 'alarm' and item:
            self.on_alarm_adjust(item, 1)

    def _on_context_minus(self, event):
        """Handle -1 minute button click for selected alarm."""
        item_type, item = self._get_selected_item()
        if item_type == 'alarm' and item:
            self.on_alarm_adjust(item, -1)

    def _on_context_delete(self, event):
        """Handle delete button click for selected item."""
        item_type, item = self._get_selected_item()
        if item:
            self.remove_item(item.id)

    def _on_clear_all(self, event):
        """Handle clear all button click."""
        # Confirm with user
        dlg = wx.MessageDialog(
            self,
            "¿Estás seguro de que quieres borrar todos los cronómetros y alarmas?",
            "Confirmar borrado",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            with self._lock:
                self._timers.clear()
                self._alarms.clear()
        
        dlg.Destroy()

    def _on_context_share(self, event):
        """Handle share alarm button click."""
        item_type, item = self._get_selected_item()
        if item_type != 'alarm' or not item:
            return

        # Show dialog to edit alarm name before sharing
        alarm = item
        remaining = alarm.get_remaining_time()
        seconds_remaining = int(remaining)
        
        if seconds_remaining <= 0:
            wx.MessageBox("No se pueden compartir alarmas expiradas", "Error", wx.OK | wx.ICON_WARNING)
            return

        # Format time for display
        minutes = seconds_remaining // 60
        seconds = seconds_remaining % 60
        time_display = f"{minutes}:{seconds:02d}"

        # Dialog to edit name
        dlg = wx.TextEntryDialog(
            self,
            f"Nombre para la alarma compartida ({time_display}):",
            "Compartir Alarma",
            alarm.name
        )

        if dlg.ShowModal() == wx.ID_OK:
            shared_name = dlg.GetValue().strip()
            # Use alarm name if no name provided
            if not shared_name:
                shared_name = alarm.name
            
            if shared_name:
                # Emit realtime event to share alarm (using seconds)
                message_bus.emit("realtime_event", {
                    'type': 'shared_alarm',
                    'name': shared_name,
                    'seconds': seconds_remaining,
                    'content': f"⏰ Alarma compartida: {shared_name} ({time_display})"
                })
                
                # Show confirmation
                message_bus.publish(
                    content=f"Alarma '{shared_name}' compartida ({time_display})",
                    level=MessageLevel.INFO
                )

        dlg.Destroy()

    def _on_remote_realtime_event(self, username, event_data):
        """Handle remote realtime events."""
        try:
            if event_data.get('type') == 'shared_alarm':
                # Ignore our own shared alarms
                if username == self._current_username:
                    return
                
                # Extract alarm data
                alarm_name = event_data.get('name')
                seconds = event_data.get('seconds')
                
                if alarm_name and seconds and isinstance(seconds, (int, float)) and seconds > 0:
                    # Convert seconds to minutes for Alarm constructor (rounded)
                    minutes = round(seconds / 60.0)
                    
                    # Add sender's username to alarm name
                    full_alarm_name = f"[{username}] {alarm_name}"
                    
                    # Create alarm, but manually set the exact remaining seconds
                    alarm = Alarm(max(1, minutes), full_alarm_name)
                    # Override the remaining seconds to use exact value
                    alarm._remaining_seconds = float(seconds)
                    alarm.start()
                    
                    with self._lock:
                        self._alarms[alarm.id] = alarm
                    
                    # Format time for display
                    mins = int(seconds // 60)
                    secs = int(seconds % 60)
                    time_display = f"{mins}:{secs:02d}"
                    
                    # Show notification
                    message_bus.emit("show_windows_notification", 
                        f"⏰ Alarma compartida por {username}: {alarm_name} ({time_display})")
                    
                    message_bus.publish(
                        content=f"Alarma recibida de {username}: {alarm_name} ({time_display})",
                        level=MessageLevel.INFO
                    )
                    
                    message_bus.publish(
                        content=f"Alarma recibida de {username}: {alarm_name} ({minutes} min)",
                        level=MessageLevel.INFO
                    )
        except Exception as e:
            message_bus.publish(
                content=f"Error handling shared alarm: {e}",
                level=MessageLevel.ERROR
            )

    def _on_username_change(self, username, old_username):
        """Handle username change events."""
        self._current_username = username

    def add_timer(self, name: str) -> Optional[Timer]:
        """
        Programmatically add a new timer.

        Args:
            name: Timer name

        Returns:
            Created Timer instance or None if failed
        """
        try:
            timer = Timer(name)
            with self._lock:
                self._timers[timer.id] = timer
            return timer
        except Exception:
            return None

    def remove_item(self, item_id: str):
        """
        Remove a timer or alarm by ID.

        Args:
            item_id: Timer or Alarm ID to remove
        """
        with self._lock:
            # Try to remove from timers
            if item_id in self._timers:
                del self._timers[item_id]
                return

            # Try to remove from alarms
            if item_id in self._alarms:
                del self._alarms[item_id]
                return

    def on_timer_lap(self, timer: Timer):
        """
        Handle lap button click for a timer.

        Args:
            timer: Timer to record lap for
        """
        lap_time = timer.lap()

        # Emit event
        message_bus.emit("timer_lap_recorded", {
            "timer_id": timer.id,
            "timer_name": timer.name,
            "lap_time": lap_time,
            "lap_count": len(timer.get_laps())
        })

    def on_timer_toggle(self, timer: Timer):
        """
        Handle start/stop toggle for a timer.

        Args:
            timer: Timer to toggle
        """
        old_state = timer.get_state()
        if old_state == "running":
            timer.stop()
            new_state = "paused"
        else:
            timer.start()
            new_state = "running"

        # Emit state change event
        message_bus.emit("timer_state_changed", {
            "timer_id": timer.id,
            "timer_name": timer.name,
            "old_state": old_state,
            "new_state": new_state
        })

    def add_alarm(self, minutes: int, name: Optional[str] = None) -> Optional[Alarm]:
        """
        Programmatically add a new alarm.

        Args:
            minutes: Alarm duration in minutes
            name: Optional alarm name

        Returns:
            Created Alarm instance or None if failed
        """
        try:
            alarm = Alarm(minutes, name)
            with self._lock:
                self._alarms[alarm.id] = alarm
            return alarm
        except Exception:
            return None

    def on_alarm_adjust(self, alarm: Alarm, delta_minutes: int):
        """
        Adjust alarm time by adding/subtracting minutes.

        Args:
            alarm: Alarm to adjust
            delta_minutes: Minutes to add (positive) or subtract (negative)
        """
        alarm.adjust_time(delta_minutes)

    def on_alarm_toggle(self, alarm: Alarm):
        """
        Handle start/pause toggle for an alarm.

        Args:
            alarm: Alarm to toggle
        """
        state = alarm.get_state()
        if state == "running":
            alarm.pause()
        elif state == "paused":
            alarm.start()

    def _check_expired_alarms(self):
        """Check for expired alarms and trigger notifications."""
        with self._lock:
            current_time = datetime.now()
            alarms_to_remove = []
            
            for alarm_id, alarm in list(self._alarms.items()):
                if alarm.is_expired():
                    # Check if we already notified
                    if not hasattr(alarm, '_notified'):
                        setattr(alarm, '_notified', True)
                        setattr(alarm, '_expired_time', current_time)
                        self._notify_alarm_expired(alarm)
                    # Check if expired alarm should be removed (after 10 seconds)
                    elif hasattr(alarm, '_expired_time'):
                        expired_time = getattr(alarm, '_expired_time')
                        elapsed = (current_time - expired_time).total_seconds()
                        if elapsed >= 10:
                            alarms_to_remove.append(alarm_id)
            
            # Remove expired alarms after 10 seconds
            for alarm_id in alarms_to_remove:
                self._alarms.pop(alarm_id, None)

    def _notify_alarm_expired(self, alarm: Alarm):
        """
        Notify user that alarm has expired.

        Args:
            alarm: Expired alarm
        """
        # Emit MessageBus event for other components
        message_bus.emit("alarm_expired", {
            "alarm_id": alarm.id,
            "alarm_name": alarm.name,
            "total_minutes": alarm._total_minutes
        })

        # Show notification via MessageBus
        message_bus.emit("show_windows_notification", f"⏰ Alarm expired: {alarm.name}")

    def _on_update_timer(self, event):
        """Handle periodic UI update timer (100ms)."""
        self._check_expired_alarms()
        wx.CallAfter(self._update_list)

    def _update_list(self):
        """Update the list display with current timer/alarm states."""
        with self._lock:
            # Initialize item_refs if needed
            if not hasattr(self, '_item_refs'):
                self._item_refs = {}

            # Block selection events during update
            if not hasattr(self, '_updating_list'):
                self._updating_list = False
            
            self._updating_list = True

            # Save current selection (by item object reference)
            selected_item = None
            index = self.list_ctrl.GetFirstSelected()
            if index >= 0:
                item_id = self.list_ctrl.GetItemData(index)
                if item_id in self._item_refs:
                    _, selected_item = self._item_refs[item_id]

            # Clear list but keep references
            self.list_ctrl.DeleteAllItems()
            self._item_refs.clear()
            # Reset item ID counter for new population
            self._next_item_id = 0

            # Add timers
            for timer_id, timer in self._timers.items():
                self._add_timer_to_list(timer)

            # Add alarms
            for alarm_id, alarm in self._alarms.items():
                self._add_alarm_to_list(alarm)

            # Restore selection if item still exists
            if selected_item:
                for idx in range(self.list_ctrl.GetItemCount()):
                    item_id = self.list_ctrl.GetItemData(idx)
                    if item_id in self._item_refs:
                        item_type, item = self._item_refs[item_id]
                        if item is selected_item:
                            # Ensure item is selected and focused
                            self.list_ctrl.Select(idx)
                            self.list_ctrl.Focus(idx)
                            self.list_ctrl.EnsureVisible(idx)
                            # Update buttons after flag is cleared
                            def update_buttons():
                                self._updating_list = False
                                self._update_context_buttons(item_type, item)
                            wx.CallAfter(update_buttons)
                            return
            
            self._updating_list = False

    def _add_timer_to_list(self, timer: Timer):
        """
        Add a timer to the list display.

        Args:
            timer: Timer instance to display
        """
        index = self.list_ctrl.GetItemCount()
        self.list_ctrl.InsertItem(index, timer.name)

        # Time column
        elapsed = timer.get_elapsed_time()
        self.list_ctrl.SetItem(index, 1, format_time(elapsed))

        # State column with color
        state = timer.get_state()
        self.list_ctrl.SetItem(index, 2, state.capitalize())

        # Color based on state
        if state == "running":
            color = wx.Colour(100, 200, 100)  # Green
        elif state == "paused":
            color = wx.Colour(200, 200, 100)  # Yellow
        else:
            color = wx.Colour(150, 150, 150)  # Gray

        self.list_ctrl.SetItemTextColour(index, color)

        # Laps column - mostrar tiempos separados por comas
        laps = timer.get_laps()
        if laps:
            laps_text = ", ".join([format_time(lap) for lap in laps])
            self.list_ctrl.SetItem(index, 3, laps_text)
        else:
            self.list_ctrl.SetItem(index, 3, "")

        # Store timer ID in item data using incremental counter
        item_key = self._next_item_id
        self._next_item_id += 1
        self.list_ctrl.SetItemData(index, item_key)
        # Store reference in a dict for retrieval
        self._item_refs[item_key] = ('timer', timer)

    def _add_alarm_to_list(self, alarm: Alarm):
        """
        Add an alarm to the list display.

        Args:
            alarm: Alarm instance to display
        """
        index = self.list_ctrl.GetItemCount()
        self.list_ctrl.InsertItem(index, alarm.name)

        # Time column (remaining time)
        remaining = alarm.get_remaining_time()
        self.list_ctrl.SetItem(index, 1, format_time(remaining))

        # State column with color
        state = alarm.get_state()
        self.list_ctrl.SetItem(index, 2, state.capitalize())

        # Color based on state
        if state == "running":
            color = wx.Colour(100, 200, 100)  # Green
        elif state == "paused":
            color = wx.Colour(200, 200, 100)  # Yellow
        else:  # expired
            color = wx.Colour(200, 100, 100)  # Red

        self.list_ctrl.SetItemTextColour(index, color)

        # Laps column (N/A for alarms)
        self.list_ctrl.SetItem(index, 3, "N/A")

        # Store alarm ID in item data using incremental counter
        item_key = self._next_item_id
        self._next_item_id += 1
        self.list_ctrl.SetItemData(index, item_key)
        # Store reference in a dict for retrieval
        self._item_refs[item_key] = ('alarm', alarm)

    def _on_item_right_click(self, event):
        """Handle right-click on list item."""
        index = event.GetIndex()

        if index < 0:
            return

        # Get item data
        item_id = self.list_ctrl.GetItemData(index)

        if not hasattr(self, '_item_refs'):
            return

        if item_id not in self._item_refs:
            return

        item_type, item = self._item_refs[item_id]

        # Get click position
        point = event.GetPoint()

        if item_type == 'timer':
            self._show_timer_context_menu(item, point)
        elif item_type == 'alarm':
            self._show_alarm_context_menu(item, point)

    def _show_timer_context_menu(self, timer: Timer, point):
        """Show context menu for timer (right-click)."""
        menu = wx.Menu()

        state = timer.get_state()

        if state == "running":
            pause_item = menu.Append(wx.ID_ANY, "⏸️ Pausar")
            self.Bind(wx.EVT_MENU, self._on_context_pause, pause_item)
            
            lap_item = menu.Append(wx.ID_ANY, "🏁 Lap")
            self.Bind(wx.EVT_MENU, self._on_context_lap, lap_item)
        else:
            start_item = menu.Append(wx.ID_ANY, "▶️ Iniciar")
            self.Bind(wx.EVT_MENU, self._on_context_start, start_item)

        menu.AppendSeparator()

        delete_item = menu.Append(wx.ID_ANY, "🗑️ Eliminar")
        self.Bind(wx.EVT_MENU, self._on_context_delete, delete_item)

        self.list_ctrl.PopupMenu(menu, point)
        menu.Destroy()

    def _show_alarm_context_menu(self, alarm: Alarm, point):
        """Show context menu for alarm (right-click)."""
        menu = wx.Menu()

        state = alarm.get_state()

        if state != "expired":
            if state == "running":
                pause_item = menu.Append(wx.ID_ANY, "⏸️ Pausar")
                self.Bind(wx.EVT_MENU, self._on_context_pause, pause_item)
            else:
                start_item = menu.Append(wx.ID_ANY, "▶️ Iniciar")
                self.Bind(wx.EVT_MENU, self._on_context_start, start_item)

            menu.AppendSeparator()

            plus_item = menu.Append(wx.ID_ANY, "➕ +1 min")
            self.Bind(wx.EVT_MENU, self._on_context_plus, plus_item)

            minus_item = menu.Append(wx.ID_ANY, "➖ -1 min")
            self.Bind(wx.EVT_MENU, self._on_context_minus, minus_item)

            menu.AppendSeparator()
            
            share_item = menu.Append(wx.ID_ANY, "📤 Compartir")
            self.Bind(wx.EVT_MENU, self._on_context_share, share_item)

            menu.AppendSeparator()

        delete_item = menu.Append(wx.ID_ANY, "🗑️ Eliminar")
        self.Bind(wx.EVT_MENU, self._on_context_delete, delete_item)

        self.list_ctrl.PopupMenu(menu, point)
        menu.Destroy()

    def cleanup(self):
        """Clean up all timers and alarms when closing widget."""
        with self._lock:
            # Stop update timer
            if self._update_timer and self._update_timer.IsRunning():
                self._update_timer.Stop()

            # Clear all data
            self._timers.clear()
            self._alarms.clear()
