"""
group_manager.GroupManager のテスト（Issue #5: メール空の連絡先のグループ追加）。
GROUPS_FILE_PATH をモジュールグローバルとして tmp_path に差し替えて検証する。
"""

import importlib

import pytest

import group_manager as gm_module
from group_manager import GroupManager


@pytest.fixture
def manager(tmp_path, monkeypatch):
    """groups.json を一時ディレクトリに向けた GroupManager を返す。"""
    test_file = tmp_path / "groups.json"
    monkeypatch.setattr(gm_module, "GROUPS_FILE_PATH", test_file)
    return GroupManager()


class TestAddContactEmptyEmail:
    """Issue #5: メールアドレスが空でもグループに追加できること。"""

    def test_add_contact_with_empty_email_succeeds(self, manager):
        manager.create_group("G1")
        ok = manager.add_contact_to_group(
            "G1", {"name": "山田太郎", "email": "", "organization": "営業部"}
        )
        assert ok is True
        contacts = manager.get_group_contacts("G1")
        assert len(contacts) == 1
        assert contacts[0]["name"] == "山田太郎"
        assert contacts[0]["email"] == ""

    def test_add_two_distinct_empty_email_contacts(self, manager):
        # メール空でも名前が異なれば別人として両方追加できる
        manager.create_group("G1")
        assert manager.add_contact_to_group("G1", {"name": "山田", "email": ""}) is True
        assert manager.add_contact_to_group("G1", {"name": "鈴木", "email": ""}) is True
        assert len(manager.get_group_contacts("G1")) == 2

    def test_duplicate_empty_email_same_name_rejected(self, manager):
        # メール空かつ同名は重複として弾く
        manager.create_group("G1")
        assert manager.add_contact_to_group("G1", {"name": "山田", "email": ""}) is True
        assert manager.add_contact_to_group("G1", {"name": "山田", "email": ""}) is False
        assert len(manager.get_group_contacts("G1")) == 1


class TestAddContactEmail:
    """メールありの場合の従来挙動が維持されていること。"""

    def test_duplicate_email_rejected(self, manager):
        manager.create_group("G1")
        assert manager.add_contact_to_group(
            "G1", {"name": "A", "email": "x@example.com"}
        ) is True
        assert manager.add_contact_to_group(
            "G1", {"name": "B", "email": "X@EXAMPLE.COM"}  # 大文字小文字無視
        ) is False
        assert len(manager.get_group_contacts("G1")) == 1

    def test_distinct_emails_added(self, manager):
        manager.create_group("G1")
        assert manager.add_contact_to_group("G1", {"name": "A", "email": "a@x.com"}) is True
        assert manager.add_contact_to_group("G1", {"name": "B", "email": "b@x.com"}) is True
        assert len(manager.get_group_contacts("G1")) == 2

    def test_add_to_missing_group_returns_false(self, manager):
        assert manager.add_contact_to_group(
            "NoSuchGroup", {"name": "A", "email": "a@x.com"}
        ) is False


class TestRemoveAndPersist:
    """削除と永続化の基本動作。"""

    def test_remove_contact_by_email(self, manager):
        manager.create_group("G1")
        manager.add_contact_to_group("G1", {"name": "A", "email": "a@x.com"})
        assert manager.remove_contact_from_group("G1", "a@x.com") is True
        assert manager.get_group_contacts("G1") == []

    def test_persistence_reload(self, manager):
        manager.create_group("G1")
        manager.add_contact_to_group("G1", {"name": "A", "email": ""})
        # 別インスタンスでも同じファイルから読める
        reloaded = GroupManager()
        assert len(reloaded.get_group_contacts("G1")) == 1
