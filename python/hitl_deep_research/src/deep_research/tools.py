from agnt5 import Context, tool
import asyncio
import ipaddress
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from urllib3.util.connection import create_connection


# The webpage tool fetches whatever URL the model hands it, so the connection
# enforces a destination policy rather than trusting the argument: a prompt
# that says "read http://169.254.169.254/latest/meta-data/" would otherwise
# make the worker fetch cloud credentials and hand them back as research
# (AGNT5-1165, the Python port of the Go fix in AGNT5-1160).
#
# The policy lives in the connection's _new_conn, not in a check before the
# request: the hostname is resolved exactly once, every address is validated,
# and the socket goes to one of those addresses. Validating first and letting
# the pool resolve again would leave a window for DNS rebinding -- a public
# answer for the check, a private one for the connection. Redirects go through
# the same pool, so every hop is held to the same rule.

MAX_WEBPAGE_BYTES = 2 * 1024 * 1024  # a page is read up to here, then cut
MAX_REDIRECTS = 5


def is_private_address(ip: str) -> bool:
    """True for anything that is the machine or its network rather than the public internet.

    Link-local covers the cloud metadata endpoints (169.254.169.254 and fd00:ec2::254).
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # unparseable is not something to connect to
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_unspecified
        or addr.is_reserved
    )


def resolve_public_addresses(host: str, port: int) -> list[str]:
    """Resolve host once and refuse if any answer is private.

    Rejecting on any private answer, rather than skipping it, closes the
    mixed-answer variant of rebinding where a public address is offered
    alongside a private one.
    """
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise requests.ConnectionError(f"could not resolve {host}: {e}") from e
    addresses = []
    for info in infos:
        ip = info[4][0]
        if is_private_address(ip):
            raise requests.ConnectionError(
                f"refusing to connect to {host}: it resolves to the private address {ip}"
            )
        if ip not in addresses:
            addresses.append(ip)
    if not addresses:
        raise requests.ConnectionError(f"{host} resolved to no addresses")
    return addresses


class _PublicOnlyConnectionMixin:
    """Dial only an address that passed the policy, in the same resolution."""

    def _new_conn(self):
        addresses = resolve_public_addresses(self._dns_host, self.port)
        last_error: Exception | None = None
        for ip in addresses:
            try:
                # An IP literal makes create_connection skip DNS, so the socket
                # goes to the address that was validated and nothing else.
                return create_connection(
                    (ip, self.port),
                    timeout=self.timeout,
                    source_address=self.source_address,
                    socket_options=self.socket_options,
                )
            except OSError as e:
                last_error = e
        raise last_error if last_error else OSError(f"could not connect to {self._dns_host}")


class PublicOnlyHTTPConnection(_PublicOnlyConnectionMixin, HTTPConnection):
    pass


class PublicOnlyHTTPSConnection(_PublicOnlyConnectionMixin, HTTPSConnection):
    # TLS still verifies against self.host (the name), not the dialed address.
    pass


class PublicOnlyHTTPConnectionPool(HTTPConnectionPool):
    ConnectionCls = PublicOnlyHTTPConnection


class PublicOnlyHTTPSConnectionPool(HTTPSConnectionPool):
    ConnectionCls = PublicOnlyHTTPSConnection


class PublicOnlyAdapter(HTTPAdapter):
    """A requests adapter whose every connection, redirects included, is policed."""

    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": PublicOnlyHTTPConnectionPool,
            "https": PublicOnlyHTTPSConnectionPool,
        }


def public_only_session() -> requests.Session:
    session = requests.Session()
    session.max_redirects = MAX_REDIRECTS
    # No proxies from the environment: a proxy would connect on the worker's
    # behalf and the address policy would never see the real destination.
    session.trust_env = False
    adapter = PublicOnlyAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def check_research_url(url: str) -> str | None:
    """Return a refusal reason for anything but an http(s) URL with a host."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"unsupported URL scheme {parsed.scheme!r}: only http and https are fetched"
    if not parsed.hostname:
        return "URL has no host"
    return None


def read_capped(response: requests.Response, limit: int = MAX_WEBPAGE_BYTES) -> bytes:
    """Read at most `limit` bytes of a streamed response. A large or endless
    page is otherwise read whole before parsing."""
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        room = limit - total
        if len(chunk) >= room:
            chunks.append(chunk[:room])
            response.close()
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


@tool(auto_schema=True)
async def fetch_webpage_tool(ctx: Context, url: str) -> str:
    """Fetch and extract text content from a webpage for research purposes.

    Retrieves the HTML page at the given URL, strips non-content elements
    (scripts, ads, navigation), and returns clean text truncated to 8 000 chars.

    Args:
        ctx: AGNT5 execution context.
        url: The webpage URL to fetch.

    Returns:
        Formatted string with page title, URL, and extracted text content.
        Returns an error message if the request fails or the content type
        is not HTML.
    """

    ctx.logger.info(f"Webpage fetch tool called for URL: {url[:100]}...")

    headers = {"User-Agent": "Mozilla/5.0 (AGNT5-DeepResearch/1.0)"}

    if (refusal := check_research_url(url)) is not None:
        ctx.logger.error(f"Refused webpage fetch for {url[:100]}: {refusal}")
        return f"Refused to fetch {url}: {refusal}"

    try:
        with public_only_session() as session:
            response = session.get(url, headers=headers, timeout=30, stream=True)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                response.close()
                return f"Content type {content_type} is not supported for URL: {url}"

            body = read_capped(response)

        soup = BeautifulSoup(body, "html.parser")

        # Remove unwanted elements
        for element in soup(
            ["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"]
        ):
            element.decompose()

        for element in soup.find_all(
            attrs={"class": ["ad", "advertisement", "menu", "navigation", "sidebar"]}
        ):
            element.decompose()

        title = soup.find("title")
        title_text = title.get_text().strip() if title else "Untitled"

        # Find main content
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"class": ["content", "main-content", "article-content"]})
            or soup.find("div", attrs={"id": ["content", "main", "article"]})
            or soup.find("body")
        )

        if main_content:
            paragraphs = main_content.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6"])
            if paragraphs:
                text = " ".join(
                    [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
                )
            else:
                text = main_content.get_text(separator=" ", strip=True)
        else:
            text = soup.get_text(separator=" ", strip=True)

        text = " ".join(text.split())

        # Remove common navigation patterns
        nav_patterns = [
            "Skip to main content",
            "Menu",
            "Home",
            "Contact",
            "About",
            "Privacy Policy",
        ]
        for pattern in nav_patterns:
            text = text.replace(pattern, "")

        # Truncate if too long
        max_chars = 8000
        if len(text) > max_chars:
            truncated = text[:max_chars]
            last_sentence = truncated.rfind(".")
            if last_sentence > max_chars * 0.8:
                text = truncated[: last_sentence + 1] + " ... [truncated]"
            else:
                text = truncated + " ... [truncated]"

        ctx.logger.info(f"Successfully fetched {len(text)} characters from webpage")

        return f"Title: {title_text}\nURL: {url}\n\nContent:\n{text}"

    except requests.Timeout:
        ctx.logger.error(f"Timeout fetching {url}")
        return f"Timeout error: Request timed out while fetching content from {url}"
    except requests.ConnectionError as e:
        # The reason travels in the exception -- including the destination
        # policy's refusal -- and the model needs it to stop retrying a URL
        # that will never be fetched.
        ctx.logger.error(f"Connection error for {url}: {e}")
        return f"Connection error: Failed to connect to {url}: {e}"
    except requests.RequestException as e:
        ctx.logger.error(f"HTTP error fetching {url}: {e}")
        return f"HTTP error fetching {url}: {str(e)}"
    except Exception as e:
        ctx.logger.error(f"Unexpected error fetching {url}: {e}")
        return f"Unexpected error fetching {url}: {str(e)}"


@tool(auto_schema=True)
async def wikipedia_search_tool(ctx: Context, query: str, max_results: int = 3) -> str:
    """Search Wikipedia for articles related to the research query.

    Queries the Wikipedia Search API and returns formatted results with
    titles, article URLs, and snippet previews.

    Args:
        ctx: AGNT5 execution context.
        query: Search term or phrase to look up on Wikipedia.
        max_results: Maximum number of articles to return (default 3, max 50).

    Returns:
        Formatted string listing matching Wikipedia articles with title,
        URL, and snippet for each result. Returns an error message if the
        search fails or no articles are found.
    """

    ctx.logger.info(f"Wikipedia search tool called with query: {query[:100]}...")

    base_url = "https://en.wikipedia.org/w/api.php"

    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json",
        "srlimit": min(max_results, 50),
        "srwhat": "text",
    }

    headers = {"User-Agent": "AGNT5-DeepResearch/1.0"}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = requests.get(base_url, params=params, headers=headers, timeout=30)

            if response.status_code == 429:
                wait = 2 ** attempt * 3  # 3s, 6s, 12s
                ctx.logger.warning(f"Wikipedia rate-limited (429), retrying in {wait}s (attempt {attempt + 1}/{max_retries})")
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()

            if "error" in data:
                ctx.logger.error(f"Wikipedia API error: {data['error']}")
                return f"Wikipedia search error: {data['error']}"

            search_results = data.get("query", {}).get("search", [])

            if not search_results:
                return f"No Wikipedia articles found for query: {query}"

            formatted_results = []
            for result in search_results:
                content = result.get("snippet", "")
                content = content.replace('<span class="searchmatch">', "").replace("</span>", "")
                content = (
                    content.replace("&quot;", '"')
                    .replace("&amp;", "&")
                    .replace("&lt;", "<")
                    .replace("&gt;", ">")
                )

                title = result.get("title", "")
                url_title = title.replace(" ", "_")
                url = f"https://en.wikipedia.org/wiki/{url_title}"

                formatted_result = f"Title: {title}\nURL: {url}\nSnippet: {content}\n"
                formatted_results.append(formatted_result)

            ctx.logger.info(f"Found {len(search_results)} Wikipedia articles")
            return f"Wikipedia search results for '{query}':\n\n" + "\n---\n".join(formatted_results)

        except requests.Timeout:
            ctx.logger.error("Wikipedia search timed out")
            return f"Wikipedia search timed out for query: {query}"
        except requests.ConnectionError:
            ctx.logger.error("Failed to connect to Wikipedia")
            return f"Failed to connect to Wikipedia for query: {query}"
        except requests.RequestException as e:
            ctx.logger.error(f"Wikipedia search failed: {e}")
            return f"Wikipedia search failed for '{query}': {str(e)}"
        except Exception as e:
            ctx.logger.error(f"Unexpected error in Wikipedia search: {e}")
            return f"Unexpected error in Wikipedia search for '{query}': {str(e)}"

    return f"Wikipedia search failed after {max_retries} retries (rate limited) for query: {query}"
