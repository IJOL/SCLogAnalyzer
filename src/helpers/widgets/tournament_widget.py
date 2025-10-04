import wx
import threading
from typing import Dict, List, Optional, Any
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.tournament.tournament_manager import TournamentManager
from helpers.tournament.corpse_detector import CorpseDetector
from helpers.ui.ui_components import DarkThemeButton, MiniDarkThemeButton
from helpers.widgets.dark_listctrl import DarkListCtrl
from helpers.ui.tournament_creation_dialog import TournamentCreationDialog

class TournamentWidget(wx.Panel):
    """Widget de seguimiento de torneos activos"""

    def __init__(self, parent):
        super().__init__(parent)
        self._tournament_manager = TournamentManager()
        self._corpse_detector = CorpseDetector()
        self._config_manager = get_config_manager(in_gui=True)
        self._lock = threading.RLock()

        self._current_tournament: Optional[Dict[str, Any]] = None
        self._connected_users: List[str] = []
        self._current_username: str = ""

        self._create_ui()
        self._initialize_event_handlers()
        self._load_initial_data()

    def _create_ui(self):
        """Create tournament management interface"""
        # Apply dark theme background
        self.SetBackgroundColour(wx.Colour(80, 80, 80))

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Top: Large active tournament info panel (fixed height)
        active_tournament_section = self._create_active_tournament_section()
        main_sizer.Add(active_tournament_section, 0, wx.EXPAND | wx.ALL, 2)

        # Main splitter: vertical split between middle and bottom
        main_splitter = wx.SplitterWindow(self, style=wx.SP_3D | wx.SP_LIVE_UPDATE)
        main_splitter.SetBackgroundColour(wx.Colour(80, 80, 80))
        main_splitter.SetMinimumPaneSize(100)

        # Top pane: Horizontal splitter for tournament list and participants
        middle_splitter = wx.SplitterWindow(main_splitter, style=wx.SP_3D | wx.SP_LIVE_UPDATE)
        middle_splitter.SetBackgroundColour(wx.Colour(80, 80, 80))
        middle_splitter.SetMinimumPaneSize(200)

        # Create panels for the splitters directly from methods
        tournament_panel = self._create_tournament_list_section(middle_splitter)

        # Participants section - directly use the panel returned by the method
        participants_panel = self._create_participants_section(middle_splitter)

        # Split horizontally in middle pane
        middle_splitter.SplitVertically(tournament_panel, participants_panel)
        middle_splitter.SetSashPosition(400)  # Initial position

        # Bottom pane: Data management
        data_panel = wx.Panel(main_splitter)
        data_panel.SetBackgroundColour(wx.Colour(80, 80, 80))
        data_sizer = wx.BoxSizer(wx.VERTICAL)
        data_management_section = self._create_data_management_panel(data_panel)
        data_sizer.Add(data_management_section, 1, wx.EXPAND)
        data_panel.SetSizer(data_sizer)

        # Split vertically in main splitter
        main_splitter.SplitHorizontally(middle_splitter, data_panel)
        main_splitter.SetSashPosition(300)  # Initial position

        main_sizer.Add(main_splitter, 1, wx.EXPAND | wx.ALL, 2)

        self.SetSizer(main_sizer)

    def _create_tournament_list_section(self, parent=None) -> wx.Panel:
        """Create tournament list section"""
        if parent is None:
            parent = self

        # Create main panel
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(80, 80, 80))

        # Create sizer for the panel
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # StaticBox for tournaments
        box = wx.StaticBox(panel, label="Torneos")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        # Tournament list
        self.tournaments_list = DarkListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.tournaments_list.AppendColumn("Nombre", width=150)
        self.tournaments_list.AppendColumn("Estado", width=80)
        self.tournaments_list.AppendColumn("Participantes", width=80)
        self.tournaments_list.AppendColumn("Creado", width=100)
        self.tournaments_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_tournament_selected)
        sizer.Add(self.tournaments_list, 1, wx.EXPAND | wx.ALL, 2)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Debug panel with admin buttons (only visible in debug mode)
        self.debug_panel = wx.Panel(panel)
        debug_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create tournament button
        self.create_btn = MiniDarkThemeButton(self.debug_panel, label="➕")
        self.create_btn.SetToolTip("Crear nuevo torneo")
        self.create_btn.Bind(wx.EVT_BUTTON, self._on_create_tournament)
        debug_sizer.Add(self.create_btn, 0, wx.ALL, 2)

        # Edit tournament button
        self.edit_btn = MiniDarkThemeButton(self.debug_panel, label="✏️")
        self.edit_btn.SetToolTip("Editar torneo seleccionado")
        self.edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_tournament)
        self.edit_btn.Enable(False)
        debug_sizer.Add(self.edit_btn, 0, wx.ALL, 2)

        # Delete tournament button
        self.delete_btn = MiniDarkThemeButton(self.debug_panel, label="🗑️")
        self.delete_btn.SetToolTip("Eliminar torneo seleccionado")
        self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_tournament)
        self.delete_btn.Enable(False)
        debug_sizer.Add(self.delete_btn, 0, wx.ALL, 2)

        # Activate tournament button
        self.activate_btn = MiniDarkThemeButton(self.debug_panel, label="▶️")
        self.activate_btn.SetToolTip("Activar torneo para etiquetado automático")
        self.activate_btn.Bind(wx.EVT_BUTTON, self._on_activate_tournament)
        self.activate_btn.Enable(False)
        debug_sizer.Add(self.activate_btn, 0, wx.ALL, 2)

        # Pause tournament button
        self.pause_btn = MiniDarkThemeButton(self.debug_panel, label="⏸️")
        self.pause_btn.SetToolTip("Pausar torneo activo")
        self.pause_btn.Bind(wx.EVT_BUTTON, self._on_pause_tournament)
        self.pause_btn.Enable(False)
        debug_sizer.Add(self.pause_btn, 0, wx.ALL, 2)

        # Resume tournament button
        self.resume_btn = MiniDarkThemeButton(self.debug_panel, label="⏯️")
        self.resume_btn.SetToolTip("Reanudar torneo pausado")
        self.resume_btn.Bind(wx.EVT_BUTTON, self._on_resume_tournament)
        self.resume_btn.Enable(False)
        debug_sizer.Add(self.resume_btn, 0, wx.ALL, 2)

        # Complete tournament button
        self.complete_btn = MiniDarkThemeButton(self.debug_panel, label="⏹️")
        self.complete_btn.SetToolTip("Finalizar torneo activo")
        self.complete_btn.Bind(wx.EVT_BUTTON, self._on_complete_tournament)
        self.complete_btn.Enable(False)
        self.complete_btn.SetBackgroundColour(wx.Colour(180, 0, 0))  # Red background
        debug_sizer.Add(self.complete_btn, 0, wx.ALL, 2)

        self.debug_panel.SetSizer(debug_sizer)
        self.debug_panel.Show(message_bus.is_debug_mode())
        button_sizer.Add(self.debug_panel, 0, wx.ALL, 2)

        sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 2)

        # Add the StaticBoxSizer to the main panel sizer
        main_sizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 2)
        panel.SetSizer(main_sizer)

        return panel

    def _create_active_tournament_section(self) -> wx.StaticBoxSizer:
        """Create large active tournament info panel"""
        box = wx.StaticBox(self, label="Torneo Activo y Equipo")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        main_sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Left: Tournament basic info with nested StaticBox
        left_box = wx.StaticBox(self, label="Información General")
        left_box.SetBackgroundColour(wx.Colour(70, 70, 70))
        left_box.SetForegroundColour(wx.Colour(220, 220, 220))
        left_sizer = wx.StaticBoxSizer(left_box, wx.VERTICAL)

        self.active_tournament_name = wx.StaticText(self, label="Ningún torneo activo")
        self.active_tournament_name.SetForegroundColour(wx.Colour(255, 255, 255))
        self.active_tournament_name.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        left_sizer.Add(self.active_tournament_name, 0, wx.ALL | wx.EXPAND, 8)

        self.active_tournament_participants = wx.StaticText(self, label="Participantes: -")
        self.active_tournament_participants.SetForegroundColour(wx.Colour(200, 200, 200))
        self.active_tournament_participants.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        left_sizer.Add(self.active_tournament_participants, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.active_tournament_description = wx.StaticText(self, label="")
        self.active_tournament_description.SetForegroundColour(wx.Colour(180, 180, 180))
        self.active_tournament_description.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_ITALIC, wx.FONTWEIGHT_NORMAL))
        left_sizer.Add(self.active_tournament_description, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        main_sizer.Add(left_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # Center: Team composition with nested StaticBox
        center_box = wx.StaticBox(self, label="Equipos")
        center_box.SetBackgroundColour(wx.Colour(70, 70, 70))
        center_box.SetForegroundColour(wx.Colour(220, 220, 220))
        center_sizer = wx.StaticBoxSizer(center_box, wx.VERTICAL)

        self.active_tournament_teams = wx.StaticText(self, label="Sin equipos")
        self.active_tournament_teams.SetForegroundColour(wx.Colour(200, 200, 200))
        self.active_tournament_teams.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        center_sizer.Add(self.active_tournament_teams, 0, wx.ALL | wx.EXPAND, 8)

        main_sizer.Add(center_sizer, 1, wx.EXPAND | wx.ALL, 5)

        # Right: User's team with nested StaticBox
        right_box = wx.StaticBox(self, label="Mi Equipo")
        right_box.SetBackgroundColour(wx.Colour(70, 70, 70))
        right_box.SetForegroundColour(wx.Colour(220, 220, 220))
        right_sizer = wx.StaticBoxSizer(right_box, wx.VERTICAL)

        self.my_team_label = wx.StaticText(self, label="Equipo: -")
        self.my_team_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.my_team_label.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        right_sizer.Add(self.my_team_label, 0, wx.ALL | wx.EXPAND, 8)

        self.teammates_label = wx.StaticText(self, label="Compañeros:\n-")
        self.teammates_label.SetForegroundColour(wx.Colour(200, 200, 200))
        self.teammates_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        right_sizer.Add(self.teammates_label, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        main_sizer.Add(right_sizer, 1, wx.EXPAND | wx.ALL, 5)

        return main_sizer

    def _create_participants_section(self, parent=None) -> wx.Panel:
        """Create participants and statistics section"""
        if parent is None:
            parent = self

        # Create main panel
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(80, 80, 80))

        # Create sizer for the panel
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # StaticBox for participants
        box = wx.StaticBox(panel, label="Participantes y Estadísticas")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Participants list
        participants_sizer = wx.BoxSizer(wx.VERTICAL)

        participants_label = wx.StaticText(panel, label="Participantes:")
        participants_label.SetForegroundColour(wx.Colour(255, 255, 255))
        participants_sizer.Add(participants_label, 0, wx.ALL, 2)

        self.participants_list = DarkListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.participants_list.AppendColumn("Usuario", width=100)
        self.participants_list.AppendColumn("Equipo", width=80)
        self.participants_list.AppendColumn("Puntos", width=60)
        self.participants_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_participant_selected)
        participants_sizer.Add(self.participants_list, 1, wx.EXPAND | wx.ALL, 2)

        # Player details panel (right)
        player_details_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament status at top
        self.status_text = wx.StaticText(panel, label="Sin torneo seleccionado")
        self.status_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.status_text, 0, wx.ALL, 2)

        self.corpse_count_text = wx.StaticText(panel, label="Bajas: 0")
        self.corpse_count_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.corpse_count_text, 0, wx.ALL, 2)

        # Player details section
        player_details_label = wx.StaticText(panel, label="Detalles del Jugador:")
        player_details_label.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(player_details_label, 0, wx.ALL, 2)

        # Selected player name
        self.selected_player_text = wx.StaticText(panel, label="Selecciona un jugador para ver detalles")
        self.selected_player_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.selected_player_text, 0, wx.ALL, 2)

        # Horizontal layout for player events and corpses
        player_data_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left side: Player events
        events_sizer = wx.BoxSizer(wx.VERTICAL)
        events_label = wx.StaticText(panel, label="Eventos de Combate:")
        events_label.SetForegroundColour(wx.Colour(255, 255, 255))
        events_sizer.Add(events_label, 0, wx.ALL, 2)

        self.player_history_list = DarkListCtrl(panel, style=wx.LC_REPORT)
        self.player_history_list.AppendColumn("Fecha", width=80)
        self.player_history_list.AppendColumn("Evento", width=60)
        self.player_history_list.AppendColumn("Objetivo", width=100)
        self.player_history_list.AppendColumn("Lugar", width=80)
        events_sizer.Add(self.player_history_list, 1, wx.EXPAND | wx.ALL, 2)

        player_data_sizer.Add(events_sizer, 1, wx.EXPAND | wx.ALL, 2)

        # Right side: Player corpses/deaths
        corpses_sizer = wx.BoxSizer(wx.VERTICAL)
        corpses_label = wx.StaticText(panel, label="Bajas Detectadas:")
        corpses_label.SetForegroundColour(wx.Colour(255, 255, 255))
        corpses_sizer.Add(corpses_label, 0, wx.ALL, 2)

        self.player_corpses_list = DarkListCtrl(panel, style=wx.LC_REPORT)
        self.player_corpses_list.AppendColumn("Fecha", width=80)
        self.player_corpses_list.AppendColumn("Ubicación", width=100)
        self.player_corpses_list.AppendColumn("Estado", width=80)
        corpses_sizer.Add(self.player_corpses_list, 1, wx.EXPAND | wx.ALL, 2)

        player_data_sizer.Add(corpses_sizer, 1, wx.EXPAND | wx.ALL, 2)

        player_details_sizer.Add(player_data_sizer, 1, wx.EXPAND | wx.ALL, 2)

        # Player stats summary
        self.player_stats_text = wx.StaticText(panel, label="")
        self.player_stats_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.player_stats_text, 0, wx.ALL, 2)

        # Add to main sizer
        sizer.Add(participants_sizer, 1, wx.EXPAND | wx.ALL, 2)
        sizer.Add(player_details_sizer, 1, wx.EXPAND | wx.ALL, 2)

        # Add the StaticBoxSizer to the main panel sizer
        main_sizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 2)
        panel.SetSizer(main_sizer)

        return panel

    def _create_data_management_panel(self, parent=None) -> wx.Panel:
        """Create data management panel for organizers (debug mode only)"""
        if parent is None:
            parent = self
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(wx.Colour(80, 80, 80))
        
        # Only show in debug mode
        panel.Show(message_bus.is_debug_mode())
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Section title
        title_label = wx.StaticText(panel, label="🔧 Gestión de Datos del Torneo")
        title_label.SetForegroundColour(wx.Colour(255, 255, 255))
        title_font = title_label.GetFont()
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title_label.SetFont(title_font)
        main_sizer.Add(title_label, 0, wx.ALL, 5)
        
        # Data lists section
        lists_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Corpses list
        corpses_sizer = wx.BoxSizer(wx.VERTICAL)
        corpses_label = wx.StaticText(panel, label="Bajas Registradas:")
        corpses_label.SetForegroundColour(wx.Colour(255, 255, 255))
        corpses_sizer.Add(corpses_label, 0, wx.ALL, 2)
        
        self.corpses_list = DarkListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(300, 100))
        self.corpses_list.AppendColumn("Víctima", width=80)
        self.corpses_list.AppendColumn("Atacante", width=80)
        self.corpses_list.AppendColumn("Tiempo", width=60)
        self.corpses_list.AppendColumn("Estado", width=60)
        corpses_sizer.Add(self.corpses_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Corpse management buttons
        corpse_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.delete_corpse_btn = MiniDarkThemeButton(panel, label="🗑️")
        self.delete_corpse_btn.Bind(wx.EVT_BUTTON, self._on_delete_corpse)
        self.delete_corpse_btn.Enable(False)
        corpse_buttons_sizer.Add(self.delete_corpse_btn, 0, wx.ALL, 2)
        corpses_sizer.Add(corpse_buttons_sizer, 0, wx.CENTER, 2)
        
        lists_sizer.Add(corpses_sizer, 1, wx.EXPAND | wx.ALL, 2)
        
        # Combat events list
        events_sizer = wx.BoxSizer(wx.VERTICAL)
        events_label = wx.StaticText(panel, label="Eventos de Combate:")
        events_label.SetForegroundColour(wx.Colour(255, 255, 255))
        events_sizer.Add(events_label, 0, wx.ALL, 2)
        
        self.combat_events_list = DarkListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(300, 100))
        self.combat_events_list.AppendColumn("Tipo", width=60)
        self.combat_events_list.AppendColumn("Jugador", width=80)
        self.combat_events_list.AppendColumn("Objetivo", width=80)
        self.combat_events_list.AppendColumn("Tiempo", width=60)
        events_sizer.Add(self.combat_events_list, 1, wx.EXPAND | wx.ALL, 2)
        
        # Combat event management buttons
        event_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.delete_event_btn = MiniDarkThemeButton(panel, label="🗑️")
        self.delete_event_btn.Bind(wx.EVT_BUTTON, self._on_delete_combat_event)
        self.delete_event_btn.Enable(False)
        event_buttons_sizer.Add(self.delete_event_btn, 0, wx.ALL, 2)
        events_sizer.Add(event_buttons_sizer, 0, wx.CENTER, 2)
        
        lists_sizer.Add(events_sizer, 1, wx.EXPAND | wx.ALL, 2)
        
        main_sizer.Add(lists_sizer, 1, wx.EXPAND | wx.ALL, 2)
        
        # Management buttons
        mgmt_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.refresh_data_btn = DarkThemeButton(panel, label="🔄 Actualizar")
        self.refresh_data_btn.Bind(wx.EVT_BUTTON, self._on_refresh_tournament_data)
        mgmt_buttons_sizer.Add(self.refresh_data_btn, 0, wx.ALL, 2)
        
        self.recalculate_btn = DarkThemeButton(panel, label="📊 Recalcular")
        self.recalculate_btn.Bind(wx.EVT_BUTTON, self._on_recalculate_statistics)
        self.recalculate_btn.Enable(False)
        mgmt_buttons_sizer.Add(self.recalculate_btn, 0, wx.ALL, 2)
        
        main_sizer.Add(mgmt_buttons_sizer, 0, wx.CENTER | wx.ALL, 5)
        
        # Bind list selection events
        self.corpses_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_corpse_selected)
        self.combat_events_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_combat_event_selected)
        
        panel.SetSizer(main_sizer)
        return panel

    def _on_tournament_selected(self, event):
        """Handle tournament selection from list"""
        selected = self.tournaments_list.GetFirstSelected()
        if selected != -1:
            # Enable buttons when tournament is selected
            self.edit_btn.Enable(True)
            self.delete_btn.Enable(True)
            tournament_name = self.tournaments_list.GetItemText(selected, 0)
            tournament_status = self.tournaments_list.GetItemText(selected, 1)

            # Enable activate button only if tournament is created
            self.activate_btn.Enable(tournament_status == "created")
            self.complete_btn.Enable(tournament_status == "active")

            # Enable pause/resume buttons based on tournament status
            self.pause_btn.Enable(tournament_status == "active")
            self.resume_btn.Enable(tournament_status == "paused")

            # Update displays
            self._update_selected_tournament_display(tournament_name)
        else:
            self.edit_btn.Enable(False)
            self.delete_btn.Enable(False)
            self.activate_btn.Enable(False)
            self.complete_btn.Enable(False)
            self.pause_btn.Enable(False)
            self.resume_btn.Enable(False)

    def _on_edit_tournament(self, event):
        """Handle tournament editing via modal dialog"""
        selected = self.tournaments_list.GetFirstSelected()
        if selected == -1:
            return

        try:
            # Get all tournaments to find the selected one
            tournaments = self._tournament_manager.get_all_tournaments()
            tournament_name = self.tournaments_list.GetItemText(selected, 0)

            # Find the tournament data by name
            tournament_data = None
            for tournament in tournaments:
                if tournament.get("name") == tournament_name:
                    tournament_data = tournament
                    break

            if not tournament_data:
                wx.MessageBox("No se pudo cargar los datos del torneo", "Error", wx.OK | wx.ICON_ERROR)
                return

            # Open dialog with tournament data for editing
            dialog = TournamentCreationDialog(self, tournament_data)

            if dialog.ShowModal() == wx.ID_OK:
                # Tournament was edited successfully
                self._refresh_tournaments_list()

            dialog.Destroy()

        except Exception as e:
            wx.MessageBox(f"Error al editar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_delete_tournament(self, event):
        """Handle tournament deletion"""
        selected = self.tournaments_list.GetFirstSelected()
        if selected == -1:
            return

        tournament_name = self.tournaments_list.GetItemText(selected, 0)

        # Confirm deletion
        result = wx.MessageBox(
            f"¿Está seguro que desea eliminar el torneo '{tournament_name}'?\n\nEsta acción no se puede deshacer.",
            "Confirmar eliminación",
            wx.YES_NO | wx.ICON_QUESTION
        )

        if result != wx.YES:
            return

        try:
            # Get tournament ID
            tournaments = self._tournament_manager.get_all_tournaments()
            tournament_to_delete = None
            for tournament in tournaments:
                if tournament.get("name") == tournament_name:
                    tournament_to_delete = tournament
                    break

            if not tournament_to_delete:
                wx.MessageBox("No se pudo encontrar el torneo para eliminar", "Error", wx.OK | wx.ICON_ERROR)
                return

            # Delete from database
            from helpers.core.data_provider import get_data_provider
            data_provider = get_data_provider(self._config_manager)
            success = data_provider.delete_tournament(tournament_to_delete["id"])

            if success:
                message_bus.publish(content=f"Torneo '{tournament_name}' eliminado", level=MessageLevel.INFO)
                self._refresh_tournaments_list()
                # Clear displays
                self.edit_btn.Enable(False)
                self.delete_btn.Enable(False)
                self.activate_btn.Enable(False)
                self.complete_btn.Enable(False)
                self._clear_tournament_display()
            else:
                wx.MessageBox("Error al eliminar el torneo de la base de datos", "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error al eliminar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _clear_tournament_display(self):
        """Clear tournament display panels"""
        self.status_text.SetLabel("Sin torneo seleccionado")
        self.corpse_count_text.SetLabel("Bajas: 0")
        self.participants_list.DeleteAllItems()
        self._clear_player_details()

    def _update_active_tournament_panel(self, event_data):
        """Update the active tournament panel at the top"""
        try:
            message_bus.publish(content="_update_active_tournament_panel called", level=MessageLevel.DEBUG)

            # Use stored current tournament instead of calling manager
            active_tournament = self._current_tournament
            message_bus.publish(content=f"Active tournament in update panel: {active_tournament}", level=MessageLevel.DEBUG)

            if active_tournament:
                tournament_name = active_tournament.get("name", "Desconocido")
                tournament_status = active_tournament.get("status", "unknown")
                participants = active_tournament.get("participants", [])
                teams = active_tournament.get("teams", {})
                config = active_tournament.get("config", {})
                description = config.get("description", "")

                # Left: basic info
                self.active_tournament_name.SetLabel(f"🏆 {tournament_name}")
                self.active_tournament_participants.SetLabel(f"Participantes: {len(participants)} | Equipos: {len(teams)}")

                # Left: description
                if description:
                    self.active_tournament_description.SetLabel(f"Descripción:\n{description}")
                else:
                    self.active_tournament_description.SetLabel("")

                # Center: teams composition
                team_lines = [f"{team}: {', '.join(members)}" for team, members in teams.items()]
                self.active_tournament_teams.SetLabel("\n".join(team_lines) if team_lines else "Sin equipos")

                # Right: user's team
                username = self._current_username if hasattr(self, '_current_username') else "Unknown"
                message_bus.publish(content=f"Looking for user {username} in teams {teams}", level=MessageLevel.DEBUG)

                user_team = None
                teammates = []
                for team_name, members in teams.items():
                    if username in members:
                        user_team = team_name
                        teammates = [m for m in members if m != username]
                        break

                if user_team:
                    self.my_team_label.SetLabel(user_team)
                    self.teammates_label.SetLabel(f"Compañeros:\n{', '.join(teammates) if teammates else 'ninguno'}")
                else:
                    self.my_team_label.SetLabel("-")
                    self.teammates_label.SetLabel("Compañeros:\n-")
            else:
                self.active_tournament_name.SetLabel("Ningún torneo activo")
                self.active_tournament_participants.SetLabel("Participantes: -")
                self.active_tournament_description.SetLabel("")
                self.active_tournament_teams.SetLabel("Sin equipos")
                self.my_team_label.SetLabel("-")
                self.teammates_label.SetLabel("Compañeros:\n-")

            # Force layout recalculation to prevent text overlap
            self.Layout()

        except Exception as e:
            message_bus.publish(content=f"Error updating active tournament panel: {str(e)}", level=MessageLevel.ERROR)

    def _initialize_event_handlers(self):
        """Set up MessageBus event handlers"""
        message_bus.on("tournament_created", self._on_tournament_created)
        message_bus.on("tournament_activated", self._on_tournament_activated)
        message_bus.on("participant_added", self._on_participant_added)
        message_bus.on("tournament_corpse_detected", self._on_corpse_detected)
        message_bus.on("connected_users_updated", self._on_connected_users_updated)
        message_bus.on("remote_realtime_event", self._on_remote_realtime_event)
        message_bus.on("username_change", self._on_username_change)

    def _load_initial_data(self):
        """Load initial tournament data"""
        try:
            message_bus.publish(content="_load_initial_data called", level=MessageLevel.DEBUG)

            # Query database for active tournament (don't rely on manager's in-memory state)
            all_tournaments = self._tournament_manager.get_all_tournaments()
            message_bus.publish(content=f"Found {len(all_tournaments)} tournaments in database", level=MessageLevel.DEBUG)

            active_tournament = None
            for tournament in all_tournaments:
                if tournament.get("status") == "active":
                    active_tournament = tournament
                    message_bus.publish(content=f"Found active tournament: {tournament.get('name')}", level=MessageLevel.DEBUG)
                    break

            if active_tournament:
                self._current_tournament = active_tournament
                # Update active tournament panel - use CallAfter to ensure UI is ready
                wx.CallAfter(self._update_active_tournament_panel, None)
            else:
                message_bus.publish(content="No active tournament found in database", level=MessageLevel.DEBUG)

            # Refresh displays
            wx.CallAfter(self._refresh_tournaments_list)

        except Exception as e:
            message_bus.publish(content=f"Error loading initial tournament data: {str(e)}", level=MessageLevel.ERROR)

    def _on_create_tournament(self, event):
        """Handle tournament creation via modal dialog"""
        dialog = TournamentCreationDialog(self)

        if dialog.ShowModal() == wx.ID_OK:
            # Tournament was created successfully in dialog
            # Refresh display to show new tournament
            self._refresh_tournaments_list()

        dialog.Destroy()

    def _refresh_tournaments_list(self):
        """Refresh the tournaments list from database"""
        self.tournaments_list.DeleteAllItems()

        try:
            # Load all tournaments from database
            tournaments = self._tournament_manager.get_all_tournaments()

            for i, tournament in enumerate(tournaments):
                # Show status directly from DB without translation
                status = tournament.get("status", "unknown")

                index = self.tournaments_list.InsertItem(i, tournament.get("name", ""))
                self.tournaments_list.SetItem(index, 1, status)
                self.tournaments_list.SetItem(index, 2, str(len(tournament.get("participants", []))))

                # Format created_at date
                created_at = tournament.get("created_at", "")
                if created_at:
                    # Handle both ISO format and simple date
                    if "T" in created_at:
                        created_at = created_at.split("T")[0]
                    elif " " in created_at:
                        created_at = created_at.split(" ")[0]
                self.tournaments_list.SetItem(index, 3, created_at)

        except Exception as e:
            message_bus.publish(content=f"Error loading tournaments: {str(e)}", level=MessageLevel.ERROR)

    def _update_selected_tournament_display(self, tournament_name):
        """Update participants list and stats for selected tournament"""
        try:
            # Get tournament data by name from all tournaments
            tournaments = self._tournament_manager.get_all_tournaments()
            tournament = None
            for t in tournaments:
                if t.get("name") == tournament_name:
                    tournament = t
                    break

            if not tournament:
                self.status_text.SetLabel("Torneo no encontrado")
                self.participants_list.DeleteAllItems()
                self.corpse_count_text.SetLabel("Bajas: 0")
                self._current_tournament = None
                return

            # Store selected tournament
            self._current_tournament = tournament

            # Update status text
            status_translations = {
                "created": "creado",
                "active": "activo",
                "completed": "completado",
                "cancelled": "cancelado"
            }
            status_spanish = status_translations.get(tournament.get("status", ""), "desconocido")
            self.status_text.SetLabel(f"Torneo: {tournament_name} ({status_spanish})")

            # Update participants list grouped by teams
            self.participants_list.DeleteAllItems()
            teams = tournament.get("teams", {})

            if not teams:
                # No teams defined, show all participants
                participants = tournament.get("participants", [])
                for i, username in enumerate(participants):
                    index = self.participants_list.InsertItem(i, username)
                    self.participants_list.SetItem(index, 1, "Sin equipo")
                    self.participants_list.SetItem(index, 2, "0")
            else:
                # Group by teams with visual separation
                row_index = 0
                for team_name, team_members in teams.items():
                    # Add team header (bold/colored)
                    if team_members:  # Only show teams with members
                        team_header_index = self.participants_list.InsertItem(row_index, f"══ {team_name} ══")
                        self.participants_list.SetItem(team_header_index, 1, "")
                        self.participants_list.SetItem(team_header_index, 2, "")
                        row_index += 1

                        # Add team members
                        for username in team_members:
                            member_index = self.participants_list.InsertItem(row_index, f"  → {username}")
                            self.participants_list.SetItem(member_index, 1, team_name)
                            self.participants_list.SetItem(member_index, 2, "0")  # TODO: Real score
                            row_index += 1

            # Update statistics
            total_participants = len(tournament.get("participants", []))
            total_teams = len([team for team, members in teams.items() if members]) if teams else 0

            # TODO: Get real corpse count from database
            self.corpse_count_text.SetLabel(f"Participantes: {total_participants} | Equipos: {total_teams} | Bajas: 0")

            # Refresh data management panel
            self._refresh_tournament_data()

        except Exception as e:
            message_bus.publish(content=f"Error updating tournament display: {str(e)}", level=MessageLevel.ERROR)
            self.status_text.SetLabel("Error cargando torneo")
            self.participants_list.DeleteAllItems()

    def _on_participant_selected(self, event):
        """Handle participant selection to show player or team details"""
        selected = self.participants_list.GetFirstSelected()
        if selected == -1:
            self._clear_player_details()
            return

        # Get the text from the list
        text = self.participants_list.GetItemText(selected, 0)

        if text.startswith("  → "):
            # Individual player selected
            username = text[4:]  # Remove "  → " prefix
            if username and username.strip():
                self._load_player_details(username.strip())
            else:
                self._clear_player_details()
        elif text.startswith("══ ") and text.endswith(" ══"):
            # Team header selected - show team statistics
            team_name = text[3:-3].strip()  # Remove "══ " and " ══"
            self._load_team_details(team_name)
        else:
            # Individual player (no team structure)
            username = text
            if username and username.strip():
                self._load_player_details(username.strip())
            else:
                self._clear_player_details()

    def _load_team_details(self, team_name):
        """Load and display team details and combined history"""
        try:
            self.selected_player_text.SetLabel(f"Equipo: {team_name}")

            # Get currently selected tournament
            selected = self.tournaments_list.GetFirstSelected()
            if selected == -1:
                self._clear_player_details()
                return

            tournament_name = self.tournaments_list.GetItemText(selected, 0)
            tournaments = self._tournament_manager.get_all_tournaments()

            current_tournament = None
            for tournament in tournaments:
                if tournament.get("name") == tournament_name:
                    current_tournament = tournament
                    break

            if not current_tournament:
                self._clear_player_details()
                return

            # Get team members
            teams = current_tournament.get("config", {}).get("teams", {})
            team_members = teams.get(team_name, [])

            if not team_members:
                self._clear_player_details()
                return

            # Clear and populate history list
            self.player_history_list.DeleteAllItems()

            # Collect combat history for all team members
            all_team_history = []
            total_kills = 0
            total_deaths = 0

            for member in team_members:
                member_history = self._get_player_combat_history(member)
                for event in member_history:
                    event["player"] = member  # Add player name to event
                    all_team_history.append(event)

                # Count stats for this member
                member_kills = len([e for e in member_history if e.get("event_type") == "kill"])
                member_deaths = len([e for e in member_history if e.get("event_type") == "death"])
                total_kills += member_kills
                total_deaths += member_deaths

            # Sort all events by timestamp
            all_team_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            # Populate history list with team events
            for event in all_team_history:
                timestamp = event.get("timestamp", "")
                if timestamp:
                    # Format timestamp to readable format
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        formatted_time = dt.strftime("%H:%M:%S")
                    except:
                        formatted_time = timestamp[:8] if len(timestamp) > 8 else timestamp
                else:
                    formatted_time = "N/A"

                event_type = event.get("event_type", "evento")
                target = event.get("target", "")
                player = event.get("player", "")
                weapon = event.get("weapon", "")

                index = self.player_history_list.InsertItem(self.player_history_list.GetItemCount(), formatted_time)
                self.player_history_list.SetItem(index, 1, player)
                self.player_history_list.SetItem(index, 2, event_type)
                self.player_history_list.SetItem(index, 3, target)
                self.player_history_list.SetItem(index, 4, weapon)

            # Update team statistics
            member_count = len(team_members)
            self.player_stats_text.SetLabel(f"Miembros: {member_count} | Bajas: {total_kills} | Muertes: {total_deaths}")

        except Exception as e:
            message_bus.publish(content=f"Error loading team details: {str(e)}", level=MessageLevel.ERROR)
            self.selected_player_text.SetLabel("Error cargando detalles del equipo")

    def _clear_player_details(self):
        """Clear player details panel"""
        self.selected_player_text.SetLabel("Selecciona un jugador o equipo para ver detalles")
        self.player_history_list.DeleteAllItems()
        self.player_stats_text.SetLabel("")

    def _load_player_details(self, username):
        """Load and display player details and history"""
        try:
            self.selected_player_text.SetLabel(f"Jugador: {username}")

            # Clear previous data
            self.player_history_list.DeleteAllItems()

            # Get player combat history from database
            player_history = self._get_player_combat_history(username)

            # Populate history list
            for i, event in enumerate(player_history):
                event_date = event.get("timestamp", "")[:10] if event.get("timestamp") else ""
                event_type = "Muerte" if event.get("event_type") == "death" else "Baja"
                target = event.get("target", event.get("victim", ""))
                location = event.get("location", "")[:15] if event.get("location") else ""

                index = self.player_history_list.InsertItem(i, event_date)
                self.player_history_list.SetItem(index, 1, event_type)
                self.player_history_list.SetItem(index, 2, target)
                self.player_history_list.SetItem(index, 3, location)

            # Calculate and display stats
            deaths = len([e for e in player_history if e.get("event_type") == "death"])
            kills = len([e for e in player_history if e.get("event_type") == "kill"])
            self.player_stats_text.SetLabel(f"Bajas: {kills} | Muertes: {deaths}")

        except Exception as e:
            message_bus.publish(content=f"Error loading player details: {str(e)}", level=MessageLevel.ERROR)
            self.selected_player_text.SetLabel("Error cargando detalles del jugador")

    def _get_player_combat_history(self, username):
        """Get player combat history from database"""
        try:
            # Get currently selected tournament to determine table to query
            selected = self.tournaments_list.GetFirstSelected()
            if selected == -1:
                return []

            tournament_name = self.tournaments_list.GetItemText(selected, 0)
            tournaments = self._tournament_manager.get_all_tournaments()

            current_tournament = None
            for tournament in tournaments:
                if tournament.get("name") == tournament_name:
                    current_tournament = tournament
                    break

            if not current_tournament:
                return []

            # Get tournament type (table name) directly
            table_name = current_tournament.get("config", {}).get("tournament_type", "sc_default")

            # Query combat events for this player from the appropriate table
            from helpers.core.data_provider import get_data_provider
            data_provider = get_data_provider(self._config_manager)

            # Get player combat history from the appropriate table
            combat_history = data_provider.get_player_combat_history(
                table_name=table_name,
                username=username,
                tournament_id=current_tournament.get("id")
            )

            return combat_history

        except Exception as e:
            message_bus.publish(content=f"Error getting player combat history: {str(e)}", level=MessageLevel.ERROR)
            return []

    def _on_activate_tournament(self, event):
        """Handle tournament activation"""
        if not self._current_tournament:
            return

        try:
            result = self._tournament_manager.activate_tournament(self._current_tournament["id"])

            if result["success"]:
                self._current_tournament = result["tournament"]
                self._refresh_tournaments_list()
                self._update_active_tournament_panel(None)
                message_bus.publish(content="Torneo activado para etiquetado de eventos de combate", level=MessageLevel.INFO)
            else:
                wx.MessageBox(f"Error al activar torneo: {result.get('error', 'Error desconocido')}",
                            "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error al activar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_pause_tournament(self, event):
        """Handle tournament pause"""
        if not self._current_tournament:
            return
        try:
            result = self._tournament_manager.pause_tournament(self._current_tournament["id"])
            if result["success"]:
                self._current_tournament = result["tournament"]
                self._refresh_tournaments_list()  # Refresh tournament list to show new status
                self._update_tournament_display()
                message_bus.publish(content="Torneo pausado", level=MessageLevel.INFO)
            else:
                wx.MessageBox(f"Error al pausar torneo: {result.get('error', 'Error desconocido')}",
                            "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error al pausar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_resume_tournament(self, event):
        """Handle tournament resume"""
        if not self._current_tournament:
            return
        try:
            result = self._tournament_manager.resume_tournament(self._current_tournament["id"])
            if result["success"]:
                self._current_tournament = result["tournament"]
                self._refresh_tournaments_list()  # Refresh tournament list to show new status
                self._update_tournament_display()
                message_bus.publish(content="Torneo reanudado", level=MessageLevel.INFO)
            else:
                wx.MessageBox(f"Error al reanudar torneo: {result.get('error', 'Error desconocido')}",
                            "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error al reanudar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_complete_tournament(self, event):
        """Handle tournament completion"""
        if not self._current_tournament:
            return

        result = wx.MessageBox("¿Está seguro que desea finalizar este torneo?",
                             "Confirmar", wx.YES_NO | wx.ICON_QUESTION)

        if result == wx.YES:
            # Implementation for completing tournament would go here
            message_bus.publish(content="Finalización de torneo aún no implementada", level=MessageLevel.INFO)


    def _on_tournament_created(self, event_data):
        """Handle tournament created event"""
        wx.CallAfter(self._refresh_tournaments_list)

    def _on_tournament_activated(self, event_data):
        """Handle tournament activated event"""
        wx.CallAfter(self._refresh_tournaments_list)
        wx.CallAfter(self._update_active_tournament_panel, event_data)

    def _on_participant_added(self, event_data):
        """Handle participant added event"""
        # Refresh the selected tournament display
        selected = self.tournaments_list.GetFirstSelected()
        if selected != -1:
            tournament_name = self.tournaments_list.GetItemText(selected, 0)
            wx.CallAfter(lambda: self._update_selected_tournament_display(tournament_name))

    def _on_corpse_detected(self, event_data):
        """Handle tournament corpse detected event"""
        corpse_count = 0  # Would get actual count from database
        wx.CallAfter(lambda: self.corpse_count_text.SetLabel(f"Bajas: {corpse_count}"))

    def _on_connected_users_updated(self, event_data):
        """Handle connected users list update"""
        # This event is no longer needed in simplified widget
        pass

    def _on_remote_realtime_event(self, username, event_data):
        """Handle realtime events from other users"""
        try:
            event_type = event_data.get('event_type')

            if event_type == 'tournament_activated':
                tournament_id = event_data.get('tournament_id')
                tournament_name = event_data.get('tournament_name', 'Unknown')
                team_composition = event_data.get('team_composition', {})

                # Find user's team and teammates
                user_team = None
                teammates = []

                for team_name, players in team_composition.items():
                    if self._current_username in players:
                        user_team = team_name
                        teammates = [player for player in players if player != self._current_username]
                        break

                # Refresh tournaments list to reflect the new status
                wx.CallAfter(self._refresh_tournaments_list)

                # If this is the currently selected tournament, update its display
                if self._current_tournament and self._current_tournament.get("id") == tournament_id:
                    wx.CallAfter(lambda: self._update_selected_tournament_display(tournament_name))

                # Show relevant notification
                if user_team:
                    teammates_str = ", ".join(teammates) if teammates else "ningún compañero"
                    notification_text = f"¡Torneo '{tournament_name}' activado por {username}! Tu equipo: {user_team} | Compañeros: {teammates_str}"
                    message_bus.publish(content=notification_text, level=MessageLevel.INFO)

                    # Desktop notification
                    message_bus.emit("show_windows_notification", {
                        "title": "🏆 Torneo Activado",
                        "message": f"Torneo: {tournament_name}\nEquipo: {user_team}\nCompañeros: {teammates_str}\nActivado por: {username}"
                    })
                else:
                    notification_text = f"Torneo '{tournament_name}' activado por {username} (no participas)"
                    message_bus.publish(content=notification_text, level=MessageLevel.INFO)

                    # Desktop notification
                    message_bus.emit("show_windows_notification", {
                        "title": "🏆 Torneo Activado",
                        "message": f"Torneo: {tournament_name}\nActivado por: {username}\n(No participas en este torneo)"
                    })

            elif event_type == 'tournament_completed':
                tournament_id = event_data.get('tournament_id')
                tournament_name = event_data.get('tournament_name', 'Unknown')
                team_composition = event_data.get('team_composition', {})
                final_statistics = event_data.get('final_statistics', {})

                # Find user's team and teammates
                user_team = None
                teammates = []

                for team_name, players in team_composition.items():
                    if self._current_username in players:
                        user_team = team_name
                        teammates = [player for player in players if player != self._current_username]
                        break

                # Refresh tournaments list to reflect the new status
                wx.CallAfter(self._refresh_tournaments_list)

                # If this is the currently selected tournament, update its display
                if self._current_tournament and self._current_tournament.get("id") == tournament_id:
                    wx.CallAfter(lambda: self._update_selected_tournament_display(tournament_name))

                # Show relevant notification
                if user_team:
                    teammates_str = ", ".join(teammates) if teammates else "ningún compañero"
                    notification_text = f"🏁 Torneo '{tournament_name}' completado por {username}! Tu equipo: {user_team} | Compañeros: {teammates_str}"
                    message_bus.publish(content=notification_text, level=MessageLevel.INFO)

                    # Desktop notification
                    message_bus.emit("show_windows_notification", {
                        "title": "🏁 Torneo Completado",
                        "message": f"Torneo: {tournament_name}\nEquipo: {user_team}\nCompañeros: {teammates_str}\nCompletado por: {username}"
                    })
                else:
                    notification_text = f"🏁 Torneo '{tournament_name}' completado por {username}"
                    message_bus.publish(content=notification_text, level=MessageLevel.INFO)

                    # Desktop notification
                    message_bus.emit("show_windows_notification", {
                        "title": "🏁 Torneo Completado",
                        "message": f"Torneo: {tournament_name}\nCompletado por: {username}"
                    })

        except Exception as e:
            message_bus.publish(content=f"Error handling remote tournament event: {str(e)}", level=MessageLevel.ERROR)

    def _on_username_change(self, username, old_username):
        """Handle username change events"""
        self._current_username = username
        # Update panel to show user's team now that we have the username
        if self._current_tournament:
            wx.CallAfter(self._update_active_tournament_panel, None)

    # Data Management Event Handlers
    
    def _on_corpse_selected(self, event):
        """Handle corpse selection from list"""
        selected = self.corpses_list.GetFirstSelected()
        self.delete_corpse_btn.Enable(selected != -1)
    
    def _on_combat_event_selected(self, event):
        """Handle combat event selection from list"""
        selected = self.combat_events_list.GetFirstSelected()
        self.delete_event_btn.Enable(selected != -1)
    
    def _on_delete_corpse(self, event):
        """Handle corpse deletion"""
        selected = self.corpses_list.GetFirstSelected()
        if selected == -1:
            return
            
        # Get corpse ID from the list (stored as item data)
        corpse_id = self.corpses_list.GetItemData(selected)
        if not corpse_id:
            wx.MessageBox("No se pudo obtener ID de la baja", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        # Confirm deletion
        victim = self.corpses_list.GetItemText(selected, 0)
        attacker = self.corpses_list.GetItemText(selected, 1)
        result = wx.MessageBox(
            f"¿Está seguro que desea eliminar la baja de {victim} por {attacker}?",
            "Confirmar eliminación",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if result == wx.YES:
            try:
                result = self._tournament_manager.delete_corpse_record(str(corpse_id))
                if result["success"]:
                    self._refresh_tournament_data()
                else:
                    wx.MessageBox(f"Error al eliminar baja: {result.get('error', 'Error desconocido')}",
                                "Error", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"Error al eliminar baja: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def _on_delete_combat_event(self, event):
        """Handle combat event deletion"""
        selected = self.combat_events_list.GetFirstSelected()
        if selected == -1:
            return
            
        # Get event data from the list
        event_type = self.combat_events_list.GetItemText(selected, 0)
        player = self.combat_events_list.GetItemText(selected, 1)
        target = self.combat_events_list.GetItemText(selected, 2)
        
        # Event ID and table name stored as item data (tuple)
        event_data = self.combat_events_list.GetItemData(selected)
        if not event_data:
            wx.MessageBox("No se pudo obtener datos del evento", "Error", wx.OK | wx.ICON_ERROR)
            return
            
        event_id, table_name = event_data
        
        # Confirm deletion
        result = wx.MessageBox(
            f"¿Está seguro que desea eliminar el evento '{event_type}' de {player} → {target}?",
            "Confirmar eliminación",
            wx.YES_NO | wx.ICON_QUESTION
        )
        
        if result == wx.YES:
            try:
                result = self._tournament_manager.delete_combat_event(table_name, str(event_id))
                if result["success"]:
                    self._refresh_tournament_data()
                else:
                    wx.MessageBox(f"Error al eliminar evento: {result.get('error', 'Error desconocido')}",
                                "Error", wx.OK | wx.ICON_ERROR)
            except Exception as e:
                wx.MessageBox(f"Error al eliminar evento: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def _on_refresh_tournament_data(self, event):
        """Handle tournament data refresh"""
        self._refresh_tournament_data()
    
    def _on_recalculate_statistics(self, event):
        """Handle tournament statistics recalculation"""
        if not self._current_tournament:
            return
            
        try:
            result = self._tournament_manager.recalculate_tournament_statistics(self._current_tournament["id"])
            if result["success"]:
                self._refresh_tournament_data()
                self._update_tournament_display()
                wx.MessageBox("Estadísticas recalculadas correctamente", "Éxito", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox(f"Error al recalcular estadísticas: {result.get('error', 'Error desconocido')}",
                            "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(f"Error al recalcular estadísticas: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)
    
    def _refresh_tournament_data(self):
        """Refresh tournament data lists"""
        if not self._current_tournament:
            self.corpses_list.DeleteAllItems()
            self.combat_events_list.DeleteAllItems()
            self.recalculate_btn.Enable(False)
            return
            
        try:
            # Load corpses
            corpses = self._tournament_manager.get_tournament_corpses(self._current_tournament["id"])
            self.corpses_list.DeleteAllItems()
            
            for i, corpse in enumerate(corpses):
                timestamp = corpse.get("detected_at", "")[:10] if corpse.get("detected_at") else ""
                confirmed = "Sí" if corpse.get("organizer_confirmed", False) else "No"
                
                index = self.corpses_list.InsertItem(i, corpse.get("participant_name", "Unknown"))
                self.corpses_list.SetItem(index, 1, corpse.get("detected_by", "Unknown"))
                self.corpses_list.SetItem(index, 2, timestamp)
                self.corpses_list.SetItem(index, 3, confirmed)
                self.corpses_list.SetItemData(index, corpse.get("id", 0))
            
            # Load combat events for current tournament
            tournament_type = self._current_tournament.get("config", {}).get("tournament_type", "sc_default")
            combat_history = []
            
            # Get combat history for all participants
            for participant in self._current_tournament.get("participants", []):
                participant_history = self._get_player_combat_history(participant)
                for event in participant_history:
                    event["source_player"] = participant
                    combat_history.append(event)
            
            # Sort by timestamp
            combat_history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            
            # Populate combat events list
            self.combat_events_list.DeleteAllItems()
            for i, event in enumerate(combat_history[:50]):  # Limit to 50 most recent
                event_type = "Muerte" if event.get("event_type") == "death" else "Baja"
                player = event.get("source_player", "Unknown")
                target = event.get("target", "Unknown")
                timestamp = event.get("timestamp", "")[:10] if event.get("timestamp") else ""
                
                index = self.combat_events_list.InsertItem(i, event_type)
                self.combat_events_list.SetItem(index, 1, player)
                self.combat_events_list.SetItem(index, 2, target)
                self.combat_events_list.SetItem(index, 3, timestamp)
                
                # Store event ID and table name as tuple
                raw_event = event.get("raw_event", {})
                event_id = raw_event.get("id", 0)
                self.combat_events_list.SetItemData(index, (event_id, tournament_type))
            
            # Enable recalculate button for active tournaments
            tournament_status = self._current_tournament.get("status", "")
            self.recalculate_btn.Enable(tournament_status in ["active", "paused"])
            
        except Exception as e:
            message_bus.publish(content=f"Error refreshing tournament data: {str(e)}", level=MessageLevel.ERROR)