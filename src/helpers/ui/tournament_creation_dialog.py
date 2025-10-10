import wx
from typing import Dict, Any, List
from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.tournament.tournament_manager import TournamentManager
from helpers.ui.ui_components import DarkThemeButton
from helpers.widgets.dark_listctrl import DarkListCtrl

class TournamentCreationDialog(wx.Dialog):

    """Modal dialog for creating and editing tournaments"""

    def __init__(self, parent, tournament_data=None):
        super().__init__(parent, title="Gestión de Torneo",
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self._tournament_manager = TournamentManager()
        self._config_manager = get_config_manager(in_gui=True)
        self._tournament_data = tournament_data
        self._connected_users = []
        self._tournament_participants = {}  # Changed to dict: {username: team}

        self._create_ui()
        self.SetSize((800, 600))
        self.CenterOnParent()

        # Apply dark theme
        self.SetBackgroundColour(wx.Colour(80, 80, 80))

        # Load initial data
        self._load_initial_data()

        # Subscribe to future updates y guardar el subscription_id
        self._users_online_subscription_id = message_bus.on("users_online_updated", self._on_users_online_updated)

    def Destroy(self):
        message_bus.off(self._users_online_subscription_id)
        return super().Destroy()

    def _create_ui(self):
        """Create dialog interface"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Title
        title = wx.StaticText(self, label="Gestión de Torneo")
        title_font = title.GetFont()
        title_font.SetPointSize(14)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        title.SetForegroundColour(wx.Colour(255, 255, 255))
        main_sizer.Add(title, 0, wx.CENTER | wx.ALL, 10)

        # Tournament configuration section
        config_section = self._create_config_section()
        main_sizer.Add(config_section, 0, wx.EXPAND | wx.ALL, 5)

        # Dual-list interface for participants
        participants_section = self._create_participants_section()
        main_sizer.Add(participants_section, 1, wx.EXPAND | wx.ALL, 5)

        # Buttons
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.save_btn = DarkThemeButton(self, id=wx.ID_OK, label="Guardar")
        self.save_btn.Bind(wx.EVT_BUTTON, self._on_save)

        self.cancel_btn = DarkThemeButton(self, id=wx.ID_CANCEL, label="Cancelar")

        button_sizer.Add(self.save_btn, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)

        self.SetSizer(main_sizer)

    def _create_config_section(self) -> wx.StaticBoxSizer:
        """Create tournament configuration section"""
        box = wx.StaticBox(self, label="Configuración del Torneo")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Left column
        left_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament name
        name_label = wx.StaticText(self, label="Nombre:")
        name_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.name_ctrl = wx.TextCtrl(self, size=(200, -1))
        left_sizer.Add(name_label, 0, wx.ALL, 2)
        left_sizer.Add(self.name_ctrl, 0, wx.EXPAND | wx.ALL, 2)

        # Tournament description
        desc_label = wx.StaticText(self, label="Descripción:")
        desc_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.desc_ctrl = wx.TextCtrl(self, size=(200, 60), style=wx.TE_MULTILINE)
        left_sizer.Add(desc_label, 0, wx.ALL, 2)
        left_sizer.Add(self.desc_ctrl, 1, wx.EXPAND | wx.ALL, 2)

        # Teams list (simple text field with pipe-separated names)
        teams_label = wx.StaticText(self, label="Equipos (separados por |):")
        teams_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.teams_ctrl = wx.TextCtrl(self, size=(200, -1))
        self.teams_ctrl.SetValue("Equipo Alfa|Equipo Beta|Equipo Gamma")
        self.teams_ctrl.Bind(wx.EVT_TEXT, self._on_teams_text_changed)
        left_sizer.Add(teams_label, 0, wx.ALL, 2)
        left_sizer.Add(self.teams_ctrl, 0, wx.EXPAND | wx.ALL, 2)

        # Right column
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament type - use table names directly as modes
        type_label = wx.StaticText(self, label="Modo de Batalla:")
        type_label.SetForegroundColour(wx.Colour(255, 255, 255))

        # Available combat tables as tournament modes
        combat_tables = [
            "sc_default",
            "ea_squadronbattle",
            "ea_freeflight",
            "ea_fpskillconfirmed",
            "ea_fpsgungame",
            "ea_tonkroyale_teambattle"
        ]

        self.type_choice = wx.Choice(self, choices=combat_tables)
        self.type_choice.SetSelection(0)  # Default to "sc_default"
        right_sizer.Add(type_label, 0, wx.ALL, 2)
        right_sizer.Add(self.type_choice, 0, wx.EXPAND | wx.ALL, 2)

        # Max participants
        max_label = wx.StaticText(self, label="Máximo Participantes:")
        max_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.max_ctrl = wx.SpinCtrl(self, value="16", min=2, max=100)
        right_sizer.Add(max_label, 0, wx.ALL, 2)
        right_sizer.Add(self.max_ctrl, 0, wx.ALL, 2)

        sizer.Add(left_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(right_sizer, 0, wx.ALL, 5)

        return sizer

    def _create_participants_section(self) -> wx.StaticBoxSizer:
        """Create dual-list interface for participants management"""
        box = wx.StaticBox(self, label="Gestión de Participantes")
        box.SetBackgroundColour(wx.Colour(80, 80, 80))
        box.SetForegroundColour(wx.Colour(255, 255, 255))
        sizer = wx.StaticBoxSizer(box, wx.HORIZONTAL)

        # Connected users list
        connected_box = wx.StaticBox(self, label="Usuarios Conectados")
        connected_box.SetBackgroundColour(wx.Colour(80, 80, 80))
        connected_box.SetForegroundColour(wx.Colour(255, 255, 255))
        connected_sizer = wx.StaticBoxSizer(connected_box, wx.VERTICAL)

        self.connected_list = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.connected_list.AppendColumn("Usuario", width=120)
        self.connected_list.AppendColumn("Estado", width=80)
        connected_sizer.Add(self.connected_list, 1, wx.EXPAND | wx.ALL, 2)

        # Move buttons
        buttons_sizer = wx.BoxSizer(wx.VERTICAL)

        self.move_to_tournament_btn = DarkThemeButton(self, label="→ Agregar")
        self.move_to_tournament_btn.Bind(wx.EVT_BUTTON, self._on_move_to_tournament)

        self.move_to_connected_btn = DarkThemeButton(self, label="← Quitar")
        self.move_to_connected_btn.Bind(wx.EVT_BUTTON, self._on_move_to_connected)

        buttons_sizer.Add(self.move_to_tournament_btn, 0, wx.CENTER | wx.ALL, 2)
        buttons_sizer.Add(self.move_to_connected_btn, 0, wx.CENTER | wx.ALL, 2)

        # Team selection (simple dropdown from teams text field)
        team_label = wx.StaticText(self, label="Asignar a equipo:")
        team_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.team_choice = wx.Choice(self)

        buttons_sizer.Add(team_label, 0, wx.ALL, 2)
        buttons_sizer.Add(self.team_choice, 0, wx.EXPAND | wx.ALL, 2)

        # Tournament participants list
        tournament_box = wx.StaticBox(self, label="Participantes del Torneo")
        tournament_box.SetBackgroundColour(wx.Colour(80, 80, 80))
        tournament_box.SetForegroundColour(wx.Colour(255, 255, 255))
        tournament_sizer = wx.StaticBoxSizer(tournament_box, wx.VERTICAL)

        self.tournament_list = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self.tournament_list.AppendColumn("Usuario", width=120)
        self.tournament_list.AppendColumn("Equipo", width=80)
        tournament_sizer.Add(self.tournament_list, 1, wx.EXPAND | wx.ALL, 2)

        # Assemble dual-list layout
        sizer.Add(connected_sizer, 1, wx.EXPAND | wx.ALL, 5)
        sizer.Add(buttons_sizer, 0, wx.CENTER | wx.ALL, 5)
        sizer.Add(tournament_sizer, 1, wx.EXPAND | wx.ALL, 5)

        return sizer

    def _load_initial_data(self):
        """Load initial data for the dialog"""
        # Load teams from text field into choice control
        self._refresh_teams_choice()

        # If editing existing tournament, load its data
        if self._tournament_data:
            self._load_tournament_data()

        # Trigger presence sync to get current users via event
        self._trigger_users_update()

    def _refresh_teams_choice(self):
        """Refresh team choice control from teams text field"""
        # Get teams from text field
        teams_text = self.teams_ctrl.GetValue().strip()
        teams = [team.strip() for team in teams_text.split('|') if team.strip()]

        # Update choice control
        self.team_choice.Clear()
        for team in teams:
            self.team_choice.Append(team)

        # Select first team by default
        if teams:
            self.team_choice.SetSelection(0)

    def _on_teams_text_changed(self, event):
        """Handle teams text field changes to update choice control"""
        self._refresh_teams_choice()

    def _on_users_online_updated(self, users_online):
        """Handle users online updates from message bus"""
        try:

            # Extract usernames from users_online data
            self._connected_users = []
            for user in users_online:
                username = user.get('username', '')
                if username and username.strip():
                    self._connected_users.append(username)

            # Refresh the connected users list on UI thread
            wx.CallAfter(self._refresh_connected_users_list)

        except Exception as e:
            message_bus.publish(content=f"Error updating connected users: {str(e)}", level=MessageLevel.ERROR)

    def _load_tournament_data(self):
        """Load existing tournament data for editing"""
        if not self._tournament_data:
            return

        # Fill form fields
        config = self._tournament_data.get("config", {})
        self.name_ctrl.SetValue(self._tournament_data.get("name", ""))
        self.desc_ctrl.SetValue(config.get("description", ""))
        self.max_ctrl.SetValue(config.get("max_participants", 16))

        # Set tournament type (table name)
        tournament_type = config.get("tournament_type", "sc_default")
        try:
            type_index = self.type_choice.FindString(tournament_type)
            if type_index != wx.NOT_FOUND:
                self.type_choice.SetSelection(type_index)
        except:
            self.type_choice.SetSelection(0)  # Default to first option

        # Load participants and teams
        participants = self._tournament_data.get("participants", [])
        teams = self._tournament_data.get("teams", {})

        # Load custom teams from tournament data into text field
        if teams:
            teams_text = "|".join(teams.keys())
            self.teams_ctrl.SetValue(teams_text)

        # Refresh teams choice control
        self._refresh_teams_choice()

        # Convert to dict format {username: team}
        self._tournament_participants = {}

        # Get teams from text field
        teams_text = self.teams_ctrl.GetValue().strip()
        teams_list = [team.strip() for team in teams_text.split('|') if team.strip()]

        for username in participants:
            # Find which team this user belongs to
            user_team = teams_list[0] if teams_list else "Equipo Alfa"  # Default to first team
            for team_name, team_members in teams.items():
                if username in team_members:
                    user_team = team_name
                    break
            self._tournament_participants[username] = user_team

        self._refresh_tournament_participants_list()
        self._refresh_connected_users_list()

    def _refresh_connected_users_list(self):
        """Refresh the connected users list excluding tournament participants"""
        # Check if dialog is still valid
        try:
            if not self.connected_list:
                return
        except RuntimeError:
            # Dialog has been destroyed, ignore
            return


        try:
            self.connected_list.DeleteAllItems()

            display_count = 0
            for i, username in enumerate(self._connected_users):
                if username not in self._tournament_participants:
                    index = self.connected_list.InsertItem(display_count, username)
                    self.connected_list.SetItem(index, 1, "Disponible")
                    display_count += 1
        except RuntimeError:
            # Dialog has been destroyed, ignore
            pass

    def _trigger_users_update(self):
        """Load current connected users from RealtimeBridge (for modal dialog)"""
        from helpers.core.realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge:
            users = bridge.get_connected_users()
            self._connected_users = [u['username'] for u in users if u.get('username')]
            wx.CallAfter(self._refresh_connected_users_list)



    def _refresh_tournament_participants_list(self):
        """Refresh the tournament participants list"""
        self.tournament_list.DeleteAllItems()

        for i, (username, team) in enumerate(self._tournament_participants.items()):
            index = self.tournament_list.InsertItem(i, username)
            self.tournament_list.SetItem(index, 1, team)

    def _on_move_to_tournament(self, event):
        """Move selected user from connected list to tournament"""
        selected = self.connected_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Por favor seleccione un usuario para agregar al torneo",
                         "Información", wx.OK | wx.ICON_INFORMATION)
            return

        username = self.connected_list.GetItemText(selected, 0)

        # Check max participants
        max_participants = self.max_ctrl.GetValue()
        if len(self._tournament_participants) >= max_participants:
            wx.MessageBox(f"Se ha alcanzado el máximo de {max_participants} participantes",
                         "Límite alcanzado", wx.OK | wx.ICON_WARNING)
            return

        # Get selected team
        selected_team = self.team_choice.GetStringSelection()
        if not selected_team:
            selected_team = "Equipo Alfa"  # Default

        # Add to tournament with selected team
        self._tournament_participants[username] = selected_team

        # Refresh both lists
        self._refresh_connected_users_list()
        self._refresh_tournament_participants_list()

    def _on_move_to_connected(self, event):
        """Move selected user from tournament back to connected list"""
        selected = self.tournament_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Por favor seleccione un participante para quitar del torneo",
                         "Información", wx.OK | wx.ICON_INFORMATION)
            return

        username = self.tournament_list.GetItemText(selected, 0)

        # Remove from tournament
        if username in self._tournament_participants:
            del self._tournament_participants[username]

        # Refresh both lists
        self._refresh_connected_users_list()
        self._refresh_tournament_participants_list()

    def _on_save(self, event):
        """Handle tournament save (create or update)"""
        tournament_name = self.name_ctrl.GetValue().strip()
        description = self.desc_ctrl.GetValue().strip()
        max_participants = self.max_ctrl.GetValue()

        if not tournament_name:
            wx.MessageBox("Por favor ingrese un nombre para el torneo",
                         "Error", wx.OK | wx.ICON_ERROR)
            return

        try:
            # Get selected tournament type (table name)
            tournament_type = self.type_choice.GetStringSelection()
            if not tournament_type:
                tournament_type = "sc_default"  # Default fallback

            # Build teams structure from participant assignments
            teams = {}
            participants_list = []

            for username, team_name in self._tournament_participants.items():
                participants_list.append(username)
                if team_name not in teams:
                    teams[team_name] = []
                teams[team_name].append(username)

            tournament_data = {
                "name": tournament_name,
                "participants": participants_list,
                "teams": teams,
                "created_by": self._config_manager.get("username", "unknown"),
                "config": {
                    "description": description,
                    "max_participants": max_participants,
                    "tournament_type": tournament_type
                }
            }

            if self._tournament_data:
                # Update existing tournament
                # TODO: Implement tournament update in manager
                message_bus.publish(content=f"Torneo '{tournament_name}' actualizado exitosamente", level=MessageLevel.INFO)
            else:
                # Create new tournament
                result = self._tournament_manager.create_tournament(tournament_data)

                if result["success"]:
                    message_bus.publish(content=f"Torneo '{tournament_name}' creado exitosamente", level=MessageLevel.INFO)
                else:
                    wx.MessageBox(f"Error al crear torneo: {result.get('error', 'Error desconocido')}",
                                 "Error", wx.OK | wx.ICON_ERROR)
                    return

            self.EndModal(wx.ID_OK)

        except Exception as e:
            wx.MessageBox(f"Error al guardar torneo: {str(e)}",
                         "Error", wx.OK | wx.ICON_ERROR)

    def get_tournament_data(self) -> Dict[str, Any]:
        """Get tournament data from form"""
        # Get selected tournament type (table name)
        tournament_type = self.type_choice.GetStringSelection()
        if not tournament_type:
            tournament_type = "sc_default"  # Default fallback

        # Build teams structure from participant assignments
        teams = {}
        participants_list = []

        for username, team_name in self._tournament_participants.items():
            participants_list.append(username)
            if team_name not in teams:
                teams[team_name] = []
            teams[team_name].append(username)

        return {
            "name": self.name_ctrl.GetValue().strip(),
            "participants": participants_list,
            "teams": teams,
            "config": {
                "description": self.desc_ctrl.GetValue().strip(),
                "max_participants": self.max_ctrl.GetValue(),
                "tournament_type": tournament_type
            }
        }