"""
search_panel.py
左パネル: 連絡先検索・表示中連絡先管理・グループ管理。
"""

import tkinter as tk
from tkinter import ttk, simpledialog, messagebox


# 表示中連絡先に割り当てる色パレット（10色）
_COLOR_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]


class SearchPanel(tk.Frame):
    """
    左パネル。
    ・上部: 連絡先検索
    ・中部: 表示中の連絡先
    ・下部: グループ管理
    """

    def __init__(self, parent, searcher, group_manager, on_contacts_changed):
        super().__init__(parent)
        self._searcher = searcher
        self._group_manager = group_manager
        self._on_contacts_changed = on_contacts_changed

        # 表示中連絡先リスト: list[dict]  dict に "color" キーを追加
        self._active_contacts: list = []
        self._color_index = 0

        # デバウンス用タイマーID
        self._debounce_id = None

        # 検索結果キャッシュ
        self._search_results: list = []

        self._build_ui()
        self._load_groups()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------

    def _build_ui(self):
        """パネル全体のレイアウトを構築する。"""

        # === 検索エリア ===
        search_frame = ttk.LabelFrame(self, text="連絡先検索", padding=4)
        search_frame.pack(fill=tk.X, padx=4, pady=4)

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_text_changed)
        search_entry = tk.Entry(search_frame, textvariable=self._search_var)
        search_entry.pack(fill=tk.X, padx=2, pady=2)

        # 検索結果 Listbox
        result_frame = tk.Frame(search_frame)
        result_frame.pack(fill=tk.BOTH, expand=True)

        self._result_listbox = tk.Listbox(
            result_frame, height=8, selectmode=tk.SINGLE
        )
        result_scroll = ttk.Scrollbar(
            result_frame, orient=tk.VERTICAL, command=self._result_listbox.yview
        )
        self._result_listbox.configure(yscrollcommand=result_scroll.set)
        self._result_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        result_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ボタン行
        btn_frame = tk.Frame(search_frame)
        btn_frame.pack(fill=tk.X, pady=2)

        tk.Button(
            btn_frame,
            text="カレンダーに追加",
            command=self._on_add_to_calendar,
        ).pack(side=tk.LEFT, padx=2)

        tk.Button(
            btn_frame,
            text="グループに追加",
            command=self._on_add_to_group,
        ).pack(side=tk.LEFT, padx=2)

        # === 表示中の連絡先エリア ===
        active_frame = ttk.LabelFrame(self, text="表示中の連絡先", padding=4)
        active_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        active_list_frame = tk.Frame(active_frame)
        active_list_frame.pack(fill=tk.BOTH, expand=True)

        self._active_listbox = tk.Listbox(
            active_list_frame, height=8, selectmode=tk.SINGLE
        )
        active_scroll = ttk.Scrollbar(
            active_list_frame, orient=tk.VERTICAL, command=self._active_listbox.yview
        )
        self._active_listbox.configure(yscrollcommand=active_scroll.set)
        self._active_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        active_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Button(
            active_frame,
            text="削除",
            command=self._on_remove_active,
        ).pack(anchor=tk.W, pady=2)

        # === グループ管理エリア ===
        group_frame = ttk.LabelFrame(self, text="グループ管理", padding=4)
        group_frame.pack(fill=tk.BOTH, padx=4, pady=4)

        group_list_frame = tk.Frame(group_frame)
        group_list_frame.pack(fill=tk.BOTH, expand=True)

        self._group_listbox = tk.Listbox(
            group_list_frame, height=6, selectmode=tk.SINGLE
        )
        group_scroll = ttk.Scrollbar(
            group_list_frame, orient=tk.VERTICAL, command=self._group_listbox.yview
        )
        self._group_listbox.configure(yscrollcommand=group_scroll.set)
        self._group_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        group_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 右クリックメニュー
        self._group_context_menu = tk.Menu(self, tearoff=0)
        self._group_context_menu.add_command(
            label="読み込み", command=self._on_load_group
        )
        self._group_context_menu.add_command(
            label="名前変更", command=self._on_rename_group
        )
        self._group_context_menu.add_command(
            label="削除", command=self._on_delete_group
        )
        self._group_listbox.bind("<Button-3>", self._show_group_context_menu)

        # グループ操作ボタン行
        gbtn_frame = tk.Frame(group_frame)
        gbtn_frame.pack(fill=tk.X, pady=2)

        tk.Button(
            gbtn_frame, text="読み込み", command=self._on_load_group
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            gbtn_frame, text="新規グループ", command=self._on_new_group
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            gbtn_frame, text="削除", command=self._on_delete_group
        ).pack(side=tk.LEFT, padx=2)
        tk.Button(
            gbtn_frame, text="名前変更", command=self._on_rename_group
        ).pack(side=tk.LEFT, padx=2)

    # ------------------------------------------------------------------
    # 検索
    # ------------------------------------------------------------------

    def _on_search_text_changed(self, *_):
        """テキスト変更時にデバウンス付きで検索を実行する。"""
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
        self._debounce_id = self.after(300, self._do_search)

    def _do_search(self):
        """実際の検索処理。"""
        query = self._search_var.get().strip()
        self._result_listbox.delete(0, tk.END)
        self._search_results = []

        if not query:
            return

        try:
            results = self._searcher.search(query)
        except Exception as e:
            messagebox.showerror("検索エラー", str(e))
            return

        self._search_results = results
        for contact in results:
            name = contact.get("name", "")
            email = contact.get("email", "")
            org = contact.get("organization", "")
            if org:
                display = f"{name} ({org})"
            else:
                display = f"{name} <{email}>"
            self._result_listbox.insert(tk.END, display)

    # ------------------------------------------------------------------
    # 表示中連絡先の操作
    # ------------------------------------------------------------------

    def _get_selected_search_result(self):
        """検索結果リストで選択中の連絡先 dict を返す。なければ None。"""
        sel = self._result_listbox.curselection()
        if not sel:
            return None
        idx = sel[0]
        if idx >= len(self._search_results):
            return None
        return self._search_results[idx]

    def _add_contact_to_active(self, contact: dict):
        """
        連絡先を表示中リストに追加する。
        重複（email が同じ）は無視する。
        """
        email = contact.get("email", "")
        for c in self._active_contacts:
            if c.get("email") == email:
                messagebox.showinfo("情報", f"{contact.get('name')} はすでに追加されています。")
                return

        color = _COLOR_PALETTE[self._color_index % len(_COLOR_PALETTE)]
        self._color_index += 1

        enriched = dict(contact)
        enriched["color"] = color
        self._active_contacts.append(enriched)
        self._refresh_active_listbox()
        self._notify_contacts_changed()

    def _refresh_active_listbox(self):
        """表示中連絡先 Listbox を再描画する。"""
        self._active_listbox.delete(0, tk.END)
        for i, contact in enumerate(self._active_contacts):
            name = contact.get("name", "")
            email = contact.get("email", "")
            color = contact.get("color", "#000000")
            self._active_listbox.insert(tk.END, f"  {name} <{email}>")
            self._active_listbox.itemconfigure(i, foreground=color)

    def _notify_contacts_changed(self):
        """CalendarPanel へ表示中連絡先の変更を通知する。"""
        self._on_contacts_changed(list(self._active_contacts))

    def _on_add_to_calendar(self):
        """「カレンダーに追加」ボタン処理。"""
        contact = self._get_selected_search_result()
        if contact is None:
            messagebox.showwarning("警告", "連絡先を選択してください。")
            return
        self._add_contact_to_active(contact)

    def _on_remove_active(self):
        """「削除」ボタン処理。"""
        sel = self._active_listbox.curselection()
        if not sel:
            messagebox.showwarning("警告", "削除する連絡先を選択してください。")
            return
        idx = sel[0]
        self._active_contacts.pop(idx)
        self._refresh_active_listbox()
        self._notify_contacts_changed()

    # ------------------------------------------------------------------
    # グループ操作
    # ------------------------------------------------------------------

    def _load_groups(self):
        """グループ一覧を GroupManager から読み込む。"""
        self._group_listbox.delete(0, tk.END)
        try:
            names = self._group_manager.get_group_names()
        except Exception as e:
            messagebox.showerror("エラー", f"グループ読み込み失敗: {e}")
            return
        for name in names:
            self._group_listbox.insert(tk.END, name)

    def _get_selected_group_name(self):
        """グループ Listbox で選択中のグループ名を返す。なければ None。"""
        sel = self._group_listbox.curselection()
        if not sel:
            return None
        return self._group_listbox.get(sel[0])

    def _on_load_group(self):
        """「読み込み」: グループの全連絡先を表示中に追加する。"""
        name = self._get_selected_group_name()
        if name is None:
            messagebox.showwarning("警告", "グループを選択してください。")
            return
        try:
            contacts = self._group_manager.get_group_contacts(name)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return
        for contact in contacts:
            self._add_contact_to_active(contact)

    def _on_new_group(self):
        """「新規グループ」ボタン処理。"""
        name = simpledialog.askstring("新規グループ", "グループ名を入力してください:")
        if not name:
            return
        try:
            ok = self._group_manager.create_group(name)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return
        if ok:
            self._load_groups()
        else:
            messagebox.showerror("エラー", "グループの作成に失敗しました。")

    def _on_delete_group(self):
        """「削除」ボタン処理。"""
        name = self._get_selected_group_name()
        if name is None:
            messagebox.showwarning("警告", "削除するグループを選択してください。")
            return
        if not messagebox.askyesno("確認", f"グループ「{name}」を削除しますか?"):
            return
        try:
            ok = self._group_manager.delete_group(name)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return
        if ok:
            self._load_groups()
        else:
            messagebox.showerror("エラー", "グループの削除に失敗しました。")

    def _on_rename_group(self):
        """「名前変更」ボタン処理。"""
        old_name = self._get_selected_group_name()
        if old_name is None:
            messagebox.showwarning("警告", "名前変更するグループを選択してください。")
            return
        new_name = simpledialog.askstring(
            "名前変更", f"新しいグループ名を入力してください（現在: {old_name}）:"
        )
        if not new_name or new_name == old_name:
            return
        try:
            ok = self._group_manager.rename_group(old_name, new_name)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return
        if ok:
            self._load_groups()
        else:
            messagebox.showerror("エラー", "グループの名前変更に失敗しました。")

    def _on_add_to_group(self):
        """「グループに追加」ボタン処理。検索結果の連絡先を選択グループに追加する。"""
        contact = self._get_selected_search_result()
        if contact is None:
            messagebox.showwarning("警告", "連絡先を選択してください。")
            return

        try:
            group_names = self._group_manager.get_group_names()
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return

        # グループ選択ダイアログ
        dialog = _GroupSelectDialog(self, group_names)
        self.wait_window(dialog)

        result = dialog.result
        if result is None:
            return  # キャンセル

        if result == "__new__":
            group_name = simpledialog.askstring("新規グループ", "グループ名を入力してください:")
            if not group_name:
                return
            try:
                self._group_manager.create_group(group_name)
                self._load_groups()
            except Exception as e:
                messagebox.showerror("エラー", str(e))
                return
        else:
            group_name = result

        # 連絡先をグループに追加
        group_contact = {
            "name": contact.get("name", ""),
            "email": contact.get("email", ""),
            "organization": contact.get("organization", ""),
        }
        try:
            ok = self._group_manager.add_contact_to_group(group_name, group_contact)
        except Exception as e:
            messagebox.showerror("エラー", str(e))
            return

        if ok:
            messagebox.showinfo(
                "完了",
                f"{contact.get('name')} をグループ「{group_name}」に追加しました。",
            )
        else:
            messagebox.showerror("エラー", "グループへの追加に失敗しました。")

    def _show_group_context_menu(self, event):
        """グループ Listbox の右クリックメニューを表示する。"""
        # クリックした行を選択
        idx = self._group_listbox.nearest(event.y)
        if idx >= 0:
            self._group_listbox.selection_clear(0, tk.END)
            self._group_listbox.selection_set(idx)
        try:
            self._group_context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self._group_context_menu.grab_release()


# ------------------------------------------------------------------
# グループ選択ダイアログ
# ------------------------------------------------------------------

class _GroupSelectDialog(tk.Toplevel):
    """グループを選択するか新規作成を選べる小ダイアログ。"""

    def __init__(self, parent, group_names: list):
        super().__init__(parent)
        self.title("グループを選択")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        tk.Label(self, text="追加するグループを選択してください:").pack(padx=10, pady=(10, 4))

        self._listbox = tk.Listbox(self, height=8, selectmode=tk.SINGLE, width=30)
        self._listbox.pack(padx=10, pady=4, fill=tk.BOTH, expand=True)
        for name in group_names:
            self._listbox.insert(tk.END, name)

        btn_frame = tk.Frame(self)
        btn_frame.pack(padx=10, pady=8)

        tk.Button(btn_frame, text="選択", command=self._on_select).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="新規作成", command=self._on_new).pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="キャンセル", command=self.destroy).pack(side=tk.LEFT, padx=4)

        self._listbox.bind("<Double-1>", lambda _: self._on_select())

    def _on_select(self):
        sel = self._listbox.curselection()
        if not sel:
            messagebox.showwarning("警告", "グループを選択してください。", parent=self)
            return
        self.result = self._listbox.get(sel[0])
        self.destroy()

    def _on_new(self):
        self.result = "__new__"
        self.destroy()
