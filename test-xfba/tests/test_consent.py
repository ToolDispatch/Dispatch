import sys, os, tempfile, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def _state_dir():
    d = tempfile.mkdtemp()
    return os.path.join(d, ".xf")


def test_trust_level_starts_at_zero():
    from consent import get_trust_level
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    assert get_trust_level(xf_dir) == 0


def test_trust_level_increments():
    from consent import get_trust_level, increment_trust
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    increment_trust(xf_dir)
    assert get_trust_level(xf_dir) == 1
    increment_trust(xf_dir)
    assert get_trust_level(xf_dir) == 2


def test_reset_trust():
    from consent import increment_trust, reset_trust, get_trust_level
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    increment_trust(xf_dir)
    increment_trust(xf_dir)
    reset_trust(xf_dir)
    assert get_trust_level(xf_dir) == 0


def test_consent_options_low_trust():
    from consent import format_consent_options
    text = format_consent_options(trust_level=0, n_violations=2)
    assert "show" in text.lower()
    assert "apply all" not in text.lower()


def test_consent_options_high_trust():
    from consent import format_consent_options
    text = format_consent_options(trust_level=2, n_violations=3)
    assert "apply" in text.lower()


def test_write_repair_log():
    from consent import append_repair_log
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    append_repair_log(xf_dir, {"violation_id": "a001", "description": "fixed"})
    log_path = os.path.join(xf_dir, "repair_log.json")
    assert os.path.isfile(log_path)
    data = json.loads(open(log_path).read())
    assert len(data["repairs"]) == 1
    assert data["repairs"][0]["violation_id"] == "a001"


def test_repair_log_appends():
    from consent import append_repair_log
    xf_dir = _state_dir()
    os.makedirs(xf_dir)
    append_repair_log(xf_dir, {"violation_id": "a001"})
    append_repair_log(xf_dir, {"violation_id": "a002"})
    data = json.loads(open(os.path.join(xf_dir, "repair_log.json")).read())
    assert len(data["repairs"]) == 2


# --- Fix 8: consent options framed as instructions to Claude ---

def test_consent_options_low_trust_framed_as_instructions():
    """Low trust output should tell user to SAY the option, not click a button."""
    from consent import format_consent_options
    text = format_consent_options(trust_level=0, n_violations=2)
    assert "say" in text.lower() or "to proceed" in text.lower()
    # Should NOT contain old bracket-button style like [show me the diff first]
    # (new format uses plain text instructions, not bracketed UI elements)
    assert "apply all" not in text.lower()
    assert "bulk-apply unlocks" in text.lower()


def test_consent_options_high_trust_mentions_apply_all():
    """High trust output should mention 'apply all N repairs'."""
    from consent import format_consent_options
    text = format_consent_options(trust_level=2, n_violations=3)
    assert "apply all 3 repairs" in text.lower()
    assert "show me the diff first" in text.lower()
    assert "skip for now" in text.lower()


def test_consent_options_trust_1_no_bulk_unlock_hint():
    """Trust level 1 should not show the bulk-apply unlock hint (only at 0)."""
    from consent import format_consent_options
    text = format_consent_options(trust_level=1, n_violations=1)
    assert "bulk-apply unlocks" not in text.lower()
