import webview
import tkinter as tk
import threading
import time

def show_reading_window(url, on_ready_callback=None, duration_seconds=300):
    # Window size and position
    width, height = 1400, 800
    bar_height = 40
    # Centering logic for Windows
    import ctypes
    from ctypes import windll
    
    # Make the process DPI aware to get actual screen dimensions
    try:
        windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
    except:
        try:
            windll.user32.SetProcessDPIAware()  # Fallback for older Windows
        except:
            pass
    
    user32 = windll.user32
    # Get actual screen dimensions (not scaled)
    screen_width = user32.GetSystemMetrics(0)
    screen_height = user32.GetSystemMetrics(1)
    
    # Get DPI scaling factor
    try:
        dpi = windll.user32.GetDpiForSystem()
        scale_factor = dpi / 96.0  # 96 DPI is 100% scaling
    except:
        scale_factor = 1.0
    
    print(f'Screen: {screen_width}x{screen_height}, Scale: {scale_factor}')
    
    # Center the webview window on screen
    # Both webview and tkinter use scaled (logical) coordinates on DPI-aware systems
    scaled_screen_width = int(screen_width / scale_factor)
    scaled_screen_height = int(screen_height / scale_factor)
    
    # Calculate center position for webview (1400x800 window)
    webview_left = int((scaled_screen_width - width) / 2)
    webview_top = int((scaled_screen_height - height) / 2)
    
    # Timer bar positioned directly below webview
    timer_left = webview_left
    timer_top = webview_top + height
    
    print(f'Screen: {scaled_screen_width}x{scaled_screen_height} (scaled), Webview: ({webview_left},{webview_top}), Timer: ({timer_left},{timer_top})')

    # Shared state for timer and webview
    webview_window = None
    timer_root = None
    webview_loaded = False

    def update_timer_position():
        """Update timer bar position to stay below webview"""
        if timer_root and timer_root.winfo_exists():
            timer_root.geometry(f'{width}x{bar_height}+{timer_left}+{timer_top}')
            timer_root.lift()
            timer_root.attributes('-topmost', True)

    def start_timer_bar():
        nonlocal timer_root
        timer_root = tk.Tk()
        timer_root.title('Reading Task Timer')
        timer_root.overrideredirect(True)  # Remove window decorations
        timer_root.configure(bg='#374151')
        
        # Set initial geometry immediately
        timer_root.geometry(f'{width}x{bar_height}+{timer_left}+{timer_top}')
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

        start_time = time.time()
        def update_timer():
            elapsed = time.time() - start_time
            remaining = max(0, duration_seconds - int(elapsed))
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
                timer_root.after(1000, update_timer)
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
        frameless=True
    )

    def on_loaded():
        nonlocal webview_loaded
        print('Webview window loaded.')
        webview_loaded = True
        
        # Reposition timer bar after webview has loaded and settled
        time.sleep(0.1)
        update_timer_position()
        
        # Set zoom to 85% and hide header, logo, and about divs
        try:
            webview_window.evaluate_js('''
                // Set zoom level to 85%
                document.body.style.zoom = "85%";
                
                // Remove the header, logo, and about divs
                var header = document.getElementById("header");
                if (header) {
                    header.remove();
                }
                var logo = document.getElementById("logo");
                if (logo) {
                    logo.remove();
                }
                var aboutDiv = document.getElementById("aboutDiv");
                if (aboutDiv) {
                    aboutDiv.remove();
                }
            ''')
        except Exception as e:
            print(f'Error setting zoom/removing elements: {e}')
        
        # Reposition again after JS execution
        time.sleep(0.1)
        update_timer_position()
        
        if on_ready_callback:
            on_ready_callback()

    webview_window.events.loaded += on_loaded

    print('Starting webview event loop...')
    try:
        webview.start(None, webview_window, gui='edgehtml')
        print('webview.start finished.')
    except Exception as e:
        print(f'Exception in webview.start: {e}')
    print('End of show_reading_window function.')


# Example usage:
if __name__ == '__main__':
    try:
        print('Launching reading window...')
        show_reading_window('https://read.gov/aesop/002.html', duration_seconds=120)
        print('Returned from show_reading_window.')
    except Exception as e:
        print(f'Error occurred: {e}')
