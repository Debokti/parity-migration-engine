from verifier.parity_differ import compare


def test_equal_values_pass():
    assert compare({"ok": True}, {"ok": True}) == []


def test_different_values_fail():
    assert compare({"ok": True}, {"ok": False})

