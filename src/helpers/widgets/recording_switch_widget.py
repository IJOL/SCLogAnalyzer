#!/usr/bin/env python
import wx
import time
import winreg
from wx.lib import buttons
from helpers.core.message_bus import message_bus, MessageLevel

class RecordingSwitchWidget(wx.Panel):
    """
    Widget autocontenido para controlar grabación a Supabase.
    Usa acceso directo al registro de Windows.
    Usa el mismo estilo visual que DarkThemeButton pero con colores rojo/verde.
    """
    
    def __init__(self, parent, monitoring_service):
        super().__init__(parent)
        self.monitoring_service = monitoring_service
        self.cooldown_seconds = 300  # 5 minutos
        self.cooldown_timer = None
        self.registry_key_path = r"Software\SCLogAnalyzer"
        
        # Estado inicial desde registro de Windows (clave padre)
        # Ubicación registro: HKEY_CURRENT_USER\Software\SCLogAnalyzer
        self.recording_enabled = not self._get_registry_value('recording_disabled', None)
        last_toggle_time_str = self._get_registry_value('cooldown_start_time', None)
        self.last_toggle_time = float(last_toggle_time_str) if last_toggle_time_str else None
        
        # Subscribe to version updates to detect test modes (PTU/EPTU)
        message_bus.on("shard_version_update", self._on_version_update)
        
        # Al iniciar: verificar si han pasado 5 minutos desde el último cambio
        if self.last_toggle_time:
            current_time = time.time()
            time_since_last_change = current_time - self.last_toggle_time
            
            if time_since_last_change < self.cooldown_seconds:
                # Aún en cooldown: usar estado guardado
                recording_state_str = self._get_registry_value('recording_state', 'True')
                self.recording_enabled = recording_state_str.lower() == 'true'
                # El timer se encargará de rehabilitar cuando termine el cooldown
            else:
                # Cooldown terminado: eliminar del registro (estado por defecto)
                self._delete_registry_value('cooldown_start_time')
                self._delete_registry_value('recording_state')
                self.recording_enabled = True
                self.last_toggle_time = None
        else:
            # No hay fecha: usar estado guardado o por defecto (activado)
            recording_state_str = self._get_registry_value('recording_state', 'True')
            self.recording_enabled = recording_state_str.lower() == 'true'
        
        self._init_ui()
        self._start_cooldown_timer()
    
    def _init_ui(self):
        # Crear sizer horizontal
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botón con estilo DarkThemeButton pero colores personalizados
        self.switch_button = buttons.GenButton(
            self, 
            label="🟢 Rec ON" if self.recording_enabled else "🔴 Rec OFF",
            size=(60, 25),
            style=wx.BORDER_NONE
        )
        self.switch_button.SetToolTip("Control de grabación")
        self.switch_button.Bind(wx.EVT_BUTTON, self._on_click)
        
        # Configurar estilo visual igual que DarkThemeButton
        self.switch_button.SetBezelWidth(1)  # Borde más fino
        
        # Añadir solo el botón al sizer
        sizer.Add(self.switch_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        
        self.SetSizer(sizer)
        self._update_ui_state()
    
    def _on_click(self, event):
        current_time = time.time()
        
        # Verificar cooldown usando timestamp guardado (bidireccional)
        if (self.last_toggle_time and 
            current_time - self.last_toggle_time < self.cooldown_seconds):
            # Revertir cambio y mostrar mensaje
            remaining = int(self.cooldown_seconds - (current_time - self.last_toggle_time))
            message_bus.publish(
                content=f"Cooldown activo. Espera {remaining} segundos.",
                level=MessageLevel.WARNING
            )
            return
        
        # Aplicar cambio
        self.recording_enabled = not self.recording_enabled
        self.last_toggle_time = current_time
        
        # Guardar timestamp del último cambio y estado actual (bidireccional)
        # Ubicación registro: HKEY_CURRENT_USER\Software\SCLogAnalyzer
        self._set_registry_value('cooldown_start_time', self.last_toggle_time)
        self._set_registry_value('recording_state', self.recording_enabled)
        
        # Actualizar block_private_lobby_recording en log_analyzer
        if self.monitoring_service and self.monitoring_service.event_handler:
            self.monitoring_service.event_handler.block_private_lobby_recording = not self.recording_enabled
        
        # Actualizar UI
        self._update_ui_state()
        
        # Programar rehabilitación después de 5 minutos
        self._start_cooldown_timer()
    
    def _start_cooldown_timer(self):
        if self.cooldown_timer:
            self.cooldown_timer.Stop()
        
        # Si hay timestamp guardado, calcular tiempo restante
        if self.last_toggle_time:
            current_time = time.time()
            time_since_last_change = current_time - self.last_toggle_time
            
            if time_since_last_change < self.cooldown_seconds:
                # Aún en cooldown: programar timer para rehabilitar
                remaining_time = self.cooldown_seconds - time_since_last_change
                self.cooldown_timer = wx.Timer(self)
                self.Bind(wx.EVT_TIMER, self._on_cooldown_timer, self.cooldown_timer)
                self.cooldown_timer.StartOnce(int(remaining_time * 1000))  # Una sola llamada
            else:
                # Cooldown ya terminado: solo eliminar timestamp
                # El estado de grabación debe persistir
                self._delete_registry_value('cooldown_start_time')
                self.last_toggle_time = None
    
    def _on_cooldown_timer(self, event):
        # Cooldown terminado: solo eliminar timestamp y rehabilitar botón
        # El estado de grabación debe persistir hasta que el usuario lo cambie
        self._delete_registry_value('cooldown_start_time')
        self.last_toggle_time = None
        self._update_ui_state()
    
    def _update_ui_state(self):
        current_time = time.time()
        in_cooldown = (self.last_toggle_time and 
                      current_time - self.last_toggle_time < self.cooldown_seconds)
        
        self.switch_button.Enable(not in_cooldown)
        
        # Actualizar etiqueta
        self.switch_button.SetLabel("🟢 Rec ON" if self.recording_enabled else "🔴 Rec OFF")
        
        # Aplicar colores según estado (mismo estilo que DarkThemeButton)
        if self.recording_enabled:
            self.switch_button.SetBackgroundColour(wx.Colour(0, 128, 0))  # Verde
            self.switch_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
        else:
            self.switch_button.SetBackgroundColour(wx.Colour(128, 0, 0))  # Rojo
            self.switch_button.SetForegroundColour(wx.Colour(255, 255, 255))  # Blanco
        
        # Forzar refresco
        self.switch_button.Refresh()
        self.switch_button.Update()
        self.Refresh()
        self.Update()
    
    def is_recording_enabled(self):
        return self.recording_enabled
    
    def _get_registry_value(self, value_name, default=None):
        """Obtener valor del registro de Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key_path, 0, winreg.KEY_READ)
            value = winreg.QueryValueEx(key, value_name)[0]
            winreg.CloseKey(key)
            return value
        except FileNotFoundError:
            return default
        except Exception as e:
            message_bus.publish(
                content=f"Error reading registry value {value_name}: {e}",
                level=MessageLevel.ERROR
            )
            return default

    def _set_registry_value(self, value_name, value):
        """Guardar valor en el registro de Windows."""
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.registry_key_path)
            winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, str(value))
            winreg.CloseKey(key)
        except Exception as e:
            message_bus.publish(
                content=f"Error saving registry value {value_name}: {e}",
                level=MessageLevel.ERROR
            )

    def _delete_registry_value(self, value_name):
        """Eliminar valor del registro de Windows."""
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.registry_key_path, 0, winreg.KEY_WRITE)
            winreg.DeleteValue(key, value_name)
            winreg.CloseKey(key)
        except FileNotFoundError:
            # No existe la clave, no es un error
            pass
        except Exception as e:
            message_bus.publish(
                content=f"Error deleting registry value {value_name}: {e}",
                level=MessageLevel.ERROR
            )

    def _on_version_update(self, shard, version, username, mode=None, private=None):
        """Handle version updates to detect test modes (PTU/EPTU vs PUB)."""
        # Detectar si NO es live mode (pub)
        is_test_mode = (version and 
                       version.split('-')[0].lower() != 'pub')
        
        if is_test_mode:
            # Forzar Rec OFF en modo test
            self.recording_enabled = False
            self.switch_button.Enable(False)
            self.switch_button.SetToolTip("Grabación deshabilitada en modo test (PTU/EPTU)")
        else:
            # Rehabilitar en pub (live) - solo si no estamos en cooldown
            current_time = time.time()
            in_cooldown = (self.last_toggle_time and 
                          current_time - self.last_toggle_time < self.cooldown_seconds)
            
            self.switch_button.Enable(not in_cooldown)
            self.switch_button.SetToolTip("Control de grabación" if not in_cooldown 
                                         else f"Cooldown activo - {int(self.cooldown_seconds - (current_time - self.last_toggle_time))}s restantes")
        
        self._update_ui_state()

    def cleanup_timer(self):
        if self.cooldown_timer:
            self.cooldown_timer.Stop() 