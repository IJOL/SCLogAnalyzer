#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import wx
import wx.richtext
from datetime import datetime

from helpers.core.message_bus import message_bus, MessageLevel
from helpers.core.config_utils import get_config_manager
from helpers.core.realtime_bridge import RealtimeBridge
from helpers.widgets.dark_listctrl import DarkListCtrl
from helpers.ui.ui_components import DarkThemeButton


class ChatWidget(wx.Panel):
    """
    Chat widget con interfaz de tres paneles para comunicación en tiempo real.
    Basado en POC validado chat_complete_poc.py con tema oscuro consistente.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.config_manager = get_config_manager()

        # Estado del chat
        self.chat_sessions = {}  # {chat_name: [messages]}
        self.current_chat = None
        self._connected_users = []  # Lista de usuarios conectados reales

        # RealtimeBridge para sincronización
        self.realtime_bridge = RealtimeBridge.get_instance()

        # Aplicar tema oscuro base
        self.SetBackgroundColour(wx.Colour(45, 45, 50))

        # Crear la interfaz
        self._create_ui()

        # Configurar eventos
        self._setup_events()
        self._setup_realtime_events()

        # Disparar actualización inicial de usuarios conectados
        self._trigger_users_update()

    def _create_ui(self):
        """Crear la interfaz de usuario usando layout POC-validado"""
        # Panel izquierdo: Lista de chats
        self.left_panel = wx.Panel(self)
        self.left_panel.SetBackgroundColour(wx.Colour(50, 50, 55))

        # Panel derecho superior: Mensajes
        self.messages_panel = wx.Panel(self)
        self.messages_panel.SetBackgroundColour(wx.Colour(40, 45, 50))

        # Panel derecho inferior: Input
        self.input_panel = wx.Panel(self)
        self.input_panel.SetBackgroundColour(wx.Colour(35, 40, 45))

        # Crear controles
        self._create_chat_list()
        self._create_message_history()
        self._create_input_area()

        # Layout usando sizers validados del POC
        self._setup_layout()

    def _create_chat_list(self):
        """Crear lista de chats usando DarkListCtrl"""
        # Título del panel
        chat_title = wx.StaticText(self.left_panel, label="Chats")
        chat_title.SetForegroundColour(wx.Colour(240, 240, 240))
        font = chat_title.GetFont()
        font.SetPointSize(10)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        chat_title.SetFont(font)

        # Lista de chats con DarkListCtrl
        self.chat_list = DarkListCtrl(
            self.left_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL,
            auto_sizing=False  # Control manual del ancho
        )

        # Configurar columnas
        self.chat_list.InsertColumn(0, "Chat", width=180)
        self.chat_list.InsertColumn(1, "Unread", width=50)

        # Botón para nuevo chat
        self.new_chat_button = DarkThemeButton(self.left_panel, label="+ New Chat")

        # Layout del panel izquierdo
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_sizer.Add(chat_title, 0, wx.ALL, 5)
        left_sizer.Add(self.chat_list, 1, wx.EXPAND | wx.ALL, 5)
        left_sizer.Add(self.new_chat_button, 0, wx.EXPAND | wx.ALL, 5)
        self.left_panel.SetSizer(left_sizer)

        # Agregar canal @all por defecto
        self._add_default_chats()

    def _create_message_history(self):
        """Crear historial de mensajes con RichTextCtrl"""
        # Título del panel
        messages_title = wx.StaticText(self.messages_panel, label="Messages")
        messages_title.SetForegroundColour(wx.Colour(240, 240, 240))
        font = messages_title.GetFont()
        font.SetPointSize(10)
        font.SetWeight(wx.FONTWEIGHT_BOLD)
        messages_title.SetFont(font)

        # Historial de mensajes
        self.message_history = wx.richtext.RichTextCtrl(
            self.messages_panel,
            style=wx.richtext.RE_READONLY | wx.richtext.RE_MULTILINE
        )

        # Aplicar colores POC-validados
        self.message_history.SetBackgroundColour(wx.Colour(30, 30, 35))
        self.message_history.SetForegroundColour(wx.Colour(255, 255, 255))

        # Layout del panel de mensajes
        messages_sizer = wx.BoxSizer(wx.VERTICAL)
        messages_sizer.Add(messages_title, 0, wx.ALL, 5)
        messages_sizer.Add(self.message_history, 1, wx.EXPAND | wx.ALL, 5)
        self.messages_panel.SetSizer(messages_sizer)

        # Mensaje de bienvenida
        self._show_welcome_message()

    def _create_input_area(self):
        """Crear área de input con contador de caracteres"""
        # Input de texto
        self.text_input = wx.TextCtrl(
            self.input_panel,
            style=wx.TE_MULTILINE,
            size=(-1, 60)
        )
        self.text_input.SetBackgroundColour(wx.Colour(80, 80, 80))
        self.text_input.SetForegroundColour(wx.Colour(255, 255, 255))

        # Contador de caracteres
        self.char_counter = wx.StaticText(self.input_panel, label="200")
        self.char_counter.SetForegroundColour(wx.Colour(150, 150, 150))

        # Botón enviar usando DarkThemeButton
        self.send_button = DarkThemeButton(self.input_panel, label="Send")

        # Layout del input
        input_sizer = wx.BoxSizer(wx.HORIZONTAL)
        input_sizer.Add(self.text_input, 1, wx.EXPAND | wx.ALL, 5)
        input_sizer.Add(self.char_counter, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        input_sizer.Add(self.send_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
        self.input_panel.SetSizer(input_sizer)

    def _setup_layout(self):
        """Configurar layout principal usando sizers POC-validados"""
        # Sizer principal horizontal
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Panel izquierdo (30% del ancho) - con tamaño mínimo
        self.left_panel.SetMinSize((200, 300))  # Ancho mínimo para la lista de chats
        main_sizer.Add(self.left_panel, 1, wx.EXPAND | wx.ALL, 5)

        # Sizer vertical para el lado derecho
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Panel de mensajes con tamaño mínimo
        self.messages_panel.SetMinSize((300, 200))  # Área mínima para ver mensajes
        right_sizer.Add(self.messages_panel, 3, wx.EXPAND | wx.ALL, 5)  # 75% de la altura

        # Panel de input con tamaño fijo mínimo
        self.input_panel.SetMinSize((300, 80))  # Altura fija para el input
        right_sizer.Add(self.input_panel, 0, wx.EXPAND | wx.ALL, 5)  # Tamaño fijo en lugar de proporción

        # Agregar sizer derecho al principal (70% del ancho)
        main_sizer.Add(right_sizer, 2, wx.EXPAND)

        # Establecer tamaño mínimo del widget completo
        self.SetMinSize((520, 400))  # Tamaño mínimo total
        self.SetSizer(main_sizer)

    def _setup_events(self):
        """Configurar eventos de la interfaz y MessageBus"""
        # Eventos UI
        self.chat_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_chat_selected)
        self.text_input.Bind(wx.EVT_TEXT, self._on_text_changed)
        self.text_input.Bind(wx.EVT_KEY_DOWN, self._on_key_down)  # Manejar Enter y Shift+Enter
        self.send_button.Bind(wx.EVT_BUTTON, self._on_send_message)
        self.new_chat_button.Bind(wx.EVT_BUTTON, self._on_new_chat)

        # Eventos MessageBus
        message_bus.on("chat_message_received", self._on_message_received)
        message_bus.on("chat_user_joined", self._on_user_joined)
        message_bus.on("chat_user_left", self._on_user_left)
        message_bus.on("users_online_updated", self._on_users_online_updated)

    def _add_default_chats(self):
        """Agregar chats por defecto"""
        # Canal @all siempre presente
        self._add_chat_to_list("@all", 0, False)

        # Inicializar sesión @all
        self.chat_sessions["@all"] = []

    def _add_chat_to_list(self, chat_name, unread_count, has_unread):
        """Agregar chat a la lista con coloreo POC-validado"""
        index = self.chat_list.InsertItem(self.chat_list.GetItemCount(), chat_name)
        self.chat_list.SetItem(index, 1, str(unread_count) if unread_count > 0 else "")

        # Aplicar colores POC-validados para mensajes no leídos
        if has_unread:
            self.chat_list.SetItemBackgroundColour(index, wx.Colour(45, 85, 140))
            self.chat_list.SetItemTextColour(index, wx.Colour(255, 255, 255))

    def _show_welcome_message(self):
        """Mostrar mensaje de bienvenida"""
        self.message_history.Clear()

        # Header en blanco y negrita
        self.message_history.BeginTextColour(wx.Colour(255, 255, 255))
        self.message_history.BeginBold()
        self.message_history.WriteText("=== Chat Widget ===\n\n")
        self.message_history.EndBold()
        self.message_history.EndTextColour()

        # Mensaje de instrucciones
        self.message_history.BeginTextColour(wx.Colour(200, 200, 200))
        self.message_history.WriteText("Select a chat from the list to start messaging.\n")
        self.message_history.WriteText("The @all channel broadcasts to all connected users.")
        self.message_history.EndTextColour()

    def _on_chat_selected(self, event):
        """Manejar selección de chat"""
        selection = event.GetIndex()
        chat_name = self.chat_list.GetItemText(selection, 0)
        self.current_chat = chat_name

        # Actualizar historial de mensajes
        self._load_chat_messages(chat_name)

        # Marcar como leído
        self._mark_chat_as_read(selection)

    def _load_chat_messages(self, chat_name):
        """Cargar mensajes del chat seleccionado"""
        self.message_history.Clear()

        # Header del chat
        self.message_history.BeginTextColour(wx.Colour(255, 255, 255))
        self.message_history.BeginBold()
        self.message_history.WriteText(f"=== {chat_name} ===\n\n")
        self.message_history.EndBold()
        self.message_history.EndTextColour()

        # Mostrar mensajes si existen
        if chat_name in self.chat_sessions:
            for message in self.chat_sessions[chat_name]:
                self._display_message(message)

    def _display_message(self, message):
        """Mostrar un mensaje con formato POC-validado"""
        sender = message.get('sender', 'Unknown')
        text = message.get('text', '')
        timestamp = message.get('timestamp', datetime.now().strftime("%H:%M"))

        # Timestamp
        self.message_history.BeginTextColour(wx.Colour(150, 150, 150))
        self.message_history.WriteText(f"[{timestamp}] ")
        self.message_history.EndTextColour()

        # Sender con color POC-validado
        if sender == "You":
            color = wx.Colour(100, 200, 100)  # Verde
        elif sender == "System":
            color = wx.Colour(255, 165, 100)  # Naranja
        else:
            color = wx.Colour(100, 150, 255)  # Azul

        self.message_history.BeginTextColour(color)
        self.message_history.BeginBold()
        self.message_history.WriteText(f"{sender}: ")
        self.message_history.EndBold()
        self.message_history.EndTextColour()

        # Mensaje en blanco
        self.message_history.BeginTextColour(wx.Colour(255, 255, 255))
        self.message_history.WriteText(f"{text}\n")
        self.message_history.EndTextColour()

    def _mark_chat_as_read(self, item_index):
        """Marcar chat como leído (remover coloreo)"""
        self.chat_list.SetItemBackgroundColour(item_index, wx.NullColour)
        self.chat_list.SetItemTextColour(item_index, wx.NullColour)
        self.chat_list.SetItem(item_index, 1, "")  # Limpiar contador

    def _on_text_changed(self, event):
        """Actualizar contador de caracteres"""
        text = self.text_input.GetValue()
        remaining = 200 - len(text)
        self.char_counter.SetLabel(str(remaining))

        # Cambiar color si excede límite
        if remaining < 0:
            self.char_counter.SetForegroundColour(wx.Colour(255, 100, 100))
        else:
            self.char_counter.SetForegroundColour(wx.Colour(150, 150, 150))

        # Prevenir input más allá de 200 caracteres
        if len(text) > 200:
            self.text_input.SetValue(text[:200])
            self.text_input.SetInsertionPointEnd()

    def _on_key_down(self, event):
        """Manejar teclas Enter y Shift+Enter"""
        keycode = event.GetKeyCode()

        if keycode == wx.WXK_RETURN:
            if event.ShiftDown():
                # Shift+Enter: Nueva línea (comportamiento por defecto)
                event.Skip()
            else:
                # Enter solo: Enviar mensaje
                self._on_send_message(event)
        else:
            # Otras teclas: comportamiento normal
            event.Skip()

    def _on_send_message(self, event):
        """Manejar envío de mensaje"""
        text = self.text_input.GetValue().strip()

        if not text or not self.current_chat:
            return

        # Crear mensaje
        message = {
            'sender': 'You',
            'text': text,
            'timestamp': datetime.now().strftime("%H:%M")
        }

        # Agregar a la sesión actual
        if self.current_chat not in self.chat_sessions:
            self.chat_sessions[self.current_chat] = []

        self.chat_sessions[self.current_chat].append(message)

        # Mostrar mensaje
        self._display_message(message)

        # Limpiar input
        self.text_input.Clear()
        self.char_counter.SetLabel("200")
        self.char_counter.SetForegroundColour(wx.Colour(150, 150, 150))

        # Enviar mensaje vía RealtimeBridge
        self._send_realtime_message(message)

        # Emitir evento a través de MessageBus
        message_bus.emit("chat_message_sent", {
            'chat': self.current_chat,
            'message': message,
            'sender': 'local_user'
        })

        message_bus.publish(f"Chat message sent to {self.current_chat}", MessageLevel.INFO)

    def _on_message_received(self, event_data):
        """Manejar mensaje recibido vía MessageBus"""
        chat_name = event_data.get('chat')
        message = event_data.get('message')
        sender = event_data.get('sender')

        if not chat_name or not message:
            return

        # Agregar mensaje a la sesión
        if chat_name not in self.chat_sessions:
            self.chat_sessions[chat_name] = []
            self._add_chat_to_list(chat_name, 1, True)  # Nuevo chat con mensaje no leído

        self.chat_sessions[chat_name].append(message)

        # Si es el chat actual, mostrar mensaje inmediatamente
        if self.current_chat == chat_name:
            self._display_message(message)
        else:
            # Marcar como no leído
            self._mark_chat_unread(chat_name)

    def _on_user_joined(self, event_data):
        """Manejar usuario que se une al chat"""
        username = event_data.get('username')
        if username:
            message_bus.publish(f"User {username} joined chat", MessageLevel.INFO)

    def _on_user_left(self, event_data):
        """Manejar usuario que abandona el chat"""
        username = event_data.get('username')
        if username:
            message_bus.publish(f"User {username} left chat", MessageLevel.INFO)

    def _mark_chat_unread(self, chat_name):
        """Marcar chat como no leído"""
        for i in range(self.chat_list.GetItemCount()):
            if self.chat_list.GetItemText(i, 0) == chat_name:
                # Contar mensajes no leídos
                unread_count = sum(1 for msg in self.chat_sessions.get(chat_name, [])
                                 if msg.get('sender') != 'You')

                self.chat_list.SetItem(i, 1, str(unread_count))
                self.chat_list.SetItemBackgroundColour(i, wx.Colour(45, 85, 140))
                self.chat_list.SetItemTextColour(i, wx.Colour(255, 255, 255))
                break

    def _send_realtime_message(self, message):
        """Enviar mensaje a través de RealtimeBridge"""
        try:
            # Preparar datos del mensaje para envío real-time
            realtime_data = {
                'type': 'chat_message',
                'chat': self.current_chat,
                'message': message,
                'timestamp': message['timestamp'],
                'sender': message['sender']
            }

            # Enviar vía RealtimeBridge usando el evento correcto
            message_bus.emit("realtime_event", realtime_data)
            message_bus.publish(f"Chat message sent to {self.current_chat}", MessageLevel.INFO)

        except Exception as e:
            message_bus.publish(f"Error sending realtime message: {e}", MessageLevel.ERROR)

    def _get_chat_recipients(self, chat_name):
        """Obtener lista de destinatarios para un chat"""
        # Para @all, no hay destinatarios específicos (es broadcast)
        if chat_name == '@all':
            return []

        # Para chats individuales, extraer username
        # Para chats grupales, sería una lista de usernames
        # TODO: Implementar lógica de recipients según el patrón de nombres de chat
        return [chat_name]  # Simplificado por ahora

    def _setup_realtime_events(self):
        """Configurar eventos de RealtimeBridge para chat en tiempo real"""
        try:
            # Suscribirse a eventos de chat en tiempo real vía MessageBus
            message_bus.on("remote_realtime_event", self._on_realtime_event_received)
            message_bus.publish("Chat widget subscribed to realtime events", MessageLevel.INFO)

        except Exception as e:
            message_bus.publish(f"Error setting up realtime events: {e}", MessageLevel.ERROR)

    def _on_realtime_event_received(self, username, event_data):
        """Manejar evento de tiempo real recibido de otros usuarios"""
        try:
            if event_data.get('type') == 'chat_message':
                # Extraer datos del mensaje de chat
                chat_name = event_data.get('chat')
                message = event_data.get('message')
                sender = event_data.get('sender')

                if message and chat_name:
                    # Procesar mensaje recibido vía MessageBus local
                    message_bus.emit("chat_message_received", {
                        'chat': chat_name,
                        'message': message,
                        'sender': sender
                    })

        except Exception as e:
            message_bus.publish(f"Error handling realtime chat event: {e}", MessageLevel.ERROR)

    def _on_realtime_message(self, data):
        """Manejar mensaje recibido en tiempo real"""
        try:
            chat_name = data.get('chat')
            message = data.get('message')

            if chat_name and message:
                # Procesar mensaje recibido vía MessageBus
                self._on_message_received({
                    'chat': chat_name,
                    'message': message,
                    'sender': 'remote_user'
                })

        except Exception as e:
            message_bus.publish(f"Error processing realtime message: {e}", MessageLevel.ERROR)

    def _on_realtime_user_joined(self, data):
        """Manejar usuario que se une en tiempo real"""
        username = data.get('username')
        if username:
            self._on_user_joined({'username': username})

    def _on_realtime_user_left(self, data):
        """Manejar usuario que se va en tiempo real"""
        username = data.get('username')
        if username:
            self._on_user_left({'username': username})

    def _on_new_chat(self, event):
        """Manejar creación de nuevo chat"""
        # Mostrar diálogo de selección - usa usuarios reales del RealtimeBridge
        dialog = UserSelectionDialog(self)
        if dialog.ShowModal() == wx.ID_OK:
            selected_users = dialog.get_selected_users()
            if selected_users:
                self._create_new_chat(selected_users)

        dialog.Destroy()

    def _get_connected_users(self):
        """Obtener lista de usuarios conectados reales"""
        return self._connected_users

    def _on_users_online_updated(self, users_online):
        """Handle users online updates from message bus - misma técnica que en tournaments"""
        try:
            # Extraer nombres de usuario de los datos de users_online
            self._connected_users = []
            for user in users_online:
                username = user.get('username', '')
                if username and username.strip():
                    self._connected_users.append(username)
        except Exception as e:
            message_bus.publish(f"Error updating connected users in chat: {str(e)}", MessageLevel.ERROR)

    def _trigger_users_update(self):
        """Trigger presence sync to get current users via event - igual que en tournaments"""
        try:
            bridge = RealtimeBridge.get_instance()
            if bridge and 'general' in bridge.channels:
                bridge._handle_presence_sync(bridge.channels['general'])
        except Exception as e:
            message_bus.publish(f"Error triggering users update: {str(e)}", MessageLevel.ERROR)

    def _create_new_chat(self, selected_users):
        """Crear nuevo chat con usuarios seleccionados"""
        if len(selected_users) == 1:
            # Chat individual
            chat_name = selected_users[0]
        else:
            # Chat grupal
            chat_name = ", ".join(selected_users[:2])
            if len(selected_users) > 2:
                chat_name += f" +{len(selected_users) - 2} more"

        # Verificar si ya existe
        for i in range(self.chat_list.GetItemCount()):
            if self.chat_list.GetItemText(i, 0) == chat_name:
                # Chat ya existe, seleccionarlo
                self.chat_list.Select(i)
                return

        # Crear nuevo chat
        self.chat_sessions[chat_name] = []
        self._add_chat_to_list(chat_name, 0, False)

        # Seleccionar el nuevo chat
        for i in range(self.chat_list.GetItemCount()):
            if self.chat_list.GetItemText(i, 0) == chat_name:
                self.chat_list.Select(i)
                break

        message_bus.publish(f"New chat created with: {', '.join(selected_users)}", MessageLevel.INFO)


class UserSelectionDialog(wx.Dialog):
    """Diálogo para seleccionar usuarios para nuevo chat - usa misma técnica que TournamentCreationDialog"""

    def __init__(self, parent):
        super().__init__(parent, title="Seleccionar usuarios para chat",
                        style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)

        self.selected_users = []
        self._connected_users = []

        self._create_ui()
        self.SetSize((400, 500))
        self.CenterOnParent()

        # Dark theme
        self.SetBackgroundColour(wx.Colour(80, 80, 80))

        # Suscribirse a actualizaciones de usuarios conectados - misma técnica que tournaments
        self._users_online_subscription_id = message_bus.on("users_online_updated", self._on_users_online_updated)

        # Disparar actualización inicial - misma técnica que tournaments
        self._trigger_users_update()

    def Destroy(self):
        # Limpiar suscripción al destruir
        message_bus.off(self._users_online_subscription_id)
        return super().Destroy()

    def _create_ui(self):
        """Crear interfaz del diálogo"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # Título
        title = wx.StaticText(self, label="Seleccionar usuarios conectados")
        title.SetForegroundColour(wx.Colour(255, 255, 255))
        title_font = title.GetFont()
        title_font.SetPointSize(12)
        title_font.SetWeight(wx.FONTWEIGHT_BOLD)
        title.SetFont(title_font)
        main_sizer.Add(title, 0, wx.ALL, 10)

        # Lista con checkboxes
        self.user_list = wx.CheckListBox(self)
        self.user_list.SetBackgroundColour(wx.Colour(45, 45, 50))  # Más oscuro para mejor contraste
        self.user_list.SetForegroundColour(wx.Colour(240, 240, 240))  # Gris claro para mejor legibilidad
        main_sizer.Add(self.user_list, 1, wx.EXPAND | wx.ALL, 10)

        # Botones
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.ok_button = DarkThemeButton(self, id=wx.ID_OK, label="Crear Chat")
        self.ok_button.Bind(wx.EVT_BUTTON, self._on_ok)

        self.cancel_button = DarkThemeButton(self, id=wx.ID_CANCEL, label="Cancelar")

        button_sizer.Add(self.ok_button, 0, wx.ALL, 5)
        button_sizer.Add(self.cancel_button, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.CENTER | wx.ALL, 10)
        self.SetSizer(main_sizer)

    def _on_users_online_updated(self, users_online):
        """Handle users online updates from message bus - misma técnica que tournaments"""
        try:
            # Extraer nombres de usuario de los datos de users_online
            self._connected_users = []
            for user in users_online:
                username = user.get('username', '')
                if username and username.strip():
                    self._connected_users.append(username)

            # Refrescar la lista en el hilo de UI
            wx.CallAfter(self._refresh_user_list)

        except Exception as e:
            message_bus.publish(f"Error updating connected users in dialog: {str(e)}", MessageLevel.ERROR)

    def _trigger_users_update(self):
        """Trigger presence sync to get current users via event - misma técnica que tournaments"""
        try:
            bridge = RealtimeBridge.get_instance()
            if bridge and 'general' in bridge.channels:
                bridge._handle_presence_sync(bridge.channels['general'])
        except Exception as e:
            message_bus.publish(f"Error triggering users update in dialog: {str(e)}", MessageLevel.ERROR)

    def _refresh_user_list(self):
        """Refresh the user list with real connected users"""
        try:
            # Check if dialog is still valid
            if not self.user_list:
                return

            # Limpiar la lista actual
            self.user_list.Clear()

            # Agregar usuarios conectados reales
            for username in self._connected_users:
                self.user_list.Append(username)

        except RuntimeError:
            # Dialog has been destroyed, ignore
            pass

    def _on_ok(self, event):
        """Manejar OK"""
        self.selected_users = []
        for i in range(self.user_list.GetCount()):
            if self.user_list.IsChecked(i):
                self.selected_users.append(self.user_list.GetString(i))

        if not self.selected_users:
            wx.MessageBox("Selecciona al menos un usuario", "Error", wx.OK | wx.ICON_ERROR)
            return

        self.EndModal(wx.ID_OK)

    def get_selected_users(self):
        """Obtener usuarios seleccionados"""
        return self.selected_users