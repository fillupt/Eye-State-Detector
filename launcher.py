import glob
import json
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, font, messagebox


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

# Task order permutations (6 possible orders for 3 tasks)
# Order number is determined by (file_count % 6)
TASK_ORDERS = {
    0: ["Reading", "Video", "Interactive"],
    1: ["Reading", "Interactive", "Video"],
    2: ["Video", "Reading", "Interactive"],
    3: ["Video", "Interactive", "Reading"],
    4: ["Interactive", "Reading", "Video"],
    5: ["Interactive", "Video", "Reading"],
}


def get_order_code(task_list):
    """Convert task list to letter code (e.g., ['Reading', 'Video', 'Interactive'] -> 'RVI')"""
    return ''.join(task[0] for task in task_list)


def find_python_executable():
    # Prefer the current Python interpreter (so a venv works if launcher is run from it)
    return sys.executable


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Blink or they're gone!")
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

        # Preview button (toggle eye tracker with window for verification)
        self.preview_btn = tk.Button(btn_frame, text="Preview", command=self.toggle_preview, bg="#3b82f6", fg="#fff", padx=12, pady=8, relief="flat", font=label_font)
        self.preview_btn.pack(side="left", padx=4)

        # Start button (run full experiment with sequential tasks) - disabled until preview is verified
        self.start_btn = tk.Button(btn_frame, text="Start", command=self.start_experiment, bg="#6b7280", fg="#d1d5db", padx=12, pady=8, relief="flat", font=label_font, state="disabled")
        self.start_btn.pack(side="left", padx=4)

        # Setup button (opens settings window)
        setup_btn = tk.Button(btn_frame, text="Setup", command=self.open_setup_window, bg="#8b5cf6", fg="#fff", padx=10, pady=8, relief="flat", font=label_font)
        setup_btn.pack(side="left", padx=4)

        # Ensure task/file attributes exist
        self.task_reading = "https://read.gov/aesop/002.html"  # Default to Aesop's Fables
        self.task_video = ""
        self.task_interactive = ""
        self.sande = False
        self.osdi6 = False
        self.last_name = ""
        self.save_dir = ""
        self.duration_minutes = 5  # Default 5 minutes
        self._needs_config_save = False  # Flag for deferred config save
        self._preview_verified = False  # Track if preview has been successfully run

        # Load saved config (if any)
        self._load_config()
        
        # Set default trivia file if not already set
        if not self.task_interactive:
            default_trivia = os.path.join(ROOT_DIR, "trivia_general_knowledge.json")
            if os.path.exists(default_trivia):
                self.task_interactive = default_trivia
                self._needs_config_save = True
        
        # Save config if files were cleared or defaults were set
        if self._needs_config_save:
            self._save_config()
            self._needs_config_save = False
        
        # Calculate task order based on existing files
        self.task_order_num = self._calculate_task_order()
        self.task_order = TASK_ORDERS[self.task_order_num]
        self.task_order_code = get_order_code(self.task_order)
        
        # Display task order code on home screen (blinded - only show letter code)
        order_label = tk.Label(self, text=f"Task Order: {self.task_order_code}", 
                               bg="#1f2937", fg="#fbbf24", font=label_font)
        order_label.pack(pady=(8, 0))

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
    
    def _send_tracker_command(self, command):
        """Send a command to the eye tracker via command file."""
        command_path = os.path.join(ROOT_DIR, "tracker.cmd")
        try:
            with open(command_path, "w") as f:
                f.write(command)
            print(f"[DEBUG] Sent command: {command}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Failed to send command: {e}", file=sys.stderr)
    
    def _generate_csv_filename(self, task_suffix):
        """Generate CSV filename: YYYYMMDDTHHMM-{participant}-{order}-{task}.csv"""
        from datetime import datetime
        timestamp_str = datetime.now().strftime("%Y%m%dT%H%M")
        name = self.name_var.get().strip()
        name_suffix = f"-{name}" if name else ""
        order_suffix = f"-{self.task_order_code}"
        return f"{timestamp_str}{name_suffix}{order_suffix}-{task_suffix}.csv"
    
    def _calculate_task_order(self):
        """Count existing CSV files in save directory and return order number (0-5)."""
        if not self.save_dir or not os.path.isdir(self.save_dir):
            return 0
        
        # Count CSV files matching the pattern YYYYMMDDTHHMM-*.csv
        csv_files = glob.glob(os.path.join(self.save_dir, "*-*.csv"))
        file_count = len(csv_files)
        
        print(f"[DEBUG] Found {file_count} existing CSV files, order = {file_count % 6}", file=sys.stderr)
        return file_count % 6

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
        # Pass task order code (e.g., "RVI")
        cmd += ["--order", self.task_order_code]

        try:
            self.process = subprocess.Popen(cmd, cwd=ROOT_DIR)
            self.status_label.config(text=f"Status: Prewarming (PID {self.process.pid})", fg="#fef3c7")
            # Update UI to show initializing state
            self.preview_btn.config(text="Initializing...", state="disabled", bg="#f59e0b", fg="#2b0500")
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
        config_modified = False
        try:
            if os.path.exists(cfg):
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sd = data.get("save_dir")
                if sd and os.path.exists(sd):
                    self.save_dir = sd
                    # Don't update UI here - dir_label doesn't exist yet during __init__

                # Load persisted task/file paths and validate they exist
                task_reading = data.get("task_reading", "") or ""
                task_video = data.get("task_video", "") or ""
                task_interactive = data.get("task_interactive", "") or ""
                
                # Validate task files - clear if they don't exist
                if task_reading and not os.path.exists(task_reading):
                    print(f"Warning: Reading task file not found: {task_reading}")
                    task_reading = ""
                    config_modified = True
                
                if task_video and not os.path.exists(task_video):
                    print(f"Warning: Video task file not found: {task_video}")
                    task_video = ""
                    config_modified = True
                
                if task_interactive and not os.path.exists(task_interactive):
                    print(f"Warning: Interactive task file not found: {task_interactive}")
                    task_interactive = ""
                    config_modified = True
                
                self.task_reading = task_reading
                self.task_video = task_video
                self.task_interactive = task_interactive
                
                self.sande = bool(data.get("sande", False))
                self.osdi6 = bool(data.get("osdi6", False))
                self.last_name = data.get("last_name", "") or ""
                # Load duration with proper type conversion
                duration_val = data.get("duration_minutes", 5)
                try:
                    self.duration_minutes = int(duration_val)
                except (ValueError, TypeError):
                    self.duration_minutes = 5
                
                # Save config if any files were cleared
                if config_modified:
                    # Use a flag to save after __init__ completes
                    self._needs_config_save = True
                
                if self.last_name:
                    self.name_var.set(self.last_name)
                
                print(f"[DEBUG] Config loaded - sande={self.sande}, osdi6={self.osdi6}, duration={self.duration_minutes}", file=sys.stderr)
        except Exception as e:
            print(f"[ERROR] Config load failed: {e}", file=sys.stderr)

    def _save_config(self):
        cfg = self._config_path()
        try:
            # Ensure duration_minutes is an integer
            duration = self.duration_minutes
            if not isinstance(duration, int):
                try:
                    duration = int(duration)
                except (ValueError, TypeError):
                    duration = 5
            
            config_data = {
                "save_dir": self.save_dir,
                "task_reading": self.task_reading,
                "task_video": self.task_video,
                "task_interactive": self.task_interactive,
                "sande": bool(self.sande),
                "osdi6": bool(self.osdi6),
                "last_name": self.name_var.get().strip(),
                "duration_minutes": duration,
            }
            
            print(f"[DEBUG] Saving config - sande={config_data['sande']}, osdi6={config_data['osdi6']}, duration={config_data['duration_minutes']}", file=sys.stderr)
            
            with open(cfg, "w", encoding="utf-8") as f:
                json.dump(config_data, f, indent=2)
        except Exception as e:
            # Log the error instead of silently ignoring
            print(f"Error saving config: {e}", file=sys.stderr)
        except Exception:
            # bubble up to caller if needed
            raise

    def stop_tracker(self):
        # Stop the running tracker process
        if self.process is None:
            self.status_label.config(text="Status: Idle", fg="#9ca3af")
            self.preview_btn.config(text="Preview", state="normal", bg="#3b82f6", fg="#fff")
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
        self.preview_btn.config(text="Preview", state="normal", bg="#3b82f6", fg="#fff")

    def _poll_ready(self):
        """Poll for the ready file or process exit to update UI state."""
        ready_path = os.path.join(ROOT_DIR, "tracker.ready")
        # If process exited
        if self.process is None or (self.process.poll() is not None):
            self.status_label.config(text="Status: Stopped", fg="#fca5a5")
            self.preview_btn.config(text="Preview", state="normal", bg="#3b82f6", fg="#fff")
            self.process = None
            return
        # If ready file exists, the tracker is running
        if os.path.exists(ready_path):
            # Add a small delay to ensure window is actually visible
            # Check if this is the first time we're detecting ready state
            if not hasattr(self, '_ready_confirmed') or not self._ready_confirmed:
                self._ready_confirmed = True
                self._ready_timestamp = self.after(1500, self._confirm_running)
            # Continue polling to detect when process exits
            self.after(500, self._poll_ready)
        else:
            # Still initializing, keep polling
            self.after(500, self._poll_ready)
    
    def _confirm_running(self):
        """Confirm tracker is running after delay to ensure window is visible."""
        if self.process and self.process.poll() is None:
            self.status_label.config(text=f"Status: Running (PID {self.process.pid})", fg="#86efac")
            self.preview_btn.config(text="Stop", state="normal", bg="#ef4444", fg="#fff")
            # Enable Start button now that preview has been verified
            self._preview_verified = True
            self.start_btn.config(state="normal", bg="#10b981", fg="#03241b")

    def toggle_preview(self):
        """Toggle preview mode - eye tracker with window for verification."""
        if self.process is None or (self.process.poll() is not None):
            # Reset ready confirmation state
            self._ready_confirmed = False
            # Save last name when starting
            try:
                self.last_name = self.name_var.get().strip()
                self._save_config()
            except Exception:
                pass
            self.start_tracker()
        else:
            # currently running -> stop
            self.preview_btn.config(text="Stopping...", state="disabled", bg="#ef4444", fg="#fff")
            self.stop_tracker()
    
    def start_experiment(self):
        """Start the full experiment with sequential tasks."""
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Name Required", "Please enter a participant name before starting.")
            return
        
        # Verify at least one task is configured
        if not any([self.task_reading, self.task_video, self.task_interactive]):
            messagebox.showwarning("No Tasks", "Please configure at least one task in Setup before starting.")
            return
        
        # Save last name
        try:
            self.last_name = name
            self._save_config()
        except Exception:
            pass
        
        # Disable buttons during experiment
        self.start_btn.config(state="disabled")
        self.preview_btn.config(state="disabled")
        
        # Start the experiment sequence
        self._run_experiment_sequence()
    
    def _run_experiment_sequence(self):
        """Run the experiment tasks in sequence."""
        try:
            name = self.name_var.get().strip()
            duration_seconds = self.duration_minutes * 60
            
            # Ensure eye tracker is running (start in headless mode if not already running)
            self.status_label.config(text="Status: Starting eye tracker...", fg="#fbbf24")
            self.update()
            
            if self.process is None or self.process.poll() is not None:
                # Start tracker in headless mode
                python_exe = find_python_executable()
                cmd = [python_exe, os.path.join(ROOT_DIR, "Eye_State_Detector.py"), "--headless"]
                if name:
                    cmd += ["--name", name]
                if self.save_dir:
                    cmd += ["--outdir", self.save_dir]
                cmd += ["--order", self.task_order_code]
                
                try:
                    self.process = subprocess.Popen(cmd, cwd=ROOT_DIR)
                    print(f"[DEBUG] Started headless tracker (PID {self.process.pid})", file=sys.stderr)
                    # Wait a moment for tracker to initialize
                    time.sleep(2)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to start tracker: {e}")
                    return
            else:
                # Tracker already running (from preview) - close window if open
                self._send_tracker_command("CLOSE_WINDOW")
                time.sleep(0.5)
            
            # Run each task in order
            for i, task_name in enumerate(self.task_order, 1):
                self.status_label.config(text=f"Status: Task {i}/3 - {task_name}", fg="#86efac")
                self.update()
                
                if task_name == "Reading":
                    self._run_reading_task(name, duration_seconds)
                elif task_name == "Video":
                    self._run_video_task(name, duration_seconds)
                elif task_name == "Interactive":
                    self._run_interactive_task(name, duration_seconds)
            
            # Stop eye tracker
            self._send_tracker_command("SHUTDOWN")
            if self.process:
                self.process.wait(timeout=3)
                self.process = None
            
            self.status_label.config(text="Status: Experiment Complete!", fg="#86efac")
            messagebox.showinfo("Complete", "Experiment completed successfully!")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error during experiment:\n{e}")
            self.status_label.config(text="Status: Error", fg="#fca5a5")
        finally:
            # Re-enable buttons
            self.start_btn.config(state="normal")
            self.preview_btn.config(state="normal")
    
    def _run_questionnaires(self):
        """
        DEPRECATED: Questionnaires are now part of InteractiveTaskWindow.
        This method is kept for backwards compatibility.
        """
        from questionnaires import QuestionnaireWindow
        
        win = QuestionnaireWindow(
            self,
            participant_name=self.name_var.get().strip(),
            order_code=self.task_order_code,
            save_dir=self.save_dir or ROOT_DIR
        )
        self.wait_window(win)
    
    def _run_reading_task(self, name, duration_seconds):
        """Run the reading task."""
        if not self.task_reading:
            return
        
        from reading_window import show_reading_window
        
        # Generate filename for this task
        csv_filename = self._generate_csv_filename("R")
        
        def on_ready():
            """Called when reading window is loaded and ready"""
            print(f"[DEBUG] Reading task ready - starting recording to {csv_filename}", file=sys.stderr)
            self._send_tracker_command(f"START_RECORDING {csv_filename}")
        
        try:
            # Launch reading window - this will block until window closes
            show_reading_window(
                self.task_reading,
                on_ready_callback=on_ready,
                duration_seconds=duration_seconds
            )
        except Exception as e:
            messagebox.showerror("Reading Task", f"Failed to launch reading window: {e}")
        finally:
            # Stop recording
            self._send_tracker_command("STOP_RECORDING")
            print(f"[DEBUG] Reading task completed - stopped recording", file=sys.stderr)
    
    def _run_video_task(self, name, duration_seconds):
        """Run the video task."""
        if not self.task_video:
            return
        
        from video_player import VideoPlayerWindow
        
        # Generate filename for this task
        csv_filename = self._generate_csv_filename("V")
        
        def on_ready():
            """Called when video is loaded and ready"""
            print(f"[DEBUG] Video task ready - starting recording to {csv_filename}", file=sys.stderr)
            self._send_tracker_command(f"START_RECORDING {csv_filename}")
        
        player = VideoPlayerWindow(
            self,
            video_file=self.task_video,
            participant_name=name,
            order_code=self.task_order_code,
            duration_seconds=duration_seconds,
            save_dir=self.save_dir or ROOT_DIR,
            on_ready_callback=on_ready
        )
        self.wait_window(player)
        
        # Stop recording
        self._send_tracker_command("STOP_RECORDING")
        print(f"[DEBUG] Video task completed - stopped recording", file=sys.stderr)
    
    def _run_interactive_task(self, name, duration_seconds):
        """Run the unified interactive task (SANDE + OSDI + Trivia MCQs)."""
        if not self.task_interactive:
            return
        
        from questionnaires import InteractiveTaskWindow
        
        # Generate filename for this task
        csv_filename = self._generate_csv_filename("I")
        
        def on_ready():
            """Called when interactive window is fully loaded"""
            print(f"[DEBUG] Interactive task ready - starting recording to {csv_filename}", file=sys.stderr)
            self._send_tracker_command(f"START_RECORDING {csv_filename}")
        
        interactive = InteractiveTaskWindow(
            self,
            trivia_file=self.task_interactive,
            duration_seconds=duration_seconds,
            participant_name=name,
            order_code=self.task_order_code,
            save_dir=self.save_dir or ROOT_DIR,
            on_ready_callback=on_ready,
            enable_sande=True,  # TODO: Make configurable in settings
            enable_osdi=True    # TODO: Make configurable in settings
        )
        self.wait_window(interactive)
        
        # Stop recording
        self._send_tracker_command("STOP_RECORDING")
        print(f"[DEBUG] Interactive task completed - stopped recording", file=sys.stderr)


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
        win.geometry("560x370")
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
        def add_task_row(parent, title, getter, filetypes=None, is_interactive=False):
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
            
            # If this is the interactive task, add SANDE/OSDI checkboxes below
            if is_interactive:
                opts_frame = tk.Frame(parent, bg="#111827")
                opts_frame.pack(fill="x", pady=(2, 4), padx=12)
                
                # Indent to align with the file picker content
                indent = tk.Label(opts_frame, text="", bg="#111827", width=14)
                indent.pack(side="left")
                
                opts_label = tk.Label(opts_frame, text="Questionnaires:", bg="#111827", fg="#9ca3af", font=label_font)
                opts_label.pack(side="left", padx=(6, 12))
                
                sande_var = tk.BooleanVar(value=bool(self.sande))
                osdi_var = tk.BooleanVar(value=bool(self.osdi6))

                def on_sande():
                    self.sande = bool(sande_var.get())
                    self._save_config()

                def on_osdi():
                    self.osdi6 = bool(osdi_var.get())
                    self._save_config()

                cb1 = tk.Checkbutton(opts_frame, text="SANDE", variable=sande_var, command=on_sande, bg="#111827", fg="#e5e7eb", selectcolor="#111827")
                cb1.pack(side="left", padx=(0, 12))
                cb2 = tk.Checkbutton(opts_frame, text="OSDI-6", variable=osdi_var, command=on_osdi, bg="#111827", fg="#e5e7eb", selectcolor="#111827")
                cb2.pack(side="left", padx=(0, 12))

            return fname_var

        # Setters/getters that update state and persist
        def set_reading(path=None, get=False):
            if get:
                return self.task_reading
            # If path looks like a URL, treat as URL
            if path and (path.startswith("http://") or path.startswith("https://")):
                self.task_reading = path
            else:
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

        # Create task mapping for reordering based on task_order
        task_map = {
            "Reading": ("Reading task (URL or file)", set_reading, [
                ("Webpage URL", "*.url"),
                ("Text files", "*.txt *.pdf"),
                ("All files", "*.*")
            ]),
            "Video": ("Video task", set_video, [
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.mpeg *.mpg"),
                ("All files", "*.*")
            ]),
            "Interactive": ("Interactive task", set_interactive, [
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ]),
        }
        
        # Add label showing task order code (blinded)
        order_frame = tk.Frame(win, bg="#111827")
        order_frame.pack(fill="x", pady=(8, 4), padx=12)
        order_info = tk.Label(order_frame, 
                             text=f"Task Order: {self.task_order_code}", 
                             bg="#111827", fg="#fbbf24", font=label_font, anchor="w")
        order_info.pack(side="left")
        
        print(f"[DEBUG] Setup window opening - sande={self.sande}, osdi6={self.osdi6}, duration={self.duration_minutes}", file=sys.stderr)
        
        # Add task rows in the correct order
        for task_name in self.task_order:
            title, getter, filetypes = task_map[task_name]
            # Mark Interactive task to include questionnaire checkboxes
            is_interactive = (task_name == "Interactive")
            add_task_row(win, title, getter, filetypes=filetypes, is_interactive=is_interactive)

        # Duration slider
        duration_frame = tk.Frame(win, bg="#111827")
        duration_frame.pack(fill="x", pady=(8, 4), padx=12)
        
        dur_lbl = tk.Label(duration_frame, text="Duration:", bg="#111827", fg="#e5e7eb", font=label_font, width=14, anchor="w")
        dur_lbl.pack(side="left")
        
        # Create the value label first so it can be referenced in the callback
        duration_value_lbl = tk.Label(duration_frame, text=f"{self.duration_minutes} min", bg="#111827", fg="#9ca3af", font=label_font, width=8, anchor="w")
        duration_value_lbl.pack(side="right", padx=(6, 0))
        
        duration_var = tk.IntVar(value=self.duration_minutes)
        
        def on_duration_change(val):
            minutes = int(float(val))
            duration_value_lbl.config(text=f"{minutes} min")
            self.duration_minutes = minutes
            self._save_config()
        
        duration_slider = tk.Scale(
            duration_frame,
            from_=1,
            to=15,
            orient="horizontal",
            variable=duration_var,
            command=on_duration_change,
            bg="#374151",
            fg="#e5e7eb",
            highlightthickness=0,
            troughcolor="#1f2937",
            activebackground="#4b5563",
            showvalue=False,
            length=200
        )
        duration_slider.pack(side="left", padx=(6, 8), fill="x", expand=True)

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
        def on_done():
            # Ensure all settings are saved before closing
            self._save_config()
            win.destroy()
        
        done_frame = tk.Frame(win, bg="#111827")
        done_frame.pack(fill="x", pady=(8, 10))
        done_btn = tk.Button(done_frame, text="Done", command=on_done, bg="#10b981", fg="#03241b", padx=12, pady=6, relief="flat")
        done_btn.pack(side="right", padx=12)


if __name__ == "__main__":
    app = Launcher()
    app.mainloop()
