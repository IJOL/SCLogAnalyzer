#!/usr/bin/env python3
"""
GameFocusDetector - Detección de foco del juego Star Citizen

Detecta cuando Star Citizen tiene el foco del sistema usando la misma lógica
que WindowsHelper del proyecto principal.

Migrado del POC funcional.
"""

import time
import threading
import win32gui
import win32process
import psutil
from typing import List, Callable, Optional, Tuple


class GameFocusDetector:
    """Detector de foco del juego usando la misma lógica que el proyecto principal"""
    
    def __init__(self, target_windows: Optional[List[str]] = None):
        # Usar la misma configuración que WindowsHelper.find_window_by_title
        self.target_title = "Star Citizen"
        self.target_class = "CryENGINE" 
        self.target_process = "StarCitizen.exe"
        self.is_focused = False
        self.monitoring = False
        self.monitor_thread = None
        self.callbacks = []
        self.current_window_info = None
        
        # Permitir configurar ventanas objetivo adicionales
        self.additional_targets = target_windows or []
    
    def add_focus_callback(self, callback: Callable):
        """Añadir callback que se ejecuta cuando cambia el foco"""
        self.callbacks.append(callback)
    
    def start_monitoring(self):
        """Iniciar monitoreo de foco en hilo separado"""
        if self.monitoring:
            return
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """Detener monitoreo de foco"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1.0)
    
    def is_target_focused(self) -> bool:
        """Verificar si alguna ventana objetivo tiene el foco"""
        return self.is_focused
    
    def find_star_citizen_window(self) -> Optional[Tuple[int, str, str, str]]:
        """Buscar ventana de Star Citizen usando la misma lógica que el proyecto principal"""
        def enum_windows_callback(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                
                # Buscar Star Citizen primero
                if self.target_title in window_title:
                    # Verificar clase de ventana
                    class_name = win32gui.GetClassName(hwnd)
                    if self.target_class and class_name != self.target_class:
                        return
                    
                    # Verificar proceso
                    if self.target_process:
                        try:
                            _, pid = win32process.GetWindowThreadProcessId(hwnd)
                            process = psutil.Process(pid)
                            if process.name() != self.target_process:
                                return
                        except (psutil.NoSuchProcess, Exception):
                            return
                    
                    windows.append((hwnd, window_title, class_name, "star_citizen"))
                
                # Verificar ventanas objetivo adicionales
                for target in self.additional_targets:
                    if target in window_title:
                        class_name = win32gui.GetClassName(hwnd)
                        windows.append((hwnd, window_title, class_name, "additional_target"))

        windows = []
        try:
            win32gui.EnumWindows(enum_windows_callback, windows)
            
            # Priorizar Star Citizen, luego targets adicionales
            sc_windows = [w for w in windows if w[3] == "star_citizen"]
            additional_windows = [w for w in windows if w[3] == "additional_target"]
            
            if sc_windows:
                return sc_windows[0]
            elif additional_windows:
                return additional_windows[0] 
            else:
                return None
        except Exception:
            return None
    
    def _monitor_loop(self):
        """Loop principal de monitoreo en hilo separado"""
        while self.monitoring:
            try:
                # Obtener ventana en primer plano
                foreground_hwnd = win32gui.GetForegroundWindow()
                
                # Buscar ventana de Star Citizen
                sc_window = self.find_star_citizen_window()
                
                # Verificar si Star Citizen está en foco
                new_focus_state = False
                window_info = "No target window found"
                
                if sc_window and foreground_hwnd:
                    sc_hwnd, sc_title, sc_class, window_type = sc_window
                    new_focus_state = (foreground_hwnd == sc_hwnd)
                    
                    if new_focus_state:
                        try:
                            pid = win32process.GetWindowThreadProcessId(sc_hwnd)[1]
                            if window_type == "star_citizen":
                                window_info = f"⭐ Star Citizen ({sc_class}) - PID: {pid}"
                            else:
                                window_info = f"🎯 Target Window ({sc_class}) - PID: {pid}"
                        except:
                            window_info = f"✅ Target focused: {sc_title}"
                    else:
                        try:
                            fg_title = win32gui.GetWindowText(foreground_hwnd)
                            window_info = f"❌ Other window: {fg_title[:50]}..."
                        except:
                            window_info = "❌ Unknown window in focus"
                
                # Notificar cambios
                if new_focus_state != self.is_focused:
                    self.is_focused = new_focus_state
                    self.current_window_info = window_info
                    for callback in self.callbacks:
                        try:
                            # Importar wx aquí para evitar dependencia circular
                            try:
                                import wx
                                wx.CallAfter(callback, self.is_focused, window_info)
                            except ImportError:
                                # Si wx no está disponible, llamar directamente
                                callback(self.is_focused, window_info)
                        except Exception as e:
                            # Ignorar errores en callbacks para no detener el monitoreo
                            pass
                
                time.sleep(0.5)
            except Exception as e:
                # En caso de error, continuar monitoreando pero con delay mayor
                time.sleep(1.0)


def main():
    """Testing standalone del GameFocusDetector"""
    print("=== GameFocusDetector Testing ===")
    
    def on_focus_change(focused, info):
        status = "🟢 FOCUSED" if focused else "🔴 NOT FOCUSED"
        print(f"{status}: {info}")
    
    detector = GameFocusDetector()
    detector.add_focus_callback(on_focus_change)
    
    print("Starting focus detection... (Press Ctrl+C to stop)")
    detector.start_monitoring()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping detector...")
        detector.stop_monitoring()


if __name__ == "__main__":
    main()