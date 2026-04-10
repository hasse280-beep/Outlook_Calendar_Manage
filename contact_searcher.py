"""
contact_searcher.py
GAL（グローバルアドレス一覧）と個人連絡先からの検索クラス。
"""

import logging
from outlook_connector import OutlookConnector

logger = logging.getLogger(__name__)

# 検索時にイテレートするGALエントリの最大件数
GAL_ITERATE_LIMIT = 200

# 最終的に返す検索結果の上限件数
RESULT_LIMIT = 50

# win32comのAddressEntryTypeの定数（個人連絡先フォルダのolFolderContacts番号）
OL_FOLDER_CONTACTS = 10


class ContactSearcher:
    """
    OutlookのGAL（グローバルアドレス一覧）および個人連絡先フォルダから
    キーワード検索を行うクラス。
    """

    def __init__(self, connector: OutlookConnector):
        """
        Args:
            connector: 接続済みのOutlookConnectorインスタンス
        """
        self._connector = connector

    def search(self, query: str) -> list:
        """
        GALおよび個人連絡先からqueryに部分一致する連絡先を検索する。
        大文字小文字は区別しない。

        Args:
            query: 検索キーワード（空文字の場合は空リストを返す）

        Returns:
            list[dict]: 最大50件の連絡先情報リスト。
                        各要素は {"name": str, "email": str, "organization": str, "type": str}
        """
        if not query or not query.strip():
            return []

        query_lower = query.strip().lower()
        results = []

        # GAL検索
        try:
            results.extend(self._search_gal(query_lower))
        except Exception as e:
            logger.error("GAL検索中にエラーが発生しました: %s", e)

        # 個人連絡先フォルダ検索（上限に達していない場合のみ）
        if len(results) < RESULT_LIMIT:
            try:
                results.extend(self._search_personal_contacts(query_lower))
            except Exception as e:
                logger.error("個人連絡先検索中にエラーが発生しました: %s", e)

        # 重複メールアドレスを除去しつつ上限を適用
        seen_emails = set()
        unique_results = []
        for contact in results:
            email_key = contact["email"].lower()
            if email_key not in seen_emails:
                seen_emails.add(email_key)
                unique_results.append(contact)
            if len(unique_results) >= RESULT_LIMIT:
                break

        return unique_results

    def _search_gal(self, query_lower: str) -> list:
        """
        GAL（グローバルアドレス一覧）から部分一致検索する。

        Args:
            query_lower: 小文字化済みの検索キーワード

        Returns:
            list[dict]: 見つかった連絡先リスト
        """
        namespace = self._connector.get_namespace()
        if namespace is None:
            logger.warning("GAL検索: Outlookに接続されていません。")
            return []

        results = []

        try:
            gal = namespace.AddressLists.Item("グローバル アドレス一覧")
        except Exception:
            # 日本語名で取得失敗した場合は英語名を試みる
            try:
                gal = namespace.AddressLists.Item("Global Address List")
            except Exception as e:
                logger.error("GALの取得に失敗しました: %s", e)
                return []

        try:
            entries = gal.AddressEntries
            count = min(entries.Count, GAL_ITERATE_LIMIT)

            for i in range(1, count + 1):
                try:
                    entry = entries.Item(i)
                    name = entry.Name or ""
                    email = ""
                    organization = ""

                    # Exchange Userの場合は詳細情報を取得
                    try:
                        exchange_user = entry.GetExchangeUser()
                        if exchange_user is not None:
                            email = exchange_user.PrimarySmtpAddress or ""
                            organization = exchange_user.CompanyName or ""
                    except Exception:
                        # Exchange User以外の場合はAddressを使用
                        email = getattr(entry, "Address", "") or ""

                    # queryがname・emailのいずれかに部分一致するか確認
                    if query_lower in name.lower() or query_lower in email.lower():
                        results.append({
                            "name": name,
                            "email": email,
                            "organization": organization,
                            "type": "GAL",
                        })

                    if len(results) >= RESULT_LIMIT:
                        break

                except Exception as e:
                    logger.debug("GALエントリ %d の処理中にエラー: %s", i, e)
                    continue

        except Exception as e:
            logger.error("GALエントリのイテレート中にエラーが発生しました: %s", e)

        return results

    def _search_personal_contacts(self, query_lower: str) -> list:
        """
        個人連絡先フォルダから部分一致検索する。

        Args:
            query_lower: 小文字化済みの検索キーワード

        Returns:
            list[dict]: 見つかった連絡先リスト
        """
        namespace = self._connector.get_namespace()
        if namespace is None:
            logger.warning("個人連絡先検索: Outlookに接続されていません。")
            return []

        results = []

        try:
            contacts_folder = namespace.GetDefaultFolder(OL_FOLDER_CONTACTS)
            items = contacts_folder.Items

            for item in items:
                try:
                    # 連絡先アイテム（olContact = 40）のみ対象
                    if item.Class != 40:
                        continue

                    name = getattr(item, "FullName", "") or ""
                    email = getattr(item, "Email1Address", "") or ""
                    organization = getattr(item, "CompanyName", "") or ""

                    # queryがname・emailのいずれかに部分一致するか確認
                    if query_lower in name.lower() or query_lower in email.lower():
                        results.append({
                            "name": name,
                            "email": email,
                            "organization": organization,
                            "type": "個人連絡先",
                        })

                    if len(results) >= RESULT_LIMIT:
                        break

                except Exception as e:
                    logger.debug("個人連絡先アイテムの処理中にエラー: %s", e)
                    continue

        except Exception as e:
            logger.error("個人連絡先フォルダの取得に失敗しました: %s", e)

        return results
