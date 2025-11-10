"""
Video Player Window for Video Task

Displays a video file with audio playback using VLC for the participant to watch.
"""

import os
import platform
import tkinter as tk
from tkinter import font, messagebox
import time
import vlc


class VideoPlayerWindow(tk.Toplevel):
    """
    Video player window that displays a video file with audio using VLC.
    
    Args:
        parent: Parent tkinter window
        video_file: Path to the video file to play
        participant_name: Name of the participant
        order_code: Task order code (e.g., "RVI")
        duration_seconds: Maximum duration to play video (0 = play full video)
        save_dir: Directory to save results
        on_ready_callback: Function to call when video is loaded and ready
    """
    
    def __init__(self, parent, video_file="", participant_name="", order_code="", 
                 duration_seconds=0, save_dir="", on_ready_callback=None):
        super().__init__(parent)
        
        self.video_file = video_file
        self.participant_name = participant_name
        self.order_code = order_code
        self.duration_seconds = duration_seconds
        self.save_dir = save_dir
        self.on_ready_callback = on_ready_callback
        
        self.title("Video Task")
        self.configure(bg="#000000")
        
        # Video state
        self.is_playing = False
        self.is_paused = False
        self.start_time = None
        self.timer_check_id = None
        
        # Fonts
        self.label_font = font.Font(family="Segoe UI", size=11)
        
        # Size and position - use 1400x800 for consistency
        self.geometry("1400x800")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1400) // 2
        y = (screen_h - 800) // 2
        self.geometry(f"1400x800+{x}+{y}")
        
        # Main container
        main_frame = tk.Frame(self, bg="#000000")
        main_frame.pack(expand=True, fill="both")
        
        # Video display frame
        self.video_frame = tk.Frame(main_frame, bg="#000000")
        self.video_frame.pack(expand=True, fill="both", padx=20, pady=20)
        
        # Control frame at bottom
        control_frame = tk.Frame(self, bg="#1f2937")
        control_frame.pack(fill="x", side="bottom")
        
        # Progress label
        self.progress_label = tk.Label(
            control_frame,
            text="Loading video...",
            bg="#1f2937",
            fg="#e5e7eb",
            font=self.label_font
        )
        self.progress_label.pack(pady=10)
        
        # Control buttons
        btn_frame = tk.Frame(control_frame, bg="#1f2937")
        btn_frame.pack(pady=(0, 10))
        
        self.play_pause_btn = tk.Button(
            btn_frame,
            text="Play",
            command=self.toggle_play_pause,
            bg="#10b981",
            fg="#03241b",
            font=self.label_font,
            padx=20,
            pady=6,
            relief="flat"
        )
        self.play_pause_btn.pack(side="left", padx=5)
        
        self.stop_btn = tk.Button(
            btn_frame,
            text="Stop",
            command=self.stop_video,
            bg="#ef4444",
            fg="#ffffff",
            font=self.label_font,
            padx=20,
            pady=6,
            relief="flat"
        )
        self.stop_btn.pack(side="left", padx=5)
        
        # Initialize VLC
        self.instance = None
        self.player = None
        
        # Load video
        self.load_video()
        
        # Autoplay if video file is provided
        if self.video_file and os.path.exists(self.video_file):
            # Start playing after a short delay to ensure window is ready
            self.after(500, self.toggle_play_pause)
        
        # Prevent closing during playback
        self.protocol("WM_DELETE_WINDOW", self.on_close_attempt)
    
    def load_video(self):
        """Load the video file"""
        if not self.video_file or not os.path.exists(self.video_file):
            messagebox.showerror(
                "Error",
                f"Video file not found: {self.video_file}",
                parent=self
            )
            return
        
        try:
            # Create VLC instance and player
            self.instance = vlc.Instance('--no-xlib')  # '--no-xlib' for Linux compatibility
            self.player = self.instance.media_player_new()
            
            # Set the window handle for video output
            if platform.system() == 'Windows':
                self.player.set_hwnd(self.video_frame.winfo_id())
            elif platform.system() == 'Darwin':  # macOS
                self.player.set_nsobject(self.video_frame.winfo_id())
            else:  # Linux
                self.player.set_xwindow(self.video_frame.winfo_id())
            
            # Load media
            media = self.instance.media_new(self.video_file)
            self.player.set_media(media)
            
            # Parse media to get duration
            media.parse()
            duration_ms = media.get_duration()
            duration_sec = duration_ms / 1000 if duration_ms > 0 else 0
            
            self.progress_label.config(
                text=f"Ready to play: {os.path.basename(self.video_file)} "
                     f"({int(duration_sec)}s) [Audio enabled]"
            )
            
            print(f"Video loaded: {self.video_file}")
            print(f"  Duration: {duration_sec:.1f}s")
            
            # Signal ready callback
            if self.on_ready_callback:
                self.after(100, self.on_ready_callback)
            
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to load video:\n{e}",
                parent=self
            )
            print(f"Error loading video: {e}")
    
    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if not self.player:
            return
        
        if self.is_playing:
            # Pause
            self.player.pause()
            self.is_playing = False
            self.is_paused = True
            self.play_pause_btn.config(text="Resume", bg="#fbbf24")
            
            # Cancel timer check
            if self.timer_check_id:
                self.after_cancel(self.timer_check_id)
                self.timer_check_id = None
        else:
            # Play/Resume
            if self.start_time is None:
                self.start_time = time.time()
            
            self.player.play()
            self.is_playing = True
            self.is_paused = False
            self.play_pause_btn.config(text="Pause", bg="#ef4444")
            
            # Start checking timer and progress
            self.check_progress()
    
    def check_progress(self):
        """Check playback progress and update UI"""
        if not self.is_playing or not self.player:
            return
        
        # Get current time and length
        current_time = self.player.get_time() / 1000  # Convert ms to seconds
        length = self.player.get_length() / 1000  # Convert ms to seconds
        
        if length > 0:
            progress = (current_time / length) * 100
            progress_text = f"Playing: {int(progress)}% ({int(current_time)}/{int(length)}s)"
        else:
            progress_text = "Playing..."
        
        # Check duration limit
        if self.duration_seconds > 0 and self.start_time:
            elapsed = time.time() - self.start_time
            if elapsed >= self.duration_seconds:
                self.stop_video()
                return
            
            remaining = max(0, self.duration_seconds - elapsed)
            progress_text += f" | Time remaining: {int(remaining)}s"
        
        self.progress_label.config(text=progress_text)
        
        # Check if video ended
        state = self.player.get_state()
        if state == vlc.State.Ended:
            self.stop_video()
            return
        
        # Schedule next check
        self.timer_check_id = self.after(100, self.check_progress)
    
    def stop_video(self):
        """Stop video playback"""
        if not self.player:
            return
        
        self.is_playing = False
        self.is_paused = False
        self.player.stop()
        self.play_pause_btn.config(text="Play", bg="#10b981")
        
        # Cancel timer check
        if self.timer_check_id:
            self.after_cancel(self.timer_check_id)
            self.timer_check_id = None
        
        elapsed = time.time() - self.start_time if self.start_time else 0
        self.progress_label.config(
            text=f"Video stopped. Total time watched: {elapsed:.1f}s"
        )
        
        # Allow closing
        self.destroy()
    
    def on_close_attempt(self):
        """Handle window close attempt"""
        if self.is_playing:
            response = messagebox.askyesno(
                "Stop Video?",
                "The video is still playing. Are you sure you want to stop?",
                parent=self
            )
            if response:
                self.stop_video()
        else:
            self.destroy()
    
    def __del__(self):
        """Cleanup when window is destroyed"""
        if self.player:
            self.player.stop()
            self.player.release()
        if self.instance:
            self.instance.release()


# Test function
def test_video_player():
    """Test the video player window"""
    root = tk.Tk()
    root.withdraw()
    
    # Try to load video file from config, otherwise use file picker
    video_file = ""
    
    # Check if there's a config file with a video path
    import json
    config_path = "launcher_config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                video_file = config.get('video_file', '')
        except:
            pass
    
    # If no video in config, ask user to select one
    if not video_file or not os.path.exists(video_file):
        from tkinter import filedialog
        video_file = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm *.m4v *.mpeg *.mpg"),
                ("All files", "*.*")
            ]
        )
    
    if video_file:
        player = VideoPlayerWindow(
            root,
            video_file=video_file,
            participant_name="TestUser",
            order_code="RVI",
            duration_seconds=0,  # 0 = play full video
            save_dir=""
        )
        root.wait_window(player)
    
    root.destroy()


if __name__ == "__main__":
    test_video_player()
