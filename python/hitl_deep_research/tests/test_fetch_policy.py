"""The webpage tool's destination policy (AGNT5-1165).

Literal addresses resolve without DNS, so these run offline and exercise the
same function every real connection and redirect goes through -- including
the cloud metadata endpoint that motivated it.
"""

import pytest
import requests

from deep_research.tools import (
    check_research_url,
    is_private_address,
    read_capped,
    resolve_public_addresses,
)


@pytest.mark.parametrize(
    "ip",
    ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.0.1", "169.254.169.254", "::1", "fe80::1", "fd00::1", "0.0.0.0", "::ffff:127.0.0.1"],
)
def test_private_addresses_are_refused(ip):
    assert is_private_address(ip)


@pytest.mark.parametrize("ip", ["1.1.1.1", "8.8.8.8", "93.184.216.34", "2606:4700:4700::1111"])
def test_public_addresses_are_allowed(ip):
    assert not is_private_address(ip)


@pytest.mark.parametrize("host", ["127.0.0.1", "169.254.169.254", "10.0.0.8", "::1"])
def test_resolution_refuses_private_targets(host):
    with pytest.raises(requests.ConnectionError, match="private address"):
        resolve_public_addresses(host, 80)


def test_resolution_returns_the_validated_public_address():
    assert resolve_public_addresses("1.1.1.1", 443) == ["1.1.1.1"]


@pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.com/x", "gopher://example.com", "http://"])
def test_non_http_urls_are_refused(url):
    assert check_research_url(url) is not None


def test_http_urls_pass_the_scheme_check():
    assert check_research_url("https://example.com/page") is None


class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    def iter_content(self, chunk_size):
        yield from self._chunks

    def close(self):
        self.closed = True


def test_read_capped_stops_at_the_limit_and_closes():
    response = _FakeResponse([b"x" * 100, b"y" * 100, b"z" * 100])
    body = read_capped(response, limit=150)
    assert len(body) == 150
    assert response.closed


def test_read_capped_reads_a_small_page_whole():
    response = _FakeResponse([b"hello ", b"world"])
    assert read_capped(response, limit=1024) == b"hello world"


# Through the real adapter, not the resolver alone. A unit test of the check in
# isolation passed in TypeScript while production connected straight to a
# literal IP, because the hook it tested is bypassed for literals; the only
# test that means anything is the one that goes through the request path.
@pytest.mark.parametrize("url", ["http://127.0.0.1:1/", "http://169.254.169.254/latest/meta-data/", "http://localhost:1/", "http://[::1]:1/"])
def test_session_refuses_private_destinations_end_to_end(url):
    from deep_research.tools import public_only_session

    with public_only_session() as session, pytest.raises(requests.ConnectionError, match="private address"):
        session.get(url, timeout=3)
