# SPDX-License-Identifier: GPL-3.0-only
"""watch_image_bytes: fetch-once/cache, the HTML-404-served-as-200 guard, the
negative cache, and codename sanitisation (it reaches a URL and a path)."""

import io
import urllib.request

import asteroid_docking_bay.watchimg as wi

PNG = b"\x89PNG\r\n\x1a\n" + b"...pixels..."


class _Ctx:
    def __init__(self, data):
        self.data = data

    def __enter__(self):
        return io.BytesIO(self.data)

    def __exit__(self, *a):
        return False


def test_fetches_png_then_serves_from_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(wi, "_CACHE_DIR", tmp_path)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=0: calls.append(url) or _Ctx(PNG))
    assert wi.watch_image_bytes("skipjack") == PNG
    assert (tmp_path / "skipjack.png").read_bytes() == PNG
    wi.watch_image_bytes("skipjack")           # second call
    assert len(calls) == 1                      # served from cache, not refetched


def test_html_404_is_a_negative_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(wi, "_CACHE_DIR", tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=0: _Ctx(b"<html>Not found</html>"))
    assert wi.watch_image_bytes("nope") is None
    assert (tmp_path / "nope.png").read_bytes() == b""   # miss cached as zero bytes
    hit = []
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda url, timeout=0: hit.append(1) or _Ctx(PNG))
    assert wi.watch_image_bytes("nope") is None and not hit


def test_prefers_local_trans_cutout_over_plain(monkeypatch, tmp_path):
    monkeypatch.setattr(wi, "_CACHE_DIR", tmp_path)
    (tmp_path / "skipjack.png").write_bytes(PNG)
    (tmp_path / "skipjack-trans.png").write_bytes(PNG + b"TRANS")
    def boom(*a, **k):
        raise AssertionError("must not fetch when a local image exists")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    assert wi.watch_image_bytes("skipjack") == PNG + b"TRANS"   # -trans wins


def test_empty_trans_falls_through_to_plain(monkeypatch, tmp_path):
    monkeypatch.setattr(wi, "_CACHE_DIR", tmp_path)
    (tmp_path / "skipjack-trans.png").write_bytes(b"")          # zero-byte -trans ignored
    (tmp_path / "skipjack.png").write_bytes(PNG)
    assert wi.watch_image_bytes("skipjack") == PNG


def test_bad_codename_never_reaches_the_network(monkeypatch, tmp_path):
    monkeypatch.setattr(wi, "_CACHE_DIR", tmp_path)

    def boom(*a, **k):
        raise AssertionError("must not fetch for a bad codename")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    for bad in ("skip/jack", "../etc/passwd", "has space", ""):
        assert wi.watch_image_bytes(bad) is None
