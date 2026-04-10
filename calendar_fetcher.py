"""
calendar_fetcher.py
他者のOutlookカレンダーを取得するクラス。
"""

import logging
from datetime import datetime
from outlook_connector import OutlookConnector

logger = logging.getLogger(__name__)

# GetSharedDefaultFolderのフォルダ種別: カレンダー
OL_FOLDER_CALENDAR = 9

# Restrict用の日付フォーマット（Outlookが要求する形式）
RESTRICT_DATE_FORMAT = "%m/%d/%Y %H:%M %p"


class CalendarFetcher:
    """
    他者のOutlookカレンダーを共有権限経由で取得するクラス。
    権限がない場合や取得に失敗した場合は空リストを返す。
    """

    def __init__(self, connector: OutlookConnector):
        """
        Args:
            connector: 接続済みのOutlookConnectorインスタンス
        """
        self._connector = connector

    def get_events(
        self,
        email: str,
        display_name: str,
        start_dt: datetime,
        end_dt: datetime,
    ) -> list:
        """
        指定した相手のカレンダーから、指定期間内の予定を取得する。

        Args:
            email:        対象ユーザーのメールアドレス
            display_name: 表示名（結果の contact_name に使用）
            start_dt:     取得期間の開始日時
            end_dt:       取得期間の終了日時

        Returns:
            list[dict]: 予定情報のリスト。取得失敗時は空リスト。
                        各要素は:
                        {
                            "subject":       str,
                            "start":         datetime,
                            "end":           datetime,
                            "location":      str,
                            "all_day":       bool,
                            "contact_name":  str,
                            "contact_email": str,
                        }
        """
        namespace = self._connector.get_namespace()
        if namespace is None:
            logger.warning("カレンダー取得: Outlookに接続されていません。")
            return []

        try:
            # 受信者オブジェクトを作成して名前解決
            recipient = namespace.CreateRecipient(email)
            resolved = recipient.Resolve()
            if not resolved:
                logger.warning("受信者の名前解決に失敗しました: %s", email)
                return []

            # 共有カレンダーフォルダを取得
            calendar_folder = namespace.GetSharedDefaultFolder(recipient, OL_FOLDER_CALENDAR)

        except Exception as e:
            logger.error("共有カレンダーフォルダの取得に失敗しました（権限なし等）: %s / エラー: %s", email, e)
            return []

        try:
            items = calendar_folder.Items

            # 定期的な予定も展開して期間検索できるよう設定
            items.IncludeRecurrences = True
            items.Sort("[Start]")

            # 期間フィルタ（Restrict）を適用
            filter_str = (
                "[Start] >= '{start}' AND [End] <= '{end}'"
            ).format(
                start=start_dt.strftime(RESTRICT_DATE_FORMAT),
                end=end_dt.strftime(RESTRICT_DATE_FORMAT),
            )
            filtered_items = items.Restrict(filter_str)

            results = []
            for item in filtered_items:
                try:
                    event = self._parse_event(item, display_name, email)
                    if event is not None:
                        results.append(event)
                except Exception as e:
                    logger.debug("予定アイテムの解析中にエラー: %s", e)
                    continue

            logger.info(
                "%s (%s) のカレンダーから %d 件の予定を取得しました。",
                display_name, email, len(results),
            )
            return results

        except Exception as e:
            logger.error("カレンダーアイテムの取得中にエラーが発生しました: %s", e)
            return []

    def _parse_event(self, item, contact_name: str, contact_email: str) -> dict | None:
        """
        Outlookの予定アイテムを辞書形式に変換する。

        Args:
            item:          Outlookの予定アイテム（AppointmentItem）
            contact_name:  所有者の表示名
            contact_email: 所有者のメールアドレス

        Returns:
            dict | None: 変換した予定情報。変換失敗時はNone。
        """
        try:
            subject = getattr(item, "Subject", "") or ""
            location = getattr(item, "Location", "") or ""
            all_day = bool(getattr(item, "AllDayEvent", False))

            # StartプロパティとEndプロパティはpywintypesのdatetime型のため
            # Pythonのdatetimeに変換する
            start_raw = item.Start
            end_raw = item.End

            start_dt = _to_python_datetime(start_raw)
            end_dt = _to_python_datetime(end_raw)

            return {
                "subject": subject,
                "start": start_dt,
                "end": end_dt,
                "location": location,
                "all_day": all_day,
                "contact_name": contact_name,
                "contact_email": contact_email,
            }
        except Exception as e:
            logger.debug("予定の変換に失敗しました: %s", e)
            return None


def _to_python_datetime(pywintypes_dt) -> datetime:
    """
    pywintypesのdatetime（win32com経由の日時オブジェクト）を
    Pythonのdatetimeオブジェクトに変換するヘルパー関数。

    Args:
        pywintypes_dt: pywintypes.datetime オブジェクト

    Returns:
        datetime: 変換後のdatetimeオブジェクト
    """
    try:
        return datetime(
            pywintypes_dt.year,
            pywintypes_dt.month,
            pywintypes_dt.day,
            pywintypes_dt.hour,
            pywintypes_dt.minute,
            pywintypes_dt.second,
        )
    except Exception:
        # フォールバック: そのまま返す
        return pywintypes_dt
