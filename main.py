"""
main.py
Outlookカレンダー管理アプリのエントリポイント。
"""

import tkinter as tk
from tkinter import messagebox

from outlook_connector import OutlookConnector
from contact_searcher import ContactSearcher
from calendar_fetcher import CalendarFetcher
from group_manager import GroupManager
from gui.main_window import MainWindow


def main():
    connector = OutlookConnector()

    if not connector.connect():
        # tkinterのエラーダイアログを表示して終了
        root = tk.Tk()
        root.withdraw()  # メインウィンドウは表示しない
        messagebox.showerror(
            "接続エラー",
            "Outlook への接続に失敗しました。\n"
            "Outlook がインストールされているか確認してください。",
        )
        root.destroy()
        return

    searcher = ContactSearcher(connector)
    fetcher = CalendarFetcher(connector)
    gm = GroupManager()

    window = MainWindow(connector, searcher, fetcher, gm)
    window.run()


if __name__ == "__main__":
    main()
