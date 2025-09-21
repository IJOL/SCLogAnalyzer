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

        self._create_ui()
        self._initialize_event_handlers()
        self._load_initial_data()

    def _create_ui(self):
        """Create tournament management interface"""
        # Apply dark theme background
        self.SetBackgroundColour(wx.Colour(80, 80, 80))

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament list section (top)
        tournament_list_section = self._create_tournament_list_section()
        main_sizer.Add(tournament_list_section, 1, wx.EXPAND | wx.ALL, 2)

        # Participants and statistics section (bottom)
        participants_section = self._create_participants_section()
        main_sizer.Add(participants_section, 1, wx.EXPAND | wx.ALL, 2)

        self.SetSizer(main_sizer)

    def _create_tournament_list_section(self) -> wx.StaticBoxSizer:
        """Create tournament list section"""
        box = wx.StaticBox(self, label="Torneos")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.VERTICAL)

        # Tournament list
        self.tournaments_list = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.tournaments_list.AppendColumn("Nombre", width=150)
        self.tournaments_list.AppendColumn("Estado", width=80)
        self.tournaments_list.AppendColumn("Participantes", width=80)
        self.tournaments_list.AppendColumn("Creado", width=100)
        self.tournaments_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_tournament_selected)
        sizer.Add(self.tournaments_list, 1, wx.EXPAND | wx.ALL, 2)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create tournament button (only in debug mode)
        if message_bus.is_debug_mode():
            self.create_btn = DarkThemeButton(self, label="Crear Torneo")
            self.create_btn.Bind(wx.EVT_BUTTON, self._on_create_tournament)
            button_sizer.Add(self.create_btn, 0, wx.ALL, 2)

        # Edit tournament button
        self.edit_btn = DarkThemeButton(self, label="Editar")
        self.edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_tournament)
        self.edit_btn.Enable(False)
        button_sizer.Add(self.edit_btn, 0, wx.ALL, 2)

        # Activate tournament button
        self.activate_btn = DarkThemeButton(self, label="Activar")
        self.activate_btn.Bind(wx.EVT_BUTTON, self._on_activate_tournament)
        self.activate_btn.Enable(False)
        button_sizer.Add(self.activate_btn, 0, wx.ALL, 2)

        sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 2)

        return sizer

    def _create_participants_section(self) -> wx.StaticBoxSizer:
        """Create participants and statistics section"""
        box = wx.StaticBox(self, label="Participantes y Estadísticas")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Participants list
        participants_sizer = wx.BoxSizer(wx.VERTICAL)

        participants_label = wx.StaticText(self, label="Participantes:")
        participants_label.SetForegroundColour(wx.Colour(255, 255, 255))
        participants_sizer.Add(participants_label, 0, wx.ALL, 2)

        self.participants_list = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.participants_list.AppendColumn("Usuario", width=100)
        self.participants_list.AppendColumn("Equipo", width=80)
        self.participants_list.AppendColumn("Puntos", width=60)
        participants_sizer.Add(self.participants_list, 1, wx.EXPAND | wx.ALL, 2)

        # Statistics panel
        stats_sizer = wx.BoxSizer(wx.VERTICAL)

        stats_label = wx.StaticText(self, label="Estadísticas:")
        stats_label.SetForegroundColour(wx.Colour(255, 255, 255))
        stats_sizer.Add(stats_label, 0, wx.ALL, 2)

        # Tournament status
        self.status_text = wx.StaticText(self, label="Sin torneo seleccionado")
        self.status_text.SetForegroundColour(wx.Colour(255, 255, 255))
        stats_sizer.Add(self.status_text, 0, wx.ALL, 2)

        # Corpse count
        self.corpse_count_text = wx.StaticText(self, label="Bajas: 0")
        self.corpse_count_text.SetForegroundColour(wx.Colour(255, 255, 255))
        stats_sizer.Add(self.corpse_count_text, 0, wx.ALL, 2)

        # Complete tournament button
        self.complete_btn = DarkThemeButton(self, label="Finalizar Torneo")
        self.complete_btn.Bind(wx.EVT_BUTTON, self._on_complete_tournament)
        self.complete_btn.Enable(False)
        stats_sizer.Add(self.complete_btn, 0, wx.ALL, 2)

        # Add to main sizer
        sizer.Add(participants_sizer, 1, wx.EXPAND | wx.ALL, 2)
        sizer.Add(stats_sizer, 0, wx.EXPAND | wx.ALL, 2)

        return sizer

    def _on_tournament_selected(self, event):
        """Handle tournament selection from list"""
        selected = self.tournaments_list.GetFirstSelected()
        if selected != -1:
            # Enable buttons when tournament is selected
            self.edit_btn.Enable(True)
            tournament_name = self.tournaments_list.GetItemText(selected, 0)
            tournament_status = self.tournaments_list.GetItemText(selected, 1)

            # Enable activate button only if tournament is created
            self.activate_btn.Enable(tournament_status == "creado")
            self.complete_btn.Enable(tournament_status == "activo")

            # Update displays
            self._update_selected_tournament_display(tournament_name)
        else:
            self.edit_btn.Enable(False)
            self.activate_btn.Enable(False)
            self.complete_btn.Enable(False)

    def _on_edit_tournament(self, event):
        """Handle tournament editing via modal dialog"""
        selected = self.tournaments_list.GetFirstSelected()
        if selected == -1:
            return

        tournament_name = self.tournaments_list.GetItemText(selected, 0)
        # TODO: Load tournament data and pass to dialog for editing
        dialog = TournamentCreationDialog(self)

        if dialog.ShowModal() == wx.ID_OK:
            # Tournament was edited successfully
            self._refresh_tournaments_list()

        dialog.Destroy()

    def _initialize_event_handlers(self):
        """Set up MessageBus event handlers"""
        message_bus.on("tournament_created", self._on_tournament_created)
        message_bus.on("tournament_activated", self._on_tournament_activated)
        message_bus.on("participant_added", self._on_participant_added)
        message_bus.on("tournament_corpse_detected", self._on_corpse_detected)
        message_bus.on("connected_users_updated", self._on_connected_users_updated)

    def _load_initial_data(self):
        """Load initial tournament data"""
        try:
            # Load active tournament
            active_tournament = self._tournament_manager.get_active_tournament()
            if active_tournament:
                self._current_tournament = active_tournament

            # Refresh displays
            self._refresh_tournaments_list()

        except Exception as e:
            message_bus.publish(f"Error loading initial tournament data: {str(e)}", MessageLevel.ERROR)

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

        # TODO: Load tournaments from database
        # For now, show placeholder if there's an active tournament
        if self._current_tournament:
            tournament = self._current_tournament
            status_translations = {
                "created": "creado",
                "active": "activo",
                "completed": "completado",
                "cancelled": "cancelado"
            }
            status_spanish = status_translations.get(tournament.get("status", ""), "desconocido")

            index = self.tournaments_list.InsertItem(0, tournament.get("name", ""))
            self.tournaments_list.SetItem(index, 1, status_spanish)
            self.tournaments_list.SetItem(index, 2, str(len(tournament.get("participants", []))))
            self.tournaments_list.SetItem(index, 3, tournament.get("created_at", "")[:10] if tournament.get("created_at") else "")

    def _update_selected_tournament_display(self, tournament_name):
        """Update participants list and stats for selected tournament"""
        if not self._current_tournament or self._current_tournament.get("name") != tournament_name:
            return

        tournament = self._current_tournament

        # Update status text
        status_translations = {
            "created": "creado",
            "active": "activo",
            "completed": "completado",
            "cancelled": "cancelado"
        }
        status_spanish = status_translations.get(tournament.get("status", ""), "desconocido")
        self.status_text.SetLabel(f"Torneo: {tournament_name} ({status_spanish})")

        # Update participants list
        self.participants_list.DeleteAllItems()
        participants = tournament.get("participants", [])
        teams = tournament.get("teams", {})

        for i, username in enumerate(participants):
            # Find user's team
            user_team = "Sin equipo"
            for team_name, team_members in teams.items():
                if username in team_members:
                    user_team = team_name
                    break

            index = self.participants_list.InsertItem(i, username)
            self.participants_list.SetItem(index, 1, user_team)
            self.participants_list.SetItem(index, 2, "0")  # Score placeholder

    def _on_activate_tournament(self, event):
        """Handle tournament activation"""
        if not self._current_tournament:
            return

        try:
            result = self._tournament_manager.activate_tournament(self._current_tournament["id"])

            if result["success"]:
                self._current_tournament = result["tournament"]
                self._update_tournament_display()
                message_bus.publish("Torneo activado para etiquetado de eventos de combate", MessageLevel.INFO)
            else:
                wx.MessageBox(f"Error al activar torneo: {result.get('error', 'Error desconocido')}",
                            "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error al activar torneo: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)


    def _on_complete_tournament(self, event):
        """Handle tournament completion"""
        if not self._current_tournament:
            return

        result = wx.MessageBox("¿Está seguro que desea finalizar este torneo?",
                             "Confirmar", wx.YES_NO | wx.ICON_QUESTION)

        if result == wx.YES:
            # Implementation for completing tournament would go here
            message_bus.publish("Finalización de torneo aún no implementada", MessageLevel.INFO)


    def _on_tournament_created(self, event_data):
        """Handle tournament created event"""
        wx.CallAfter(self._refresh_tournaments_list)

    def _on_tournament_activated(self, event_data):
        """Handle tournament activated event"""
        wx.CallAfter(self._refresh_tournaments_list)

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