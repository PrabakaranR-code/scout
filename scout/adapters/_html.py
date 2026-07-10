"""A tiny, forgiving HTML tree built on the stdlib parser.

Engine adapters parse saved (or live) HTML with this instead of a heavy
dependency. It tolerates unclosed and mismatched tags: bad markup yields a
lopsided tree, never an exception.
"""

from __future__ import annotations

from html.parser import HTMLParser

VOID_TAGS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


class Node:
    """One element with attributes, children, and collected text."""

    __slots__ = ("tag", "attrs", "children", "_text_parts")

    def __init__(self, tag: str, attrs: dict[str, str | None] | None = None) -> None:
        self.tag = tag
        self.attrs: dict[str, str | None] = attrs or {}
        self.children: list[Node] = []
        self._text_parts: list[str] = []

    @property
    def classes(self) -> set[str]:
        return set((self.attrs.get("class") or "").split())

    def attr(self, name: str) -> str:
        return self.attrs.get(name) or ""

    def text(self) -> str:
        """All descendant text, whitespace-collapsed."""
        parts: list[str] = []
        self._collect_text(parts)
        return " ".join(" ".join(parts).split())

    def _collect_text(self, parts: list[str]) -> None:
        parts.extend(self._text_parts)
        for child in self.children:
            child._collect_text(parts)

    def find_all(self, tag: str | None = None, cls: str | None = None) -> list["Node"]:
        """Descendants matching tag and/or a single CSS class."""
        found: list[Node] = []
        for child in self.children:
            if (tag is None or child.tag == tag) and (
                cls is None or cls in child.classes
            ):
                found.append(child)
            found.extend(child.find_all(tag, cls))
        return found

    def find(self, tag: str | None = None, cls: str | None = None) -> "Node | None":
        matches = self.find_all(tag, cls)
        return matches[0] if matches else None


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("[root]")
        self._stack: list[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag, dict(attrs))
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._stack[-1].children.append(Node(tag, dict(attrs)))

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return
        # stray close tag: ignore

    def handle_data(self, data: str) -> None:
        if data.strip():
            self._stack[-1]._text_parts.append(data.strip())


def parse_html(markup: str) -> Node:
    """Parse markup into a tree; never raises on bad HTML."""
    builder = _TreeBuilder()
    try:
        builder.feed(markup)
        builder.close()
    except Exception:
        pass  # keep whatever was built before the parser choked
    return builder.root
