"""
calendar_panel.py
右パネル: 週ビューのカレンダー表示（Canvas 使用）。
"""

import threading
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta, date


# 連絡先ごとの色パレット（10色）
_COLOR_PALETTE = [
    "#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
    "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC",
]

# カレンダーの表示時間帯
_HOUR_START = 6
_HOUR_END = 22  # 22時まで（22:00 の行まで）

# 列の設定
_DAYS = ["月", "火", "水", "木", "金", "土", "日"]

# 左端（時間軸）の幅
_TIME_COL_WIDTH = 48
# 上端（日付行）の高さ
_HEADER_HEIGHT = 36
# 終日イベントエリアの高さ
_ALLDAY_HEIGHT = 24
# 1時間あたりのピクセル高さ
_HOUR_HEIGHT = 48


class CalendarPanel(tk.Frame):
    """
    週ビューのカレンダーパネル。
    連絡先リストを受け取り、イベントを取得して Canvas に描画する。
    """

    def __init__(self, parent, fetcher):
        super().__init__(parent)
        self._fetcher = fetcher

        # 現在表示中の週の月曜日
        today = date.today()
        self._week_monday = today - timedelta(days=today.weekday())

        # 連絡先リスト（colorキー付き）
        self._contacts: list = []
        # 取得済みイベント: list[dict]
        self._events: list = []

        # 取得スレッド
        self._fetch_thread: threading.Thread | None = None
        self._fetch_lock = threading.Lock()

        self._build_ui()

    # ------------------------------------------------------------------
    # UI構築
    # ------------------------------------------------------------------

    def _build_ui(self):
        """パネル全体のレイアウトを構築する。"""

        # ---- ナビゲーションバー ----
        nav_frame = tk.Frame(self, pady=4)
        nav_frame.pack(side=tk.TOP, fill=tk.X)

        tk.Button(nav_frame, text="← 前週", command=self._on_prev_week).pack(
            side=tk.LEFT, padx=6
        )
        tk.Button(nav_frame, text="今週", command=self._on_this_week).pack(
            side=tk.LEFT, padx=2
        )
        tk.Button(nav_frame, text="次週 →", command=self._on_next_week).pack(
            side=tk.LEFT, padx=6
        )

        self._week_label_var = tk.StringVar()
        tk.Label(nav_frame, textvariable=self._week_label_var, font=("", 11, "bold")).pack(
            side=tk.LEFT, padx=12
        )

        self._loading_var = tk.StringVar(value="")
        tk.Label(nav_frame, textvariable=self._loading_var, fg="gray").pack(
            side=tk.LEFT, padx=8
        )

        self._update_week_label()

        # ---- カレンダー本体 + 凡例 ----
        body_frame = tk.Frame(self)
        body_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Canvas（スクロール可）
        canvas_frame = tk.Frame(body_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._canvas = tk.Canvas(canvas_frame, bg="white", highlightthickness=0)
        v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._canvas.yview)
        h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL, command=self._canvas.xview)

        self._canvas.configure(
            yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set
        )
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # マウスホイールスクロール
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # 凡例パネル（右端、固定幅）
        legend_outer = tk.Frame(body_frame, width=140)
        legend_outer.pack(side=tk.RIGHT, fill=tk.Y)
        legend_outer.pack_propagate(False)

        tk.Label(legend_outer, text="凡例", font=("", 10, "bold")).pack(pady=(8, 4))

        self._legend_frame = tk.Frame(legend_outer)
        self._legend_frame.pack(fill=tk.BOTH, expand=True, padx=4)

    # ------------------------------------------------------------------
    # ナビゲーション
    # ------------------------------------------------------------------

    def _on_prev_week(self):
        self._week_monday -= timedelta(weeks=1)
        self._update_week_label()
        self._fetch_events()

    def _on_this_week(self):
        today = date.today()
        self._week_monday = today - timedelta(days=today.weekday())
        self._update_week_label()
        self._fetch_events()

    def _on_next_week(self):
        self._week_monday += timedelta(weeks=1)
        self._update_week_label()
        self._fetch_events()

    def _update_week_label(self):
        """週ラベルを "YYYY年M月D日 〜 M月D日" の形式で更新する。"""
        start = self._week_monday
        end = start + timedelta(days=6)
        if start.month == end.month:
            label = f"{start.year}年{start.month}月{start.day}日 〜 {end.day}日"
        else:
            label = (
                f"{start.year}年{start.month}月{start.day}日 "
                f"〜 {end.month}月{end.day}日"
            )
        self._week_label_var.set(label)

    # ------------------------------------------------------------------
    # イベント取得（バックグラウンドスレッド）
    # ------------------------------------------------------------------

    def update_contacts(self, contacts: list):
        """SearchPanel からの連絡先変更通知。"""
        self._contacts = contacts
        self._refresh_legend()
        self._fetch_events()

    def _fetch_events(self):
        """バックグラウンドスレッドでイベントを取得する。"""
        if not self._contacts:
            self._events = []
            self._draw_calendar()
            return

        start_dt = datetime.combine(self._week_monday, datetime.min.time())
        end_dt = datetime.combine(self._week_monday + timedelta(days=6), datetime.max.time())

        contacts_snapshot = list(self._contacts)
        self._loading_var.set("読み込み中...")

        def worker():
            all_events = []
            for contact in contacts_snapshot:
                try:
                    events = self._fetcher.get_events(
                        email=contact.get("email", ""),
                        display_name=contact.get("name", ""),
                        start_dt=start_dt,
                        end_dt=end_dt,
                    )
                    # 色情報を付加
                    for ev in events:
                        ev["_color"] = contact.get("color", "#888888")
                        ev["contact_name"] = contact.get("name", "")
                        ev["contact_email"] = contact.get("email", "")
                    all_events.extend(events)
                except Exception:
                    pass
            self.after(0, lambda: self._on_fetch_done(all_events))

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def _on_fetch_done(self, events: list):
        """イベント取得完了後、メインスレッドで UI を更新する。"""
        self._events = events
        self._loading_var.set("")
        self._draw_calendar()

    # ------------------------------------------------------------------
    # 描画
    # ------------------------------------------------------------------

    def _on_canvas_configure(self, event):
        """Canvas サイズ変更時に再描画する。"""
        self._draw_calendar()

    def _day_col_width(self) -> int:
        """1日分の列幅を Canvas 幅から計算する。"""
        canvas_w = self._canvas.winfo_width()
        available = max(canvas_w - _TIME_COL_WIDTH, 7 * 80)
        return available // 7

    def _draw_calendar(self):
        """Canvas 全体を描画する。"""
        self._canvas.delete("all")

        col_w = self._day_col_width()
        hour_count = _HOUR_END - _HOUR_START  # 表示する時間数
        total_h = _HEADER_HEIGHT + _ALLDAY_HEIGHT + hour_count * _HOUR_HEIGHT
        total_w = _TIME_COL_WIDTH + 7 * col_w

        self._canvas.configure(scrollregion=(0, 0, total_w, total_h))

        # ---- 日付ヘッダー ----
        self._draw_header(col_w)

        # ---- 終日イベントエリア ----
        self._draw_allday_area(col_w)

        # ---- 時間グリッド ----
        self._draw_time_grid(col_w, hour_count)

        # ---- 通常イベント ----
        self._draw_events(col_w)

    def _draw_header(self, col_w: int):
        """日付ヘッダー行を描画する。"""
        monday = self._week_monday
        today = date.today()

        for i, day_label in enumerate(_DAYS):
            d = monday + timedelta(days=i)
            x0 = _TIME_COL_WIDTH + i * col_w
            x1 = x0 + col_w
            y0 = 0
            y1 = _HEADER_HEIGHT

            bg = "#E8F4FD" if d == today else "#F5F5F5"
            self._canvas.create_rectangle(x0, y0, x1, y1, fill=bg, outline="#CCCCCC")

            text = f"{day_label}\n{d.month}/{d.day}"
            font_style = ("", 9, "bold") if d == today else ("", 9)
            self._canvas.create_text(
                (x0 + x1) // 2, (y0 + y1) // 2,
                text=text, font=font_style, justify=tk.CENTER
            )

    def _draw_allday_area(self, col_w: int):
        """終日イベント行を描画する。"""
        y0 = _HEADER_HEIGHT
        y1 = y0 + _ALLDAY_HEIGHT

        # ラベル
        self._canvas.create_rectangle(0, y0, _TIME_COL_WIDTH, y1, fill="#F0F0F0", outline="#CCCCCC")
        self._canvas.create_text(
            _TIME_COL_WIDTH // 2, (y0 + y1) // 2, text="終日", font=("", 8)
        )

        # 各列の背景
        for i in range(7):
            x0 = _TIME_COL_WIDTH + i * col_w
            x1 = x0 + col_w
            self._canvas.create_rectangle(x0, y0, x1, y1, fill="white", outline="#CCCCCC")

        # 終日イベントを描画
        allday_events = [e for e in self._events if e.get("all_day")]
        allday_by_day: dict[int, list] = {i: [] for i in range(7)}
        for ev in allday_events:
            day_idx = self._event_day_index(ev)
            if day_idx is not None:
                allday_by_day[day_idx].append(ev)

        for i in range(7):
            for ev in allday_by_day[i]:
                x0 = _TIME_COL_WIDTH + i * col_w + 2
                x1 = _TIME_COL_WIDTH + (i + 1) * col_w - 2
                color = ev.get("_color", "#888888")
                item = self._canvas.create_rectangle(
                    x0, y0 + 3, x1, y1 - 3,
                    fill=color, outline="white"
                )
                text_item = self._canvas.create_text(
                    (x0 + x1) // 2, (y0 + y1) // 2,
                    text=ev.get("subject", ""),
                    font=("", 8), fill="white",
                    width=x1 - x0 - 4
                )
                self._bind_event_popup(item, ev)
                self._bind_event_popup(text_item, ev)

    def _draw_time_grid(self, col_w: int, hour_count: int):
        """時間グリッドを描画する。"""
        y_offset = _HEADER_HEIGHT + _ALLDAY_HEIGHT

        for h_idx in range(hour_count + 1):
            hour = _HOUR_START + h_idx
            y = y_offset + h_idx * _HOUR_HEIGHT

            # 時間ラベル
            self._canvas.create_text(
                _TIME_COL_WIDTH - 4, y + 2,
                text=f"{hour:02d}:00", font=("", 8), anchor=tk.NE
            )

            # 横線（各列にわたって）
            self._canvas.create_line(
                _TIME_COL_WIDTH, y,
                _TIME_COL_WIDTH + 7 * col_w, y,
                fill="#E0E0E0"
            )

            # 30分線
            if h_idx < hour_count:
                y_half = y + _HOUR_HEIGHT // 2
                self._canvas.create_line(
                    _TIME_COL_WIDTH, y_half,
                    _TIME_COL_WIDTH + 7 * col_w, y_half,
                    fill="#F0F0F0", dash=(2, 4)
                )

        # 縦線（列区切り）
        for i in range(8):
            x = _TIME_COL_WIDTH + i * col_w
            self._canvas.create_line(
                x, _HEADER_HEIGHT,
                x, _HEADER_HEIGHT + _ALLDAY_HEIGHT + hour_count * _HOUR_HEIGHT,
                fill="#CCCCCC"
            )

    def _draw_events(self, col_w: int):
        """通常イベント（終日以外）を描画する。"""
        y_offset = _HEADER_HEIGHT + _ALLDAY_HEIGHT
        normal_events = [e for e in self._events if not e.get("all_day")]

        # 同日同時間帯の重複イベントを処理するため日付×時間でグループ化
        day_events: dict[int, list] = {i: [] for i in range(7)}
        for ev in normal_events:
            day_idx = self._event_day_index(ev)
            if day_idx is not None:
                day_events[day_idx].append(ev)

        for day_idx, events in day_events.items():
            if not events:
                continue

            # 同時間帯のイベントを列に割り当て
            columns = self._assign_columns(events)
            total_cols = max(c for _, c in columns.values()) + 1 if columns else 1

            for ev, col_num in columns.items():
                start_dt: datetime = ev.get("start")
                end_dt: datetime = ev.get("end")
                if start_dt is None or end_dt is None:
                    continue

                # Y 座標を計算
                y_top = self._time_to_y(start_dt.hour, start_dt.minute, y_offset)
                y_bottom = self._time_to_y(end_dt.hour, end_dt.minute, y_offset)
                if y_bottom <= y_top:
                    y_bottom = y_top + _HOUR_HEIGHT // 4  # 最小高さ保証

                # X 座標を計算（列内で分割）
                day_x0 = _TIME_COL_WIDTH + day_idx * col_w
                sub_w = col_w // total_cols
                x0 = day_x0 + col_num * sub_w + 2
                x1 = day_x0 + (col_num + 1) * sub_w - 2

                color = ev.get("_color", "#888888")
                rect = self._canvas.create_rectangle(
                    x0, y_top, x1, y_bottom,
                    fill=color, outline="white", width=1
                )

                # テキスト（件名 + 開始時刻）
                subject = ev.get("subject", "（件名なし）")
                time_str = start_dt.strftime("%H:%M")
                display_text = f"{time_str}\n{subject}"
                text = self._canvas.create_text(
                    x0 + 4, y_top + 4,
                    text=display_text,
                    font=("", 8), fill="white",
                    anchor=tk.NW,
                    width=x1 - x0 - 6
                )

                self._bind_event_popup(rect, ev)
                self._bind_event_popup(text, ev)

    def _time_to_y(self, hour: int, minute: int, y_offset: int) -> int:
        """時刻を Y 座標に変換する。"""
        h = max(_HOUR_START, min(_HOUR_END, hour))
        m = minute
        return y_offset + int((h - _HOUR_START + m / 60) * _HOUR_HEIGHT)

    def _event_day_index(self, ev: dict) -> int | None:
        """イベントが今週の何曜日（0=月〜6=日）に属するか返す。範囲外は None。"""
        if ev.get("all_day"):
            start = ev.get("start")
            if start is None:
                return None
            if isinstance(start, datetime):
                d = start.date()
            else:
                d = start
        else:
            start = ev.get("start")
            if start is None:
                return None
            if isinstance(start, datetime):
                d = start.date()
            else:
                d = start

        delta = (d - self._week_monday).days
        if 0 <= delta <= 6:
            return delta
        return None

    def _assign_columns(self, events: list) -> dict:
        """
        同日のイベントリストを受け取り、重複を考慮して列番号を割り当てる。
        Returns: {ev: col_num}
        """
        result = {}
        # 開始時刻でソート
        sorted_events = sorted(events, key=lambda e: e.get("start") or datetime.min)
        columns: list[datetime] = []  # 各列の最後の終了時刻

        for ev in sorted_events:
            start = ev.get("start") or datetime.min
            end = ev.get("end") or (start + timedelta(hours=1))

            placed = False
            for col_idx, col_end in enumerate(columns):
                if start >= col_end:
                    result[ev] = col_idx
                    columns[col_idx] = end
                    placed = True
                    break
            if not placed:
                result[ev] = len(columns)
                columns.append(end)

        return result

    # ------------------------------------------------------------------
    # イベントポップアップ
    # ------------------------------------------------------------------

    def _bind_event_popup(self, canvas_item, ev: dict):
        """Canvas アイテムにクリックでポップアップを表示するバインドを設定する。"""
        self._canvas.tag_bind(
            canvas_item, "<Button-1>", lambda e, ev=ev: self._show_event_popup(e, ev)
        )

    def _show_event_popup(self, tk_event, ev: dict):
        """イベント詳細をポップアップ表示する。"""
        popup = tk.Toplevel(self)
        popup.title("イベント詳細")
        popup.resizable(False, False)

        # クリック位置付近に表示
        popup.geometry(f"+{tk_event.x_root + 10}+{tk_event.y_root + 10}")

        pad = {"padx": 8, "pady": 2, "anchor": tk.W}

        subject = ev.get("subject", "（件名なし）")
        tk.Label(popup, text=subject, font=("", 11, "bold")).pack(**pad, pady=(8, 2))

        ttk.Separator(popup, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=8, pady=4)

        contact_name = ev.get("contact_name", "")
        contact_email = ev.get("contact_email", "")
        if contact_name:
            tk.Label(popup, text=f"連絡先: {contact_name} <{contact_email}>").pack(**pad)

        if ev.get("all_day"):
            start = ev.get("start")
            date_str = start.strftime("%Y/%m/%d") if isinstance(start, datetime) else str(start)
            tk.Label(popup, text=f"日付: {date_str}（終日）").pack(**pad)
        else:
            start: datetime = ev.get("start")
            end: datetime = ev.get("end")
            if start and end:
                tk.Label(
                    popup,
                    text=(
                        f"開始: {start.strftime('%Y/%m/%d %H:%M')}\n"
                        f"終了: {end.strftime('%Y/%m/%d %H:%M')}"
                    ),
                ).pack(**pad)

        location = ev.get("location", "")
        if location:
            tk.Label(popup, text=f"場所: {location}").pack(**pad)

        tk.Button(popup, text="閉じる", command=popup.destroy).pack(pady=8)

        # ポップアップ外クリックで閉じる
        popup.bind("<FocusOut>", lambda _: popup.destroy())
        popup.focus_set()

    # ------------------------------------------------------------------
    # 凡例
    # ------------------------------------------------------------------

    def _refresh_legend(self):
        """凡例エリアを連絡先リストに合わせて更新する。"""
        for widget in self._legend_frame.winfo_children():
            widget.destroy()

        for contact in self._contacts:
            color = contact.get("color", "#888888")
            name = contact.get("name", "")
            row = tk.Frame(self._legend_frame)
            row.pack(anchor=tk.W, pady=2)
            # 色見本
            swatch = tk.Canvas(row, width=16, height=16, highlightthickness=0, bg=color)
            swatch.pack(side=tk.LEFT, padx=(0, 4))
            tk.Label(row, text=name, font=("", 9), wraplength=110, justify=tk.LEFT).pack(
                side=tk.LEFT
            )

    # ------------------------------------------------------------------
    # スクロール
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event):
        self._canvas.yview_scroll(-1 * (event.delta // 120), "units")
