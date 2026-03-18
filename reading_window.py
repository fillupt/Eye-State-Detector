import os
import re
import webview
import tkinter as tk
import threading
import time
from monitor_geometry import get_selected_monitor


def show_reading_window(url, on_ready_callback=None, duration_seconds=300,
                        save_dir=None, participant_name=None, order_code=None):
    # Window size and position
    width, height = 1400, 860
    bar_height = 40
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

    max_width = max(900, logical_w - 80)
    max_height = max(600, logical_h - 120)
    width = min(width, max_width)
    height = min(height, max_height)

    webview_left = logical_x + int((logical_w - width) / 2)
    webview_top = logical_y + int((logical_h - height) / 2)

    # Timer bar positioned directly below webview
    timer_left = int(webview_left * scale_factor)
    timer_top = int((webview_top + height) * scale_factor) - 80
    timer_width = int(width * scale_factor) - 30  # Adjust for window borders

    print(
        f"Monitor #{monitor['display_number']} ({monitor['work_x']},{monitor['work_y']}) "
        f"{monitor['work_width']}x{monitor['work_height']}, Scale: {scale_factor}, "
        f"Webview: ({webview_left},{webview_top}), Timer: ({timer_left},{timer_top}) width={timer_width}"
    )

    # Shared state for timer and webview
    webview_window = None
    timer_root = None
    webview_loaded = False
    next_btn_ref = [None]  # mutable ref to the Next Story button widget
    story_label_ref = [None]  # mutable ref to the story counter label

    # Story tracking - all times in ms relative to task_start_time
    task_start_time = time.time()
    story_log = []      # list of {url, shown_ms, next_clicked_ms}
    next_url = [None]   # next-page URL extracted before stripping hrefs

    # Count total stories if reading from a local directory of HTML files
    total_stories = [0]
    if not url.startswith('http://') and not url.startswith('https://'):
        try:
            story_dir = os.path.dirname(os.path.abspath(url))
            total_stories[0] = len([f for f in os.listdir(story_dir) if f.endswith('.html')])
        except Exception:
            pass

    def _elapsed_ms():
        return (time.time() - task_start_time) * 1000

    # Expose a Python API to JS so the in-page Next button can record its click time
    class _ReadingApi:
        def record_next_click(self):
            if story_log and story_log[-1]['next_clicked_ms'] is None:
                story_log[-1]['next_clicked_ms'] = _elapsed_ms()
                print(f'[DEBUG] In-page Next click recorded at {story_log[-1]["next_clicked_ms"]:.0f}ms')

    api_obj = _ReadingApi()

    def update_timer_position():
        """Update timer bar position to stay below webview."""
        if timer_root and timer_root.winfo_exists():
            timer_root.geometry(f'{timer_width}x{bar_height}+{timer_left}+{timer_top}')
            timer_root.lift()
            timer_root.attributes('-topmost', True)

    def on_next_clicked():
        """Navigate to the next story when the Next Story button is clicked."""
        # Stamp click time only if not already captured by the in-page Next handler
        if story_log and story_log[-1]['next_clicked_ms'] is None:
            story_log[-1]['next_clicked_ms'] = _elapsed_ms()

        target = next_url[0]
        if not target:
            # Fallback: increment the story number in the current URL
            if story_log:
                current = story_log[-1]['url']
                match = re.search(r'(\d+)(\.html)$', current, re.IGNORECASE)
                if match:
                    n = int(match.group(1))
                    padded = str(n + 1).zfill(len(match.group(1)))
                    target = current[:match.start()] + padded + match.group(2)

        if target:
            next_url[0] = None  # Clear until next on_loaded fires
            try:
                webview_window.load_url(target)
            except Exception as e:
                print(f'[ERROR] Could not navigate to next story: {e}')
        else:
            # No next story found - disable the button
            if next_btn_ref[0] and timer_root and timer_root.winfo_exists():
                timer_root.after(0, lambda: next_btn_ref[0].config(state='disabled', bg='#6b7280'))

    def start_timer_bar():
        nonlocal timer_root
        timer_root = tk.Tk()
        timer_root.title('Reading Task Timer')
        timer_root.overrideredirect(True)  # Remove window decorations
        timer_root.configure(bg='#374151')

        # Set initial geometry immediately
        timer_root.geometry(f'{timer_width}x{bar_height}+{timer_left}+{timer_top}')
        timer_root.attributes('-topmost', True)

        progress_frame = tk.Frame(timer_root, bg='#374151', height=bar_height)
        progress_frame.pack(fill='both', expand=True)
        progress_frame.pack_propagate(False)

        progress_bar = tk.Frame(progress_frame, bg='#10b981')
        progress_bar.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        progress_label = tk.Label(
            progress_frame,
            text=f'Time remaining: {duration_seconds//60}:{duration_seconds%60:02d}',
            bg='#10b981',
            fg='#ffffff',
            font=('Segoe UI', 10)
        )
        progress_label.place(relx=0.5, rely=0.5, anchor='center')

        # Next Story button - pinned to the right end of the timer bar
        next_btn = tk.Button(
            progress_frame,
            text='Next Story \u2192',
            command=on_next_clicked,
            bg='#3b82f6', fg='#ffffff',
            font=('Segoe UI', 10, 'bold'),
            relief='flat', cursor='hand2',
            padx=10,
        )
        next_btn.place(relx=1.0, rely=0.5, anchor='e', x=-4)
        next_btn_ref[0] = next_btn

        # Story counter label - pinned to the left end of the timer bar
        story_label = tk.Label(
            progress_frame,
            text='Story 0',
            bg='#374151',
            fg='#e5e7eb',
            font=('Segoe UI', 10, 'bold'),
            padx=10,
        )
        story_label.place(relx=0.0, rely=0.5, anchor='w', x=4)
        story_label_ref[0] = story_label

        start_time = time.time()
        def update_timer():
            elapsed = time.time() - start_time
            remaining = max(0, duration_seconds - elapsed)
            ratio = remaining / duration_seconds if duration_seconds > 0 else 0
            progress_bar.place(x=0, y=0, relwidth=ratio, relheight=1.0)
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            progress_label.config(text=f'Time remaining: {mins}:{secs:02d}')

            # Reposition timer bar periodically if webview has loaded
            if webview_loaded:
                update_timer_position()

            if remaining <= 0:
                timer_root.after(500, timer_root.destroy)
                # Close webview window properly
                if webview_window:
                    webview_window.destroy()
            else:
                timer_root.after(50, update_timer)
        update_timer()
        timer_root.mainloop()

    print('Starting timer bar thread...')
    timer_thread = threading.Thread(target=start_timer_bar, daemon=True)
    timer_thread.start()

    print('Creating webview window...')
    webview_window = webview.create_window(
        'Reading Task',
        url,
        width=width,
        height=height,
        x=webview_left,
        y=webview_top,
        resizable=False,
        frameless=True,
        easy_drag=False,
        js_api=api_obj
    )

    def on_loaded():
        nonlocal webview_loaded
        webview_loaded = True
        time.sleep(0.1)
        update_timer_position()

        # Record the current story URL and when it was shown
        try:
            current_url = webview_window.evaluate_js('window.location.href') or url
        except Exception:
            current_url = url

        story_log.append({
            'url': current_url,
            'shown_ms': _elapsed_ms(),
            'next_clicked_ms': None,
        })

        # Update story counter label
        n = len(story_log)
        total = total_stories[0]
        counter_text = f'Story {n} of {total}' if total > 0 else f'Story {n}'
        if story_label_ref[0] and timer_root and timer_root.winfo_exists():
            timer_root.after(0, lambda t=counter_text: story_label_ref[0].config(text=t))

        # Disable interactivity, wire in-page Next to record click, return next URL.
        # Uses double quotes throughout — EdgeHTML eval has issues with single-quoted JS strings.
        # join('\n') is also avoided as the Python '\n' becomes a literal newline inside a JS string literal.
        _js = (
            "(function() {"
            " document.querySelectorAll(\"[onclick]\").forEach(function(el) {"
            "  el.removeAttribute(\"onclick\");"
            " });"
            " var nextLink = null;"
            " document.querySelectorAll(\"a\").forEach(function(a) {"
            "  if (!nextLink && a.textContent.trim().toLowerCase().indexOf(\"next\") !== -1) {"
            "   nextLink = a;"
            "  }"
            " });"
            " if (nextLink) {"
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
            " var style = document.createElement(\"style\");"
            " style.textContent = \"a,button,input,select,textarea,label{"
            "pointer-events:none!important;cursor:default!important}"
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
            " document.body.style.opacity = \"1\";"
            " return nextLink ? nextLink.href : null;"
            "})()"
        )
        try:
            extracted = webview_window.evaluate_js(_js)
            next_url[0] = extracted if extracted else None
        except Exception as e:
            print(f'[ERROR] Could not disable interactivity: {e}')
            next_url[0] = None

        time.sleep(0.1)
        update_timer_position()

        # Fire on_ready_callback only on the first story load
        if len(story_log) == 1 and on_ready_callback:
            on_ready_callback()

    webview_window.events.loaded += on_loaded

    try:
        webview.start(None, webview_window, gui='edgehtml')
    except Exception as e:
        print(f'Exception in webview.start: {e}')

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
