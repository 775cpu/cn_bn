from binance_tracker.main import resolve_verify_ssl


def test_domain_mode_uses_configured_ssl_value():
    assert resolve_verify_ssl("domain", True) is True
    assert resolve_verify_ssl("domain", False) is False


def test_direct_mode_defaults_to_ssl_disabled():
    assert resolve_verify_ssl("direct", True) is False
    assert resolve_verify_ssl("direct", False) is False


def test_insecure_overrides_any_mode():
    assert resolve_verify_ssl("domain", True, insecure=True) is False