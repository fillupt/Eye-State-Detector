import os
import re
import html as _html
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from html.parser import HTMLParser
import base64
import sys

_CSS = """
html { zoom: 80%; }
body {
    font-family: Georgia, 'Times New Roman', serif;
    max-width: 820px;
    margin: 40px auto;
    padding: 0 32px;
    line-height: 1.9;
    background: #f8f6f1;
    color: #1c1c1c;
    font-size: 1.1em;
    opacity: 0;
    transition: opacity 0.18s ease;
}
h1 {
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 1.75em;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin-bottom: 0.55em;
    color: #111;
}
p { margin: 0.82em 0; }
.nav { margin-top: 2.8em; text-align: left; }
.nav a {
    display: inline-block;
    font-family: 'Segoe UI', system-ui, sans-serif;
    font-size: 0.95em;
    font-weight: 600;
    text-decoration: none;
    color: #fff;
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    padding: 10px 26px;
    border-radius: 50px;
    box-shadow: 0 2px 8px rgba(37,99,235,0.28);
    letter-spacing: 0.02em;
    transition: background 0.15s, box-shadow 0.15s, transform 0.1s;
}
.nav a:hover {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
    box-shadow: 0 4px 14px rgba(37,99,235,0.38);
    transform: translateY(-1px);
}
p.moral {
    font-style: italic;
    text-align: center;
    margin-top: 1.6em;
    color: #444;
}
img.story-img {
    float: right;
    max-width: 260px;
    margin: 0 0 1.2em 2em;
    border-radius: 6px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.12);
}
"""


class _StoryParser(HTMLParser):
    """Extract title, paragraphs, blockquote morals, images, and next-link."""

    # Filenames that are clearly decorative/navigation rather than story art
    _SKIP_IMGS = {"vines.jpg", "logo-loc.jpg", "logo.jpg", "spacer.gif", "bullet.gif"}

    def __init__(self):
        super().__init__()
        self.title = ""
        self.paragraphs = []   # list of (inner_html, is_moral)
        self.images = []       # list of (src, alt) — story art only
        self.next_href = None

        self._depth = 0
        self._content_div_depth = None
        self._in_p = False
        self._p_chunks = []    # (text, is_italic) within current <p>
        self._em_depth = 0
        self._in_blockquote = False
        self._bq_buf = []
        self._in_heading = False
        self._heading_buf = []
        self._in_a = False
        self._a_href = ""
        self._a_buf = []

    @staticmethod
    def _strip_query_fragment(url):
        """Remove query string and fragment from a URL-like path for filename filtering."""
        return (url or "").split("?", 1)[0].split("#", 1)[0]

    def handle_starttag(self, tag, attrs):
        self._depth += 1
        attrs_d = dict(attrs)

        if tag == "div" and self._content_div_depth is None:
            classes = str(attrs_d.get("class") or "").lower()
            id_ = str(attrs_d.get("id") or "").lower()
            if any(k in classes + id_ for k in ("story", "content", "main", "text", "body")):
                self._content_div_depth = self._depth

        if tag == "p":
            self._in_p = True
            self._p_chunks = []
            self._em_depth = 0

        if tag in ("em", "i") and self._in_p:
            self._em_depth += 1

        if tag == "blockquote":
            self._in_blockquote = True
            self._bq_buf = []

        if tag in ("h1", "h2", "h3") and not self.title:
            self._in_heading = True
            self._heading_buf = []

        if tag == "a":
            self._in_a = True
            self._a_href = attrs_d.get("href", "")
            self._a_buf = []

        if tag == "img":
            src = attrs_d.get("src", "") or attrs_d.get("data-src", "") or attrs_d.get("data-original", "")
            srcset = attrs_d.get("srcset", "")
            if not src and srcset:
                first_srcset = srcset.split(",", 1)[0].strip()
                src = first_srcset.split(" ", 1)[0].strip() if first_srcset else ""
            alt = attrs_d.get("alt", "")
            clean_src = self._strip_query_fragment(src)
            fname = clean_src.rsplit("/", 1)[-1].lower()
            if src and fname not in self._SKIP_IMGS and not fname.startswith("logo"):
                self.images.append((src, alt))

    def handle_endtag(self, tag):
        if tag in ("em", "i") and self._in_p and self._em_depth > 0:
            self._em_depth -= 1

        if tag == "p" and self._in_p:
            inner_parts = []
            for text, is_em in self._p_chunks:
                esc = _html.escape(text)
                inner_parts.append(f"<em>{esc}</em>" if is_em else esc)
            inner = "".join(inner_parts).strip()
            total_text = "".join(t for t, _ in self._p_chunks).strip()
            if inner and len(total_text) > 15:
                non_ws = [(t, em) for t, em in self._p_chunks if t.strip()]
                all_italic = bool(non_ws) and all(em for _, em in non_ws)
                is_moral = all_italic or total_text.lower().startswith("moral")
                self.paragraphs.append((inner, is_moral))
            self._in_p = False
            self._p_chunks = []
            self._em_depth = 0

        if tag == "blockquote" and self._in_blockquote:
            text = "".join(self._bq_buf).strip()
            if text:
                self.paragraphs.append((_html.escape(text), True))
            self._in_blockquote = False
            self._bq_buf = []

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
            self._p_chunks.append((data, self._em_depth > 0))
        if self._in_blockquote:
            self._bq_buf.append(data)
        if self._in_heading:
            self._heading_buf.append(data)
        if self._in_a:
            self._a_buf.append(data)


def _fetch(url):
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=15) as resp:
        charset = resp.info().get_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace"), resp.geturl()


def _fetch_image_b64(url):
    """Download an image and return a base64 data URI, or None on failure."""
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            content_type = resp.headers.get_content_type()
            if not content_type or content_type == "application/octet-stream":
                lower_url = url.lower()
                if ".png" in lower_url:
                    content_type = "image/png"
                elif ".gif" in lower_url:
                    content_type = "image/gif"
                elif ".webp" in lower_url:
                    content_type = "image/webp"
                else:
                    content_type = "image/jpeg"
            data = resp.read()
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{content_type};base64,{b64}"
    except Exception as e:
        print(f"[WARN] Failed to fetch image: {url} ({type(e).__name__}: {e})", file=sys.stderr)
        return None


def _extract_hype_images(html_text, resolved_url):
    """Extract default image candidates from Tumult Hype script-based graphics."""
    candidates = []
    script_pattern = re.compile(r'<script[^>]+src=["\']([^"\']*hype_generated_script\.js[^"\']*)["\']', re.I)
    image_pattern = re.compile(r'([A-Za-z0-9_./-]+\.(?:jpg|jpeg|png|gif|webp))', re.I)

    for m in script_pattern.finditer(html_text):
        script_src = m.group(1)
        script_url = urljoin(resolved_url, script_src)
        script_url_clean = script_url.split("?", 1)[0].split("#", 1)[0]
        script_base = script_url_clean.rsplit("/", 1)[0] + "/"
        try:
            script_text, _ = _fetch(script_url)
        except Exception as e:
            print(f"[WARN] Failed to fetch Hype script: {script_url} ({type(e).__name__}: {e})", file=sys.stderr)
            continue

        seen = set()
        for img_match in image_pattern.finditer(script_text):
            img_ref = img_match.group(1)
            img_clean = img_ref.split("?", 1)[0].split("#", 1)[0]
            fname = img_clean.rsplit("/", 1)[-1].lower()
            if fname in _StoryParser._SKIP_IMGS or fname.startswith("logo"):
                continue
            if fname in seen:
                continue
            seen.add(fname)

            if re.match(r'^https?://', img_ref, re.I):
                img_url = img_ref
            elif "/" in img_ref:
                img_url = urljoin(resolved_url, img_ref)
            else:
                img_url = urljoin(script_base, img_ref)

            candidates.append((img_url, "Interactive illustration"))

        if candidates:
            break

    return candidates


def _make_html(title, paragraphs, next_filename=None, image_uri=None, image_alt=""):
    esc_title = _html.escape(title)

    img_html = ""
    if image_uri:
        img_html = f'<img class="story-img" src="{image_uri}" alt="{_html.escape(image_alt)}">\n'

    paras_html_parts = []
    for inner_html, is_moral in paragraphs:
        cls = ' class="moral"' if is_moral else ""
        paras_html_parts.append(f"<p{cls}>{inner_html}</p>")
    paras_html = "\n".join(paras_html_parts)

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
        f"{img_html}"
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
        paragraphs = parser.paragraphs or [("(No text found on this page.)", False)]
        next_href = parser.next_href
        images = [(urljoin(resolved_url, src), alt) for src, alt in parser.images]
        if not images:
            images = _extract_hype_images(html_text, resolved_url)

        collected.append((title, paragraphs, images, resolved_url))

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
    for i, (title, paragraphs, images, _) in enumerate(collected):
        filename = f"story_{i + 1:03d}.html"
        filepath = os.path.join(output_dir, filename)
        next_filename = f"story_{i + 2:03d}.html" if i + 1 < len(collected) else None
        # Try each extracted image in order and use the first that downloads successfully.
        image_uri = image_alt = None
        if images:
            for img_url, img_alt in images:
                image_uri = _fetch_image_b64(img_url)
                if image_uri:
                    image_alt = img_alt
                    break
        html_content = _make_html(title, paragraphs, next_filename,
                                   image_uri=image_uri, image_alt=image_alt or "")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content)
        saved_paths.append(os.path.abspath(filepath))

    if progress_callback:
        progress_callback(len(collected), count, "Done")

    return saved_paths
