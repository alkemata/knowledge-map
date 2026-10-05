"""Read published Alkemata articles from the WordPress REST API."""

from html.parser import HTMLParser

import httpx

WORDPRESS_API = "https://alkemata.com/wp-json/wp/v2/posts"


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.skip += 1
        elif not self.skip and tag in {"p", "div", "h1", "h2", "h3", "h4", "li", "br", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.skip:
            self.skip -= 1
        elif not self.skip and tag in {"p", "div", "h1", "h2", "h3", "h4", "li", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.parts.append(data)


def _plain(value: str) -> str:
    parser = _Text()
    parser.feed(value)
    lines = [" ".join(line.split()) for line in "".join(parser.parts).splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _request(url: str, params: dict | None = None) -> tuple[object, httpx.Headers]:
    try:
        response = httpx.get(url, params=params, timeout=8, follow_redirects=False)
        response.raise_for_status()
    except httpx.HTTPError as error:
        raise RuntimeError("WordPress articles are temporarily unavailable") from error
    if int(response.headers.get("content-length", "0")) > 2_000_000 or len(response.content) > 2_000_000:
        raise RuntimeError("WordPress article response is too large")
    try:
        return response.json(), response.headers
    except ValueError as error:
        raise RuntimeError("WordPress returned an invalid article response") from error


def search_articles(query: str = "", limit: int = 10, page: int = 1) -> dict:
    """Search published WordPress articles, newest first, without requiring a login."""
    if len(query) > 200:
        raise ValueError("query must be 200 characters or fewer")
    if not 1 <= limit <= 50 or not 1 <= page <= 100:
        raise ValueError("limit must be 1-50 and page must be 1-100")
    params = {
        "status": "publish", "search": query, "per_page": limit, "page": page,
        "orderby": "date", "order": "desc",
        "_fields": "id,date,modified,slug,link,title,excerpt,categories,tags",
    }
    items, headers = _request(WORDPRESS_API, params)
    return {
        "source": "Alkemata WordPress",
        "total": int(headers.get("x-wp-total", "0")),
        "page": page,
        "items": [{
            "id": item["id"],
            "title": _plain(item["title"]["rendered"]),
            "summary": _plain(item["excerpt"]["rendered"]),
            "published_at": item["date"],
            "updated_at": item["modified"],
            "url": item["link"],
            "category_ids": item.get("categories", []),
            "tag_ids": item.get("tags", []),
        } for item in items],
    }


def get_article(article_id: int) -> dict:
    """Read one published WordPress article as plain text with its canonical link."""
    if article_id < 1:
        raise ValueError("article_id must be positive")
    item, _ = _request(f"{WORDPRESS_API}/{article_id}", {
        "_fields": "id,status,date,modified,slug,link,title,excerpt,content,categories,tags",
    })
    if item.get("status") != "publish" or item["content"].get("protected"):
        raise ValueError("Published article not found")
    return {
        "source": "Alkemata WordPress",
        "id": item["id"],
        "title": _plain(item["title"]["rendered"]),
        "summary": _plain(item["excerpt"]["rendered"]),
        "content": _plain(item["content"]["rendered"]),
        "published_at": item["date"],
        "updated_at": item["modified"],
        "url": item["link"],
        "category_ids": item.get("categories", []),
        "tag_ids": item.get("tags", []),
    }
