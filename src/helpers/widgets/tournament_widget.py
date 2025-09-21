import wx
import threading
from typing import Dict, List, Optional, Any
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.tournament.tournament_manager import TournamentManager
from helpers.tournament.corpse_detector import CorpseDetector

class TournamentWidget(wx.Panel):
    """Main tournament management widget with dual-list interface"""

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
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament creation section
        tournament_section = self._create_tournament_section()
        main_sizer.Add(tournament_section, 0, wx.EXPAND | wx.ALL, 5)

        # Dual-list interface section
        lists_section = self._create_dual_list_section()
        main_sizer.Add(lists_section, 1, wx.EXPAND | wx.ALL, 5)

        # Tournament status and controls
        status_section = self._create_status_section()
        main_sizer.Add(status_section, 0, wx.EXPAND | wx.ALL, 5)

        self.SetSizer(main_sizer)

    def _create_tournament_section(self) -> wx.StaticBoxSizer:
        """Create tournament creation and management section"""
        box = wx.StaticBox(self, label="Tournament Management")
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Tournament name input
        self.tournament_name_ctrl = wx.TextCtrl(self, size=(200, -1))
        sizer.Add(wx.StaticText(self, label="Name:"), 0, wx.CENTER | wx.ALL, 5)
        sizer.Add(self.tournament_name_ctrl, 0, wx.CENTER | wx.ALL, 5)

        # Create tournament button
        self.create_btn = wx.Button(self, label="Create Tournament")
        self.create_btn.Bind(wx.EVT_BUTTON, self._on_create_tournament)
        sizer.Add(self.create_btn, 0, wx.CENTER | wx.ALL, 5)

        # Activate tournament button
        self.activate_btn = wx.Button(self, label="Activate")
        self.activate_btn.Bind(wx.EVT_BUTTON, self._on_activate_tournament)
        self.activate_btn.Enable(False)
        sizer.Add(self.activate_btn, 0, wx.CENTER | wx.ALL, 5)

        return sizer

    def _create_dual_list_section(self) -> wx.StaticBoxSizer:
        """Create dual-list interface for team building"""
        box = wx.StaticBox(self, label="Team Building")
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Connected users list
        connected_box = wx.StaticBox(self, label="Connected Users")
        connected_sizer = wx.StaticBoxSizer(connected_box, wx.VERTICAL)

        self.connected_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.connected_list.AppendColumn("Username", width=150)
        self.connected_list.AppendColumn("Status", width=100)
        connected_sizer.Add(self.connected_list, 1, wx.EXPAND | wx.ALL, 5)

        # Move buttons
        buttons_sizer = wx.BoxSizer(wx.VERTICAL)
        self.move_to_team_btn = wx.Button(self, label="Add to Team >>")
        self.move_to_team_btn.Bind(wx.EVT_BUTTON, self._on_move_to_team)
        self.move_to_connected_btn = wx.Button(self, label="<< Remove from Team")
        self.move_to_connected_btn.Bind(wx.EVT_BUTTON, self._on_move_to_connected)

        buttons_sizer.Add(self.move_to_team_btn, 0, wx.CENTER | wx.ALL, 5)
        buttons_sizer.Add(self.move_to_connected_btn, 0, wx.CENTER | wx.ALL, 5)

        # Team selection
        self.team_choice = wx.Choice(self, choices=["Team Alpha", "Team Beta", "Team Gamma"])
        self.team_choice.SetSelection(0)
        buttons_sizer.Add(wx.StaticText(self, label="Team:"), 0, wx.CENTER | wx.ALL, 2)
        buttons_sizer.Add(self.team_choice, 0, wx.CENTER | wx.ALL, 2)

        # Tournament participants list
        tournament_box = wx.StaticBox(self, label="Tournament Teams")
        tournament_sizer = wx.StaticBoxSizer(tournament_box, wx.VERTICAL)

        self.tournament_list = wx.ListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.tournament_list.AppendColumn("Username", width=150)
        self.tournament_list.AppendColumn("Team", width=100)
        self.tournament_list.AppendColumn("Score", width=80)
        tournament_sizer.Add(self.tournament_list, 1, wx.EXPAND | wx.ALL, 5)

        # Assemble dual-list layout
        sizer.Add(connected_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(buttons_sizer, 0, wx.CENTER | wx.ALL, 10)
        sizer.Add(tournament_sizer, 1, wx.EXPAND | wx.ALL, 5)

        return sizer

    def _create_status_section(self) -> wx.StaticBoxSizer:
        """Create tournament status and statistics section"""
        box = wx.StaticBox(self, label="Tournament Status")
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Status display
        self.status_text = wx.StaticText(self, label="No active tournament")
        sizer.Add(self.status_text, 1, wx.CENTER | wx.ALL, 5)

        # Corpse statistics
        self.corpse_count_text = wx.StaticText(self, label="Corpses: 0")
        sizer.Add(self.corpse_count_text, 0, wx.CENTER | wx.ALL, 5)

        # Complete tournament button
        self.complete_btn = wx.Button(self, label="Complete Tournament")
        self.complete_btn.Bind(wx.EVT_BUTTON, self._on_complete_tournament)
        self.complete_btn.Enable(False)
        sizer.Add(self.complete_btn, 0, wx.CENTER | wx.ALL, 5)

        return sizer

    def _initialize_event_handlers(self):
        """Set up MessageBus event handlers"""
        message_bus.on("tournament_created", self._on_tournament_created)
        message_bus.on("tournament_activated", self._on_tournament_activated)
        message_bus.on("participant_added", self._on_participant_added)
        message_bus.on("tournament_corpse_detected", self._on_corpse_detected)
        message_bus.on("connected_users_updated", self._on_connected_users_updated)

    def _load_initial_data(self):
        """Load initial tournament and user data"""
        try:
            # Load active tournament
            active_tournament = self._tournament_manager.get_active_tournament()
            if active_tournament:
                self._current_tournament = active_tournament
                self._update_tournament_display()

            # Load connected users (from existing system)
            self._refresh_connected_users()

        except Exception as e:
            message_bus.publish(f"Error loading initial tournament data: {str(e)}", MessageLevel.ERROR)

    def _on_create_tournament(self, event):
        """Handle tournament creation"""
        tournament_name = self.tournament_name_ctrl.GetValue().strip()
        if not tournament_name:
            wx.MessageBox("Please enter a tournament name", "Error", wx.OK | wx.ICON_ERROR)
            return

        try:
            tournament_data = {
                "name": tournament_name,
                "participants": [],
                "teams": {},
                "created_by": self._config_manager.get("username", "unknown")
            }

            result = self._tournament_manager.create_tournament(tournament_data)

            if result["success"]:
                self._current_tournament = result["tournament"]
                self._update_tournament_display()
                self.tournament_name_ctrl.Clear()
                message_bus.publish(f"Tournament '{tournament_name}' created successfully", MessageLevel.INFO)
            else:
                wx.MessageBox(f"Failed to create tournament: {result.get('error', 'Unknown error')}",
                            "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error creating tournament: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_activate_tournament(self, event):
        """Handle tournament activation"""
        if not self._current_tournament:
            return

        try:
            result = self._tournament_manager.activate_tournament(self._current_tournament["id"])

            if result["success"]:
                self._current_tournament = result["tournament"]
                self._update_tournament_display()
                message_bus.publish("Tournament activated for combat event tagging", MessageLevel.INFO)
            else:
                wx.MessageBox(f"Failed to activate tournament: {result.get('error', 'Unknown error')}",
                            "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error activating tournament: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_move_to_team(self, event):
        """Move selected user from connected list to tournament team"""
        selected = self.connected_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a user to add to the tournament", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        if not self._current_tournament:
            wx.MessageBox("Please create a tournament first", "Error", wx.OK | wx.ICON_ERROR)
            return

        username = self.connected_list.GetItemText(selected, 0)
        team_name = self.team_choice.GetStringSelection()

        try:
            participant_data = {
                "username": username,
                "team": team_name
            }

            result = self._tournament_manager.add_participant(self._current_tournament["id"], participant_data)

            if result["success"]:
                self._current_tournament = result["tournament"]
                self._update_tournament_display()
                self._refresh_connected_users()
            else:
                wx.MessageBox(f"Failed to add participant: {result.get('error', 'Unknown error')}",
                            "Error", wx.OK | wx.ICON_ERROR)

        except Exception as e:
            wx.MessageBox(f"Error adding participant: {str(e)}", "Error", wx.OK | wx.ICON_ERROR)

    def _on_move_to_connected(self, event):
        """Move selected user from tournament team back to connected list"""
        selected = self.tournament_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Please select a participant to remove from the tournament", "Info", wx.OK | wx.ICON_INFORMATION)
            return

        username = self.tournament_list.GetItemText(selected, 0)

        # Implementation for removing participant would go here
        wx.MessageBox(f"Remove {username} from tournament (not implemented yet)", "Info", wx.OK | wx.ICON_INFORMATION)

    def _on_complete_tournament(self, event):
        """Handle tournament completion"""
        if not self._current_tournament:
            return

        result = wx.MessageBox("Are you sure you want to complete this tournament?",
                             "Confirm", wx.YES_NO | wx.ICON_QUESTION)

        if result == wx.YES:
            # Implementation for completing tournament would go here
            message_bus.publish("Tournament completion not implemented yet", MessageLevel.INFO)

    def _update_tournament_display(self):
        """Update UI with current tournament data"""
        if not self._current_tournament:
            self.status_text.SetLabel("No active tournament")
            self.activate_btn.Enable(False)
            self.complete_btn.Enable(False)
            self.tournament_list.DeleteAllItems()
            return

        tournament = self._current_tournament
        status = tournament.get("status", "unknown")
        name = tournament.get("name", "Unknown")

        self.status_text.SetLabel(f"Tournament: {name} ({status})")

        # Enable/disable buttons based on status
        self.activate_btn.Enable(status == "created")
        self.complete_btn.Enable(status == "active")

        # Update tournament participants list
        self.tournament_list.DeleteAllItems()
        participants = tournament.get("participants", [])
        teams = tournament.get("teams", {})

        for i, username in enumerate(participants):
            # Find user's team
            user_team = "Unknown"
            for team_name, team_members in teams.items():
                if username in team_members:
                    user_team = team_name
                    break

            index = self.tournament_list.InsertItem(i, username)
            self.tournament_list.SetItem(index, 1, user_team)
            self.tournament_list.SetItem(index, 2, "0")  # Score placeholder

    def _refresh_connected_users(self):
        """Refresh connected users list excluding tournament participants"""
        self.connected_list.DeleteAllItems()

        tournament_participants = []
        if self._current_tournament:
            tournament_participants = self._current_tournament.get("participants", [])

        for i, username in enumerate(self._connected_users):
            if username not in tournament_participants:
                index = self.connected_list.InsertItem(i, username)
                self.connected_list.SetItem(index, 1, "Available")

    def _on_tournament_created(self, event_data):
        """Handle tournament created event"""
        wx.CallAfter(self._update_tournament_display)

    def _on_tournament_activated(self, event_data):
        """Handle tournament activated event"""
        wx.CallAfter(self._update_tournament_display)

    def _on_participant_added(self, event_data):
        """Handle participant added event"""
        wx.CallAfter(self._update_tournament_display)
        wx.CallAfter(self._refresh_connected_users)

    def _on_corpse_detected(self, event_data):
        """Handle tournament corpse detected event"""
        corpse_count = 0  # Would get actual count from database
        wx.CallAfter(lambda: self.corpse_count_text.SetLabel(f"Corpses: {corpse_count}"))

    def _on_connected_users_updated(self, event_data):
        """Handle connected users list update"""
        self._connected_users = event_data.get("users", [])
        wx.CallAfter(self._refresh_connected_users)