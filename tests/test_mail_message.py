"""
Тесты формата письма kind:1301 (RFC 2822) — mail_message.py.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mailbridge import mail_message as mm


def test_roundtrip_basic():
    mail = mm.build_mail(
        from_addr="cryter@cryter-mail.v2.site",
        to_addr="npub1abc@nostr",
        subject="Hello world",
        body="First line.\nSecond line.",
    )
    parsed = mm.parse_mail(mail)
    assert parsed["from"] == "cryter@cryter-mail.v2.site"
    assert parsed["to"] == "npub1abc@nostr"
    assert parsed["subject"] == "Hello world"
    assert parsed["body"] == "First line.\nSecond line."
    assert parsed["message_id"].startswith("<") and parsed["message_id"].endswith(">")
    assert parsed["date"]  # Date заполнена


def test_unicode_subject_and_body():
    mail = mm.build_mail(
        from_addr="cryter@cryter-mail.v2.site",
        to_addr="alice@nostr",
        subject="Привет, мир! 📮",
        body="Тело с русским текстом и эмодзи 🚀\nВторая строка.",
    )
    parsed = mm.parse_mail(mail)
    assert parsed["subject"] == "Привет, мир! 📮"
    assert parsed["body"] == "Тело с русским текстом и эмодзи 🚀\nВторая строка."


def test_unique_message_ids():
    m1 = mm.build_mail("a@x", "b@y", "s", "b")
    m2 = mm.build_mail("a@x", "b@y", "s", "b")
    assert mm.parse_mail(m1)["message_id"] != mm.parse_mail(m2)["message_id"]


def test_thread_headers():
    mail = mm.build_mail(
        from_addr="a@x", to_addr="b@y", subject="Re: hello", body="reply",
        in_reply_to="<orig@x>", references="<orig@x> <prev@y>",
    )
    parsed = mm.parse_mail(mail)
    assert parsed["in_reply_to"] == "<orig@x>"
    assert parsed["references"] == "<orig@x> <prev@y>"


def test_explicit_message_id_and_date():
    import datetime

    dt = datetime.datetime(2026, 8, 25, 12, 0, 0, tzinfo=datetime.timezone.utc)
    mail = mm.build_mail(
        "a@x", "b@y", "s", "b", date=dt, message_id="<custom@x>"
    )
    parsed = mm.parse_mail(mail)
    assert parsed["message_id"] == "<custom@x>"
    assert "2026" in parsed["date"]


def test_size_limit():
    big_body = "x" * (mm.MAX_MAIL_SIZE + 1000)
    try:
        mm.build_mail("a@x", "b@y", "s", big_body)
        assert False, "должен был выкинуть ValueError"
    except ValueError:
        pass


def test_extract_addresses():
    mail = mm.build_mail("cryter@cryter-mail.v2.site", "bob@nostr", "s", "b")
    frm, to = mm.extract_addresses(mail)
    assert frm == "cryter@cryter-mail.v2.site"
    assert to == "bob@nostr"


if __name__ == "__main__":
    import traceback

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"✅ {t.__name__}")
            passed += 1
        except Exception:
            print(f"❌ {t.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(tests)} тестов прошло")
    sys.exit(0 if passed == len(tests) else 1)
