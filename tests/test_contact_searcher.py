"""
contact_searcher.ContactSearcher._matches の純粋ロジックテスト（Issue #5）。
COM 依存部（_search_gal / _search_personal_contacts）は対象外。
"""

from contact_searcher import ContactSearcher


class TestMatchesField:
    """検索対象フィールド指定（all / name / org / email）の判定テスト。"""

    def test_field_name_hits_only_name(self):
        m = ContactSearcher._matches
        assert m("yamada", "name", "Yamada Taro", "t.s@example.com", "営業部") is True
        # 名前に無いキーワードはメール・所属に在っても name 指定ではヒットしない
        assert m("example", "name", "Yamada Taro", "t.s@example.com", "営業部") is False

    def test_field_org_hits_only_org(self):
        m = ContactSearcher._matches
        assert m("営業", "org", "Yamada Taro", "t.s@example.com", "営業部") is True
        assert m("yamada", "org", "Yamada Taro", "t.s@example.com", "営業部") is False

    def test_field_email_hits_only_email(self):
        m = ContactSearcher._matches
        assert m("example.com", "email", "Yamada", "t.s@example.com", "営業部") is True
        assert m("yamada", "email", "Yamada", "t.s@example.com", "営業部") is False

    def test_field_all_hits_any(self):
        m = ContactSearcher._matches
        assert m("yamada", "all", "Yamada", "x@y.com", "営業部") is True
        assert m("y.com", "all", "Yamada", "x@y.com", "営業部") is True
        assert m("営業", "all", "Yamada", "x@y.com", "営業部") is True
        assert m("zzz", "all", "Yamada", "x@y.com", "営業部") is False

    def test_haystack_case_insensitive(self):
        # _matches の契約: queryは呼び出し側で小文字化済み（引数名 query_lower）。
        # 一致対象(name/email/org)側が大文字でも小文字クエリでヒットすること。
        m = ContactSearcher._matches
        assert m("yamada", "name", "YAMADA Taro", "", "") is True
        assert m("example", "email", "", "T@EXAMPLE.COM", "") is True
        assert m("営業", "org", "", "", "営業部") is True

    def test_unknown_field_falls_back_to_all(self):
        # 想定外のfield指定は "all" 相当として扱われる
        m = ContactSearcher._matches
        assert m("yamada", "unknown_field", "Yamada", "", "") is True
