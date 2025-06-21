#!/usr/bin/env python
"""
Test script para UltimateListCtrlAdapter
Compara wx.ListCtrl estándar con UltimateListCtrlAdapter
Prueba especial: inserción de nuevas filas en la parte superior empujando las antiguas hacia abajo
"""

import wx
import sys
import os
import time
import threading

# Añadir el directorio src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from helpers.ultimate_listctrl_adapter import UltimateListCtrlAdapter, patch_header_empty_bg

class TestFrame(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Test UltimateListCtrlAdapter - Inserción de Filas", size=(1400, 700))
        panel = wx.Panel(self)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Panel de controles principales
        control_panel = wx.Panel(panel)
        control_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botones de tema
        self.btn_dark = wx.Button(control_panel, label="Tema Oscuro")
        self.btn_light = wx.Button(control_panel, label="Tema Claro")
        self.btn_custom = wx.Button(control_panel, label="Tema Personalizado")
        
        control_sizer.Add(self.btn_dark, 0, wx.ALL, 5)
        control_sizer.Add(self.btn_light, 0, wx.ALL, 5)
        control_sizer.Add(self.btn_custom, 0, wx.ALL, 5)
        control_sizer.Add(wx.StaticLine(control_panel, style=wx.LI_VERTICAL), 0, wx.EXPAND | wx.ALL, 5)
        
        # Botones para colores de selección
        self.btn_sel_blue = wx.Button(control_panel, label="Selección Azul")
        self.btn_sel_green = wx.Button(control_panel, label="Selección Verde")
        self.btn_sel_red = wx.Button(control_panel, label="Selección Roja")
        self.btn_sel_default = wx.Button(control_panel, label="Selección Por Defecto")
        
        control_sizer.Add(self.btn_sel_blue, 0, wx.ALL, 5)
        control_sizer.Add(self.btn_sel_green, 0, wx.ALL, 5)
        control_sizer.Add(self.btn_sel_red, 0, wx.ALL, 5)
        control_sizer.Add(self.btn_sel_default, 0, wx.ALL, 5)
        
        control_panel.SetSizer(control_sizer)
        main_sizer.Add(control_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Panel de controles de testing
        test_panel = wx.Panel(panel)
        test_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Grupo de botones de test
        self.btn_clear = wx.Button(test_panel, label="Limpiar Listas")
        self.btn_add_top = wx.Button(test_panel, label="Añadir Fila Arriba")
        self.btn_add_bottom = wx.Button(test_panel, label="Añadir Fila Abajo")
        self.btn_start_auto = wx.Button(test_panel, label="Iniciar Auto-Test")
        self.btn_stop_auto = wx.Button(test_panel, label="Detener Auto-Test")
        
        test_sizer.Add(wx.StaticText(test_panel, label="Controles de Test:"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        test_sizer.Add(self.btn_clear, 0, wx.ALL, 5)
        test_sizer.Add(self.btn_add_top, 0, wx.ALL, 5)
        test_sizer.Add(self.btn_add_bottom, 0, wx.ALL, 5)
        test_sizer.Add(wx.StaticLine(test_panel, style=wx.LI_VERTICAL), 0, wx.EXPAND | wx.ALL, 5)
        test_sizer.Add(self.btn_start_auto, 0, wx.ALL, 5)
        test_sizer.Add(self.btn_stop_auto, 0, wx.ALL, 5)
        
        # Control de velocidad del auto-test
        test_sizer.Add(wx.StaticText(test_panel, label="Intervalo (ms):"), 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
        self.spin_interval = wx.SpinCtrl(test_panel, value="2000", min=500, max=10000)
        test_sizer.Add(self.spin_interval, 0, wx.ALL, 5)
        
        test_panel.SetSizer(test_sizer)
        main_sizer.Add(test_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Panel de listas
        list_panel = wx.Panel(panel)
        list_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # wx.ListCtrl a la izquierda
        left_panel = wx.Panel(list_panel)
        left_sizer = wx.BoxSizer(wx.VERTICAL)
        left_label = wx.StaticText(left_panel, label="wx.ListCtrl (Referencia):")
        self.left_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
        left_sizer.Add(left_label, 0, wx.ALL, 5)
        left_sizer.Add(self.left_list, 1, wx.EXPAND | wx.ALL, 5)
        left_panel.SetSizer(left_sizer)
        
        # UltimateListCtrlAdapter a la derecha
        right_panel = wx.Panel(list_panel)
        right_sizer = wx.BoxSizer(wx.VERTICAL)
        right_label = wx.StaticText(right_panel, label="UltimateListCtrlAdapter (Prueba):")
        self.right_list = UltimateListCtrlAdapter(right_panel, style=wx.LC_REPORT | wx.LC_HRULES | wx.LC_VRULES)
        right_sizer.Add(right_label, 0, wx.ALL, 5)
        right_sizer.Add(self.right_list, 1, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_sizer)
        
        list_sizer.Add(left_panel, 1, wx.EXPAND | wx.ALL, 5)
        list_sizer.Add(right_panel, 1, wx.EXPAND | wx.ALL, 5)
        list_panel.SetSizer(list_sizer)
        main_sizer.Add(list_panel, 1, wx.EXPAND | wx.ALL, 5)
        
        # Panel de información
        info_panel = wx.Panel(panel)
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        self.info_text = wx.TextCtrl(info_panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 100))
        info_sizer.Add(wx.StaticText(info_panel, label="Log de Actividad:"), 0, wx.ALL, 5)
        info_sizer.Add(self.info_text, 1, wx.EXPAND | wx.ALL, 5)
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        panel.SetSizer(main_sizer)
        
        # Configurar las listas
        self.setup_lists()
        
        # Variables para el auto-test
        self.auto_test_running = False
        self.auto_test_timer = None
        self.next_id = 1
        
        # Eventos de tema
        self.btn_dark.Bind(wx.EVT_BUTTON, self.on_dark_theme)
        self.btn_light.Bind(wx.EVT_BUTTON, self.on_light_theme)
        self.btn_custom.Bind(wx.EVT_BUTTON, self.on_custom_theme)
        
        # Eventos para colores de selección
        self.btn_sel_blue.Bind(wx.EVT_BUTTON, self.on_selection_blue)
        self.btn_sel_green.Bind(wx.EVT_BUTTON, self.on_selection_green)
        self.btn_sel_red.Bind(wx.EVT_BUTTON, self.on_selection_red)
        self.btn_sel_default.Bind(wx.EVT_BUTTON, self.on_selection_default)
        
        # Eventos de test
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear_lists)
        self.btn_add_top.Bind(wx.EVT_BUTTON, self.on_add_top)
        self.btn_add_bottom.Bind(wx.EVT_BUTTON, self.on_add_bottom)
        self.btn_start_auto.Bind(wx.EVT_BUTTON, self.on_start_auto_test)
        self.btn_stop_auto.Bind(wx.EVT_BUTTON, self.on_stop_auto_test)
        
        # Aplicar tema oscuro por defecto
        self.apply_dark_theme()
        
        # Aplicar parche de cabecera
        patch_header_empty_bg(self.right_list)
        
        # Eventos de selección
        self.right_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_right_selected)
        self.left_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_left_selected)
        
        # Eventos de clic derecho (menú contextual)
        self.left_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_right_click)
        self.right_list.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_right_click)
        
        # Información inicial
        self.log_info("Aplicación iniciada. Listas vacías preparadas para test.")
        self.log_info("COMPORTAMIENTO ESPERADO:")
        self.log_info("- wx.ListCtrl: nuevas filas insertadas en posición 0 empujan las antiguas hacia abajo")
        self.log_info("- UltimateListCtrlAdapter: debe comportarse exactamente igual")
        
        # Iniciar auto-test automáticamente
        wx.CallAfter(self.start_auto_test_on_startup)

    def setup_lists(self):
        """Configurar las columnas de ambas listas, empezando vacías"""
        columns = ["ID", "Timestamp", "Usuario", "Evento", "Detalles"]
        
        # Insertar columnas en ambas listas
        for i, col in enumerate(columns):
            self.left_list.InsertColumn(i, col, width=120)
            self.right_list.InsertColumn(i, col, width=120)
        
        # Comenzar con listas vacías para el test
        self.log_info("Listas configuradas con columnas. Listas vacías preparadas para test.")

    def generate_test_data(self):
        """Genera datos de prueba simulando eventos de log"""
        import datetime
        
        eventos = [
            ("Login", "Usuario autenticado correctamente"),
            ("Logout", "Sesión cerrada por el usuario"),
            ("Error", "Fallo en la conexión a la base de datos"),
            ("Warning", "Memoria RAM al 85%"),
            ("Info", "Proceso de respaldo completado"),
            ("Debug", "Consulta SQL ejecutada en 120ms"),
            ("Critical", "Espacio en disco crítico"),
            ("Success", "Operación completada exitosamente")
        ]
        
        evento, detalle = eventos[self.next_id % len(eventos)]
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        
        data = (
            str(self.next_id),
            timestamp,
            f"User{self.next_id % 10}",
            evento,
            detalle
        )
        
        self.next_id += 1
        return data

    def log_info(self, message):
        """Agregar mensaje al log de información"""
        timestamp = time.strftime("%H:%M:%S")
        self.info_text.AppendText(f"[{timestamp}] {message}\n")

    def on_clear_lists(self, event):
        """Limpiar ambas listas"""
        self.left_list.DeleteAllItems()
        self.right_list.DeleteAllItems()
        self.next_id = 1
        self.log_info("Listas limpiadas. Reiniciando contador de ID.")

    def on_add_top(self, event):
        """Añadir una fila en la parte superior (posición 0)"""
        data = self.generate_test_data()
        
        # Insertar en posición 0 (arriba) para empujar las demás hacia abajo
        left_idx = self.left_list.InsertStringItem(0, data[0])
        right_idx = self.right_list.InsertStringItem(0, data[0])
        
        # Completar las demás columnas
        for j, cell in enumerate(data[1:], 1):
            self.left_list.SetItem(left_idx, j, cell)
            self.right_list.SetItem(right_idx, j, cell)
        
        self.log_info(f"Fila añadida ARRIBA: ID={data[0]}, Evento={data[3]}")

    def on_add_bottom(self, event):
        """Añadir una fila en la parte inferior (al final)"""
        data = self.generate_test_data()
        
        # Insertar al final
        left_idx = self.left_list.InsertStringItem(self.left_list.GetItemCount(), data[0])
        right_idx = self.right_list.InsertStringItem(self.right_list.GetItemCount(), data[0])
        
        # Completar las demás columnas
        for j, cell in enumerate(data[1:], 1):
            self.left_list.SetItem(left_idx, j, cell)
            self.right_list.SetItem(right_idx, j, cell)
        
        self.log_info(f"Fila añadida ABAJO: ID={data[0]}, Evento={data[3]}")

    def on_start_auto_test(self, event):
        """Iniciar el test automático"""
        if not self.auto_test_running:
            self.auto_test_running = True
            self.btn_start_auto.Enable(False)
            self.btn_stop_auto.Enable(True)
            self.start_auto_timer()
            self.log_info("Auto-test INICIADO. Nuevas filas se añadirán automáticamente en la parte superior.")

    def on_stop_auto_test(self, event):
        """Detener el test automático"""
        if self.auto_test_running:
            self.auto_test_running = False
            self.btn_start_auto.Enable(True)
            self.btn_stop_auto.Enable(False)
            if self.auto_test_timer:
                self.auto_test_timer.Stop()
                self.auto_test_timer = None
            self.log_info("Auto-test DETENIDO.")

    def start_auto_timer(self):
        """Iniciar el timer para el auto-test"""
        if self.auto_test_running:
            interval = self.spin_interval.GetValue()
            self.auto_test_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.on_auto_timer, self.auto_test_timer)
            self.auto_test_timer.Start(interval)

    def on_auto_timer(self, event):
        """Evento del timer - añadir fila automáticamente"""
        if self.auto_test_running:
            self.on_add_top(None)  # Añadir en la parte superior
    
    def start_auto_test_on_startup(self):
        """Iniciar auto-test automáticamente al arrancar"""
        self.log_info("Iniciando auto-test automáticamente...")
        self.on_start_auto_test(None)
    
    def on_right_click(self, event):
        """Manejar clic derecho - mostrar menú contextual"""
        try:
            # Obtener información de la fila
            row_index = event.GetIndex()
            listctrl = event.GetEventObject()
            
            if row_index >= 0:
                row_content = self.get_row_content(listctrl, row_index)
                self.show_context_menu(event, row_index, row_content, listctrl)
            else:
                self.log_info("Clic derecho en área vacía - no se muestra menú")
        except Exception as e:
            self.log_info(f"Error en clic derecho: {str(e)}")
    
    def get_row_content(self, listctrl, row_index):
        """Extraer contenido de todas las columnas de una fila"""
        row_content = {}
        column_names = ["ID", "Timestamp", "Usuario", "Evento", "Detalles"]
        
        try:
            for col in range(len(column_names)):
                if col == 0:
                    # Primera columna
                    content = listctrl.GetItemText(row_index)
                else:
                    # Demás columnas
                    if hasattr(listctrl, 'GetItem'):
                        item = listctrl.GetItem(row_index, col)
                        content = item.GetText()
                    else:
                        content = listctrl.GetItemText(row_index, col)
                
                row_content[column_names[col]] = content
        except Exception as e:
            self.log_info(f"Error extrayendo contenido de fila {row_index}: {str(e)}")
            
        return row_content
    
    def show_context_menu(self, event, row_index, row_content, listctrl):
        """Crear y mostrar menú contextual"""
        try:
            menu = wx.Menu()
            
            # Título del menú
            menu_title = wx.MenuItem(menu, wx.ID_ANY, "Información de Fila")
            menu_title.Enable(False)
            menu.Append(menu_title)
            menu.AppendSeparator()
            
            # Información de la fila
            line_info = wx.MenuItem(menu, wx.ID_ANY, f"📍 Línea: {row_index + 1}")
            line_info.Enable(False)
            menu.Append(line_info)
            
            # Contenido de cada columna
            for col_name, content in row_content.items():
                # Truncar contenido largo
                display_content = content[:30] + "..." if len(content) > 30 else content
                col_item = wx.MenuItem(menu, wx.ID_ANY, f"• {col_name}: {display_content}")
                col_item.Enable(False)
                menu.Append(col_item)
            
            menu.AppendSeparator()
            
            # Acciones
            copy_line_id = wx.NewId()
            copy_id_id = wx.NewId()
            delete_line_id = wx.NewId()
            
            menu.Append(copy_line_id, "📋 Copiar Línea Completa")
            menu.Append(copy_id_id, "📋 Copiar Solo ID")
            menu.Append(delete_line_id, "❌ Eliminar Línea")
            
            # Eventos del menú
            self.Bind(wx.EVT_MENU, lambda evt: self.copy_full_line(row_content), id=copy_line_id)
            self.Bind(wx.EVT_MENU, lambda evt: self.copy_field("ID", row_content), id=copy_id_id)
            self.Bind(wx.EVT_MENU, lambda evt: self.delete_line(listctrl, row_index), id=delete_line_id)
            
            # Mostrar menú en la posición del cursor
            self.PopupMenu(menu)
            menu.Destroy()
            
            # Log de la acción
            control_name = "wx.ListCtrl" if listctrl == self.left_list else "UltimateListCtrlAdapter"
            self.log_info(f"Menú contextual mostrado en {control_name}, línea {row_index + 1}")
            
        except Exception as e:
            self.log_info(f"Error mostrando menú contextual: {str(e)}")
    
    def copy_full_line(self, row_content):
        """Copiar línea completa al clipboard"""
        try:
            # Crear texto con toda la información
            full_text = " | ".join([f"{col}: {content}" for col, content in row_content.items()])
            
            # Copiar al clipboard
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(full_text))
                wx.TheClipboard.Close()
                self.log_info(f"Línea completa copiada al clipboard: {full_text[:50]}...")
            else:
                self.log_info("Error: No se pudo abrir el clipboard")
        except Exception as e:
            self.log_info(f"Error copiando línea completa: {str(e)}")
    
    def copy_field(self, field_name, row_content):
        """Copiar campo específico al clipboard"""
        try:
            field_content = row_content.get(field_name, "")
            
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(wx.TextDataObject(field_content))
                wx.TheClipboard.Close()
                self.log_info(f"Campo '{field_name}' copiado al clipboard: {field_content}")
            else:
                self.log_info("Error: No se pudo abrir el clipboard")
        except Exception as e:
            self.log_info(f"Error copiando campo '{field_name}': {str(e)}")
    
    def delete_line(self, listctrl, row_index):
        """Eliminar línea seleccionada"""
        try:
            # Obtener información antes de eliminar
            row_content = self.get_row_content(listctrl, row_index)
            id_value = row_content.get("ID", "N/A")
            
            # Confirmar eliminación
            dlg = wx.MessageDialog(self, 
                                 f"¿Eliminar la línea {row_index + 1} (ID: {id_value})?",
                                 "Confirmar Eliminación",
                                 wx.YES_NO | wx.ICON_QUESTION)
            
            if dlg.ShowModal() == wx.ID_YES:
                # Eliminar de ambas listas para mantener sincronización
                self.left_list.DeleteItem(row_index)
                self.right_list.DeleteItem(row_index)
                
                control_name = "wx.ListCtrl" if listctrl == self.left_list else "UltimateListCtrlAdapter"
                self.log_info(f"Línea {row_index + 1} eliminada de {control_name} (ID: {id_value})")
            
            dlg.Destroy()
            
        except Exception as e:
            self.log_info(f"Error eliminando línea {row_index}: {str(e)}")

    def apply_dark_theme(self):
        dark_header_bg = wx.Colour(64, 64, 64)
        dark_header_fg = wx.Colour(240, 240, 240)
        dark_row_bg = wx.Colour(80, 80, 80)
        dark_row_fg = wx.Colour(230, 230, 230)
        
        # Solo aplicar a UltimateListCtrlAdapter (el wx.ListCtrl no tiene estos métodos)
        self.right_list.SetAllColumnHeaderColors(dark_header_bg, dark_header_fg)
        self.right_list.SetRowColors(dark_row_bg, dark_row_fg)
        self.right_list.Refresh()

    def apply_light_theme(self):
        light_header_bg = wx.Colour(255, 255, 255)
        light_header_fg = wx.Colour(0, 0, 0)
        light_row_bg = wx.Colour(255, 255, 255)
        light_row_fg = wx.Colour(0, 0, 0)
        
        # Solo aplicar a UltimateListCtrlAdapter
        self.right_list.SetAllColumnHeaderColors(light_header_bg, light_header_fg)
        self.right_list.SetRowColors(light_row_bg, light_row_fg)
        self.right_list.Refresh()

    def apply_custom_theme(self):
        colors = [
            (wx.Colour(100, 150, 200), wx.Colour(255, 255, 255)),
            (wx.Colour(200, 100, 150), wx.Colour(255, 255, 255)),
            (wx.Colour(150, 200, 100), wx.Colour(255, 255, 255)),
            (wx.Colour(200, 150, 100), wx.Colour(255, 255, 255)),
            (wx.Colour(100, 100, 200), wx.Colour(255, 255, 255)),
        ]
        
        # Aplicar colores por columna
        for i, (bg, fg) in enumerate(colors):
            self.right_list.SetColumnHeaderColors(i, bg, fg)

    def on_dark_theme(self, event):
        print("Aplicando tema oscuro...")
        self.apply_dark_theme()

    def on_light_theme(self, event):
        print("Aplicando tema claro...")
        self.apply_light_theme()

    def on_custom_theme(self, event):
        print("Aplicando tema personalizado...")
        self.apply_custom_theme()

    def on_right_selected(self, event):
        item = event.GetIndex()
        print(f"Seleccionado en UltimateListCtrlAdapter: item {item}")

    def on_left_selected(self, event):
        item = event.GetIndex()
        print(f"Seleccionado en wx.ListCtrl: item {item}")

    def on_selection_blue(self, event):
        print("Aplicando selección azul moderna...")
        # Azul moderno estilo Windows 10/11
        self.right_list.SetHighlightColour(wx.Colour(0, 120, 215))
        self.right_list.SetHighlightTextColour(wx.Colour(255, 255, 255))

    def on_selection_green(self, event):
        print("Aplicando selección verde...")
        # Verde moderno
        self.right_list.SetHighlightColour(wx.Colour(76, 175, 80))
        self.right_list.SetHighlightTextColour(wx.Colour(255, 255, 255))

    def on_selection_red(self, event):
        print("Aplicando selección roja...")
        # Rojo moderno
        self.right_list.SetHighlightColour(wx.Colour(244, 67, 54))
        self.right_list.SetHighlightTextColour(wx.Colour(255, 255, 255))

    def on_selection_default(self, event):
        print("Restaurando selección por defecto del sistema...")
        # Resetear a colores del sistema
        self.right_list.SetHighlightColour(None)
        self.right_list.SetHighlightTextColour(None)

def main():
    app = wx.App()
    frame = TestFrame()
    frame.Show()
    frame.Refresh()
    app.MainLoop()

if __name__ == "__main__":
    main() 