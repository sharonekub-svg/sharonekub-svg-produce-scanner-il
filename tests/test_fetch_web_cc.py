"""Licence filtering of scripts/fetch_web_cc.py with mocked API responses (no network)."""
import importlib.util
import io
import json
from pathlib import Path

from PIL import Image

spec = importlib.util.spec_from_file_location("fetch_web_cc", Path(__file__).resolve().parents[1] / "scripts/fetch_web_cc.py")
fw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fw)


def _jpeg():
    b = io.BytesIO(); Image.new("RGB", (40, 30), (230, 200, 70)).save(b, "JPEG"); return b.getvalue()


def test_commons_license_normalisation():
    assert fw.normalise_commons_license("CC BY 4.0") == ("by", "4.0")
    assert fw.normalise_commons_license("CC0") == ("cc0", "1.0")
    assert fw.normalise_commons_license("Public domain") == ("pdm", "")
    for bad in ("CC BY-SA 4.0", "CC BY-NC 2.0", "CC BY-ND 3.0", "GFDL", ""):
        assert fw.normalise_commons_license(bad) is None


def test_openverse_keeps_only_commercial_non_sa(monkeypatch, tmp_path):
    api = {"page_count": 1, "results": [
        {"id": "a", "url": "http://x/a.jpg", "license": "by", "license_version": "2.0", "creator": "Ann", "foreign_landing_url": "http://f/a"},
        {"id": "b", "url": "http://x/b.jpg", "license": "by-sa", "license_version": "2.0"},
        {"id": "c", "url": "http://x/c.jpg", "license": "by-nc", "license_version": "2.0"},
        {"id": "d", "url": "http://x/d.jpg", "license": "cc0", "license_version": "1.0"}]}
    monkeypatch.setattr(fw, "_get", lambda url: json.dumps(api).encode() if "api.openverse" in url else _jpeg())
    monkeypatch.setattr(fw.time, "sleep", lambda s: None)
    n = fw.save(fw.openverse_items("banana", 10), "banana:overripe", out=tmp_path)
    assert n == 2
    att = (tmp_path / "attribution.csv").read_text().splitlines()
    assert len(att) == 3 and "Ann" in att[1] and not any("by-sa" in l or "by-nc" in l for l in att)


def test_commons_drops_restricted_and_sharealike(monkeypatch, tmp_path):
    def page(pid, lic, restr=""):
        return {"pageid": pid, "title": f"File:{pid}.jpg", "imageinfo": [{"mime": "image/jpeg", "url": "http://u/x.jpg",
                "descriptionurl": "http://c/x", "extmetadata": {"LicenseShortName": {"value": lic},
                "Artist": {"value": "<a>Bob</a>"}, "Restrictions": {"value": restr}}}]}
    api = {"query": {"pages": {"1": page(1, "CC BY 4.0"), "2": page(2, "CC BY-SA 4.0"),
                               "3": page(3, "CC0", "personality"), "4": page(4, "Public domain")}}}
    monkeypatch.setattr(fw, "_get", lambda url: json.dumps(api).encode() if "api.php" in url else _jpeg())
    monkeypatch.setattr(fw.time, "sleep", lambda s: None)
    assert fw.save(fw.commons_items("Rotting tomatoes", 10), "tomato:rotting", out=tmp_path) == 2
    assert "Bob" in (tmp_path / "attribution.csv").read_text()
