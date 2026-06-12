import os
import json
import webview
import time
from urllib.parse import unquote, urlparse
from monitor_geometry import get_selected_monitor


def show_reading_window(url, on_ready_callback=None, duration_seconds=300,
                        save_dir=None, participant_name=None, order_code=None,
                        auto_advance_seconds=None, total_stories=None):
    timeout_url = "about:blank#reading-timeout"
    # Window size and position
    width, height = 1600, 1000
    # Centering logic for Windows
    from ctypes import windll

    monitor = get_selected_monitor()

    # Get DPI scaling factor
    try:
        dpi = windll.user32.GetDpiForSystem()
        scale_factor = dpi / 96.0  # 96 DPI is 100% scaling
    except:
        scale_factor = 1.0

    # pywebview expects logical coordinates while Tk timer placement uses physical coords.
    logical_x = int(monitor['work_x'] / scale_factor)
    logical_y = int(monitor['work_y'] / scale_factor)
    logical_w = int(monitor['work_width'] / scale_factor)
    logical_h = int(monitor['work_height'] / scale_factor)

    max_width = max(1500, logical_w - 80)
    max_height = max(900, logical_h - 80)
    width = min(width, max_width)
    height = min(height, max_height)

    webview_left = logical_x + int((logical_w - width) / 2)
    webview_top = logical_y + int((logical_h - height) / 2)

    print(
        f"Monitor #{monitor['display_number']} ({monitor['work_x']},{monitor['work_y']}) "
        f"{monitor['work_width']}x{monitor['work_height']}, Scale: {scale_factor}, "
        f"Webview: ({webview_left},{webview_top})"
    )

    # Shared state for webview lifecycle
    timed_out = [False]

    # Story tracking - all times in ms relative to task_start_time
    task_start_time = time.time()
    story_log = []      # list of {url, shown_ms, next_clicked_ms}

    # Count total stories if reading from a local directory of HTML files
    requested_total_stories = total_stories
    total_stories = [0]
    local_story_paths = []
    story_index_by_norm = {}

    def _norm_local_path(value):
        if not value:
            return ""
        try:
            parsed = urlparse(value)
            if parsed.scheme == "file":
                p = unquote(parsed.path or "")
                if os.name == "nt" and len(p) >= 3 and p[0] == "/" and p[2] == ":":
                    p = p[1:]
                p = p.replace("/", os.sep)
            elif parsed.scheme:
                return ""
            else:
                p = value
            return os.path.normcase(os.path.normpath(os.path.abspath(p)))
        except Exception:
            return ""

    if not url.startswith('http://') and not url.startswith('https://'):
        try:
            story_dir = os.path.dirname(os.path.abspath(url))
            local_story_paths = sorted(
                [
                    os.path.abspath(os.path.join(story_dir, f))
                    for f in os.listdir(story_dir)
                    if f.lower().endswith('.html')
                ],
                key=lambda p: os.path.basename(p).lower(),
            )
            story_index_by_norm = {_norm_local_path(p): i for i, p in enumerate(local_story_paths)}
            computed_total = len(local_story_paths)
            total_stories[0] = int(requested_total_stories) if isinstance(requested_total_stories, int) and requested_total_stories > 0 else computed_total
        except Exception:
            pass

    def _next_story_url(current_url, story_number):
        """Return (target_url, wraps_to_first) for local downloaded stories.

        Use sequence order as the primary source of truth because pywebview URL reads
        may intermittently fail on some systems; this avoids click events that log
        successfully but appear to not navigate.
        """
        if not local_story_paths:
            return None, False

        # Primary: deterministic sequence index from loaded story count.
        # story_number is 1-based; next_idx is 0-based.
        if story_number > 0:
            next_idx = story_number % len(local_story_paths)
            wraps = next_idx == 0
            # Relative target is more reliable with local HTML stories.
            return os.path.basename(local_story_paths[next_idx]), wraps

        # Fallback (should rarely execute): infer from current URL.
        current_norm = _norm_local_path(current_url)
        idx = story_index_by_norm.get(current_norm)
        if idx is None:
            idx = story_index_by_norm.get(_norm_local_path(url), -1)
        next_idx = (idx + 1) % len(local_story_paths)
        wraps = idx >= 0 and next_idx == 0
        return os.path.basename(local_story_paths[next_idx]), wraps

    def _elapsed_ms():
        return (time.time() - task_start_time) * 1000

    # Expose a Python API to JS so the in-page Next button can record its click time
    class _ReadingApi:
        def record_next_click(self):
            if story_log and story_log[-1]['next_clicked_ms'] is None:
                story_log[-1]['next_clicked_ms'] = _elapsed_ms()
                print(f'[DEBUG] In-page Next click recorded at {story_log[-1]["next_clicked_ms"]:.0f}ms')
        def notify_time_expired(self):
            if timed_out[0]:
                return
            timed_out[0] = True
            print('[DEBUG] Reading task timer expired')

    api_obj = _ReadingApi()

    print('Creating webview window...')
    window = webview.create_window(
        'Reading Task',
        url,
        width=width,
        height=height,
        x=webview_left,
        y=webview_top,
        resizable=False,
        frameless=True,
        on_top=True,
        easy_drag=False,
        js_api=api_obj
    )
    if window is None:
        print('[ERROR] Failed to create reading webview window')
        return

    def on_loaded():
        # Record the current story URL and when it was shown
        try:
            current_url = window.evaluate_js('window.location.href') or url
        except Exception:
            current_url = url

        if current_url.startswith(timeout_url):
            if not timed_out[0]:
                timed_out[0] = True
                print('[DEBUG] Reading task timer expired')
            try:
                window.destroy()
            except Exception as e:
                print(f'[ERROR] Could not close reading window after timeout: {e}')
            return

        if timed_out[0]:
            return

        story_log.append({
            'url': current_url,
            'shown_ms': _elapsed_ms(),
            'next_clicked_ms': None,
        })

        # Update story counter label
        n = len(story_log)
        total = total_stories[0]
        counter_text = f'Story {n} of {total}' if total > 0 else f'Story {n}'
        remaining_seconds = max(0, int(duration_seconds - (time.time() - task_start_time)))
        target_href, wraps_to_first = _next_story_url(current_url, n)
        if target_href:
            print(f"[DEBUG] Story {n}: next target -> {target_href}")

        # Disable interactivity, inject timer + next controls, return next URL.
        # Uses double quotes throughout — EdgeHTML eval has issues with single-quoted JS strings.
        # join('\n') is also avoided as the Python '\n' becomes a literal newline inside a JS string literal.
        _js = (
            "(function(counterText, remainingSeconds, autoAdvanceSeconds, targetHref, wrapsToFirst) {"
            " if (window.__readingTimerInterval) {"
            "  clearInterval(window.__readingTimerInterval);"
            "  window.__readingTimerInterval = null;"
            " }"
            " if (window.__blinkrAutoNextInterval) {"
            "  clearInterval(window.__blinkrAutoNextInterval);"
            "  window.__blinkrAutoNextInterval = null;"
            " }"
            " document.querySelectorAll(\"[onclick]\").forEach(function(el) {"
            "  el.removeAttribute(\"onclick\");"
            " });"
            " var nextLink = null;"
            " document.querySelectorAll(\"a\").forEach(function(a) {"
            "  if (!nextLink && a.textContent.trim().toLowerCase().indexOf(\"next\") !== -1) {"
            "   nextLink = a;"
            "  }"
            " });"
            " if (nextLink && !nextLink.__blinkrRecordHooked) {"
            "  nextLink.__blinkrRecordHooked = true;"
            "  nextLink.addEventListener(\"click\", function() {"
            "   if (window.pywebview && window.pywebview.api) {"
            "    window.pywebview.api.record_next_click();"
            "   }"
            "  }, true);"
            " }"
            " document.querySelectorAll(\"a\").forEach(function(a) {"
            "  if (a !== nextLink) {"
            "   a.removeAttribute(\"href\");"
            "   a.removeAttribute(\"onclick\");"
            "  }"
            " });"
            " var timerBar = document.getElementById(\"__blinkrTimerBar\");"
            " if (timerBar) timerBar.remove();"
            " timerBar = document.createElement(\"div\");"
            " timerBar.id = \"__blinkrTimerBar\";"
            " timerBar.style.position = \"fixed\";"
            " timerBar.style.left = \"0\";"
            " timerBar.style.right = \"0\";"
            " timerBar.style.bottom = \"0\";"
            " timerBar.style.height = \"40px\";"
            " timerBar.style.background = \"#374151\";"
            " timerBar.style.display = \"flex\";"
            " timerBar.style.alignItems = \"center\";"
            " timerBar.style.justifyContent = \"space-between\";"
            " timerBar.style.padding = \"0 10px\";"
            " timerBar.style.boxSizing = \"border-box\";"
            " timerBar.style.zIndex = \"2147483646\";"
            " timerBar.style.fontFamily = \"Segoe UI, sans-serif\";"
            " timerBar.style.userSelect = \"none\";"
            " var storyLabel = document.createElement(\"span\");"
            " storyLabel.textContent = counterText;"
            " storyLabel.style.color = \"#e5e7eb\";"
            " storyLabel.style.fontWeight = \"700\";"
            " var timerLabel = document.createElement(\"span\");"
            " timerLabel.style.color = \"#ffffff\";"
            " timerLabel.style.fontWeight = \"700\";"
            " timerLabel.style.margin = \"0 8px\";"
            " var nextBtn = document.createElement(\"button\");"
            " nextBtn.textContent = \"Next Story\";"
            " nextBtn.style.background = \"#3b82f6\";"
            " nextBtn.style.color = \"#ffffff\";"
            " nextBtn.style.border = \"none\";"
            " nextBtn.style.borderRadius = \"6px\";"
            " nextBtn.style.padding = \"6px 10px\";"
            " nextBtn.style.fontWeight = \"700\";"
            " nextBtn.style.cursor = \"pointer\";"
            " nextBtn.style.pointerEvents = \"auto\";"
            " nextBtn.style.marginLeft = \"8px\";"
            " var rightWrap = document.createElement(\"div\");"
            " rightWrap.style.display = \"flex\";"
            " rightWrap.style.alignItems = \"center\";"
            " rightWrap.appendChild(timerLabel);"
            " rightWrap.appendChild(nextBtn);"
            " timerBar.appendChild(storyLabel);"
            " timerBar.appendChild(rightWrap);"
            " document.body.appendChild(timerBar);"
            " function formatTime(totalSeconds) {"
            "  var mins = Math.floor(totalSeconds / 60);"
            "  var secs = totalSeconds % 60;"
            "  return \"Time remaining: \" + mins + \":\" + (secs < 10 ? \"0\" + secs : secs);"
            " }"
            " if (wrapsToFirst) {"
            "  nextBtn.textContent = \"Back to First Story\";"
            " }"
            " if (!targetHref) {"
            "  nextBtn.disabled = true;"
            "  nextBtn.style.background = \"#6b7280\";"
            "  nextBtn.style.cursor = \"default\";"
            " }"
            " function goNext() {"
            "  if (!targetHref) return;"
            "  if (window.pywebview && window.pywebview.api) {"
            "   window.pywebview.api.record_next_click();"
            "  }"
            "  if (nextLink && nextLink.href) {"
            "   try { nextLink.click(); return; } catch (e) {}"
            "  }"
            "  window.location.href = targetHref;"
            " }"
            " nextBtn.addEventListener(\"click\", function() { goNext(); }, true);"
            " var autoSecs = parseFloat(autoAdvanceSeconds);"
            " if (targetHref && isFinite(autoSecs) && autoSecs > 0) {"
            "  window.__blinkrAutoNextInterval = setInterval(function() {"
            "   goNext();"
            "  }, Math.max(250, autoSecs * 1000));"
            " }"
            " var remaining = Math.max(0, parseInt(remainingSeconds, 10) || 0);"
            " timerLabel.textContent = formatTime(remaining);"
            " window.__readingTimerInterval = setInterval(function() {"
            "  remaining = Math.max(0, remaining - 1);"
            "  timerLabel.textContent = formatTime(remaining);"
            "  if (remaining <= 0) {"
            "   clearInterval(window.__readingTimerInterval);"
            "   window.__readingTimerInterval = null;"
            "   if (window.__blinkrAutoNextInterval) {"
            "    clearInterval(window.__blinkrAutoNextInterval);"
            "    window.__blinkrAutoNextInterval = null;"
            "   }"
            "   window.location.href = \"about:blank#reading-timeout\";"
            "  }"
            " }, 1000);"
            " var style = document.createElement(\"style\");"
            " style.textContent = \"a,button,input,select,textarea,label{"
            "pointer-events:none!important;cursor:default!important}"
            "#__blinkrTimerBar,#__blinkrTimerBar *{pointer-events:auto!important}"
            "img{pointer-events:none!important}\";"
            " document.head.appendChild(style);"
            " if (nextLink) {"
            "  nextLink.style.setProperty(\"pointer-events\", \"auto\", \"important\");"
            "  nextLink.style.cursor = \"pointer\";"
            "  nextLink.addEventListener(\"mouseover\", function() {"
            "   this.style.background = \"linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%)\";"
            "   this.style.boxShadow = \"0 4px 14px rgba(37,99,235,0.38)\";"
            "   this.style.transform = \"translateY(-1px)\";"
            "  });"
            "  nextLink.addEventListener(\"mouseout\", function() {"
            "   this.style.background = \"linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%)\";"
            "   this.style.boxShadow = \"0 2px 8px rgba(37,99,235,0.28)\";"
            "   this.style.transform = \"\";"
            "  });"
            " }"
            " [\"header\",\"logo\",\"aboutDiv\"].forEach(function(id) {"
            "  var el = document.getElementById(id);"
            "  if (el) el.remove();"
            " });"
            " document.body.style.paddingBottom = \"48px\";"
            " document.body.style.opacity = \"1\";"
            " return targetHref || null;"
            "})(__COUNTER__, __REMAINING__, __AUTONEXT__, __TARGET__, __WRAPS__)"
        )
        try:
            js_payload = _js.replace('__COUNTER__', json.dumps(counter_text)).replace(
                '__REMAINING__', str(remaining_seconds)
            ).replace('__AUTONEXT__', json.dumps(auto_advance_seconds)).replace(
                '__TARGET__', json.dumps(target_href)
            ).replace(
                '__WRAPS__', json.dumps(wraps_to_first)
            )
            window.evaluate_js(js_payload)
        except Exception as e:
            print(f'[ERROR] Could not disable interactivity: {e}')

        # Fire on_ready_callback only on the first story load
        if len(story_log) == 1 and on_ready_callback:
            on_ready_callback()

    window.events.loaded += on_loaded

    try:
        webview.start(gui='edgechromium')
    except Exception as e:
        print(f'[WARN] edgechromium backend failed: {e}')
        try:
            webview.start(gui='mshtml')
        except Exception as e2:
            print(f'Exception in webview.start: {e2}')

    # Save story navigation log once webview has closed
    _save_reading_log(story_log, save_dir, participant_name, order_code)


def _save_reading_log(story_log, save_dir, participant_name, order_code):
    """Save story navigation log to a reading_tasks/ subfolder CSV."""
    if not save_dir or not story_log:
        return
    from datetime import datetime

    tasks_dir = os.path.join(save_dir, "reading_tasks")
    os.makedirs(tasks_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name_part = f"-{participant_name}" if participant_name else ""
    order_part = f"-{order_code}" if order_code else ""
    filename = f"{timestamp}{name_part}{order_part}-R.csv"
    filepath = os.path.join(tasks_dir, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("story_number,url,shown_ms,next_clicked_ms,duration_ms\n")
            for i, entry in enumerate(story_log, 1):
                shown = int(entry['shown_ms'])
                clicked = entry['next_clicked_ms']
                url_val = entry['url'].replace(',', '%2C')
                if clicked is not None:
                    clicked_str = str(int(clicked))
                    duration_str = str(int(clicked) - shown)
                else:
                    clicked_str = ""
                    duration_str = ""
                f.write(f"{i},{url_val},{shown},{clicked_str},{duration_str}\n")
        print(f"[DEBUG] Reading log saved to {filepath}")
    except Exception as e:
        print(f"[ERROR] Failed to save reading log: {e}")
