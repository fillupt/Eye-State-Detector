import os
import re
import html as _html
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from html.parser import HTMLParser

_CSS = """
body { font-family: Georgia, serif; max-width: 820px; margin: 40px auto; padding: 0 24px;
       line-height: 1.85; background: #fafaf8; color: #1a1a1a; font-size: 1.05em; }
h1   { font-size: 1.6em; margin-bottom: 0.4em; }
p    { margin: 0.75em 0; }
.nav { margin-top: 2.5em; }
.nav a { font-size: 1em; text-decoration: none; color: #1a5fa8; border: 1px solid #1a5fa8;
         padding: 6px 16px; border-radius: 4px; }
"""


class _StoryParser(HTMLParser):
    """Extract story title, body paragraphs, and next-link href from a page."""

    def __init__(self):
        super().__init__()
        self.title = ""
        self.paragraphs = []
        self.next_href = None

        self._depth = 0
        self._content_div_depth = None
        self._in_p = False
        self._p_buf = []
        self._in_heading = False
        self._heading_buf = []
        self._in_a = False
        self._a_href = ""
        self._a_buf = []

    def handle_starttag(self, tag, attrs):
        self._depth += 1
        attrs_d = dict(attrs)

        if tag == "div" and self._content_div_depth is None:
            classes = attrs_d.get("class", "").lower()
            id_ = attrs_d.get("id", "").lower()
            if any(k in classes + id_ for k in ("story", "content", "main", "text", "body")):
                self._content_div_depth = self._depth

        if tag == "p":
            self._in_p = True
            self._p_buf = []

        if tag in ("h1", "h2", "h3") and not self.title:
            self._in_heading = True
            self._heading_buf = []

        if tag == "a":
            self._in_a = True
            self._a_href = attrs_d.get("href", "")
            self._a_buf = []

    def handle_endtag(self, tag):
        if tag == "p" and self._in_p:
            text = "".join(self._p_buf).strip()
            if text and len(text) > 15:
                self.paragraphs.append(text)
            self._in_p = False
            self._p_buf = []

        if tag in ("h1", "h2", "h3") and self._in_heading:
            candidate = "".join(self._heading_buf).strip()
            if candidate:
                self.title = candidate
            self._in_heading = False
            self._heading_buf = []

        if tag == "a":
            link_text = "".join(self._a_buf).strip().lower()
            if "next" in link_text and self._a_href and not self._a_href.startswith("#"):
                if self.next_href is None:
                    self.next_href = self._a_href
            self._in_a = False
            self._a_href = ""
            self._a_buf = []

        if tag == "div" and self._content_div_depth == self._depth:
            self._content_div_depth = None

        self._depth -= 1

    def handle_data(self, data):
        if self._in_p:
            self._p_buf.append(data)
        if self._in_heading:
            self._heading_buf.append(data)
        if self._in_a:
            self._a_buf.append(data)


def _fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        charset = resp.info().get_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace"), resp.geturl()


def _make_html(title, paragraphs, next_filename=None):
    esc_title = _html.escape(title)
    paras_html = "\n".join(f"<p>{_html.escape(p)}</p>" for p in paragraphs)
    nav_html = (
        f'<div class="nav"><a href="{_html.escape(next_filename)}">Next story &rarr;</a></div>'
        if next_filename else ""
    )
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head><meta charset=\"utf-8\">\n"
        f"<title>{esc_title}</title>\n"
        f"<style>{_CSS}</style></head>\n"
        "<body>\n"
        f"<h1>{esc_title}</h1>\n"
        f"{paras_html}\n"
        f"{nav_html}\n"
        "</body>\n</html>\n"
    )


def download_stories(start_url, count, output_dir, progress_callback=None):
    """
    Download up to `count` stories starting from `start_url`, following Next links.
    Saves clean local HTML files (title + body text only) to `output_dir`.
    Returns a list of absolute paths to the saved files.
    """
    os.makedirs(output_dir, exist_ok=True)

    collected = []   # list of (title, paragraphs, resolved_url)
    current_url = start_url

    for i in range(count):
        if progress_callback:
            progress_callback(i, count, current_url)

        try:
            html_text, resolved_url = _fetch(current_url)
        except Exception as e:
            if progress_callback:
                progress_callback(i, count, f"Fetch error: {e}")
            break

        parser = _StoryParser()
        parser.feed(html_text)

        title = parser.title or f"Story {i + 1}"
        paragraphs = parser.paragraphs or ["(No text found on this page.)"]
        next_href = parser.next_href

        collected.append((title, paragraphs, resolved_url))

        if next_href:
            current_url = urljoin(resolved_url, next_href)
        else:
            # Fallback: increment the trailing number in the URL (e.g. 002.html -> 003.html)
            m = re.search(r'(\d+)(\.\w+)$', resolved_url)
            if m:
                n = int(m.group(1))
                padded = str(n + 1).zfill(len(m.group(1)))
                current_url = resolved_url[:m.start()] + padded + m.group(2)
            else:
                break

    # Write HTML files with relative forward links
    saved_paths = []
    for i, (title, paragraphs, _) in enumerate(collected):
        filename = f"story_{i + 1:03d}.html"
        filepath = os.path.join(output_dir, filename)
        next_filename = f"story_{i + 2:03d}.html" if i + 1 < len(collected) else None
        html_content = _make_html(title, paragraphs, next_filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        saved_paths.append(os.path.abspath(filepath))

    if progress_callback:
        progress_callback(len(collected), count, "Done")

    return saved_paths
