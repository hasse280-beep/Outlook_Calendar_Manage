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

    def search(self, query: str, field: str = "all") -> list:
        """
        GALおよび個人連絡先からqueryに部分一致する連絡先を検索する。
        大文字小文字は区別しない。

        Args:
            query: 検索キーワード（空文字の場合は空リストを返す）
            field: 検索対象フィールド。"all"(全体), "name"(名前), "org"(所属), "email"(メール)

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
            results.extend(self._search_gal(query_lower, field))
        except Exception as e:
            logger.error("GAL検索中にエラーが発生しました: %s", e)

        # 個人連絡先フォルダ検索（上限に達していない場合のみ）
        if len(results) < RESULT_LIMIT:
            try:
                results.extend(self._search_personal_contacts(query_lower, field))
            except Exception as e:
                logger.error("個人連絡先検索中にエラーが発生しました: %s", e)

        # 重複を除去しつつ上限を適用（メールが空の場合は名前で識別）
        seen_keys = set()
        unique_results = []
        for contact in results:
            email = contact["email"].lower()
            key = email if email else f"__name__{contact['name'].lower()}"
            if key not in seen_keys:
                seen_keys.add(key)
                unique_results.append(contact)
            if len(unique_results) >= RESULT_LIMIT:
                break

        return unique_results

    @staticmethod
    def _matches(query_lower: str, field: str, name: str, email: str, org: str) -> bool:
        """指定フィールドでqueryに一致するか判定する。"""
        if field == "name":
            return query_lower in name.lower()
        if field == "org":
            return query_lower in org.lower()
        if field == "email":
            return query_lower in email.lower()
        # "all": いずれかに一致
        return (query_lower in name.lower()
                or query_lower in email.lower()
                or query_lower in org.lower())

    def _search_gal(self, query_lower: str, field: str = "all") -> list:
        """
        GAL（グローバルアドレス一覧）から部分一致検索する。

        Args:
            query_lower: 小文字化済みの検索キーワード
            field:       検索対象フィールド

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

                    if self._matches(query_lower, field, name, email, organization):
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

    def _search_personal_contacts(self, query_lower: str, field: str = "all") -> list:
        """
        個人連絡先フォルダから部分一致検索する。

        Args:
            query_lower: 小文字化済みの検索キーワード
            field:       検索対象フィールド

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

                    if self._matches(query_lower, field, name, email, organization):
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
