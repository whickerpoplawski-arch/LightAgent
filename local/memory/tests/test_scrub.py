from local.memory.scrub import scrub_text


def test_scrub_rejects_fake_api_key():
    result = scrub_text("请记住我的密钥 sk-testFAKEKEY1234567890")
    assert result.allowed is False
    assert "api-key" in (result.reason or "")
    assert result.text == ""


def test_scrub_rejects_credential_assignment_and_private_key():
    password = scrub_text("password=hunter2secret 以后叫我小Q")
    assert password.allowed is False
    private = scrub_text("-----BEGIN PRIVATE KEY-----\nabc")
    assert private.allowed is False


def test_scrub_redacts_email_and_keeps_preference():
    result = scrub_text("联系邮箱 ada@example.com ，以后简称我小Q")
    assert result.allowed is True
    assert "ada@example.com" not in result.text
    assert "[redacted-email]" in result.text
    assert "小Q" in result.text


def test_scrub_marks_sensitive_health_fact_for_confirm():
    result = scrub_text("我对花生过敏，做菜不要放花生")
    assert result.allowed is True
    assert result.needs_confirm is True


def test_scrub_rejects_empty_and_pii_only():
    assert scrub_text("   ").allowed is False
    only = scrub_text("ada@example.com")
    assert only.allowed is False
    assert only.reason == "rejected: only PII"