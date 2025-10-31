import json
import os
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, font, messagebox


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def find_python_executable():
    # Prefer the current Python interpreter (so a venv works if launcher is run from it)
    return sys.executable


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Blink or they're gone — Launcher")
        self.configure(bg="#1f2937")
        self.process = None

        # Center window
        self.width = 420
        # Make window taller so the directory label can wrap to multiple lines
        self.height = 300
        self._center_window()

        # Styling
        header_font = font.Font(family="Segoe UI", size=16, weight="bold")
        label_font = font.Font(family="Segoe UI", size=11)

        header = tk.Label(self, text="Blink or they're gone!", bg="#1f2937", fg="#ffffff", font=header_font)
        header.pack(pady=(14, 6))

        sub = tk.Label(self, text="Enter subject name", bg="#1f2937", fg="#cbd5e1", font=label_font)
        sub.pack(pady=(0, 10))

        entry_frame = tk.Frame(self, bg="#1f2937")
        entry_frame.pack(pady=(0, 8))

        self.name_var = tk.StringVar()
        name_entry = tk.Entry(entry_frame, textvariable=self.name_var, width=30, font=label_font)
        name_entry.pack(ipady=6, padx=6)
        name_entry.focus()

        btn_frame = tk.Frame(self, bg="#1f2937")
        btn_frame.pack(pady=(4, 6))

        # Single toggle button
        self.toggle_btn = tk.Button(btn_frame, text="Start", command=self.toggle_tracker, bg="#10b981", fg="#03241b", padx=12, pady=8, relief="flat", font=label_font)
        self.toggle_btn.pack(side="left", padx=8)

        # Setup button (opens settings window)
        setup_btn = tk.Button(btn_frame, text="Setup", command=self.open_setup_window, bg="#8b5cf6", fg="#fff", padx=10, pady=8, relief="flat", font=label_font)
        setup_btn.pack(side="left", padx=8)

        # Ensure task/file attributes exist
        self.task_reading = ""
        self.task_video = ""
        self.task_interactive = ""
        self.sande = False
        self.osdi6 = False
        self.last_name = ""
        self.save_dir = ""

        # Load saved config (if any)
        self._load_config()

        self.status_label = tk.Label(self, text="Status: Idle", bg="#1f2937", fg="#9ca3af", font=label_font)
        self.status_label.pack(pady=(8, 0))

        # Close behavior
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _center_window(self):
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w // 2) - (self.width // 2)
        y = (screen_h // 2) - (self.height // 2)
        self.geometry(f"{self.width}x{self.height}+{x}+{y}")

    def start_tracker(self):
        # Start process and begin polling for readiness
        name = self.name_var.get().strip()
        python_exe = find_python_executable()
        cmd = [python_exe, os.path.join(ROOT_DIR, "Eye_State_Detector.py")]
        if name:
            cmd += ["--name", name]
        # Pass save directory if configured
        if self.save_dir:
            cmd += ["--outdir", self.save_dir]

        try:
            self.process = subprocess.Popen(cmd, cwd=ROOT_DIR)
            self.status_label.config(text=f"Status: Initializing (PID {self.process.pid})", fg="#fef3c7")
            # Update UI to show initializing state
            self.toggle_btn.config(text="Initializing...", state="disabled", bg="#f59e0b", fg="#2b0500")
            # Start polling for ready file and process state
            self.after(500, self._poll_ready)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start tracker: {e}")

    def choose_directory(self):
        """Open a directory picker and store the chosen path."""
        selected = filedialog.askdirectory(title="Select save directory", initialdir=ROOT_DIR)
        if selected:
            self.save_dir = selected
            display = selected if len(selected) <= 80 else f"...{selected[-77:]}"
            self.dir_label.config(text=f"Save dir: {display}")
            # Persist selection to local config
            try:
                self._save_config()
            except Exception:
                # Non-fatal if write fails
                pass

    def _config_path(self):
        return os.path.join(ROOT_DIR, "launcher_config.json")

    def _load_config(self):
        cfg = self._config_path()
        try:
            if os.path.exists(cfg):
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sd = data.get("save_dir")
                if sd and os.path.exists(sd):
                    self.save_dir = sd
                    display = sd if len(sd) <= 80 else f"...{sd[-77:]}"
                    self.dir_label.config(text=f"Save dir: {display}")

                # Load persisted task/file paths and flags
                self.task_reading = data.get("task_reading", "") or ""
                self.task_video = data.get("task_video", "") or ""
                self.task_interactive = data.get("task_interactive", "") or ""
                self.sande = bool(data.get("sande", False))
                self.osdi6 = bool(data.get("osdi6", False))
                self.last_name = data.get("last_name", "") or ""
                if self.last_name:
                    self.name_var.set(self.last_name)
        except Exception:
            # ignore config load errors
            pass

    def _save_config(self):
        cfg = self._config_path()
        try:
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump({
                    "save_dir": self.save_dir,
                    "task_reading": self.task_reading,
                    "task_video": self.task_video,
                    "task_interactive": self.task_interactive,
                    "sande": bool(self.sande),
                    "osdi6": bool(self.osdi6),
                    "last_name": self.name_var.get().strip(),
                }, f, indent=2)
        except Exception:
            # bubble up to caller if needed
            raise

    def stop_tracker(self):
        # Stop the running tracker process
        if self.process is None:
            self.status_label.config(text="Status: Idle", fg="#9ca3af")
            self.toggle_btn.config(text="Start", state="normal", bg="#10b981", fg="#03241b")
            return
        if self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=3)
                self.status_label.config(text="Status: Stopped", fg="#fca5a5")
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
                self.status_label.config(text="Status: Stopped", fg="#fca5a5")
        else:
            self.status_label.config(text="Status: Idle", fg="#9ca3af")
        self.process = None
        # Reset button
        self.toggle_btn.config(text="Start", state="normal", bg="#10b981", fg="#03241b")

    def _poll_ready(self):
        """Poll for the ready file or process exit to update UI state."""
        ready_path = os.path.join(ROOT_DIR, "tracker.ready")
        # If process exited
        if self.process is None or (self.process.poll() is not None):
            self.status_label.config(text="Status: Not running", fg="#fca5a5")
            self.toggle_btn.config(text="Start", state="normal", bg="#10b981", fg="#03241b")
            self.process = None
            return
        # If ready file exists, the tracker is running
        if os.path.exists(ready_path):
            self.status_label.config(text=f"Status: Running (PID {self.process.pid})", fg="#86efac")
            self.toggle_btn.config(text="Stop", state="normal", bg="#ef4444", fg="#fff")
            # Continue polling to detect when process exits
            self.after(500, self._poll_ready)
        else:
            # Still initializing, keep polling
            self.after(500, self._poll_ready)

    def toggle_tracker(self):
        # Single-button handler
        if self.process is None or (self.process.poll() is not None):
            # Save last name when starting
            try:
                self.last_name = self.name_var.get().strip()
                self._save_config()
            except Exception:
                pass
            self.start_tracker()
        else:
            # currently running -> stop
            self.toggle_btn.config(text="Stopping...", state="disabled", bg="#ef4444", fg="#fff")
            self.stop_tracker()

    def on_close(self):
        # Stop child process if running
        if self.process is not None and self.process.poll() is None:
            if messagebox.askyesno("Quit", "Tracker is running. Stop it and quit?"):
                self.stop_tracker()
            else:
                return
        self.destroy()

    # --- Setup window implementation -------------------------------------------------
    def open_setup_window(self):
        win = tk.Toplevel(self)
        win.title("Setup — Task files and options")
        win.configure(bg="#111827")
        win.geometry("560x320")
        # center relative to main window
        win.transient(self)
        # Position the setup window centered over the main launcher window
        try:
            self.update_idletasks()
            win.update_idletasks()
            main_x = self.winfo_rootx()
            main_y = self.winfo_rooty()
            main_w = self.winfo_width()
            main_h = self.winfo_height()
            win_w = win.winfo_width()
            win_h = win.winfo_height()
            cx = main_x + max(0, (main_w - win_w) // 2)
            cy = main_y + max(0, (main_h - win_h) // 2)
            win.geometry(f"{win_w}x{win_h}+{cx}+{cy}")
        except Exception:
            # best-effort centering; ignore if window metrics aren't available
            pass

        label_font = font.Font(family="Segoe UI", size=10)

        rowpad = dict(pady=8, padx=12)

        # Helper to render a task row (label, choose button, filename label)
        def add_task_row(parent, title, getter, filetypes=None):
            frame = tk.Frame(parent, bg="#111827")
            frame.pack(fill="x", **rowpad)
            lbl = tk.Label(frame, text=title + ":", bg="#111827", fg="#e5e7eb", font=label_font, width=14, anchor="w")
            lbl.pack(side="left")

            def choose_file():
                path = filedialog.askopenfilename(title=f"Choose {title}", initialdir=ROOT_DIR, filetypes=filetypes)
                if path:
                    # Update backing storage and persist
                    getter(path)
                    # Update the visible filename to the right of the button
                    shortp = path if len(path) <= 60 else f"...{path[-57:]}"
                    fname_var.set(shortp)

            btn = tk.Button(frame, text="Choose file...", command=choose_file, bg="#374151", fg="#fff", relief="flat", padx=8)
            btn.pack(side="left", padx=(6, 8))

            fname_var = tk.StringVar()
            fname = getter(None, get=True)
            if fname:
                short = fname if len(fname) <= 60 else f"...{fname[-57:]}"
                fname_var.set(short)
            lbl_name = tk.Label(frame, textvariable=fname_var, bg="#111827", fg="#9ca3af", font=label_font, anchor="w", justify="left")
            lbl_name.pack(side="left", fill="x", expand=True)

            # Lightweight tooltip that shows the full path on hover. It queries the getter each time
            # so the tooltip text stays in sync when the selection changes.
            tooltip = {'win': None}

            def show_tooltip(event):
                try:
                    full = getter(None, get=True) or ""
                    if not full:
                        return
                    # create a small toplevel without decorations
                    t = tk.Toplevel(self)
                    t.wm_overrideredirect(True)
                    lbl = tk.Label(t, text=full, bg="#111827", fg="#e5e7eb", bd=1, relief="solid", font=("Segoe UI", 9))
                    lbl.pack(ipadx=6, ipady=4)
                    # position near the mouse cursor
                    x = event.x_root + 16
                    y = event.y_root + 10
                    t.wm_geometry(f"+{x}+{y}")
                    tooltip['win'] = t
                except Exception:
                    pass

            def hide_tooltip(event):
                try:
                    if tooltip['win'] is not None:
                        tooltip['win'].destroy()
                        tooltip['win'] = None
                except Exception:
                    pass

            lbl_name.bind("<Enter>", show_tooltip)
            lbl_name.bind("<Leave>", hide_tooltip)

            return fname_var

        # Setters/getters that update state and persist
        def set_reading(path=None, get=False):
            if get:
                return self.task_reading
            self.task_reading = path or ""
            self._save_config()

        def set_video(path=None, get=False):
            if get:
                return self.task_video
            self.task_video = path or ""
            self._save_config()

        def set_interactive(path=None, get=False):
            if get:
                return self.task_interactive
            self.task_interactive = path or ""
            self._save_config()

        reading_var = add_task_row(win, "Reading task", set_reading)
        video_var = add_task_row(win, "Video task", set_video, filetypes=[
            ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.mpeg *.mpg"),
            ("All files", "*.*")
        ])
        interactive_var = add_task_row(win, "Interactive task", set_interactive)

        # Options row (checkboxes)
        opts = tk.Frame(win, bg="#111827")
        opts.pack(fill="x", pady=(6, 4), padx=12)

        sande_var = tk.BooleanVar(value=bool(self.sande))
        osdi_var = tk.BooleanVar(value=bool(self.osdi6))

        def on_sande():
            self.sande = bool(sande_var.get())
            self._save_config()

        def on_osdi():
            self.osdi6 = bool(osdi_var.get())
            self._save_config()

        cb1 = tk.Checkbutton(opts, text="SANDE", variable=sande_var, command=on_sande, bg="#111827", fg="#e5e7eb", selectcolor="#111827")
        cb1.pack(side="left", padx=(6, 12))
        cb2 = tk.Checkbutton(opts, text="OSDI-6", variable=osdi_var, command=on_osdi, bg="#111827", fg="#e5e7eb", selectcolor="#111827")
        cb2.pack(side="left", padx=(6, 12))

        # Save directory section
        save_frame = tk.Frame(win, bg="#111827")
        save_frame.pack(fill="x", pady=(8, 4), padx=12)
        
        save_lbl = tk.Label(save_frame, text="Save directory:", bg="#111827", fg="#e5e7eb", font=label_font, width=14, anchor="w")
        save_lbl.pack(side="left")
        
        def choose_save_dir():
            selected = filedialog.askdirectory(title="Select save directory", initialdir=ROOT_DIR)
            if selected:
                self.save_dir = selected
                display = selected if len(selected) <= 50 else f"...{selected[-47:]}"
                save_dir_var.set(display)
                self._save_config()
        
        save_btn = tk.Button(save_frame, text="Choose directory...", command=choose_save_dir, bg="#374151", fg="#fff", relief="flat", padx=8)
        save_btn.pack(side="left", padx=(6, 8))
        
        save_dir_var = tk.StringVar()
        if self.save_dir:
            display = self.save_dir if len(self.save_dir) <= 50 else f"...{self.save_dir[-47:]}"
            save_dir_var.set(display)
        else:
            save_dir_var.set("(not set)")
        
        save_dir_label = tk.Label(save_frame, textvariable=save_dir_var, bg="#111827", fg="#9ca3af", font=label_font, anchor="w", justify="left")
        save_dir_label.pack(side="left", fill="x", expand=True)
        
        # Tooltip for save directory
        save_tooltip = {'win': None}
        
        def show_save_tooltip(event):
            try:
                if not self.save_dir:
                    return
                t = tk.Toplevel(self)
                t.wm_overrideredirect(True)
                lbl = tk.Label(t, text=self.save_dir, bg="#111827", fg="#e5e7eb", bd=1, relief="solid", font=("Segoe UI", 9))
                lbl.pack(ipadx=6, ipady=4)
                x = event.x_root + 16
                y = event.y_root + 10
                t.wm_geometry(f"+{x}+{y}")
                save_tooltip['win'] = t
            except Exception:
                pass
        
        def hide_save_tooltip(event):
            try:
                if save_tooltip['win'] is not None:
                    save_tooltip['win'].destroy()
                    save_tooltip['win'] = None
            except Exception:
                pass
        
        save_dir_label.bind("<Enter>", show_save_tooltip)
        save_dir_label.bind("<Leave>", hide_save_tooltip)

        # Done button
        done_frame = tk.Frame(win, bg="#111827")
        done_frame.pack(fill="x", pady=(8, 10))
        done_btn = tk.Button(done_frame, text="Done", command=win.destroy, bg="#10b981", fg="#03241b", padx=12, pady=6, relief="flat")
        done_btn.pack(side="right", padx=12)


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
