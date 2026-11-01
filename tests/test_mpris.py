import mpris


def test_mpris_call_timeout_is_short():
    assert mpris.TIMEOUT_MS == 500


def test_mpris_prefix():
    assert mpris.MPRIS_PREFIX == "org.mpris.MediaPlayer2."
