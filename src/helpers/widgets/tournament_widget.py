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

        # Debug panel with admin buttons (only visible in debug mode)
        self.debug_panel = wx.Panel(self)
        debug_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Create tournament button
        self.create_btn = DarkThemeButton(self.debug_panel, label="Crear Torneo")
        self.create_btn.Bind(wx.EVT_BUTTON, self._on_create_tournament)
        debug_sizer.Add(self.create_btn, 0, wx.ALL, 2)

        # Edit tournament button
        self.edit_btn = DarkThemeButton(self.debug_panel, label="Editar")
        self.edit_btn.Bind(wx.EVT_BUTTON, self._on_edit_tournament)
        self.edit_btn.Enable(False)
        debug_sizer.Add(self.edit_btn, 0, wx.ALL, 2)

        # Delete tournament button
        self.delete_btn = DarkThemeButton(self.debug_panel, label="Borrar")
        self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete_tournament)
        self.delete_btn.Enable(False)
        debug_sizer.Add(self.delete_btn, 0, wx.ALL, 2)

        self.debug_panel.SetSizer(debug_sizer)
        self.debug_panel.Show(message_bus.is_debug_mode())
        button_sizer.Add(self.debug_panel, 0, wx.ALL, 2)

        # Operational buttons (always visible)
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
        self.participants_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_participant_selected)
        participants_sizer.Add(self.participants_list, 1, wx.EXPAND | wx.ALL, 2)

        # Player details panel (right)
        player_details_sizer = wx.BoxSizer(wx.VERTICAL)

        # Tournament status at top
        self.status_text = wx.StaticText(self, label="Sin torneo seleccionado")
        self.status_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.status_text, 0, wx.ALL, 2)

        self.corpse_count_text = wx.StaticText(self, label="Bajas: 0")
        self.corpse_count_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.corpse_count_text, 0, wx.ALL, 2)

        # Player details section
        player_details_label = wx.StaticText(self, label="Detalles del Jugador:")
        player_details_label.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(player_details_label, 0, wx.ALL, 2)

        # Selected player name
        self.selected_player_text = wx.StaticText(self, label="Selecciona un jugador para ver detalles")
        self.selected_player_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.selected_player_text, 0, wx.ALL, 2)

        # Player history list
        self.player_history_list = DarkListCtrl(self, style=wx.LC_REPORT)
        self.player_history_list.AppendColumn("Fecha", width=80)
        self.player_history_list.AppendColumn("Evento", width=60)
        self.player_history_list.AppendColumn("Objetivo", width=100)
        self.player_history_list.AppendColumn("Lugar", width=80)
        player_details_sizer.Add(self.player_history_list, 1, wx.EXPAND | wx.ALL, 2)

        # Player stats summary
        self.player_stats_text = wx.StaticText(self, label="")
        self.player_stats_text.SetForegroundColour(wx.Colour(255, 255, 255))
        player_details_sizer.Add(self.player_stats_text, 0, wx.ALL, 2)

        # Complete tournament button at bottom
        self.complete_btn = DarkThemeButton(self, label="Finalizar Torneo")
        self.complete_btn.Bind(wx.EVT_BUTTON, self._on_complete_tournament)
        self.complete_btn.Enable(False)
        player_details_sizer.Add(self.complete_btn, 0, wx.ALL, 2)

        # Add to main sizer
        sizer.Add(participants_sizer, 1, wx.EXPAND | wx.ALL, 2)
        sizer.Add(player_details_sizer, 1, wx.EXPAND | wx.ALL, 2)

        return sizer

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
            self.activate_btn.Enable(tournament_status == "creado")
            self.complete_btn.Enable(tournament_status == "activo")

            # Update displays
            self._update_selected_tournament_display(tournament_name)
        else:
            self.edit_btn.Enable(False)
            self.delete_btn.Enable(False)
            self.activate_btn.Enable(False)
            self.complete_btn.Enable(False)

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
                message_bus.publish(f"Torneo '{tournament_name}' eliminado", MessageLevel.INFO)
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

        try:
            # Load all tournaments from database
            tournaments = self._tournament_manager.get_all_tournaments()

            status_translations = {
                "created": "creado",
                "active": "activo",
                "completed": "completado",
                "cancelled": "cancelado"
            }

            for i, tournament in enumerate(tournaments):
                status_spanish = status_translations.get(tournament.get("status", ""), "desconocido")

                index = self.tournaments_list.InsertItem(i, tournament.get("name", ""))
                self.tournaments_list.SetItem(index, 1, status_spanish)
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
            message_bus.publish(f"Error loading tournaments: {str(e)}", MessageLevel.ERROR)

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
                return

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

        except Exception as e:
            message_bus.publish(f"Error updating tournament display: {str(e)}", MessageLevel.ERROR)
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
            message_bus.publish(f"Error loading team details: {str(e)}", MessageLevel.ERROR)
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
            message_bus.publish(f"Error loading player details: {str(e)}", MessageLevel.ERROR)
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
            message_bus.publish(f"Error getting player combat history: {str(e)}", MessageLevel.ERROR)
            return []

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