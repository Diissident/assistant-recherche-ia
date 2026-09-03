"""Tests du garde-fou SSRF et du filtre d'URLs du scraper."""

import asyncio

import pytest

import scraper


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "10.0.0.1",
                                  "192.168.1.10", "169.254.169.254", "0.0.0.0"])
def test_private_hosts_are_rejected(host):
    """169.254.169.254 est l'endpoint de métadonnées des principaux clouds :
    un résultat de recherche piégé ne doit jamais pouvoir le faire interroger."""
    assert scraper._is_public_host(host) is False


def test_unresolvable_host_is_rejected():
    assert scraper._is_public_host("hote-qui-nexiste-vraiment-pas.invalid") is False


@pytest.mark.parametrize("url", [
    "file:///etc/passwd",
    "ftp://exemple.fr/x",
    "javascript:alert(1)",
    "http://",
])
def test_non_http_schemes_are_rejected(url):
    assert asyncio.run(scraper.is_url_allowed(url)) is False


def test_private_url_is_rejected():
    assert asyncio.run(scraper.is_url_allowed("http://127.0.0.1:8000/admin")) is False


def test_filter_can_be_disabled_for_local_use(monkeypatch):
    """ALLOW_PRIVATE_ADDRESSES existe pour scraper un wiki interne ; le
    schéma reste vérifié même dans ce mode."""
    monkeypatch.setattr(scraper, "ALLOW_PRIVATE_ADDRESSES", True)
    assert asyncio.run(scraper.is_url_allowed("http://127.0.0.1:8000/wiki")) is True
    assert asyncio.run(scraper.is_url_allowed("file:///etc/passwd")) is False


def test_extract_text_rejects_too_short_pages(monkeypatch):
    monkeypatch.setattr(scraper, "MIN_TEXT_LENGTH", 200)
    assert scraper.extract_text("<html><body><p>court</p></body></html>", "http://a.fr") is None


def test_extract_text_survives_garbage_input():
    """Une entrée non-HTML ne doit pas lever, juste renvoyer None."""
    assert scraper.extract_text("\x00\x01 pas du html", "http://a.fr") is None


def test_scrape_many_with_no_urls():
    assert asyncio.run(scraper.scrape_many([])) == []
