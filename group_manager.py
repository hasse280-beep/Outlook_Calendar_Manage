"""
group_manager.py
グループ情報をJSONファイルで管理するクラス。
保存先: C:\Users\hasse\Outlook_Calendar_Manage\data\groups.json
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# グループ情報を保存するJSONファイルのパス
GROUPS_FILE_PATH = Path(r"C:\Users\hasse\Outlook_Calendar_Manage\data\groups.json")


class GroupManager:
    """
    グループ（連絡先の集まり）をJSONファイルに永続化して管理するクラス。

    JSONの構造:
    {
        "グループ名": [
            {"name": str, "email": str, "organization": str},
            ...
        ],
        ...
    }
    """

    def __init__(self):
        # dataディレクトリが存在しない場合は作成する
        GROUPS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 読み書きの基本操作
    # ------------------------------------------------------------------

    def load_groups(self) -> dict:
        """
        JSONファイルからグループ情報を読み込む。
        ファイルが存在しない場合は空の辞書を返す。

        Returns:
            dict[str, list[dict]]: グループ名をキー、連絡先リストを値とする辞書
        """
        if not GROUPS_FILE_PATH.exists():
            return {}

        try:
            with open(GROUPS_FILE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning("groups.jsonの形式が不正です。空の辞書を返します。")
                return {}
            return data
        except Exception as e:
            logger.error("groups.jsonの読み込みに失敗しました: %s", e)
            return {}

    def save_groups(self, groups: dict) -> None:
        """
        グループ情報をJSONファイルに保存する。

        Args:
            groups: グループ名をキー、連絡先リストを値とする辞書
        """
        try:
            with open(GROUPS_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(groups, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("groups.jsonの保存に失敗しました: %s", e)

    # ------------------------------------------------------------------
    # グループ操作
    # ------------------------------------------------------------------

    def get_group_names(self) -> list:
        """
        存在するグループ名の一覧を返す。

        Returns:
            list[str]: グループ名のリスト
        """
        return list(self.load_groups().keys())

    def get_group_contacts(self, group_name: str) -> list:
        """
        指定グループに属する連絡先リストを返す。
        グループが存在しない場合は空リストを返す。

        Args:
            group_name: グループ名

        Returns:
            list[dict]: 連絡先情報のリスト
        """
        groups = self.load_groups()
        return list(groups.get(group_name, []))

    def create_group(self, group_name: str) -> bool:
        """
        新しいグループを作成する。
        同名のグループが既に存在する場合はFalseを返す。

        Args:
            group_name: 作成するグループ名

        Returns:
            bool: 作成成功時True、重複時False
        """
        if not group_name or not group_name.strip():
            logger.warning("グループ名が空です。")
            return False

        groups = self.load_groups()
        if group_name in groups:
            logger.warning("グループ '%s' は既に存在します。", group_name)
            return False

        groups[group_name] = []
        self.save_groups(groups)
        logger.info("グループ '%s' を作成しました。", group_name)
        return True

    def delete_group(self, group_name: str) -> bool:
        """
        指定グループを削除する。
        グループが存在しない場合はFalseを返す。

        Args:
            group_name: 削除するグループ名

        Returns:
            bool: 削除成功時True、存在しない場合False
        """
        groups = self.load_groups()
        if group_name not in groups:
            logger.warning("グループ '%s' が見つかりません。", group_name)
            return False

        del groups[group_name]
        self.save_groups(groups)
        logger.info("グループ '%s' を削除しました。", group_name)
        return True

    def add_contact_to_group(self, group_name: str, contact: dict) -> bool:
        """
        指定グループに連絡先を追加する。
        同じメールアドレスの連絡先が既に存在する場合はFalseを返す。

        Args:
            group_name: 追加先のグループ名
            contact:    追加する連絡先情報
                        {"name": str, "email": str, "organization": str}

        Returns:
            bool: 追加成功時True、重複メール時またはグループ不在時False
        """
        groups = self.load_groups()
        if group_name not in groups:
            logger.warning("グループ '%s' が見つかりません。", group_name)
            return False

        new_email = (contact.get("email") or "").lower()
        if not new_email:
            logger.warning("連絡先のメールアドレスが空です。")
            return False

        # 重複チェック（メールアドレスで判定、大文字小文字無視）
        existing_emails = {c.get("email", "").lower() for c in groups[group_name]}
        if new_email in existing_emails:
            logger.warning(
                "メールアドレス '%s' はグループ '%s' に既に存在します。",
                new_email, group_name,
            )
            return False

        # 保存するフィールドを正規化
        normalized = {
            "name": contact.get("name", ""),
            "email": contact.get("email", ""),
            "organization": contact.get("organization", ""),
        }
        groups[group_name].append(normalized)
        self.save_groups(groups)
        logger.info(
            "連絡先 '%s' をグループ '%s' に追加しました。",
            normalized["name"], group_name,
        )
        return True

    def remove_contact_from_group(self, group_name: str, email: str) -> bool:
        """
        指定グループから、指定メールアドレスの連絡先を削除する。

        Args:
            group_name: 削除元のグループ名
            email:      削除する連絡先のメールアドレス

        Returns:
            bool: 削除成功時True、見つからない場合False
        """
        groups = self.load_groups()
        if group_name not in groups:
            logger.warning("グループ '%s' が見つかりません。", group_name)
            return False

        email_lower = (email or "").lower()
        original_count = len(groups[group_name])
        groups[group_name] = [
            c for c in groups[group_name]
            if c.get("email", "").lower() != email_lower
        ]

        if len(groups[group_name]) == original_count:
            logger.warning(
                "メールアドレス '%s' はグループ '%s' に見つかりませんでした。",
                email, group_name,
            )
            return False

        self.save_groups(groups)
        logger.info(
            "メールアドレス '%s' をグループ '%s' から削除しました。",
            email, group_name,
        )
        return True

    def rename_group(self, old_name: str, new_name: str) -> bool:
        """
        グループ名を変更する。
        変更先の名前が既に存在する場合、または元の名前が存在しない場合はFalseを返す。

        Args:
            old_name: 変更前のグループ名
            new_name: 変更後のグループ名

        Returns:
            bool: 変更成功時True、失敗時False
        """
        if not new_name or not new_name.strip():
            logger.warning("新しいグループ名が空です。")
            return False

        groups = self.load_groups()

        if old_name not in groups:
            logger.warning("グループ '%s' が見つかりません。", old_name)
            return False

        if new_name in groups:
            logger.warning("グループ名 '%s' は既に存在します。", new_name)
            return False

        # キーの順序を保ちながらリネーム
        renamed = {}
        for key, value in groups.items():
            if key == old_name:
                renamed[new_name] = value
            else:
                renamed[key] = value

        self.save_groups(renamed)
        logger.info("グループ名を '%s' から '%s' に変更しました。", old_name, new_name)
        return True
