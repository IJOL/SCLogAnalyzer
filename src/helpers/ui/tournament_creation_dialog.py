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

        # Right column
        right_sizer = wx.BoxSizer(wx.VERTICAL)

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

        # Team management section
        team_management_sizer = wx.BoxSizer(wx.VERTICAL)

        # Team selection
        team_label = wx.StaticText(self, label="Asignar a equipo:")
        team_label.SetForegroundColour(wx.Colour(255, 255, 255))
        self.team_choice = wx.Choice(self)

        # Team list management
        teams_label = wx.StaticText(self, label="Equipos:")
        teams_label.SetForegroundColour(wx.Colour(255, 255, 255))

        # Teams list
        self.teams_list = DarkListCtrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 80))
        self.teams_list.AppendColumn("Nombre del Equipo", width=120)

        # Team management buttons
        team_buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.add_team_btn = DarkThemeButton(self, label="+", size=(30, 25))
        self.add_team_btn.Bind(wx.EVT_BUTTON, self._on_add_team)

        self.edit_team_btn = DarkThemeButton(self, label="✎", size=(30, 25))
        self.edit_team_btn.Bind(wx.EVT_BUTTON, self._on_edit_team)

        self.delete_team_btn = DarkThemeButton(self, label="✗", size=(30, 25))
        self.delete_team_btn.Bind(wx.EVT_BUTTON, self._on_delete_team)

        team_buttons_sizer.Add(self.add_team_btn, 0, wx.ALL, 1)
        team_buttons_sizer.Add(self.edit_team_btn, 0, wx.ALL, 1)
        team_buttons_sizer.Add(self.delete_team_btn, 0, wx.ALL, 1)

        # Initialize default teams
        self._teams = ["Equipo Alfa", "Equipo Beta", "Equipo Gamma"]

        team_management_sizer.Add(team_label, 0, wx.ALL, 2)
        team_management_sizer.Add(self.team_choice, 0, wx.EXPAND | wx.ALL, 2)
        team_management_sizer.Add(teams_label, 0, wx.ALL, 2)
        team_management_sizer.Add(self.teams_list, 0, wx.EXPAND | wx.ALL, 2)
        team_management_sizer.Add(team_buttons_sizer, 0, wx.CENTER | wx.ALL, 2)

        buttons_sizer.Add(team_management_sizer, 0, wx.EXPAND | wx.ALL, 2)

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
        # Load default teams into UI
        self._refresh_teams_list()

        # If editing existing tournament, load its data
        if self._tournament_data:
            self._load_tournament_data()

        # Trigger presence sync to get current users via event
        self._trigger_users_update()

    def _on_users_online_updated(self, users_online):
        """Handle users online updates from message bus"""
        try:
            message_bus.publish(f"Raw users_online data: {users_online}", MessageLevel.DEBUG)

            # Extract usernames from users_online data
            self._connected_users = []
            for user in users_online:
                username = user.get('username', '')
                if username and username.strip():
                    self._connected_users.append(username)
                    message_bus.publish(f"Added user: {username}", MessageLevel.DEBUG)

            message_bus.publish(f"Final connected users list: {self._connected_users}", MessageLevel.DEBUG)

            # Refresh the connected users list on UI thread
            wx.CallAfter(self._refresh_connected_users_list)

        except Exception as e:
            message_bus.publish(f"Error updating connected users: {str(e)}", MessageLevel.ERROR)

    def _load_tournament_data(self):
        """Load existing tournament data for editing"""
        if not self._tournament_data:
            return

        # Fill form fields
        config = self._tournament_data.get("config", {})
        self.name_ctrl.SetValue(self._tournament_data.get("name", ""))
        self.desc_ctrl.SetValue(config.get("description", ""))
        self.max_ctrl.SetValue(config.get("max_participants", 16))

        # Load participants and teams
        participants = self._tournament_data.get("participants", [])
        teams = self._tournament_data.get("teams", {})

        # Convert to dict format {username: team}
        self._tournament_participants = {}
        for username in participants:
            # Find which team this user belongs to
            user_team = "Equipo Alfa"  # Default
            for team_name, team_members in teams.items():
                if username in team_members:
                    user_team = team_name
                    break
            self._tournament_participants[username] = user_team

        self._refresh_tournament_participants_list()
        self._refresh_connected_users_list()

    def _refresh_connected_users_list(self):
        """Refresh the connected users list excluding tournament participants"""
        message_bus.publish(f"Refreshing connected users list. Total users: {len(self._connected_users)}", MessageLevel.DEBUG)
        message_bus.publish(f"Tournament participants: {list(self._tournament_participants.keys())}", MessageLevel.DEBUG)

        self.connected_list.DeleteAllItems()

        display_count = 0
        for i, username in enumerate(self._connected_users):
            if username not in self._tournament_participants:
                index = self.connected_list.InsertItem(display_count, username)
                self.connected_list.SetItem(index, 1, "Disponible")
                display_count += 1
                message_bus.publish(f"Added to UI: {username}", MessageLevel.DEBUG)

        message_bus.publish(f"Total users displayed in list: {display_count}", MessageLevel.DEBUG)

    def _trigger_users_update(self):
        """Trigger presence sync to get current users via event"""
        from helpers.core.realtime_bridge import RealtimeBridge
        bridge = RealtimeBridge.get_instance()
        if bridge and 'general' in bridge.channels:
            bridge._handle_presence_sync(bridge.channels['general'])

    def _refresh_teams_list(self):
        """Refresh teams list and choice control"""
        # Update teams list
        self.teams_list.DeleteAllItems()
        for i, team_name in enumerate(self._teams):
            index = self.teams_list.InsertItem(i, team_name)

        # Update team choice dropdown
        self.team_choice.Clear()
        for team_name in self._teams:
            self.team_choice.Append(team_name)
        if self._teams:
            self.team_choice.SetSelection(0)

    def _on_add_team(self, event):
        """Add new team"""
        dialog = wx.TextEntryDialog(self, "Nombre del nuevo equipo:", "Agregar Equipo")
        if dialog.ShowModal() == wx.ID_OK:
            team_name = dialog.GetValue().strip()
            if team_name and team_name not in self._teams:
                self._teams.append(team_name)
                self._refresh_teams_list()
            elif team_name in self._teams:
                wx.MessageBox("Ya existe un equipo con ese nombre", "Error", wx.OK | wx.ICON_ERROR)
        dialog.Destroy()

    def _on_edit_team(self, event):
        """Edit selected team"""
        selected = self.teams_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Seleccione un equipo para editar", "Información", wx.OK | wx.ICON_INFORMATION)
            return

        old_name = self._teams[selected]
        dialog = wx.TextEntryDialog(self, "Nuevo nombre del equipo:", "Editar Equipo", old_name)
        if dialog.ShowModal() == wx.ID_OK:
            new_name = dialog.GetValue().strip()
            if new_name and new_name not in self._teams:
                # Update team name in teams list
                self._teams[selected] = new_name

                # Update existing participant assignments
                for username, team in self._tournament_participants.items():
                    if team == old_name:
                        self._tournament_participants[username] = new_name

                self._refresh_teams_list()
                self._refresh_tournament_participants_list()
            elif new_name in self._teams:
                wx.MessageBox("Ya existe un equipo con ese nombre", "Error", wx.OK | wx.ICON_ERROR)
        dialog.Destroy()

    def _on_delete_team(self, event):
        """Delete selected team"""
        selected = self.teams_list.GetFirstSelected()
        if selected == -1:
            wx.MessageBox("Seleccione un equipo para eliminar", "Información", wx.OK | wx.ICON_INFORMATION)
            return

        team_name = self._teams[selected]

        # Check if any participants are assigned to this team
        assigned_users = [user for user, team in self._tournament_participants.items() if team == team_name]
        if assigned_users:
            result = wx.MessageBox(f"El equipo '{team_name}' tiene {len(assigned_users)} participantes asignados.\n¿Desea eliminar el equipo y mover los participantes al primer equipo disponible?",
                                 "Confirmar eliminación", wx.YES_NO | wx.ICON_QUESTION)
            if result == wx.YES:
                # Move participants to first available team
                if len(self._teams) > 1:
                    new_team = self._teams[0] if selected != 0 else self._teams[1]
                    for user in assigned_users:
                        self._tournament_participants[user] = new_team
                else:
                    # If this is the last team, remove participants from tournament
                    for user in assigned_users:
                        del self._tournament_participants[user]
            else:
                return

        # Don't allow deleting if it's the last team and there are participants
        if len(self._teams) == 1 and self._tournament_participants:
            wx.MessageBox("No se puede eliminar el último equipo cuando hay participantes asignados",
                         "Error", wx.OK | wx.ICON_ERROR)
            return

        # Remove team
        del self._teams[selected]
        self._refresh_teams_list()
        self._refresh_tournament_participants_list()

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
                    "max_participants": max_participants
                }
            }

            if self._tournament_data:
                # Update existing tournament
                # TODO: Implement tournament update in manager
                message_bus.publish(f"Torneo '{tournament_name}' actualizado exitosamente", MessageLevel.INFO)
            else:
                # Create new tournament
                result = self._tournament_manager.create_tournament(tournament_data)

                if result["success"]:
                    message_bus.publish(f"Torneo '{tournament_name}' creado exitosamente", MessageLevel.INFO)
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
                "max_participants": self.max_ctrl.GetValue()
            }
        }