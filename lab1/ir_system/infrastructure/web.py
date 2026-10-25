"""HTTP-адаптер и HTML-парсер. Не индексируют текст и не сохраняют документы."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from email.message import Message
from html.parser import HTMLParser
from http.client import HTTPException
from typing import Protocol
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from lab1.ir_system.domain.errors import FetchError
from lab1.ir_system.domain.models import DocumentDraft
from lab1.ir_system.domain.text import normalize_url


class HttpResponse(Protocol):
    headers: Message

    def geturl(self) -> str: ...

    def read(self, size: int) -> bytes: ...


class HTMLTextExtractor(HTMLParser):
    IGNORED = {"script", "style", "noscript", "template", "svg", "head"}
    BLOCKS = {"p", "div", "br", "li", "h1", "h2", "h3", "section", "article", "td"}
    VOID = {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._title_parts: list[str] = []
        self._stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in self.VOID:
            self._stack.append(tag)
        if tag in self.BLOCKS:
            self._parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in self._stack:
            position = len(self._stack) - 1 - self._stack[::-1].index(tag)
            del self._stack[position:]
        if tag in self.BLOCKS:
            self._parts.append(" ")

    def handle_data(self, data: str) -> None:
        if "title" in self._stack:
            self._title_parts.append(data)
        elif not any(tag in self.IGNORED for tag in self._stack):
            self._parts.append(data)

    @property
    def title(self) -> str:
        return " ".join("".join(self._title_parts).split())

    @property
    def text(self) -> str:
        return " ".join("".join(self._parts).split())


class HttpDocumentFetcher:
    def __init__(
        self,
        timeout: float = 15,
        max_bytes: int = 2 * 1024 * 1024,
        opener: Callable[..., AbstractContextManager[HttpResponse]] = urlopen,
    ) -> None:
        self._timeout, self._max_bytes, self._opener = timeout, max_bytes, opener

    def fetch(self, url: str) -> DocumentDraft:
        url = normalize_url(url)
        request = Request(url, headers={"User-Agent": "IRLab36/1.0 (educational page importer)"})
        try:
            with self._opener(request, timeout=self._timeout) as response:
                final_url = normalize_url(response.geturl())
                content_type = response.headers.get_content_type()
                if content_type not in {"text/html", "application/xhtml+xml", "text/plain"}:
                    raise FetchError(
                        f"Не поддерживается формат {content_type}; нужны HTML или plain text"
                    )
                raw = response.read(self._max_bytes + 1)
                if len(raw) > self._max_bytes:
                    raise FetchError(f"Страница превышает ограничение {self._max_bytes} байт")
                encoding = response.headers.get_content_charset() or "utf-8"
                text = raw.decode(encoding, errors="replace")
        except (OSError, URLError, HTTPException, LookupError, ValueError) as exc:
            raise FetchError(f"Не удалось загрузить страницу: {exc}") from exc
        if content_type == "text/plain":
            title = urlsplit(final_url).path.rsplit("/", 1)[-1] or final_url
            return DocumentDraft(final_url, title, text)
        parser = HTMLTextExtractor()
        parser.feed(text)
        return DocumentDraft(final_url, parser.title or final_url, parser.text)
