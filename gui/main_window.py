"""
main_window.py
アプリケーションのメインウィンドウ。
"""

import tkinter as tk
from tkinter import ttk

from gui.search_panel import SearchPanel
from gui.calendar_panel import CalendarPanel


class MainWindow:
    """
    Outlookカレンダー管理アプリのメインウィンドウ。
    左パネル（SearchPanel）と右パネル（CalendarPanel）を持つ。
    """

    def __init__(self, connector, searcher, fetcher, group_manager):
        self._connector = connector
        self._searcher = searcher
        self._fetcher = fetcher
        self._group_manager = group_manager

        self._root = tk.Tk()
        self._root.title("Outlook カレンダー管理")
        self._root.geometry("1400x800")
        self._root.minsize(1000, 600)

        self._build_ui()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------

    def _build_ui(self):
        """ウィンドウ全体のレイアウトを構築する。"""

        # ---- ステータスバー（上部）----
        self._status_var = tk.StringVar()
        self._update_status_text()

        status_bar = tk.Frame(self._root, bd=1, relief=tk.SUNKEN)
        status_bar.pack(side=tk.TOP, fill=tk.X)

        status_label = tk.Label(
            status_bar,
            textvariable=self._status_var,
            anchor=tk.W,
            padx=6,
            pady=2,
        )
        status_label.pack(side=tk.LEFT)

        # ---- メインコンテンツエリア ----
        main_frame = tk.Frame(self._root)
        main_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # ---- 左パネル（SearchPanel, 固定幅 300px）----
        left_frame = tk.Frame(main_frame, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        left_frame.pack_propagate(False)  # 幅を固定

        self._search_panel = SearchPanel(
            left_frame,
            searcher=self._searcher,
            group_manager=self._group_manager,
            on_contacts_changed=self._on_contacts_changed,
        )
        self._search_panel.pack(fill=tk.BOTH, expand=True)

        # ---- セパレータ ----
        sep = ttk.Separator(main_frame, orient=tk.VERTICAL)
        sep.pack(side=tk.LEFT, fill=tk.Y)

        # ---- 右パネル（CalendarPanel, 残り）----
        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._calendar_panel = CalendarPanel(
            right_frame,
            fetcher=self._fetcher,
        )
        self._calendar_panel.pack(fill=tk.BOTH, expand=True)

    def _update_status_text(self):
        """接続状態に応じてステータスバーのテキストを更新する。"""
        if self._connector.is_connected():
            self._status_var.set("状態: Outlook に接続済み")
        else:
            self._status_var.set("状態: 未接続")

    # ------------------------------------------------------------------
    # コールバック
    # ------------------------------------------------------------------

    def _on_contacts_changed(self, contacts: list):
        """SearchPanel から連絡先リストが変わった時に呼ばれる。"""
        self._calendar_panel.update_contacts(contacts)

    # ------------------------------------------------------------------
    # 公開 API
    # ------------------------------------------------------------------

    def run(self):
        """メインループを開始する。"""
        self._root.mainloop()
