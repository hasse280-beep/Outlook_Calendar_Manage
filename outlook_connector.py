"""
outlook_connector.py
win32com経由でローカルOutlookに接続するクラス。
"""

import logging
import win32com.client

logger = logging.getLogger(__name__)


class OutlookConnector:
    """
    ローカルにインストールされたOutlookへのCOM接続を管理するクラス。
    接続状態を保持し、MAPIネームスペースを提供する。
    """

    def __init__(self):
        self._outlook = None       # Outlook.Applicationオブジェクト
        self._namespace = None     # MAPIネームスペースオブジェクト
        self._connected = False    # 接続フラグ

    def connect(self) -> bool:
        """
        Outlookアプリケーションに接続し、MAPIネームスペースを取得する。

        Returns:
            bool: 接続成功時True、失敗時False
        """
        try:
            # 既存のOutlookプロセスに接続、なければ起動
            self._outlook = win32com.client.Dispatch("Outlook.Application")
            self._namespace = self._outlook.GetNamespace("MAPI")

            # ログオン（既にログオン済みの場合は何もしない）
            self._namespace.Logon()

            self._connected = True
            logger.info("Outlookへの接続に成功しました。")
            return True

        except Exception as e:
            logger.error("Outlookへの接続に失敗しました: %s", e)
            self._outlook = None
            self._namespace = None
            self._connected = False
            return False

    def get_namespace(self):
        """
        MAPIネームスペースオブジェクトを返す。
        未接続の場合はNoneを返す。

        Returns:
            win32com.client.Dispatch | None: MAPIネームスペース
        """
        if not self._connected:
            logger.warning("Outlookに接続されていません。先にconnect()を呼び出してください。")
            return None
        return self._namespace

    def is_connected(self) -> bool:
        """
        現在Outlookに接続中かどうかを返す。

        Returns:
            bool: 接続中の場合True
        """
        return self._connected
