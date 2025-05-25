import os
import wx
import shutil
import json
import datetime
from .gui_module import WindowsHelper
from .config_utils import get_application_path

FREEZER_DIR = os.path.abspath(os.path.join(get_application_path(), 'SCLogAnalyzer.freezer'))
INDEX_FILE = os.path.join(FREEZER_DIR, 'freezer_index.json')

class FreezerPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)
        self._init_ui()
        self.refresh_list()

    def _init_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.list_ctrl = wx.ListCtrl(self, style=wx.LC_REPORT|wx.BORDER_SUNKEN)
        self.list_ctrl.InsertColumn(0, "Name", width=120)
        self.list_ctrl.InsertColumn(1, "Description", width=200)
        self.list_ctrl.InsertColumn(2, "Timestamp", width=120)
        self.list_ctrl.InsertColumn(3, "Log", width=80)
        self.list_ctrl.InsertColumn(4, "Screenshot", width=100)
        sizer.Add(self.list_ctrl, 1, wx.EXPAND|wx.ALL, 5)
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.btn_open = wx.Button(self, label="Open Folder")
        self.btn_delete = wx.Button(self, label="Delete")
        btn_sizer.Add(self.btn_open, 0, wx.ALL, 2)
        btn_sizer.Add(self.btn_delete, 0, wx.ALL, 2)
        sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT)
        self.SetSizer(sizer)
        self.btn_open.Bind(wx.EVT_BUTTON, self.on_open)
        self.btn_delete.Bind(wx.EVT_BUTTON, self.on_delete)

    def refresh_list(self):
        self.list_ctrl.DeleteAllItems()
        index = self.load_freezer_index()
        for entry in index:
            idx = self.list_ctrl.InsertItem(self.list_ctrl.GetItemCount(), entry.get('name', ''))
            self.list_ctrl.SetItem(idx, 1, entry.get('description', ''))
            self.list_ctrl.SetItem(idx, 2, entry.get('timestamp', ''))
            self.list_ctrl.SetItem(idx, 3, entry.get('log_path', ''))
            self.list_ctrl.SetItem(idx, 4, entry.get('screenshot_path', ''))

    def on_open(self, event):
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a freeze entry first.", "Info", wx.OK | wx.ICON_INFORMATION)
            return
        folder = self.list_ctrl.GetItemText(idx, col=2)
        path = os.path.join(FREEZER_DIR, folder)
        if os.path.exists(path):
            os.startfile(path)
        else:
            wx.MessageBox("Folder not found.", "Error", wx.OK | wx.ICON_ERROR)

    def on_delete(self, event):
        idx = self.list_ctrl.GetFirstSelected()
        if idx == -1:
            wx.MessageBox("Select a freeze entry first.", "Info", wx.OK | wx.ICON_INFORMATION)
            return
        folder = self.list_ctrl.GetItemText(idx, col=2)
        try:
            self.delete_freeze(folder)
            self.refresh_list()
        except Exception as e:
            wx.MessageBox(f"Delete failed: {e}", "Error", wx.OK | wx.ICON_ERROR)

    @staticmethod
    def ensure_freezer_dir():
        os.makedirs(FREEZER_DIR, exist_ok=True)
        return FREEZER_DIR

    @staticmethod
    def load_freezer_index():
        if os.path.exists(INDEX_FILE):
            try:
                with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    @staticmethod
    def delete_freeze(folder):
        path = os.path.join(FREEZER_DIR, folder)
        if os.path.exists(path):
            shutil.rmtree(path)
        # Update index
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                index = json.load(f)
            index = [e for e in index if e.get('timestamp') != folder]
            with open(INDEX_FILE, 'w', encoding='utf-8') as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
