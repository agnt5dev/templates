from agnt5 import Context, tool
import requests
from bs4 import BeautifulSoup


@tool(auto_schema=True)
async def fetch_webpage_tool(ctx: Context, url: str) -> str:
    """Fetch and extract text content from a webpage for research purposes."""

    ctx.logger.info(f"Webpage fetch tool called for URL: {url[:100]}...")

    headers = {"User-Agent": "Mozilla/5.0 (AGNT5-DeepResearch/1.0)"}

    try:
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            return f"Content type {content_type} is not supported for URL: {url}"

        soup = BeautifulSoup(response.content, "html.parser")

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
    except requests.ConnectionError:
        ctx.logger.error(f"Connection error for {url}")
        return f"Connection error: Failed to connect to {url}"
    except requests.RequestException as e:
        ctx.logger.error(f"HTTP error fetching {url}: {e}")
        return f"HTTP error fetching {url}: {str(e)}"
    except Exception as e:
        ctx.logger.error(f"Unexpected error fetching {url}: {e}")
        return f"Unexpected error fetching {url}: {str(e)}"


@tool(auto_schema=True)
async def wikipedia_search_tool(ctx: Context, query: str, max_results: int = 3) -> str:
    """Search Wikipedia for articles related to the research query."""

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

    try:
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
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
            # Clean HTML tags from snippet
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


@tool(auto_schema=True)
async def analyze_research_findings_tool(ctx: Context, research_data: str, topic: str) -> str:
    """Analyze and synthesize research findings from multiple sources."""

    ctx.logger.info(f"Research analysis tool called for topic: {topic[:50]}...")

    try:
        # Basic analysis of the research data
        lines = research_data.split("\n")
        sources = []
        key_points = []

        current_section = ""
        for line in lines:
            line = line.strip()
            if line.startswith("Title:") or line.startswith("Wikipedia search"):
                current_section = line
                sources.append(current_section)
            elif (
                line
                and len(line) > 20
                and not line.startswith("URL:")
                and not line.startswith("Snippet:")
            ):
                key_points.append(line)

        analysis = f"# Research Analysis: {topic}\n\n"

        if sources:
            analysis += "## Sources Analyzed:\n"
            for i, source in enumerate(sources[:5], 1):  # Limit to 5 sources
                analysis += f"{i}. {source}\n"
            analysis += "\n"

        if key_points:
            analysis += "## Key Information Extracted:\n"
            unique_points = list(dict.fromkeys(key_points))  # Remove duplicates
            for i, point in enumerate(unique_points[:10], 1):  # Limit to 10 points
                if len(point) > 30:  # Filter out very short points
                    analysis += f"• {point}\n"
            analysis += "\n"

        analysis += "## Research Summary:\n"
        analysis += f"The research on '{topic}' has been compiled from multiple sources including "
        analysis += (
            f"Wikipedia articles and web content. The analysis reveals {len(unique_points)} "
        )
        analysis += (
            "key pieces of information that provide a comprehensive understanding of the topic.\n\n"
        )

        word_count = len(research_data.split())
        analysis += f"## Research Metrics:\n"
        analysis += f"• Total words analyzed: {word_count:,}\n"
        analysis += f"• Sources consulted: {len(sources)}\n"
        analysis += f"• Key points identified: {len(unique_points)}\n"

        ctx.logger.info(f"Research analysis completed successfully")
        return analysis

    except Exception as e:
        ctx.logger.error(f"Research analysis tool failed: {e}")
        return (
            f"Research analysis failed for '{topic}'. Error: {str(e)}\n\nRaw data:\n{research_data}"
        )
