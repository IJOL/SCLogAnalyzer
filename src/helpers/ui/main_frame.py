#!/usr/bin/env python
import wx
import os
import sys
import webcolors
from helpers.core import log_analyzer
import win32event
import win32api
import winerror
from datetime import datetime

from helpers.ui.ui_components import TabCreator, DynamicLabels
from helpers.services.monitoring_service import MonitoringService
from helpers.ui.data_display_manager import DataDisplayManager
from helpers.ui.window_state_manager import WindowStateManager
from helpers.ui.gui_module import ConfigDialog, ProcessDialog, TaskBarIcon, AboutDialog
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_application_path, get_config_manager, get_template_base_dir
from helpers.core.supabase_manager import supabase_manager
from helpers.widgets.recording_switch_widget import RecordingSwitchWidget
from helpers.widgets.toggle_button_widget import ToggleButtonWidget
from helpers.services import updater
from version import get_version
from helpers.ui.ui_components import DarkThemeButton
from helpers.widgets.tournament_widget import TournamentWidget

# Define constants for repeated strings and values
CONFIG_FILE_NAME = "config.json"
REGISTRY_KEY_PATH = r"Software\SCLogAnalyzer\WindowInfo"
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_APP_NAME = "SCLogAnalyzer"
STARTUP_COMMAND_FLAG = "--start-hidden"
DEFAULT_WINDOW_POSITION = (50, 50)
DEFAULT_WINDOW_SIZE = (800, 600)
LOG_FILE_WILDCARD = "Log files (*.log)|*.log|All files (*.*)|*.*"
TASKBAR_ICON_TOOLTIP = "SC Log Analyzer"
MUTEX_NAME = "Global\\SCLogAnalyzer_SingleInstance_Mutex"

# Use constants from the updater module
from helpers.services.updater import UPDATER_EXECUTABLE, LEGACY_UPDATER


class LogAnalyzerFrame(wx.Frame):
    """Main application frame for SC Log Analyzer."""
    
    def __init__(self, debug_mode=False):
        """Initialize the main application frame."""
        super().__init__(None, title="SC Log Analyzer", size=(800, 600))
        message_bus.on("datasource_changed", self.handle_datasource_change)
        message_bus.on("config_saved", self.on_config_saved)
        
        # Set the application icon
        icon_path = os.path.join(get_template_base_dir(),'assets', "SCLogAnalyzer.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))
        
        # Initialize state properties
        self.username = "Unknown"
        self.shard = "Unknown"
        self.version = "Unknown"
        self.mode = "None"
        # Set debug mode from parameter (solo para UI)
        self.debug_mode = debug_mode
        # Sincroniza el estado global de debug
        message_bus.set_debug_mode(self.debug_mode)
        
        # Define a consistent name for log message subscription
        self.log_subscription_name = "gui_main"
        
        # Initialize manager and service objects
        self.config_manager = get_config_manager(in_gui=True)
        self.tab_creator = TabCreator(self)
        self.monitoring_service = MonitoringService(self)
        self.data_manager = DataDisplayManager(self)
        self.window_manager = WindowStateManager(self)
        self.dynamic_labels = DynamicLabels(self)
        
        # Initialize RealtimeBridge if using Supabase
        self.realtime_bridge = None
        if self.config_manager.get('datasource') == 'supabase' and supabase_manager.is_connected():
            try:
                # Importar el puente de Realtime
                from helpers.core.realtime_bridge import RealtimeBridge
                
                # Obtener el cliente Supabase ya configurado
                supabase_client = supabase_manager.supabase
                
                if supabase_client:
                    # Crear la instancia de RealtimeBridge
                    self.realtime_bridge = RealtimeBridge(supabase_client, self.config_manager)
                    message_bus.publish(
                        content="Realtime intercommunication enabled",
                        level=MessageLevel.INFO,
                        metadata={"source": "main_frame"}
                    )
                else:
                    message_bus.publish(
                        content="Realtime bridge NOT initialized (datasource is not supabase or not connected)",
                        level=MessageLevel.DEBUG,
                        metadata={"source": "main_frame"}
                    )
            except Exception as e:
                message_bus.publish(
                    content=f"Error initializing Realtime bridge: {e}",
                    level=MessageLevel.ERROR,
                    metadata={"source": "main_frame"}
                )
        
        # Create main panel and UI components
        self._create_ui_components()
        self.panel.Layout()

        # Set flag for GUI mode in log_analyzer
        log_analyzer.main.in_gui = True

        
        # Subscribe to message bus for log messages with history replay
        message_bus.subscribe(
            self.log_subscription_name, 
            self._append_log_message_from_bus,
            replay_history=True,  # Enable message history replay
            max_replay_messages=100,  # Replay up to 100 most recent messages
            min_replay_level=MessageLevel.DEBUG if self.debug_mode else MessageLevel.INFO  # Include DEBUG messages if in debug mode
        )
        
        # Subscribe to events using MessageBus
        message_bus.on("shard_version_update", self.on_shard_version_update)
        message_bus.on("mode_change", self.on_mode_change)
        message_bus.on("username_change", self.on_username_change)
        
        # The direct gui_log_handler is deprecated and removed.
        # All logging is now handled via the MessageBus subscription.
    
       
        # Initialize configuration and settings
        self.initialize_config()
        self.config_manager.renew_config()
        
        # Set up stdout redirection

        # Create taskbar icon
        self.taskbar_icon = TaskBarIcon(self, TASKBAR_ICON_TOOLTIP)

        # Check if the app is started with the --start-hidden flag
        if STARTUP_COMMAND_FLAG in sys.argv:
            self.Hide()  # Hide the main window at startup
            
        # Check for updates after UI is visible, not blocking startup
        wx.CallAfter(lambda: wx.CallLater(1000, self.check_for_updates))

        # Start monitoring by default when GUI is launched, but with a smaller delay
        if self.log_file_path:
            wx.CallAfter(self.monitoring_service.start_monitoring, 500)

        # Restore window position, size, and state
        self.window_manager.restore_window_info()

        # Bind close event to handle cleanup
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Bind keyboard events for secret debug mode activation
        self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Frame-level binding
        if hasattr(self, 'log_text'):
            self.log_text.Bind(wx.EVT_KEY_DOWN, self.on_key_down)  # Bind to log text control
        
        # Initialize dynamic labels
        wx.CallAfter(self.update_dynamic_labels)
        
        # Initially hide debug elements
        self.update_debug_ui_visibility()

        # Initialize hotkey system after MessageBus is ready
        wx.CallAfter(self._initialize_hotkey_system)

        # --- Suscripción para broadcast_ping_missing: siempre delega a hilo principal con wx.CallAfter ---
        message_bus.on("broadcast_ping_missing", lambda *a, **k: wx.CallAfter(self.handle_broadcast_ping_missing))
        message_bus.on("realtime_reconnected", lambda *a, **k: wx.CallAfter(self.handle_realtime_reconnected))
    
    def handle_realtime_reconnected(self):
        """
        Handle the event when the realtime connection is reconnected.
        This method is always called in the main thread.
        You can safely update UI here.
        """
        self.SetStatusText("Ready")
        
    def handle_broadcast_ping_missing(self):
        """
        Handle the event when no ping is received from any user in over 120 seconds.
        This method is always called in the main thread.
        You can safely start wx.Timer or update UI here.
        """
        self.SetStatusText("Warning: No pings received in 120s. Realtime reconnecting...")
    
    def _initialize_hotkey_system(self):
        """Inicializar sistema de hotkeys con manejo de errores"""
        try:
            if self.config_manager.get('hotkey_system.enabled', True):
                from helpers.services.hotkey_manager import get_hotkey_manager
                from helpers.overlay.overlay_manager import OverlayManager
                
                # Obtener instancia singleton del HotkeyManager
                self.hotkey_manager = get_hotkey_manager()
                
                # Iniciar sistema de hotkeys
                self.hotkey_manager.start_listening()
                
                # Registrar hotkeys de sistema
                self._initialize_system_hotkeys()
                
                # Inicializar hotkeys de overlays
                OverlayManager.get_instance().initialize_hotkeys()
                
                message_bus.publish(
                    content="Hotkey system initialized successfully",
                    level=MessageLevel.INFO
                )
            else:
                message_bus.publish(
                    content="Hotkey system disabled in configuration",
                    level=MessageLevel.INFO
                )
                
        except Exception as e:
            message_bus.publish(
                content=f"Hotkey system initialization failed: {e}",
                level=MessageLevel.ERROR
            )
    
    def _initialize_system_hotkeys(self):
        """Registrar hotkeys específicos del sistema principal"""
        try:
            # Registrar hotkeys de sistema
            self.hotkey_manager.register_hotkey("ctrl+alt+m", "system_toggle_monitoring", "Toggle Monitoring", "System")
            self.hotkey_manager.register_hotkey("ctrl+alt+s", "system_auto_shard", "Auto Shard", "System")  
            self.hotkey_manager.register_hotkey("ctrl+alt+c", "system_open_config", "Open Config", "System")
            self.hotkey_manager.register_hotkey("ctrl+alt+r", "system_toggle_recording", "Toggle Recording", "System")
            self.hotkey_manager.register_hotkey("ctrl+alt+n", "system_toggle_notifications", "Toggle Notifications", "System")
            
            # Registrar handlers de sistema - usar wx.CallAfter para thread safety
            message_bus.on("system_toggle_monitoring", lambda: wx.CallAfter(self.on_monitor, None))
            message_bus.on("system_auto_shard", lambda: wx.CallAfter(self.on_autoshard, None))
            message_bus.on("system_open_config", lambda: wx.CallAfter(self.on_edit_config, None))
            message_bus.on("system_toggle_recording", lambda: wx.CallAfter(self.on_recording, None))
            message_bus.on("system_toggle_notifications", lambda: wx.CallAfter(self.on_toggle_notifications, None))
            
            message_bus.publish(
                content="System hotkeys registered successfully",
                level=MessageLevel.DEBUG
            )
            
        except Exception as e:
            message_bus.publish(
                content=f"Error registering system hotkeys: {e}",
                level=MessageLevel.ERROR
            )
    

    def _create_ui_components(self):
        """Create all UI components for the main application window."""
        # Create main panel
        self.panel = wx.Panel(self)
        panel = self.panel
        
        # Bind keyboard events to panel as well
        panel.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

        # Create main vertical sizer
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Add dynamic labels for username, shard, version, and mode
        self.dynamic_labels.label_sizer = self.dynamic_labels.create_labels(panel, main_sizer)

        # Create notebook for log output and Google Sheets data
        self.notebook = wx.Notebook(panel)
        self.log_page = wx.Panel(self.notebook)
        self.notebook.AddPage(self.log_page, "Main Log")

        # Tournament tab
        try:
            self.tournament_widget = TournamentWidget(self.notebook)
            self.notebook.AddPage(self.tournament_widget, "Tournaments")
            message_bus.publish(
                content="Tournament tab created successfully",
                level=MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error creating tournament tab: {str(e)}",
                level=MessageLevel.ERROR
            )

        # Bind the notebook page change event
        self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_notebook_page_changed)

        # Create a vertical sizer for the log page
        log_page_sizer = wx.BoxSizer(wx.VERTICAL)

        # --- NUEVO: Separación de sizers para botones principales y debug ---
        # Sizer para botones principales
        self.main_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Sizer para botones de debug (creado una vez, gestionado dinámicamente)
        self.debug_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Add a horizontal sizer for buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        # Control de notificaciones (ahora con ToggleButtonWidget)
        self.notifications_button = ToggleButtonWidget(
            parent=self.log_page,
            on_text="Notif ON",
            off_text="Notif OFF",
            tooltip="Activar/desactivar notificaciones Windows"
        )
        self.notifications_button.SetValue(self.config_manager.get('notifications_enabled', True))
        self.notifications_button.Bind(wx.EVT_TOGGLEBUTTON, self.on_toggle_notifications)
        self.main_button_sizer.Add(self.notifications_button, 0, wx.ALL, 1)
        
        # Widget de grabación (acceso directo al registro)
        self.recording_switch = RecordingSwitchWidget(self.log_page, self.monitoring_service)
        self.main_button_sizer.Add(self.recording_switch, 0, wx.ALL, 1)
        # Botones principales (compactos)
        self.process_log_button = self._create_button(self.main_button_sizer, "📄 Process", wx.ART_FILE_OPEN)
        self.autoshard_button = self._create_button(self.main_button_sizer, "🌐 Shard", wx.ART_TIP)
        self.autoshard_button.Enable(False)
        self.monitor_button = self._create_button(self.main_button_sizer, "▶ Start", wx.ART_EXECUTABLE_FILE)
        # --- Botón 'Freeze' ---
        self.freeze_button = self._create_button(self.main_button_sizer, "❄️ Freeze", wx.ART_NEW)
        self.freeze_button.Bind(wx.EVT_BUTTON, self.on_freeze)
        # Añadir botón Profile Request al lado de Freeze
        self.profile_request_button = self._create_button(self.main_button_sizer, "👤 Profile Request", wx.ART_FIND)
        self.profile_request_button.Bind(wx.EVT_BUTTON, self.on_profile_request)
        # --- Botón 'Congelar' (se añade aquí, pero la lógica se implementa en el siguiente plan) ---
        # Botones de debug (compactos, solo en debug_button_sizer)
        self.check_db_button = self._create_button(self.debug_button_sizer, "🔍 Check DB", wx.ART_FIND)
        self.data_transfer_button = self._create_button(self.debug_button_sizer, "📤 Transfer", wx.ART_COPY)
        self.test_data_provider_button = self._create_button(self.debug_button_sizer, "🧪 Test Data", wx.ART_LIST_VIEW)
        self.simulate_notification_button = self._create_button(self.debug_button_sizer, "🔔 Test Notif", wx.ART_INFORMATION)
        self.simulate_notification_button.Bind(wx.EVT_BUTTON, self.on_simulate_notification)
        # Ya no se hace Hide() de los botones de debug, la visibilidad la gestiona el sizer de debug
        # --- Añadir sizers al layout ---
        log_page_sizer.Add(self.main_button_sizer, 0, wx.EXPAND | wx.ALL, 2)
        # El sizer de debug solo se añade si debug_mode está activo
        if self.debug_mode:
            log_page_sizer.Add(self.debug_button_sizer, 0, wx.EXPAND | wx.ALL, 2)
        # Add the log text area with fixed-width font and rich text support
        # Crear splitter para dividir la página
        from helpers.widgets import SharedLogsWidget, StalledWidget

        log_splitter = wx.SplitterWindow(self.log_page, style=wx.SP_3D | wx.SP_LIVE_UPDATE)

        # Crear log_text directamente con el splitter como padre
        self.log_text = wx.TextCtrl(
            log_splitter,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.HSCROLL | wx.TE_RICH2
        )
        fixed_font = wx.Font(
            10, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        )
        self.log_text.SetFont(fixed_font)
        self.log_text.SetForegroundColour(wx.Colour(0, 255, 0))  # Green text
        self.log_text.SetBackgroundColour(wx.Colour(0, 0, 0))  # Black background

        # Panel inferior para split horizontal
        bottom_panel = wx.Panel(log_splitter)
        bottom_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Splitter horizontal para la zona inferior
        bottom_splitter = wx.SplitterWindow(bottom_panel, style=wx.SP_3D | wx.SP_LIVE_UPDATE)
        
        # Widget Stalled (izquierda)
        self.stalled_widget = StalledWidget(bottom_splitter)
        
        # Widget de logs compartidos (derecha)
        self.shared_logs_widget = SharedLogsWidget(bottom_splitter, max_logs=500)
        
        # Configurar splitter horizontal
        bottom_splitter.SplitVertically(self.stalled_widget, self.shared_logs_widget)
        bottom_splitter.SetSashPosition(310)  # 310px para stalled widget
        bottom_splitter.SetMinimumPaneSize(150)
        
        # Añadir splitter horizontal al panel inferior
        bottom_sizer.Add(bottom_splitter, 1, wx.EXPAND)
        bottom_panel.SetSizer(bottom_sizer)

        # Configurar splitter principal con log_text arriba y panel inferior abajo
        log_splitter.SplitHorizontally(self.log_text, bottom_panel)
        
        # Calcular posición para 80% log_text, 20% shared_widget
        # Usar CallAfter para asegurar que el tamaño esté disponible
        wx.CallAfter(self._set_initial_splitter_position, log_splitter)
        
        log_splitter.SetSashGravity(0.8)  # Al redimensionar: 80% para log_text, 20% para shared_widget
        log_splitter.SetMinimumPaneSize(50)

        # Añadir splitter al layout
        log_page_sizer.Add(log_splitter, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the log page
        self.log_page.SetSizer(log_page_sizer)

        # Add notebook to the main sizer
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 2)

        # Set the sizer for the main panel
        panel.SetSizer(main_sizer)

        # Bind buttons
        self.process_log_button.Bind(wx.EVT_BUTTON, self.on_process_log)
        self.autoshard_button.Bind(wx.EVT_BUTTON, self.on_autoshard)
        self.monitor_button.Bind(wx.EVT_BUTTON, self.on_monitor)
        self.check_db_button.Bind(wx.EVT_BUTTON, self.on_check_db)
        self.data_transfer_button.Bind(wx.EVT_BUTTON, self.on_data_transfer)
        self.test_data_provider_button.Bind(wx.EVT_BUTTON, self.on_test_data_provider)

        # Add menu items
        menu_bar = wx.MenuBar()
        config_menu = wx.Menu()
        self.discord_check = config_menu.AppendCheckItem(wx.ID_ANY, "Use Discord")
        config_menu.AppendSeparator()
        edit_config_item = config_menu.Append(wx.ID_ANY, "Edit Configuration")
        menu_bar.Append(config_menu, "Config")

        # Add Help menu with About item
        help_menu = wx.Menu()
        about_item = help_menu.Append(wx.ID_ABOUT, "About")
        menu_bar.Append(help_menu, "Help")
        self.SetMenuBar(menu_bar)

        # Bind menu events
        self.Bind(wx.EVT_MENU, self.on_toggle_check, self.discord_check)
        self.Bind(wx.EVT_MENU, self.on_edit_config, edit_config_item)
        self.Bind(wx.EVT_MENU, self.on_about, about_item)

        # Status bar
        self.CreateStatusBar()
        self.SetStatusText("Ready")
    
    def _create_button(self, sizer, label, art_id=None, min_size=None):
        """Crea un botón compacto, look Windows, lo añade al sizer y lo devuelve. Ajusta tamaño al texto salvo que se indique min_size."""
        button = DarkThemeButton(self.log_page, label=label)
        button.SetFont(wx.SystemSettings.GetFont(wx.SYS_DEFAULT_GUI_FONT))
        if min_size is not None:
            button.SetMinSize(min_size)
        sizer.Add(button, 0, wx.ALL, 1)
        return button
    
    def _set_initial_splitter_position(self, splitter):
        """Establece la posición inicial del splitter para 80% log_text, 20% shared_widget"""
        total_height = splitter.GetSize().height
        if total_height > 100:  # Solo si el splitter ya tiene tamaño
            position = int(total_height * 0.8)  # 80% para log_text
            splitter.SetSashPosition(position)
    
    def __getattr__(self, name):
        """
        Dynamically retrieve attributes from the config_manager when they're not found
        in the instance. This allows direct access to any configuration value without
        explicitly defining it in the class.
        
        Args:
            name (str): The attribute name to look for in the config_manager
            
        Returns:
            The value from the config_manager
            
        Raises:
            AttributeError: If the attribute doesn't exist in the config_manager either
        """
        try:
            return self.config_manager.get(name)
        except Exception as e:
            # If that fails or if the property doesn't exist, raise AttributeError
            raise AttributeError(f"Neither {self.__class__.__name__} nor ConfigManager has an attribute named '{name}'") from e
    
    def check_for_updates(self):
        """Check for updates by querying the GitHub API."""
        current_version = get_version()
        updater.check_for_updates(self, current_version)
    
    def update_dynamic_labels(self):
        """Update the username, shard, version, and mode labels dynamically."""
        try:
            # Use instance properties if they're set, fall back to event_handler if needed
            username = self.username if self.username != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "username", "Unknown")
            shard = self.shard if self.shard != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_shard", "Unknown")
            version = self.version if self.version != "Unknown" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_version", "Unknown")
            mode = self.mode if self.mode != "None" and self.monitoring_service.event_handler else getattr(self.monitoring_service.event_handler, "current_mode", "None")
            private = self.private if self.private is not None else getattr(self.monitoring_service.event_handler, "block_private_lobby_recording", False)
            self.dynamic_labels.update_labels(username, shard, version, mode,private)
        except Exception as e:
            message_bus.publish(
                content=f"Error updating labels: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_shard_version_update(self, shard, version, username, mode=None, private=None):
        """
        Handle updates to the shard, version, username, and mode, and show 'Privado' label if private is True.
        """
        try:
            self.shard = shard
            self.version = version
            self.username = username
            self.private = private
            if mode is not None:
                self.mode = mode
            self.update_dynamic_labels()  # Call update_dynamic_labels to refresh UI
            # Mostrar/ocultar la etiqueta 'Privado' según private
        except Exception as e:
            message_bus.publish(
                content=f"Error updating shard/version/username/mode: {e}",
                level=MessageLevel.ERROR
            )

    def on_mode_change(self, new_mode, old_mode, live = False):
        """
        Handle mode change events.

        Args:
            new_mode (str): The new mode entered.
            old_mode (str): The previous mode exited.
        """
        if new_mode == "SC_Default":
            self.autoshard_button.Enable(True)
        else:
            self.autoshard_button.Enable(False)
            
        # Update mode label when mode changes
        self.update_dynamic_labels()
    
    def on_username_change(self, username, old_username):
        """
        Handle username change events.

        Args:
            username (str): The new username.
            old_username (str): The previous username.
        """
        # Update the stored username
        self.username = username
        self.update_dynamic_labels()
        
        # Usar el método _refresh_all_tabs con el nombre original
        #safe_call_after(wx.CallLater, 500, self.data_manager._refresh_all_tabs)
    
    def on_about(self, event):
        """Show the About dialog."""
        dialog = AboutDialog(self, update_callback=self.check_for_updates)
        dialog.ShowModal()
    
    def initialize_config(self):
        """Initialize configuration: load settings, ensure config exists with latest template, and validate."""
        try:
            # 1. Load configuration values from ConfigManager
            self.default_log_file_path = self.log_file_path
            
            self.discord_check.Check(self.use_discord or True)
            
            # 3. Validate critical settings and prompt for missing ones
            missing_settings = []
            if not self.default_log_file_path:
                missing_settings.append("Log file path")
            elif not os.path.exists(self.default_log_file_path):
                missing_settings.append("Log file path does not exist")
                
            if self.datasource == 'googlesheets' and not self.google_sheets_webhook:
                missing_settings.append("Google Sheets webhook URL")
                
            if self.datasource == 'supabase' and not self.supabase_key:
                missing_settings.append("Supabase credentials")
                
            if not self.discord_webhook_url:
                self.discord_check.Check(False)  # Uncheck Discord usage
                
            if missing_settings:
                warning = ", ".join(missing_settings)
                message_bus.publish(
                    content=f"Missing or invalid settings: {warning}",
                    level=MessageLevel.WARNING
                )
                
                # Show message box without timer - safer during startup
                wx.CallAfter(lambda: wx.MessageBox(
                    f"Please check your configuration. The following settings need attention:\n\n{warning}",
                    "Configuration Warning",
                    wx.OK | wx.ICON_WARNING
                ))
        except Exception as e:
            message_bus.publish(
                content=f"Error in initialize_config: {e}",
                level=MessageLevel.ERROR
            )
    
    def on_process_log(self, event):
        """Open the process log dialog."""
        dialog = ProcessDialog(self)
        dialog.ShowModal()
    
    def run_process_log(self, log_file):
        """Run log processing."""
        self.monitoring_service.run_process_log(log_file)
    
    def on_monitor(self, event):
        """Handle start/stop monitoring button click event."""
        if not self or not self.IsShown():
            return  # Prevent actions if the frame is destroyed
            
        if self.monitoring_service.is_monitoring():
            self.monitoring_service.stop_monitoring()
        else:
            self.monitoring_service.start_monitoring()
        
    
    def on_autoshard(self, event):
        """Handle Auto Shard button click."""
        try:
            self.send_keystrokes_to_sc()  # Call the method to send keystrokes
            message_bus.publish(
                content="Auto Shard keystrokes sent.",
                level=MessageLevel.INFO
            )
        except Exception as e:
            message_bus.publish(
                content=f"Error sending Auto Shard keystrokes: {e}",
                level=MessageLevel.ERROR
            )
    
    def send_keystrokes_to_sc(self):
        """Send predefined keystrokes to the Star Citizen window."""
        from helpers.ui.gui_module import WindowsHelper
        
        # Derive the ScreenShots folder from the current log file path
        screenshots_folder = os.path.join(os.path.dirname(self.config_manager.get('log_file_path')), "ScreenShots")
        ck = self.console_key if self.console_key != '' else WindowsHelper.CONSOLE_KEY
        WindowsHelper.send_keystrokes_to_window(
            "Star Citizen",
            [
                ck , "r_DisplaySessionInfo 1", WindowsHelper.RETURN_KEY,
                ck, WindowsHelper.PRINT_SCREEN_KEY,
                ck, "r_DisplaySessionInfo 0", WindowsHelper.RETURN_KEY,
                ck
            ],
            screenshots_folder=screenshots_folder,
            class_name="CryENGINE",
            process_name="StarCitizen.exe"
        )
    
    def on_toggle_check(self, event):
        """Handle Discord checkbox menu item toggle."""
        # Get the menu item directly from the event source
        menu_item = event.GetEventObject().FindItemById(event.GetId())
        
        if menu_item and menu_item == self.discord_check:
            # Update configuration for Discord
            new_state = menu_item.IsChecked()
            self.config_manager.set('use_discord', new_state)
            
            # Save configuration
            self.config_manager.save_config()
            
            # Update UI if monitoring is active
            if self.monitoring_service.is_monitoring():
                self.monitoring_service.stop_monitoring()
                self.monitoring_service.start_monitoring()
                
            # Log state change
            message_bus.publish(
                content=f"Discord integration {'enabled' if new_state else 'disabled'}",            level=MessageLevel.INFO
            )

    def on_edit_config(self, event):
        """Open the configuration dialog."""
        config_dialog = ConfigDialog(self, self.config_manager)
        
        # Center the dialog on the parent window
        config_dialog.Centre(wx.BOTH)
        
        # Show the dialog modally
        result = config_dialog.ShowModal()
        
        # Handle the result if needed
        if result == wx.ID_OK:
            # Configuration was saved successfully
            pass
        else:
            # Configuration was cancelled
            pass
            
        # Clean up
        config_dialog.Destroy()
    
    def on_test_data_provider(self, event):
        """Handle the Test Data Provider button click."""
        self.data_manager.test_data_provider()
    
    def on_data_transfer(self, event):
        """Handle the Data Transfer button click."""
        message_bus.publish(
            content="Opening Data Transfer dialog...",
            level=MessageLevel.INFO
        )
        
        # Check if both Google Sheets and Supabase are configured
        google_sheets_webhook = self.config_manager.get('google_sheets_webhook', '')
        supabase_key = self.config_manager.get('supabase_key', '')
        
        # Validate configurations
        missing_config = []
        
        if not google_sheets_webhook:
            missing_config.append("Google Sheets webhook URL")
            
        if not supabase_key:
            missing_config.append("Supabase credentials")
        
        if missing_config:
            error_message = f"Missing configuration: {', '.join(missing_config)}.\nPlease update your configuration before transferring data."
            wx.MessageBox(error_message, "Configuration Error", wx.OK | wx.ICON_ERROR)
            message_bus.publish(
                content=error_message,
                level=MessageLevel.ERROR
            )
            return
        
        # Import here to avoid circular imports
        from helpers.ui.gui_module import DataTransferDialog
        
        # Create and show the dialog
        dialog = DataTransferDialog(self)
        dialog.ShowModal()

    def on_check_db(self, event):
        """Handle Check DB button click."""
        try:
            message_bus.publish(
                content="Checking Supabase database setup...",
                level=MessageLevel.INFO
            )
            
            # Check if we're using Supabase
            if self.config_manager.get('datasource') != 'supabase':
                message_bus.publish(
                    content="Cannot check DB: Current data source is not Supabase",
                    level=MessageLevel.WARNING
                )
                wx.MessageBox(
                    "This function is only available when Supabase is set as the data source.",
                    "Data Source Error",
                    wx.OK | wx.ICON_WARNING
                )
                return
                
            # Import here to avoid circular imports
            from helpers.data.supabase_onboarding import SupabaseOnboarding
            
            # Create onboarding instance with the parent window
            onboarding = SupabaseOnboarding(self)
            
            # Perform comprehensive check of database components
            check_results = onboarding.check_database_components()
            
            # Format detailed results message
            status_list = []
            status_list.append("Database Component Status:")
            status_list.append(f"• run_sql function: {'✓ Present' if check_results['run_sql_function'] else '✗ Missing'}")
            status_list.append(f"• get_metadata function: {'✓ Present' if check_results['get_metadata_function'] else '✗ Missing'}")
            
            # Only show table status if we have metadata access
            if check_results['get_metadata_function']:
                status_list.append(f"• config table: {'✓ Present' if check_results['config_table'] else '✗ Missing'}")
            else:
                status_list.append("(Cannot check tables without get_metadata function)")
            
            status_message = "\n".join(status_list)
            message_bus.publish(
                content=status_message,
                level=MessageLevel.INFO
            )
            
            # If any component is missing, offer to repair
            if check_results['missing_components']:
                missing_components = ", ".join(check_results['missing_components'])
                repair_message = f"The following components are missing: {missing_components}\n\nWould you like to run the repair process?"
                
                if wx.MessageBox(
                    repair_message,
                    "Missing Components",
                    wx.YES_NO | wx.ICON_QUESTION
                ) == wx.YES:
                    # Run the onboarding process to repair
                    success = onboarding.start_onboarding()
                    
                    if success:
                        wx.MessageBox(
                            "Database check and repair completed successfully!",
                            "DB Check Complete",
                            wx.OK | wx.ICON_INFORMATION
                        )
                    else:
                        wx.MessageBox(
                            "Database check and repair failed or was cancelled.",
                            "DB Check Failed",
                            wx.OK | wx.ICON_ERROR
                        )
                else:
                    wx.MessageBox(
                        "No repairs were made. Some components are still missing.",
                        "Repair Skipped",
                        wx.OK | wx.ICON_INFORMATION
                    )
            else:
                message_bus.publish(
                    content="Database check completed - all required components are present",
                    level=MessageLevel.INFO
                )
                wx.MessageBox(
                    "Database check complete. All required components are present and working correctly.",
                    "DB Check Complete",
                    wx.OK | wx.ICON_INFORMATION
                )
                
        except Exception as e:
            message_bus.publish(
                content=f"Error during database check: {e}",
                level=MessageLevel.ERROR
            )
            wx.MessageBox(
                f"An error occurred during the database check:\n\n{str(e)}",
                "DB Check Error",
                wx.OK | wx.ICON_ERROR
            )

    def handle_datasource_change(self, old_datasource, new_datasource):
        """
        Explicitly handle changes to the datasource configuration.
        
        Args:
            old_datasource (str): Previous datasource value
            new_datasource (str): New datasource value
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            message_bus.publish(
                content=f"Handling datasource change from '{old_datasource}' to '{new_datasource}'...",
                level=MessageLevel.INFO,
                metadata={"source": "config_manager"}
            )
            
            # Validate the new datasource
            if new_datasource not in ['googlesheets', 'supabase']:
                message_bus.publish(
                    content=f"Invalid datasource '{new_datasource}', reverting to '{old_datasource}'",
                    level=MessageLevel.WARNING,
                    metadata={"source": "config_manager"}
                )
                self.config_manager.set('datasource', old_datasource)
                return False
            
            # If changing to 'supabase', check if we need onboarding
            if new_datasource == 'supabase' and old_datasource != 'supabase':
                from helpers.data.supabase_onboarding import SupabaseOnboarding, check_needs_onboarding
                
                if check_needs_onboarding(self.config_manager):
                    # Get the parent window 
                    onboarding = SupabaseOnboarding(self.config_manager)
                    
                    if onboarding.check_onboarding_needed():
                        message_bus.publish(
                            content="Starting Supabase onboarding process",
                            level=MessageLevel.INFO,
                            metadata={"source": "config_manager"}
                        )
                        
                        # Start the onboarding process
                        success = onboarding.start_onboarding()
                        
                        if not success:
                            # Onboarding failed or was cancelled, revert to previous datasource
                            message_bus.publish(
                                content="Supabase onboarding was cancelled or failed",
                                level=MessageLevel.WARNING,
                                metadata={"source": "config_manager"}
                            )
                            self.config_manager.set('datasource', old_datasource)
                            return False
                        
                        message_bus.publish(
                            content="Supabase onboarding completed successfully",
                            level=MessageLevel.INFO,
                            metadata={"source": "config_manager"}
                        )

            return True
        except Exception as e:
            message_bus.publish(
                content=f"Error handling datasource change: {e}",
                level=MessageLevel.ERROR,
                metadata={"source": "config_manager"}
            )
            return False

    def on_config_saved(self, old_config, new_config, config_manager=None):
        """
        Handle the config.saved event to process configuration changes.
        
        Args:
            old_config (dict): The configuration before changes
            new_config (dict): The configuration after changes
            config_manager (ConfigManager, optional): The config manager instance
        """
        try:
            message_bus.publish(
                content="Configuration saved event received, processing changes...",
                level=MessageLevel.INFO
            )
            
            # Reload configuration to ensure all settings are applied
            self.initialize_config()
            
            # Get important values from old and new configurations
            old_datasource = old_config.get('datasource', 'googlesheets')
            new_datasource = new_config.get('datasource', 'googlesheets')
            
            old_supabase_key = old_config.get('supabase_key', '')
            new_supabase_key = new_config.get('supabase_key', '')
            
            old_tabs = old_config.get('tabs', {})
            new_tabs = new_config.get('tabs', {})
            
            # Detect specific changes
            tabs_changed = (old_tabs != new_tabs)
            datasource_changed_to_supabase = (new_datasource == 'supabase' and old_datasource != 'supabase')
            supabase_key_changed = (new_datasource == 'supabase' and 
                                  old_supabase_key != new_supabase_key and 
                                  new_supabase_key)
            
            # Handle tabs configuration change when using Supabase
            if tabs_changed and new_datasource == 'supabase':
                message_bus.publish(
                    content="Dynamic tabs configuration has changed, updating views...",
                    level=MessageLevel.INFO
                )
                
                # Import at function call time to avoid circular imports
                from helpers.core.data_provider import get_data_provider, SupabaseDataProvider
                
                # Get the data provider
                data_provider = get_data_provider(self.config_manager)
                
                # Dynamic tabs are now handled via execute_generic_query - no view creation needed
            
            # NOTE: We don't need to handle datasource_changed_to_supabase here
            # because our ConfigDialog.save_config already emits the "datasource_changed" event
            
            # Handle Supabase key changes
            if supabase_key_changed:
                message_bus.publish(
                    content=f"Supabase key changed from '{old_supabase_key[:5]}...' to '{new_supabase_key[:5]}...', checking if onboarding is needed",
                    level=MessageLevel.INFO
                )
                # Force reconnect with the new key using force parameter
                supabase_manager.connect(self.config_manager, force=True)
                
                # Import here to avoid circular imports
                from helpers.data.supabase_onboarding import SupabaseOnboarding, check_needs_onboarding
                
                # Check if onboarding is needed
                if check_needs_onboarding(self.config_manager):
                    # Create and run onboarding
                    onboarding = SupabaseOnboarding(self)
                    if onboarding.check_onboarding_needed():
                        message_bus.publish(
                            content="Starting Supabase onboarding after key change",
                            level=MessageLevel.INFO
                        )
                        onboarding.start_onboarding()
            
            # If Supabase is the current datasource, verify connection
            if new_datasource == 'supabase':
                if not supabase_manager.is_connected():
                    connection_result = supabase_manager.connect()
                    if connection_result:
                        message_bus.publish(
                            content="Connected to Supabase successfully after config change.",
                            level=MessageLevel.INFO
                        )
                    else:
                        wx.MessageBox(
                            "Failed to connect to Supabase. Check your credentials in config.",
                            "Connection Failed",
                            wx.OK | wx.ICON_ERROR
                        )
                        message_bus.publish(
                            content="Failed to connect to Supabase after configuration change.",
                            level=MessageLevel.ERROR
                        )
            
            # Restart monitoring if it was active
            if self.monitoring_service.is_monitoring():
                self.monitoring_service.stop_monitoring()
                self.monitoring_service.start_monitoring()
            
            # Update tabs based on the data source
            # self.data_manager.update_data_source_tabs()
            
        except Exception as e:
            message_bus.publish(
                content=f"Error processing config_saved event: {e}",
                level=MessageLevel.ERROR
            )

    def on_close(self, event):
        """Handle window close event."""
        # Use the window manager to clean up and save state
        self.window_manager.cleanup()
        
        # Stop monitoring if active
        if self.monitoring_service.is_monitoring():
            self.monitoring_service.stop_monitoring()
        
        # Cleanup recording switch timer
        if hasattr(self, 'recording_switch'):
            self.recording_switch.cleanup_timer()
        
        # Cleanup hotkey system
        if hasattr(self, 'hotkey_manager'):
            self.hotkey_manager.shutdown()
        
        # Restore original stdout
        sys.stdout = sys.__stdout__

        # Remove the custom log handler
        log_analyzer.main.gui_log_handler = None

        # Destroy the taskbar icon
        if hasattr(self, "taskbar_icon") and self.taskbar_icon:
            self.taskbar_icon.RemoveIcon()
            self.taskbar_icon.Destroy()
            self.taskbar_icon = None

        # Destroy the window
        self.Destroy()
    
    # The append_log_message method has been removed as it is a legacy
    # component. All UI logging is now handled exclusively by the
    # _append_log_message_from_bus method, which is subscribed to the MessageBus.
    
    def _append_log_message_from_bus(self, message):
        """
        Process a message from the message bus and display it in the log text control.
        
        Args:
            message: The message object from the message bus
        """
        if self.log_text:
            # Default colors
            foreground_color = wx.Colour(255, 255, 255)  # White text
            background_color = wx.Colour(0, 0, 0)  # Black background

            # Load colors and patterns from the configuration
            colors = getattr(self, "colors", {})
            pattern_name = message.pattern_name
            
            if pattern_name:
                for color_spec, pattern_names in colors.items():
                    if pattern_name in pattern_names:
                        # Parse the color specification
                        color_parts = color_spec.split(",")
                        if len(color_parts) > 0:
                            try:
                                rgb = webcolors.name_to_rgb(color_parts[0].strip())
                                foreground_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                            except ValueError:
                                try:
                                    rgb = webcolors.hex_to_rgb(color_parts[0].strip())
                                    foreground_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                                except ValueError:
                                    pass  # Ignore invalid foreground color
                        if len(color_parts) > 1:
                            try:
                                rgb = webcolors.name_to_rgb(color_parts[1].strip())
                                background_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                            except ValueError:
                                try:
                                    rgb = webcolors.hex_to_rgb(color_parts[1].strip())
                                    background_color = wx.Colour(rgb.red, rgb.green, rgb.blue)
                                except ValueError:
                                    pass  # Ignore invalid background color
                        break

            # Apply the colors and append the message
            self.log_text.SetDefaultStyle(wx.TextAttr(foreground_color, background_color))
            self.log_text.AppendText(message.get_formatted_message() + "\n")
    
    def on_key_down(self, event):
        """Handle keyboard events for debug mode activation"""
        # Get the key code and modifier states
        key_code = event.GetKeyCode()
        ctrl_down = event.ControlDown()
        shift_down = event.ShiftDown()
        alt_down = event.AltDown()
        
        # Secret key combination: CTRL+SHIFT+ALT+D
        if ctrl_down and shift_down and alt_down and key_code == ord('D'):
            # Toggle debug mode (solo UI)
            self.debug_mode = not self.debug_mode
            # Sincroniza el estado global de debug
            message_bus.set_debug_mode(self.debug_mode)
            self.update_debug_ui_visibility()
            
            # Show a subtle indication in the status bar
            if self.debug_mode:
                self.SetStatusText("Developer mode activated")
                message_bus.publish(
                    content="Developer tools activated",
                    level=MessageLevel.INFO
                )
            else:
                self.SetStatusText("Ready")
                message_bus.publish(
                    content="Developer tools deactivated",
                    level=MessageLevel.INFO
                )
        
        # Process the event normally
        event.Skip()
        
    def update_debug_ui_visibility(self):
        """Update UI elements based on debug mode state"""
        # --- Gestión dinámica del sizer de debug ---
        log_page_sizer = self.log_page.GetSizer()
        # Comprobar si el sizer de debug está en el layout de forma compatible con wxPython
        debug_sizer_in_layout = any(
            item.IsSizer() and item.GetSizer() is self.debug_button_sizer
            for item in log_page_sizer.GetChildren()
        )
        debug_active = message_bus.is_debug_mode()
        if debug_active and not debug_sizer_in_layout:
            log_page_sizer.Insert(1, self.debug_button_sizer, 0, wx.EXPAND | wx.ALL, 2)
        elif not debug_active and debug_sizer_in_layout:
            log_page_sizer.Detach(self.debug_button_sizer)
        # Visibilidad y lógica especial de botones de debug
        self.test_data_provider_button.Show(debug_active)
        self.data_transfer_button.Show(debug_active)
        self.simulate_notification_button.Show(debug_active)
        # Check DB button: solo visible en debug y habilitado solo si datasource es 'supabase'
        self.check_db_button.Show(debug_active)
        is_supabase = self.config_manager.get('datasource') == 'supabase'
        self.check_db_button.Enable(is_supabase)
        if is_supabase:
            self.check_db_button.SetLabel(" Check DB")
        else:
            self.check_db_button.SetLabel(" Check DB (Supabase only)")
        # Elimina llamada redundante a set_debug_mode en data_manager

        # Forzar refresco de layout
        self.log_page.Layout()
        self.Refresh()
    
    def async_init_tabs(self):
        """Initialize tabs asynchronously after the main window is loaded."""
        self.data_manager.create_tabs()
    
    def on_notebook_page_changed(self, event):
        """
        Handle notebook page change event to refresh the grid of the selected tab.
        
        Args:
            event (wx.BookCtrlEvent): The notebook page changed event.
        """
        try:
            # Skip the event first to ensure normal processing
            event.Skip()
            
            # Get the currently selected page index
            current_page = event.GetSelection()
            
            # Skip refresh for the main log page (index 0)
            if current_page == 0:
                return
            
            # Validate page index before accessing
            if current_page < 0 or current_page >= self.notebook.GetPageCount():
                return
            
            # Get the page title
            page_title = self.notebook.GetPageText(current_page)
            
            message_bus.publish(
                content=f"Tab changed to: {page_title}, refreshing grid data...",
                level=MessageLevel.DEBUG
            )
            
            # Si es el tab Data, refrescar el subtab activo
            if page_title == "Data":
                data_panel = self.notebook.GetPage(current_page)
                nested_notebook = None
                for child in data_panel.GetChildren():
                    if isinstance(child, wx.Notebook):
                        nested_notebook = child
                        break
                if nested_notebook:
                    subtab_index = nested_notebook.GetSelection()
                    if subtab_index >= 0:
                        subtab_title = nested_notebook.GetPageText(subtab_index)
                        full_title = f"Data_{subtab_title}"
                        if hasattr(self, 'tab_creator') and hasattr(self.tab_creator, 'tab_references'):
                            tab_refs = self.tab_creator.tab_references
                            if full_title in tab_refs:
                                grid, refresh_button = tab_refs[full_title]
                                wx.CallLater(100, self.data_manager.execute_refresh_event, refresh_button)
                return
            
            # Handle regular tabs (Stats, Usuarios conectados)
            if hasattr(self, 'tab_creator') and hasattr(self.tab_creator, 'tab_references'):
                tab_refs = self.tab_creator.tab_references
                if page_title in tab_refs:
                    grid, refresh_button = tab_refs[page_title]
                    # Use a slight delay to ensure UI is updated first
                    wx.CallLater(100, self.data_manager.execute_refresh_event, refresh_button)
                    
            # Note: Data tab refresh is handled by the nested notebook binding
                    
        except Exception as e:
            message_bus.publish(
                content=f"Error refreshing tab after page change: {e}",
                level=MessageLevel.ERROR
            )

    def on_toggle_notifications(self, event):
        enabled = self.notifications_button.GetValue()
        self.config_manager.set('notifications_enabled', enabled)
        self.realtime_bridge.notification_manager.reload_config()

    def on_simulate_notification(self, event):
        # Muestra una notificación de prueba.
        message_bus.emit('show_windows_notification', 'Esta es una notificación de prueba.')

    def on_profile_request(self, event):
        dlg = wx.TextEntryDialog(self, "Introduce el nombre del jugador:", "Profile Request")
        if dlg.ShowModal() == wx.ID_OK:
            player_name = dlg.GetValue().strip()
            if player_name:
                event_data = {
                    'player_name': player_name,
                    'action': 'get',
                    'timestamp': datetime.now().isoformat()
                }
                message_bus.emit(
                    "request_profile",
                    event_data,
                    "manual_request"
                )
        dlg.Destroy()

def main():
    from helpers.core.message_bus import MessageLevel
    """Main entry point for the application."""
    # Create the wx.App instance first, before any wx operations
    app = wx.App()
    
    # Check if running as script or executable
    is_script = getattr(sys, 'frozen', False) == False
    
    if os.path.basename(sys.argv[0]) in (UPDATER_EXECUTABLE,LEGACY_UPDATER):
        updater.update_application()    
    else:
        updater.cleanup_updater_script()
    
    # Initialize debug mode based on script detection and command line arguments
    debug_mode = is_script or '--debug' in sys.argv or '-d' in sys.argv
    
    if debug_mode:
        # If debug mode enabled, log startup information
        message_bus.publish(content="Debug mode enabled", level=MessageLevel.DEBUG)
        # Configure message bus with debug as default minimum level
        message_bus.publish(
            content="Application started with DEBUG level enabled",
            level=MessageLevel.DEBUG
        )
    
    # Mutex-based single-instance check
    mutex = win32event.CreateMutex(None, False, MUTEX_NAME)
    if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
        sys.stdout = sys.__stdout__
        print("\nERROR: Another instance of SC Log Analyzer is already running.")
        print("Please close the existing instance before starting a new one.\n")
        wx.MessageBox(
            "Another instance of SC Log Analyzer is already running.",
            "Instance Check",
            wx.OK | wx.ICON_WARNING
        )
        return
    
    # Create frame with debug_mode parameter
    frame = LogAnalyzerFrame(debug_mode=debug_mode)
    
    frame.Show()
    frame.async_init_tabs()  # Initialize tabs asynchronously
    app.MainLoop()

if __name__ == "__main__":
    main()