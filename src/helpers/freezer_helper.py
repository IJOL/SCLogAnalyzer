import os
import shutil
import json
import datetime
import wx
from .gui_module import WindowsHelper
from .config_utils import get_application_path

FREEZER_DIR = os.path.abspath(os.path.join(get_application_path(), 'SCLogAnalyzer.freezer'))
INDEX_FILE = os.path.join(FREEZER_DIR, 'freezer_index.json')


def ensure_freezer_dir():
    os.makedirs(FREEZER_DIR, exist_ok=True)
    return FREEZER_DIR


def create_freeze(log_src, hwnd, parent=None):
    ensure_freezer_dir()
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    freeze_dir = os.path.join(FREEZER_DIR, timestamp)
    os.makedirs(freeze_dir, exist_ok=True)
    log_dst = os.path.join(freeze_dir, f'log_{timestamp}.log')
    if log_src and os.path.exists(log_src):
        shutil.copy2(log_src, log_dst)
    else:
        wx.MessageBox("Log file not found.", "Freeze Error", wx.OK | wx.ICON_ERROR, parent)
        return None
    screenshot_path = os.path.join(freeze_dir, f'screenshot_{timestamp}.jpg')
    try:
        if hwnd:
            WindowsHelper.capture_window_screenshot(hwnd, screenshot_path, full=True)
        else:
            wx.MessageBox("Star Citizen window not found.", "Freeze Error", wx.OK | wx.ICON_ERROR, parent)
            return None
    except Exception as e:
        wx.MessageBox(f"Screenshot failed: {e}", "Freeze Error", wx.OK | wx.ICON_ERROR, parent)
        return None
    dlg = wx.TextEntryDialog(parent, "Enter a name for this freeze:", "Freeze Name", timestamp)
    if dlg.ShowModal() == wx.ID_OK:
        freeze_name = dlg.GetValue()
    else:
        return None
    dlg.Destroy()
    dlg2 = wx.TextEntryDialog(parent, "Enter a description:", "Freeze Description", "")
    if dlg2.ShowModal() == wx.ID_OK:
        freeze_desc = dlg2.GetValue()
    else:
        freeze_desc = ""
    dlg2.Destroy()
    entry = {
        'name': freeze_name,
        'description': freeze_desc,
        'timestamp': timestamp,
        'log_path': os.path.relpath(log_dst, FREEZER_DIR),
        'screenshot_path': os.path.relpath(screenshot_path, FREEZER_DIR),
        'folder': timestamp
    }
    update_freezer_index(entry)
    return entry


def update_freezer_index(entry):
    try:
        if os.path.exists(INDEX_FILE):
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                index = json.load(f)
        else:
            index = []
    except Exception:
        index = []
    index.append(entry)
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2, ensure_ascii=False)


def load_freezer_index():
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


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


def open_freeze_folder(folder):
    path = os.path.join(FREEZER_DIR, folder)
    if os.path.exists(path):
        os.startfile(path)
        return True
    return False


def create_freezer_tab(frame):
    """Crea la pestaña Freezer y su UI en el frame dado."""
    panel = frame.freezer_page
    sizer = wx.BoxSizer(wx.VERTICAL)
    frame.freezer_list = wx.ListCtrl(panel, style=wx.LC_REPORT|wx.BORDER_SUNKEN)
    frame.freezer_list.InsertColumn(0, "Name", width=120)
    frame.freezer_list.InsertColumn(1, "Description", width=200)
    frame.freezer_list.InsertColumn(2, "Timestamp", width=120)
    frame.freezer_list.InsertColumn(3, "Log", width=80)
    frame.freezer_list.InsertColumn(4, "Screenshot", width=100)
    sizer.Add(frame.freezer_list, 1, wx.EXPAND|wx.ALL, 5)
    btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
    frame.btn_open = wx.Button(panel, label="Open Folder")
    frame.btn_delete = wx.Button(panel, label="Delete")
    btn_sizer.Add(frame.btn_open, 0, wx.ALL, 2)
    btn_sizer.Add(frame.btn_delete, 0, wx.ALL, 2)
    sizer.Add(btn_sizer, 0, wx.ALIGN_RIGHT)
    panel.SetSizer(sizer)
    frame.btn_open.Bind(wx.EVT_BUTTON, frame._on_freezer_open)
    frame.btn_delete.Bind(wx.EVT_BUTTON, frame._on_freezer_delete)


def refresh_freezer_tab(frame):
    """Recarga la lista de congelados en la pestaña Freezer del frame."""
    frame.freezer_list.DeleteAllItems()
    index = load_freezer_index()
    for entry in index:
        idx = frame.freezer_list.InsertItem(frame.freezer_list.GetItemCount(), entry.get('name', ''))
        frame.freezer_list.SetItem(idx, 1, entry.get('description', ''))
        frame.freezer_list.SetItem(idx, 2, entry.get('timestamp', ''))
        frame.freezer_list.SetItem(idx, 3, entry.get('log_path', ''))
        frame.freezer_list.SetItem(idx, 4, entry.get('screenshot_path', ''))


def handle_freezer_open(frame, event):
    idx = frame.freezer_list.GetFirstSelected()
    if idx == -1:
        wx.MessageBox("Select a freeze entry first.", "Info", wx.OK | wx.ICON_INFORMATION)
        return
    folder = frame.freezer_list.GetItemText(idx, col=2)  # timestamp as folder
    if not open_freeze_folder(folder):
        wx.MessageBox("Folder not found.", "Error", wx.OK | wx.ICON_ERROR)


def handle_freezer_delete(frame, event):
    idx = frame.freezer_list.GetFirstSelected()
    if idx == -1:
        wx.MessageBox("Select a freeze entry first.", "Info", wx.OK | wx.ICON_INFORMATION)
        return
    folder = frame.freezer_list.GetItemText(idx, col=2)  # timestamp as folder
    try:
        delete_freeze(folder)
        refresh_freezer_tab(frame)
    except Exception as e:
        wx.MessageBox(f"Delete failed: {e}", "Error", wx.OK | wx.ICON_ERROR)
