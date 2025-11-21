"""
Dry Eye Questionnaire Module
Implements SANDE and OSDI-6 questionnaires for interactive task
Also includes trivia MCQ presentation
"""

import json
import os
import random
import time
import tkinter as tk
from tkinter import font, messagebox
from datetime import datetime


class QuestionnaireWindow(tk.Toplevel):
    """
    Unified window for SANDE and OSDI-6 questionnaires.
    Transitions between questionnaires without closing the window.
    """
    
    def __init__(self, parent, participant_name="", order_code="", save_dir=""):
        super().__init__(parent)
        
        self.participant_name = participant_name
        self.order_code = order_code
        self.save_dir = save_dir
        self.completed = False
        self.current_questionnaire = "SANDE"  # Start with SANDE
        
        # Storage for responses
        self.sande_responses = {}
        self.osdi_responses = {}
        self.osdi_buttons = {}  # Store button references for styling
        
        self.title("Dry Eye Questionnaire")
        self.configure(bg="#1f2937")
        
        # Fonts
        self.title_font = font.Font(family="Segoe UI", size=14, weight="bold")
        self.label_font = font.Font(family="Segoe UI", size=11)
        self.small_font = font.Font(family="Segoe UI", size=9)
        
        # Size and center window - consistent 1400x800
        self.geometry("1400x800")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1400) // 2
        y = (screen_h - 800) // 2
        self.geometry(f"1400x800+{x}+{y}")
        
        # Container for content that will be swapped
        self.content_container = tk.Frame(self, bg="#1f2937")
        self.content_container.pack(expand=True, fill="both")
        
        # Build initial UI (SANDE)
        self._show_sande()
        
        # Prevent closing without completing
        self.protocol("WM_DELETE_WINDOW", self.on_close_attempt)
    
    def _clear_content(self):
        """Clear the current content"""
        for widget in self.content_container.winfo_children():
            widget.destroy()
    
    def _show_sande(self):
        """Show SANDE questionnaire"""
        self.current_questionnaire = "SANDE"
        self.title("SANDE Dry Eye Questionnaire")
        self._clear_content()
        
        # Container frame to center all content
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        # Content frame (centered within container)
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Header
        header = tk.Label(
            content,
            text="SANDE Dry Eye Questionnaire",
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font
        )
        header.pack(pady=(20, 10))
        
        # Instructions
        instructions = tk.Label(
            content,
            text="Please rate your dry eye symptoms by clicking on the scales below.",
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.label_font
        )
        instructions.pack(pady=(0, 30))
        
        # Question 1: Frequency
        self._add_sande_question(
            content,
            question_num=1,
            question_text="How OFTEN have your eyes felt dry, uncomfortable or irritated?",
            left_label="Rarely",
            right_label="All the time",
            var_name="frequency"
        )
        
        # Question 2: Severity
        self._add_sande_question(
            content,
            question_num=2,
            question_text="How SEVERE is the discomfort, dryness or irritation of your eyes?",
            left_label="Very Mild",
            right_label="Very Severe",
            var_name="severity"
        )
        
        # Submit button
        btn_frame = tk.Frame(content, bg="#1f2937")
        btn_frame.pack(pady=(30, 20))
        
        submit_btn = tk.Button(
            btn_frame,
            text="Next →",
            command=self._sande_next,
            bg="#10b981",
            fg="#03241b",
            font=self.label_font,
            padx=40,
            pady=8,
            relief="flat"
        )
        submit_btn.pack()
    
    def _add_sande_question(self, parent, question_num, question_text, left_label, right_label, var_name):
        """Add a SANDE question with a visual analog scale"""
        
        # Question frame
        q_frame = tk.Frame(parent, bg="#1f2937")
        q_frame.pack(fill="x", pady=(0, 35), padx=40)
        
        # Question text
        q_label = tk.Label(
            q_frame,
            text=f"{question_num}. {question_text}",
            bg="#1f2937",
            fg="#e5e7eb",
            font=self.label_font,
            wraplength=1000,
            justify="left"
        )
        q_label.pack(anchor="w", pady=(0, 15))
        
        # Slider variable (0-100 scale)
        if var_name not in self.sande_responses:
            var = tk.DoubleVar(value=50)  # Start at midpoint
            self.sande_responses[var_name] = var
        else:
            var = self.sande_responses[var_name]
        
        # Labels on same line as slider
        slider_container = tk.Frame(q_frame, bg="#1f2937")
        slider_container.pack(fill="x", pady=(0, 5))
        
        # Left label
        left_lbl = tk.Label(
            slider_container,
            text=left_label,
            bg="#1f2937",
            fg="#9ca3af",
            font=self.small_font,
            width=12,
            anchor="e"
        )
        left_lbl.pack(side="left", padx=(0, 15))
        
        # Slider frame (to contain the slider properly)
        slider_frame = tk.Frame(slider_container, bg="#1f2937")
        slider_frame.pack(side="left", fill="x", expand=True)
        
        # Create the slider
        slider = tk.Scale(
            slider_frame,
            from_=0,
            to=100,
            orient="horizontal",
            variable=var,
            showvalue=False,
            bg="#374151",
            fg="#e5e7eb",
            troughcolor="#1f2937",
            highlightthickness=0,
            sliderlength=20,
            width=15
        )
        slider.pack(fill="x", expand=True)
        
        # Make slider jump to click position instead of moving incrementally
        def on_slider_click(event):
            # Calculate position as percentage of slider width
            slider_width = slider.winfo_width()
            click_pos = event.x
            # Clamp to valid range
            if click_pos < 0:
                click_pos = 0
            elif click_pos > slider_width:
                click_pos = slider_width
            # Convert to value (0-100)
            value = (click_pos / slider_width) * 100
            var.set(value)
        
        slider.bind("<Button-1>", on_slider_click)
        
        # Right label
        right_lbl = tk.Label(
            slider_container,
            text=right_label,
            bg="#1f2937",
            fg="#9ca3af",
            font=self.small_font,
            width=12,
            anchor="w"
        )
        right_lbl.pack(side="left", padx=(15, 0))
        
        # Value display below slider
        value_label = tk.Label(
            q_frame,
            text=f"{int(var.get())}",
            bg="#1f2937",
            fg="#fbbf24",
            font=self.small_font
        )
        value_label.pack(anchor="center", pady=(5, 0))
        
        # Update value display when slider moves
        def update_value(*args):
            value_label.config(text=f"{int(var.get())}")
        
        var.trace("w", update_value)
        update_value()
    
    def _sande_next(self):
        """Move from SANDE to OSDI"""
        self._show_osdi()
    
    def _show_osdi(self):
        """Show OSDI-6 questionnaire"""
        self.current_questionnaire = "OSDI"
        self.title("OSDI-6 Dry Eye Questionnaire")
        self._clear_content()
        
        # Container frame to center all content
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        # Content frame (centered within container)
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Header
        header = tk.Label(
            content,
            text="OSDI-6 Dry Eye Questionnaire",
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font
        )
        header.pack(pady=(20, 10))
        
        # Instructions
        instructions = tk.Label(
            content,
            text="Please answer the following questions about your eyes.",
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.label_font
        )
        instructions.pack(pady=(0, 20))
        
        # OSDI-6 Questions with proper groupings and headers
        # Symptoms and visual disturbance subscale
        self._add_osdi_section_header(
            content,
            "Have you experienced any of the following during a typical day within the last month?"
        )
        
        self._add_osdi_question(
            content,
            question_num=1,
            question_text="Eyes that are sensitive to light?",
            var_name="q1"
        )
        
        self._add_osdi_question(
            content,
            question_num=2,
            question_text="Vision blurring between blinks (with your refractive correction if needed)?",
            var_name="q2"
        )
        
        # Visual function / tasks subscale
        self._add_osdi_section_header(
            content,
            "Have problems with your eyes limited you in performing any of the following during a typical day within the last month?"
        )
        
        self._add_osdi_question(
            content,
            question_num=3,
            question_text="Driving or being driven at night?",
            var_name="q3"
        )
        
        self._add_osdi_question(
            content,
            question_num=4,
            question_text="Watching TV, or a similar task?",
            var_name="q4"
        )
        
        # Environmental subscale
        self._add_osdi_section_header(
            content,
            "Have your eyes felt uncomfortable in any of the following situations during a typical day within the last month?"
        )
        
        self._add_osdi_question(
            content,
            question_num=5,
            question_text="Windy conditions?",
            var_name="q5"
        )
        
        self._add_osdi_question(
            content,
            question_num=6,
            question_text="Places or areas with low humidity?",
            var_name="q6"
        )
        
        # Button frame with Back and Submit
        btn_frame = tk.Frame(content, bg="#1f2937")
        btn_frame.pack(pady=(20, 20))
        
        back_btn = tk.Button(
            btn_frame,
            text="← Back",
            command=self._osdi_back,
            bg="#6b7280",
            fg="#ffffff",
            font=self.label_font,
            padx=30,
            pady=10,
            relief="flat"
        )
        back_btn.pack(side="left", padx=(0, 10))
        
        submit_btn = tk.Button(
            btn_frame,
            text="Submit",
            command=self._osdi_submit,
            bg="#10b981",
            fg="#03241b",
            font=self.label_font,
            padx=30,
            pady=10,
            relief="flat"
        )
        submit_btn.pack(side="left")
    
    def _add_osdi_section_header(self, parent, header_text):
        """Add a section header for OSDI question groups"""
        header_frame = tk.Frame(parent, bg="#1f2937")
        header_frame.pack(fill="x", pady=(10, 5), padx=20)
        
        header_label = tk.Label(
            header_frame,
            text=header_text,
            bg="#1f2937",
            fg="#fbbf24",
            font=("Segoe UI", 10, "italic"),
            wraplength=1100,
            justify="left"
        )
        header_label.pack(anchor="w")
    
    def _add_osdi_question(self, parent, question_num, question_text, var_name):
        """Add an OSDI multiple choice question with compact horizontal layout"""
        
        # Question frame - horizontal layout
        q_frame = tk.Frame(parent, bg="#1f2937")
        q_frame.pack(fill="x", pady=(0, 12), padx=20)
        
        # Question text on the left with FIXED WIDTH for alignment
        q_label = tk.Label(
            q_frame,
            text=f"{question_num}. {question_text}",
            bg="#1f2937",
            fg="#e5e7eb",
            font=self.label_font,
            wraplength=450,  # Allow text to wrap
            justify="left",
            anchor="w",
            width=50  # Fixed width in characters to ensure alignment
        )
        q_label.pack(side="left", padx=(0, 20))
        
        # Options frame on the right
        options_frame = tk.Frame(q_frame, bg="#1f2937")
        options_frame.pack(side="left", fill="x", expand=False)  # Don't expand to maintain alignment
        
        # Response options - CORRECT ORDER from image headers (left to right)
        # Constantly(4), Mostly(3), Often(2), Sometimes(1), Never(0)
        options = [
            ("Constantly", 4),
            ("Mostly", 3),
            ("Often", 2),
            ("Sometimes", 1),
            ("Never", 0)
        ]
        
        if var_name not in self.osdi_responses:
            var = tk.IntVar(value=-1)  # -1 means not answered
            self.osdi_responses[var_name] = var
        else:
            var = self.osdi_responses[var_name]
        
        # Store buttons for this question for styling updates
        button_key = f"{var_name}_buttons"
        self.osdi_buttons[button_key] = []
        
        # Create button-style radio options for better touch targets
        for text, value in options:
            # Container frame for each option
            option_container = tk.Frame(
                options_frame,
                bg="#374151",
                relief="solid",
                borderwidth=2,
                highlightthickness=0
            )
            option_container.pack(side="left", padx=4, ipadx=12, ipady=8)
            
            # Make selection callback
            def make_osdi_select(v, val, btn_key):
                return lambda event=None: self._select_osdi_option(v, val, btn_key)
            
            option_label = tk.Label(
                option_container,
                text=text,
                bg="#374151",
                fg="#e5e7eb",
                font=self.small_font,
                cursor="hand2",
                padx=8,
                pady=6
            )
            option_label.pack()
            
            # Make entire container clickable
            callback = make_osdi_select(var, value, button_key)
            option_container.bind("<Button-1>", callback)
            option_label.bind("<Button-1>", callback)
            
            # Store for styling updates
            self.osdi_buttons[button_key].append((option_container, option_label, value))
        
        # Apply initial styling if already selected
        if var.get() != -1:
            self._select_osdi_option(var, var.get(), button_key)
    
    def _select_osdi_option(self, var, value, button_key):
        """Handle OSDI option selection with visual feedback"""
        var.set(value)
        
        # Update visual styling for all options in this question
        if button_key in self.osdi_buttons:
            for container, label, option_value in self.osdi_buttons[button_key]:
                if option_value == value:
                    # Selected style - bright highlight
                    container.config(bg="#10b981", borderwidth=3)
                    label.config(bg="#10b981", fg="#03241b", font=("Segoe UI", 9, "bold"))
                else:
                    # Unselected style - default
                    container.config(bg="#374151", borderwidth=2)
                    label.config(bg="#374151", fg="#e5e7eb", font=("Segoe UI", 9))
    
    def _osdi_back(self):
        """Go back to SANDE questionnaire"""
        self._show_sande()
    
    def _osdi_submit(self):
        """Validate and save both questionnaires"""
        
        # Check all OSDI questions answered
        unanswered = []
        for i in range(1, 7):
            if self.osdi_responses[f"q{i}"].get() == -1:
                unanswered.append(i)
        
        if unanswered:
            messagebox.showwarning(
                "Incomplete",
                f"Please answer all questions.\n\nUnanswered: {', '.join(map(str, unanswered))}",
                parent=self
            )
            return
        
        # Save both questionnaires
        self._save_responses()
        
        self.completed = True
        self.destroy()
    
    def _save_responses(self):
        """Save SANDE and OSDI-6 responses to CSV in questionnaires subfolder"""
        
        # Create questionnaires subfolder if it doesn't exist
        if self.save_dir:
            questionnaire_dir = os.path.join(self.save_dir, "questionnaires")
        else:
            questionnaire_dir = os.path.join(os.path.dirname(__file__), "questionnaires")
        
        os.makedirs(questionnaire_dir, exist_ok=True)
        
        # Generate filename
        timestamp_str = datetime.now().strftime("%Y%m%dT%H%M")
        user_suffix = f"-{self.participant_name}" if self.participant_name else ""
        order_suffix = f"-{self.order_code}" if self.order_code else ""
        csv_filename = f"{timestamp_str}{user_suffix}{order_suffix}-questionnaires.csv"
        csv_path = os.path.join(questionnaire_dir, csv_filename)
        
        # Collect response values
        frequency = int(self.sande_responses["frequency"].get())
        severity = int(self.sande_responses["severity"].get())
        
        # Write to CSV
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                # Write headers
                f.write("questionnaire,question,response\n")
                
                # Write SANDE responses
                f.write(f"SANDE,frequency,{frequency}\n")
                f.write(f"SANDE,severity,{severity}\n")
                
                # Write OSDI-6 responses
                for i in range(1, 7):
                    response = self.osdi_responses[f"q{i}"].get()
                    f.write(f"OSDI6,q{i},{response}\n")
            
            print(f"Questionnaire responses saved to: {csv_path}")
        except Exception as e:
            print(f"Failed to save questionnaire responses: {e}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save responses:\n{e}",
                parent=self
            )
    
    def on_close_attempt(self):
        """Handle window close attempt"""
        response = messagebox.askyesno(
            "Exit Without Submitting?",
            "Are you sure you want to exit without submitting?\n\nYour responses will not be saved.",
            parent=self
        )
        
        if response:
            self.completed = False
            self.destroy()


# Legacy class names for backwards compatibility
SANDEQuestionnaire = QuestionnaireWindow
OSDI6Questionnaire = QuestionnaireWindow


class TriviaMCQWindow(tk.Toplevel):
    """
    Trivia Multiple Choice Question window.
    Displays questions one at a time with 5 choices and a countdown timer.
    """
    
    def __init__(self, parent, trivia_file="", duration_seconds=300, participant_name="", order_code="", save_dir=""):
        super().__init__(parent)
        
        self.participant_name = participant_name
        self.order_code = order_code
        self.save_dir = save_dir
        self.duration_seconds = duration_seconds
        self.trivia_file = trivia_file
        
        # Trivia state
        self.questions = []
        self.current_question_index = 0
        self.score = 0
        self.total_shown = 0
        self.start_time = None
        self.responses = []  # Store all responses for later analysis
        
        self.title("Interactive Task - Trivia Questions")
        self.configure(bg="#1f2937")
        
        # Fonts
        self.title_font = font.Font(family="Segoe UI", size=14, weight="bold")
        self.label_font = font.Font(family="Segoe UI", size=11)
        self.small_font = font.Font(family="Segoe UI", size=9)
        self.large_font = font.Font(family="Segoe UI", size=16, weight="bold")
        
        # Size and center window - 1400x800
        self.geometry("1400x800")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1400) // 2
        y = (screen_h - 800) // 2
        self.geometry(f"1400x800+{x}+{y}")
        
        # Load questions
        self._load_questions()
        
        # Main content container
        self.content_container = tk.Frame(self, bg="#1f2937")
        self.content_container.pack(expand=True, fill="both")
        
        # Progress bar at bottom
        self.progress_frame = tk.Frame(self, bg="#374151", height=30)
        self.progress_frame.pack(side="bottom", fill="x")
        self.progress_frame.pack_propagate(False)
        
        self.progress_bar = tk.Frame(self.progress_frame, bg="#10b981")
        self.progress_bar.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Time remaining: 0:00",
            bg="#10b981",
            fg="#ffffff",
            font=self.small_font
        )
        self.progress_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Start timer
        self.start_time = time.time()
        
        # Show first question or completion if no questions
        if self.questions:
            self._show_question()
            self._update_timer()
        else:
            self._show_completion()
        
        # Prevent closing during task
        self.protocol("WM_DELETE_WINDOW", self.on_close_attempt)
    
    def _load_questions(self):
        """Load questions from JSON file and randomize"""
        if not self.trivia_file or not os.path.exists(self.trivia_file):
            messagebox.showerror(
                "Error",
                f"Trivia file not found: {self.trivia_file}",
                parent=self
            )
            return
        
        try:
            with open(self.trivia_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.questions = data.get('questions', [])
                self.trivia_title = data.get('title', 'Trivia Questions')
                
                # Randomize question order
                random.shuffle(self.questions)
                
                print(f"Loaded {len(self.questions)} questions from {self.trivia_file}")
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to load trivia file:\n{e}",
                parent=self
            )
            self.questions = []
    
    def _show_question(self):
        """Display current question"""
        # Clear content
        for widget in self.content_container.winfo_children():
            widget.destroy()
        
        if self.current_question_index >= len(self.questions):
            # No more questions, show completion
            self._show_completion()
            return
        
        question_data = self.questions[self.current_question_index]
        
        # Container for centering
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Header with question number and score
        header_frame = tk.Frame(content, bg="#1f2937")
        header_frame.pack(fill="x", pady=(20, 10))
        
        question_num_label = tk.Label(
            header_frame,
            text=f"Question {self.total_shown + 1}",
            bg="#1f2937",
            fg="#ffffff",
            font=self.label_font
        )
        question_num_label.pack(side="left", padx=(0, 20))
        
        score_label = tk.Label(
            header_frame,
            text=f"Score: {self.score}/{self.total_shown}",
            bg="#1f2937",
            fg="#10b981",
            font=self.label_font
        )
        score_label.pack(side="left")
        
        # Question text
        q_label = tk.Label(
            content,
            text=question_data.get('question', ''),
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font,
            wraplength=1000,
            justify="left"
        )
        q_label.pack(pady=(10, 30), padx=40)
        
        # Shuffle choices to avoid position bias
        original_choices = question_data.get('choices', [])
        original_correct = question_data.get('correct', -1)
        
        # Create list of (index, choice_text) pairs and shuffle
        indexed_choices = list(enumerate(original_choices))
        random.shuffle(indexed_choices)
        
        # Track which shuffled position contains the correct answer
        self.current_correct_index = -1
        for shuffled_idx, (original_idx, choice_text) in enumerate(indexed_choices):
            if original_idx == original_correct:
                self.current_correct_index = shuffled_idx
                break
        
        self.selected_answer = tk.IntVar(value=-1)
        
        choices_frame = tk.Frame(content, bg="#1f2937")
        choices_frame.pack(pady=(0, 30), padx=40, fill="x")
        
        # Store choice buttons for styling updates
        self.choice_buttons = []
        
        # Display shuffled choices as large touch-friendly buttons
        for shuffled_idx, (original_idx, choice_text) in enumerate(indexed_choices):
            # Create a frame for each choice to make the entire area clickable
            choice_container = tk.Frame(
                choices_frame,
                bg="#374151",
                relief="solid",
                borderwidth=2,
                highlightthickness=0
            )
            choice_container.pack(fill="x", pady=6, ipady=8, ipadx=12)
            
            # Use a button-style approach for better touch targets
            def make_select_callback(idx):
                return lambda event=None: self._select_choice(idx)
            
            choice_label = tk.Label(
                choice_container,
                text=choice_text,
                bg="#374151",
                fg="#e5e7eb",
                font=self.label_font,
                wraplength=1000,
                justify="left",
                cursor="hand2",
                anchor="w",
                padx=20,
                pady=12
            )
            choice_label.pack(fill="both", expand=True)
            
            # Make the entire container clickable
            choice_container.bind("<Button-1>", make_select_callback(shuffled_idx))
            choice_label.bind("<Button-1>", make_select_callback(shuffled_idx))
            
            # Store for later styling
            self.choice_buttons.append((choice_container, choice_label))
        
        # Submit button
        submit_btn = tk.Button(
            content,
            text="Submit Answer",
            command=self._submit_answer,
            bg="#10b981",
            fg="#03241b",
            font=self.label_font,
            padx=40,
            pady=12,
            relief="flat"
        )
        submit_btn.pack(pady=(10, 20))
    
    def _select_choice(self, choice_index):
        """Handle choice selection with visual feedback"""
        self.selected_answer.set(choice_index)
        
        # Update visual styling for all choices
        for idx, (container, label) in enumerate(self.choice_buttons):
            if idx == choice_index:
                # Selected style - bright highlight
                container.config(bg="#10b981", borderwidth=3)
                label.config(bg="#10b981", fg="#03241b", font=("Segoe UI", 11, "bold"))
            else:
                # Unselected style - default
                container.config(bg="#374151", borderwidth=2)
                label.config(bg="#374151", fg="#e5e7eb", font=("Segoe UI", 11))
    
    def _submit_answer(self):
        """Process the submitted answer"""
        if self.selected_answer.get() == -1:
            messagebox.showwarning(
                "No Answer Selected",
                "Please select an answer before submitting.",
                parent=self
            )
            return
        
        question_data = self.questions[self.current_question_index]
        original_correct = question_data.get('correct', -1)
        user_answer = self.selected_answer.get()
        
        # Check if correct (comparing with shuffled position)
        is_correct = (user_answer == self.current_correct_index)
        if is_correct:
            self.score += 1
        
        # Store response
        self.responses.append({
            'question_id': question_data.get('id', self.current_question_index),
            'question': question_data.get('question', ''),
            'user_answer_position': user_answer,
            'correct_answer_position': self.current_correct_index,
            'original_correct_index': original_correct,
            'is_correct': is_correct,
            'timestamp': time.time() - self.start_time
        })
        
        self.total_shown += 1
        self.current_question_index += 1
        
        # Check if time is up
        elapsed = time.time() - self.start_time
        if elapsed >= self.duration_seconds:
            self._show_completion()
        else:
            # Show next question
            if self.current_question_index < len(self.questions):
                self._show_question()
            else:
                # Ran out of questions
                self._show_completion()
    
    def _update_timer(self):
        """Update the progress bar and check if time is up"""
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        remaining = max(0, self.duration_seconds - elapsed)
        
        # Update progress bar width
        progress_ratio = remaining / self.duration_seconds
        self.progress_bar.place(x=0, y=0, relwidth=progress_ratio, relheight=1.0)
        
        # Update time text
        mins = int(remaining // 60)
        secs = int(remaining % 60)
        self.progress_label.config(text=f"Time remaining: {mins}:{secs:02d}")
        
        # Check if time is up
        if remaining <= 0:
            self._show_completion()
            return
        
        # Schedule next update (smooth animation)
        self.after(100, self._update_timer)
    
    def _show_completion(self):
        """Show completion screen with final score"""
        # Stop timer updates
        self.start_time = None
        
        # Clear content
        for widget in self.content_container.winfo_children():
            widget.destroy()
        
        # Hide progress bar
        self.progress_frame.pack_forget()
        
        # Save results
        self._save_results()
        
        # Container for centering
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Completion header
        header = tk.Label(
            content,
            text="Trivia Task Complete!",
            bg="#1f2937",
            fg="#10b981",
            font=self.large_font
        )
        header.pack(pady=(40, 30))
        
        # Score display
        if self.total_shown > 0:
            percentage = (self.score / self.total_shown) * 100
        else:
            percentage = 0
        
        score_text = f"You answered {self.score} out of {self.total_shown} questions correctly"
        score_label = tk.Label(
            content,
            text=score_text,
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font
        )
        score_label.pack(pady=(0, 20))
        
        percentage_label = tk.Label(
            content,
            text=f"{percentage:.1f}%",
            bg="#1f2937",
            fg="#fbbf24",
            font=self.large_font
        )
        percentage_label.pack(pady=(0, 40))
        
        # Done button
        done_btn = tk.Button(
            content,
            text="Finish",
            command=self.destroy,
            bg="#10b981",
            fg="#03241b",
            font=self.label_font,
            padx=50,
            pady=15,
            relief="flat"
        )
        done_btn.pack(pady=(20, 40))
    
    def _save_results(self):
        """Save trivia results to CSV"""
        if not self.responses:
            return
        
        # Create trivia subfolder if it doesn't exist
        if self.save_dir:
            trivia_dir = os.path.join(self.save_dir, "trivia")
        else:
            trivia_dir = os.path.join(os.path.dirname(__file__), "trivia")
        
        os.makedirs(trivia_dir, exist_ok=True)
        
        # Generate filename
        timestamp_str = datetime.now().strftime("%Y%m%dT%H%M")
        user_suffix = f"-{self.participant_name}" if self.participant_name else ""
        order_suffix = f"-{self.order_code}" if self.order_code else ""
        csv_filename = f"{timestamp_str}{user_suffix}{order_suffix}-trivia.csv"
        csv_path = os.path.join(trivia_dir, csv_filename)
        
        # Write to CSV
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                # Write headers
                f.write("question_id,question,user_answer_position,correct_answer_position,original_correct_index,is_correct,timestamp\n")
                
                # Write responses
                for response in self.responses:
                    question = response['question'].replace('"', '""')  # Escape quotes
                    f.write(
                        f'{response["question_id"]},'
                        f'"{question}",'
                        f'{response["user_answer_position"]},'
                        f'{response["correct_answer_position"]},'
                        f'{response["original_correct_index"]},'
                        f'{response["is_correct"]},'
                        f'{response["timestamp"]:.2f}\n'
                    )
            
            # Write summary file
            summary_path = csv_path.replace('-trivia.csv', '-trivia-summary.txt')
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(f"Trivia Task Summary\n")
                f.write(f"==================\n\n")
                f.write(f"Participant: {self.participant_name}\n")
                f.write(f"Order Code: {self.order_code}\n")
                f.write(f"Trivia File: {os.path.basename(self.trivia_file)}\n")
                f.write(f"Duration: {self.duration_seconds} seconds\n\n")
                f.write(f"Results:\n")
                f.write(f"  Questions Answered: {self.total_shown}\n")
                f.write(f"  Correct Answers: {self.score}\n")
                f.write(f"  Score: {self.score}/{self.total_shown}")
                if self.total_shown > 0:
                    f.write(f" ({(self.score/self.total_shown)*100:.1f}%)\n")
                else:
                    f.write("\n")
            
            print(f"Trivia results saved to: {csv_path}")
            print(f"Trivia summary saved to: {summary_path}")
        except Exception as e:
            print(f"Failed to save trivia results: {e}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save results:\n{e}",
                parent=self
            )
    
    def on_close_attempt(self):
        """Handle window close attempt"""
        response = messagebox.askyesno(
            "Exit Task?",
            "Are you sure you want to exit the trivia task?\n\nYour progress will be saved.",
            parent=self
        )
        
        if response:
            self._show_completion()


class InteractiveTaskWindow(tk.Toplevel):
    """
    Unified Interactive Task Window combining:
    - SANDE Dry Eye Questionnaire
    - OSDI-6 Questionnaire  
    - MCQ Trivia Questions
    
    All sections flow in one window with consistent styling and smooth transitions.
    Signals when ready via callback, manages timing, and saves to single CSV.
    """
    
    def __init__(self, parent, trivia_file="", duration_seconds=300, 
                 participant_name="", order_code="", save_dir="",
                 on_ready_callback=None, enable_sande=True, enable_osdi=True):
        super().__init__(parent)
        
        self.participant_name = participant_name
        self.order_code = order_code
        self.save_dir = save_dir
        self.duration_seconds = duration_seconds
        self.trivia_file = trivia_file
        self.on_ready_callback = on_ready_callback
        self.enable_sande = enable_sande
        self.enable_osdi = enable_osdi
        
        # State tracking
        self.current_section = None  # "sande", "osdi", or "trivia"
        self.completed = False
        self.start_time = None
        
        # SANDE state
        self.sande_responses = {}
        
        # OSDI state
        self.osdi_responses = {}
        self.osdi_buttons = {}
        
        # Trivia state
        self.questions = []
        self.current_question_index = 0
        self.score = 0
        self.total_shown = 0
        self.trivia_responses = []
        
        # Combined responses for single CSV
        self.all_responses = {
            'sande': {},
            'osdi': {},
            'trivia': []
        }
        
        self.title("Interactive Task")
        self.configure(bg="#1f2937")
        
        # Shared fonts
        self.title_font = font.Font(family="Segoe UI", size=14, weight="bold")
        self.label_font = font.Font(family="Segoe UI", size=11)
        self.small_font = font.Font(family="Segoe UI", size=9)
        self.large_font = font.Font(family="Segoe UI", size=16, weight="bold")
        
        # Size and center window - consistent 1400x800
        self.geometry("1400x800")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - 1400) // 2
        y = (screen_h - 800) // 2
        self.geometry(f"1400x800+{x}+{y}")
        
        # Main content container (swappable)
        self.content_container = tk.Frame(self, bg="#1f2937")
        self.content_container.pack(expand=True, fill="both")
        
        # Progress bar at bottom (shared across all sections)
        self.progress_frame = tk.Frame(self, bg="#374151", height=30)
        self.progress_frame.pack(side="bottom", fill="x")
        self.progress_frame.pack_propagate(False)
        
        self.progress_bar = tk.Frame(self.progress_frame, bg="#10b981")
        self.progress_bar.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        
        self.progress_label = tk.Label(
            self.progress_frame,
            text="Time remaining: --:--",
            bg="#10b981",
            fg="#ffffff",
            font=self.small_font
        )
        self.progress_label.place(relx=0.5, rely=0.5, anchor="center")
        
        # Load trivia questions (needed for later)
        self._load_trivia_questions()
        
        # Determine starting section
        self._start_first_section()
        
        # Prevent closing without completing
        self.protocol("WM_DELETE_WINDOW", self.on_close_attempt)
    
    def _start_first_section(self):
        """Start with first enabled section"""
        if self.enable_sande:
            self._show_sande()
        elif self.enable_osdi:
            self._show_osdi()
        else:
            self._show_trivia()
        
        # Signal ready after window is shown
        if self.on_ready_callback:
            self.after(100, self.on_ready_callback)
        
        # Start the timer
        self.start_time = time.time()
        self._update_timer()
    
    def _clear_content(self):
        """Clear the current content container"""
        for widget in self.content_container.winfo_children():
            widget.destroy()
    
    # ==================== SANDE Section ====================
    
    def _show_sande(self):
        """Show SANDE questionnaire section"""
        self.current_section = "sande"
        self.title("Interactive Task - SANDE Questionnaire")
        self._clear_content()
        
        # Container frame to center all content
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        # Content frame (centered within container)
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Header
        header = tk.Label(
            content,
            text="SANDE Dry Eye Questionnaire",
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font
        )
        header.pack(pady=(20, 10))
        
        # Instructions
        instructions = tk.Label(
            content,
            text="Please complete the following questions regarding the frequency and severity of your dry eye symptoms.",
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.label_font,
            wraplength=1000
        )
        instructions.pack(pady=(0, 30))
        
        # SANDE Questions - only 2 sliders as per official questionnaire
        self._add_sande_slider(
            content, 
            "frequency", 
            question_number="1",
            question_heading="Frequency of symptoms:",
            question_detail="Please mark on the line how often, on average, your eyes feel dry and/or irritated:",
            left_label="Rarely",
            right_label="All the time"
        )
        
        self._add_sande_slider(
            content, 
            "severity", 
            question_number="2",
            question_heading="Severity of symptoms:",
            question_detail="Please mark on the line how severe, on average, you feel your symptoms of dryness and/or irritation:",
            left_label="Very Mild",
            right_label="Very Severe"
        )
        
        # Next button
        next_btn = tk.Button(
            content,
            text="Next →",
            command=self._sande_next,
            font=self.label_font,
            bg="#3b82f6",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=30,
            pady=8
        )
        next_btn.pack(pady=30)
    
    def _add_sande_slider(self, parent, key, question_number, question_heading, question_detail, left_label="Rarely", right_label="All the time"):
        """Add a SANDE slider question with horizontal layout and drag support"""
        question_frame = tk.Frame(parent, bg="#1f2937")
        question_frame.pack(pady=20, padx=40, fill="x")
        
        # Question heading (bold) with number
        heading_font = font.Font(family="Segoe UI", size=11, weight="bold")
        heading_label = tk.Label(
            question_frame,
            text=f"{question_number}. {question_heading}",
            bg="#1f2937",
            fg="#ffffff",
            font=heading_font,
            anchor="w",
            justify="left"
        )
        heading_label.pack(fill="x", pady=(0, 5))
        
        # Question detail (regular font)
        detail_label = tk.Label(
            question_frame,
            text=question_detail,
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.label_font,
            anchor="w",
            justify="left"
        )
        detail_label.pack(fill="x", pady=(0, 15))
        
        # Slider container
        slider_container = tk.Frame(question_frame, bg="#1f2937")
        slider_container.pack(fill="x", padx=(0, 0))
        
        # Scale labels above the slider
        scale_labels_frame = tk.Frame(slider_container, bg="#1f2937")
        scale_labels_frame.pack(fill="x", pady=(0, 5))
        
        left_lbl = tk.Label(
            scale_labels_frame,
            text=left_label,
            bg="#1f2937",
            fg="#94a3b8",
            font=self.small_font
        )
        left_lbl.pack(side="left")
        
        right_lbl = tk.Label(
            scale_labels_frame,
            text=right_label,
            bg="#1f2937",
            fg="#94a3b8",
            font=self.small_font
        )
        right_lbl.pack(side="right")
        
        # Canvas for interactive slider (with click and drag)
        canvas_height = 40
        canvas = tk.Canvas(
            slider_container,
            bg="#374151",
            height=canvas_height,
            highlightthickness=0
        )
        canvas.pack(fill="x", pady=(0, 5))
        
        # Value label (shows selected value)
        value_label = tk.Label(
            slider_container,
            text="Click or drag on the scale to select",
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.small_font
        )
        value_label.pack()
        
        # Store initial value
        self.sande_responses[key] = None
        
        def update_slider(x):
            """Update slider based on x position"""
            canvas_width = canvas.winfo_width()
            if canvas_width > 0:
                # Calculate value (0-100 based on x position)
                value = int((x / canvas_width) * 100)
                value = max(0, min(100, value))  # Clamp to 0-100
                
                self.sande_responses[key] = value
                
                # Update visual feedback
                canvas.delete("all")
                
                # Draw filled portion
                fill_width = (value / 100) * canvas_width
                canvas.create_rectangle(
                    0, 0, fill_width, canvas_height,
                    fill="#3b82f6", outline=""
                )
                
                # Draw marker at position
                x_pos = (value / 100) * canvas_width
                canvas.create_oval(
                    x_pos - 8, canvas_height // 2 - 8,
                    x_pos + 8, canvas_height // 2 + 8,
                    fill="#ffffff", outline="#3b82f6", width=2
                )
                
                # Update value label
                value_label.config(text=f"{value}/100", fg="#10b981")
        
        def on_click(event):
            """Handle click on canvas"""
            update_slider(event.x)
        
        def on_drag(event):
            """Handle drag on canvas"""
            update_slider(event.x)
        
        canvas.bind("<Button-1>", on_click)
        canvas.bind("<B1-Motion>", on_drag)
    
    def _sande_next(self):
        """Validate SANDE and move to next section"""
        # Check all questions answered (only 2 questions now)
        required_keys = ["frequency", "severity"]
        missing = [k for k in required_keys if self.sande_responses.get(k) is None]
        
        if missing:
            messagebox.showwarning(
                "Incomplete",
                "Please answer all questions before proceeding.",
                parent=self
            )
            return
        
        # Save SANDE responses
        self.all_responses['sande'] = self.sande_responses.copy()
        
        # Move to next section
        if self.enable_osdi:
            self._show_osdi()
        else:
            self._show_trivia()
    
    # ==================== OSDI Section ====================
    
    def _show_osdi(self):
        """Show OSDI-6 questionnaire section"""
        self.current_section = "osdi"
        self.title("Interactive Task - OSDI-6 Questionnaire")
        self._clear_content()
        
        # Container frame
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        # Content frame (centered)
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Header
        header = tk.Label(
            content,
            text="OSDI-6 Dry Eye Assessment",
            bg="#1f2937",
            fg="#ffffff",
            font=self.title_font
        )
        header.pack(pady=(20, 10))
        
        # Instructions
        instructions = tk.Label(
            content,
            text="Please answer the following questions about your eyes.",
            bg="#1f2937",
            fg="#cbd5e1",
            font=self.label_font
        )
        instructions.pack(pady=(0, 15))
        
        # OSDI-6 Questions with proper groupings
        # Symptoms and visual disturbance subscale
        self._add_osdi_section_header(
            content,
            "Have you experienced any of the following during a typical day within the last month?"
        )
        
        self._add_osdi_question(content, "osdi_1", "Eyes that are sensitive to light?")
        self._add_osdi_question(content, "osdi_2", "Vision blurring between blinks (with your refractive correction if needed)?")
        
        # Visual function / tasks subscale
        self._add_osdi_section_header(
            content,
            "Have problems with your eyes limited you in performing any of the following during a typical day within the last month?"
        )
        
        self._add_osdi_question(content, "osdi_3", "Driving or being driven at night?")
        self._add_osdi_question(content, "osdi_4", "Watching TV, or a similar task?")
        
        # Environmental subscale
        self._add_osdi_section_header(
            content,
            "Have your eyes felt uncomfortable in any of the following situations during a typical day within the last month?"
        )
        
        self._add_osdi_question(content, "osdi_5", "Windy conditions?")
        self._add_osdi_question(content, "osdi_6", "Places or areas with low humidity?")
        
        # Submit button
        submit_btn = tk.Button(
            content,
            text="Next →",
            command=self._osdi_next,
            font=self.label_font,
            bg="#3b82f6",
            fg="#ffffff",
            activebackground="#2563eb",
            activeforeground="#ffffff",
            relief="flat",
            cursor="hand2",
            padx=30,
            pady=8
        )
        submit_btn.pack(pady=20)
    
    def _add_osdi_section_header(self, parent, header_text):
        """Add a section header for OSDI questions"""
        # Create bold font for section headers
        header_font = font.Font(family="Segoe UI", size=11, weight="bold")
        header = tk.Label(
            parent,
            text=header_text,
            bg="#1f2937",
            fg="#ffffff",  # Changed to white like SANDE headings
            font=header_font,  # Now bold
            wraplength=1000,
            justify="left"
        )
        header.pack(pady=(15, 10), padx=40, anchor="w")
    
    def _add_osdi_question(self, parent, key, question_text):
        """Add OSDI question with button-style options in horizontal layout"""
        question_frame = tk.Frame(parent, bg="#1f2937")
        question_frame.pack(pady=8, padx=40, fill="x")
        
        # Question label
        label = tk.Label(
            question_frame,
            text=question_text,
            bg="#1f2937",
            fg="#ffffff",
            font=self.label_font,
            anchor="w",
            wraplength=600
        )
        label.pack(side="left", padx=(0, 20))
        
        # Options frame (horizontal layout)
        options_frame = tk.Frame(question_frame, bg="#1f2937")
        options_frame.pack(side="right")
        
        # Initialize response
        self.osdi_responses[key] = None
        self.osdi_buttons[key] = {}  # Changed to dict for value->button mapping
        
        # Correct OSDI-6 response options
        options = [
            ("All of the time", 4),
            ("Most of the time", 3),
            ("Half of the time", 2),
            ("Some of the time", 1),
            ("None of the time", 0)
        ]
        
        def make_handler(option_key, value):
            def handler():
                self._select_osdi_option(option_key, value)
            return handler
        
        for text, value in options:
            btn = tk.Button(
                options_frame,
                text=text,
                command=make_handler(key, value),
                font=self.small_font,
                bg="#374151",
                fg="#cbd5e1",
                activebackground="#4b5563",
                activeforeground="#ffffff",
                relief="flat",
                cursor="hand2",
                padx=12,
                pady=6,
                width=14
            )
            btn.pack(side="left", padx=2)
            self.osdi_buttons[key][value] = btn  # Store button by its value
    
    def _select_osdi_option(self, key, value):
        """Handle OSDI option selection with visual feedback"""
        self.osdi_responses[key] = value
        
        # Update button styles - now using dict mapping
        for btn_value, btn in self.osdi_buttons[key].items():
            if btn_value == value:
                btn.config(bg="#3b82f6", fg="#ffffff")
            else:
                btn.config(bg="#374151", fg="#cbd5e1")
    
    def _osdi_next(self):
        """Validate OSDI and move to trivia"""
        # Check all questions answered
        required_keys = [f"osdi_{i}" for i in range(1, 7)]
        missing = [k for k in required_keys if self.osdi_responses.get(k) is None]
        
        if missing:
            messagebox.showwarning(
                "Incomplete",
                "Please answer all questions before proceeding.",
                parent=self
            )
            return
        
        # Save OSDI responses
        self.all_responses['osdi'] = self.osdi_responses.copy()
        
        # Move to trivia
        self._show_trivia()
    
    # ==================== Trivia Section ====================
    
    def _load_trivia_questions(self):
        """Load trivia questions from JSON file"""
        if not self.trivia_file or not os.path.exists(self.trivia_file):
            self.questions = []
            return
        
        try:
            with open(self.trivia_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.questions = data.get('questions', [])
                random.shuffle(self.questions)
        except Exception as e:
            print(f"Error loading trivia questions: {e}")
            self.questions = []
    
    def _show_trivia(self):
        """Show trivia MCQ section"""
        self.current_section = "trivia"
        self.title("Interactive Task - Trivia Questions")
        
        if not self.questions:
            self._show_completion()
            return
        
        self._show_question()
    
    def _show_question(self):
        """Display current trivia question"""
        self._clear_content()
        
        if self.current_question_index >= len(self.questions):
            self._show_completion()
            return
        
        question_data = self.questions[self.current_question_index]
        
        # Container
        container = tk.Frame(self.content_container, bg="#1f2937")
        container.pack(expand=True, fill="both")
        
        # Content (centered)
        content = tk.Frame(container, bg="#1f2937")
        content.pack(expand=True)
        
        # Progress indicator (just question number, not total) - large white text
        progress_text = f"Question {self.current_question_index + 1}"
        progress_label = tk.Label(
            content,
            text=progress_text,
            bg="#1f2937",  # Same as background (no visible background)
            fg="#ffffff",  # White text
            font=self.title_font  # Larger font (size 14, bold)
        )
        progress_label.pack(pady=(20, 10))
        
        # Question text
        question_label = tk.Label(
            content,
            text=question_data['question'],
            bg="#1f2937",
            fg="#ffffff",
            font=self.large_font,
            wraplength=1000,
            justify="center"
        )
        question_label.pack(pady=(10, 40))
        
        # Choices frame
        choices_frame = tk.Frame(content, bg="#1f2937")
        choices_frame.pack(pady=20)
        
        # Get correct answer (index-based in JSON)
        choices = question_data['choices'][:]
        correct_index = question_data.get('correct', 0)
        correct_answer = choices[correct_index]
        
        # Shuffle choices but track correct answer
        random.shuffle(choices)
        
        # Store question start time
        question_start_time = time.time()
        
        # Store button references for feedback
        choice_buttons = []
        
        def make_choice_handler(choice, button, is_correct_choice):
            def handler():
                # Disable all buttons to prevent multiple clicks
                for btn in choice_buttons:
                    btn.config(state="disabled")
                
                # Show visual feedback
                if is_correct_choice:
                    # Flash green for correct answer
                    button.config(bg="#10b981", fg="#ffffff")
                else:
                    # Flash red for incorrect answer
                    button.config(bg="#ef4444", fg="#ffffff")
                
                # Record response
                is_correct = (choice == correct_answer)
                response_time = time.time() - question_start_time
                
                self.trivia_responses.append({
                    'question_number': self.current_question_index + 1,
                    'question': question_data['question'],
                    'selected_answer': choice,
                    'correct_answer': correct_answer,
                    'is_correct': is_correct,
                    'response_time': response_time
                })
                
                if is_correct:
                    self.score += 1
                
                self.total_shown += 1
                
                # Move to next question after brief delay 150ms)
                self.current_question_index += 1
                self.after(150, self._show_question)
            
            return handler
        
        # Create choice buttons (large, touch-friendly)
        for i, choice in enumerate(choices):
            is_correct_choice = (choice == correct_answer)
            btn = tk.Button(
                choices_frame,
                text=choice,  # Removed f"{chr(65 + i)}. " prefix
                font=self.label_font,
                bg="#374151",
                fg="#ffffff",
                activebackground="#4b5563",
                activeforeground="#ffffff",
                relief="flat",
                cursor="hand2",
                padx=30,
                pady=20,
                width=60,
                anchor="w"
            )
            btn.config(command=make_choice_handler(choice, btn, is_correct_choice))
            btn.pack(pady=8)
            choice_buttons.append(btn)
    
    def _show_completion(self):
        """Complete the task and close window immediately"""
        # Save all responses to single CSV
        self._save_all_responses()
        
        # Mark as completed and close immediately (no thank you screen)
        self._complete_and_close()
    
    def _save_all_responses(self):
        """Save all responses to single CSV file"""
        if not self.save_dir:
            return
        
        # Create interactive_tasks directory
        save_path = os.path.join(self.save_dir, "interactive_tasks")
        os.makedirs(save_path, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}-{self.participant_name}-{self.order_code}-I.csv"
        filepath = os.path.join(save_path, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Header
                f.write("section,question,response,value,timestamp\n")
                
                # SANDE responses
                if self.all_responses['sande']:
                    for key, value in self.all_responses['sande'].items():
                        f.write(f"SANDE,{key},{value},{value},{timestamp}\n")
                
                # OSDI responses with correct labels
                if self.all_responses['osdi']:
                    osdi_labels = ["None of the time", "Some of the time", "Half of the time", "Most of the time", "All of the time"]
                    for key, value in self.all_responses['osdi'].items():
                        option_text = osdi_labels[value]
                        f.write(f"OSDI,{key},{option_text},{value},{timestamp}\n")
                
                # Trivia responses
                for response in self.trivia_responses:
                    q_num = response['question_number']
                    question = response['question'].replace(',', ';')  # Escape commas
                    selected = response['selected_answer'].replace(',', ';')
                    correct = response['correct_answer'].replace(',', ';')
                    is_correct = 1 if response['is_correct'] else 0
                    resp_time = response['response_time']
                    
                    f.write(f"Trivia,Q{q_num},{selected},{is_correct},{resp_time}\n")
            
            print(f"Interactive task responses saved to: {filepath}")
        
        except Exception as e:
            print(f"Error saving interactive task responses: {e}")
            messagebox.showerror(
                "Save Error",
                f"Could not save responses:\n{e}",
                parent=self
            )
    
    def _update_timer(self):
        """Update the progress bar and timer"""
        if not self.start_time:
            return
        
        elapsed = time.time() - self.start_time
        remaining = max(0, self.duration_seconds - elapsed)
        
        # Update progress bar
        if self.duration_seconds > 0:
            progress = remaining / self.duration_seconds
            self.progress_bar.place(relwidth=progress)
        
        # Update timer label
        minutes = int(remaining // 60)
        seconds = int(remaining % 60)
        self.progress_label.config(text=f"Time remaining: {minutes}:{seconds:02d}")
        
        # Check if time expired
        if remaining <= 0:
            self._show_completion()
            return
        
        # Schedule next update (smooth animation)
        self.after(100, self._update_timer)
    
    def _complete_and_close(self):
        """Mark as completed and close window"""
        self.completed = True
        self.destroy()
    
    def on_close_attempt(self):
        """Handle window close attempt"""
        response = messagebox.askyesno(
            "Exit Task?",
            "Are you sure you want to exit?",
            parent=self
        )
        
        if response:
            self._show_completion()


# Test function
def test_questionnaires():
    """Test the unified questionnaire window"""
    root = tk.Tk()
    root.withdraw()
    
    # Test unified questionnaire window
    questionnaire = QuestionnaireWindow(root, participant_name="TestUser", order_code="RVI", save_dir="")
    root.wait_window(questionnaire)
    print(f"Questionnaire completed: {questionnaire.completed}")
    
    root.destroy()


def test_trivia():
    """Test the trivia window"""
    root = tk.Tk()
    root.withdraw()
    
    # Test with 60 second duration
    trivia = TriviaMCQWindow(
        root, 
        trivia_file="trivia_general_knowledge.json",
        duration_seconds=60,
        participant_name="TestUser",
        order_code="RVI",
        save_dir=""
    )
    root.wait_window(trivia)
    
    root.destroy()


def test_full_interactive_task():
    """Test the full interactive task flow: questionnaires -> trivia"""
    root = tk.Tk()
    root.withdraw()
    
    import time
    
    # Record start time
    task_start = time.time()
    
    # First: Show questionnaires
    print("Starting dry eye questionnaires...")
    questionnaire = QuestionnaireWindow(root, participant_name="TestUser", order_code="RVI", save_dir="")
    root.wait_window(questionnaire)
    
    if not questionnaire.completed:
        print("Questionnaires cancelled")
        root.destroy()
        return
    
    # Calculate time spent on questionnaires
    questionnaire_duration = time.time() - task_start
    print(f"Questionnaires completed in {questionnaire_duration:.1f} seconds")
    
    # Second: Show trivia for remaining time
    total_task_duration = 300  # 5 minutes total
    trivia_duration = max(60, total_task_duration - questionnaire_duration)  # At least 60 seconds
    
    print(f"Starting trivia task for {trivia_duration:.0f} seconds...")
    trivia = TriviaMCQWindow(
        root,
        trivia_file="trivia_general_knowledge.json",
        duration_seconds=trivia_duration,
        participant_name="TestUser",
        order_code="RVI",
        save_dir=""
    )
    root.wait_window(trivia)
    
    print("Interactive task complete!")
    root.destroy()


def test_unified_interactive():
    """Test the new unified InteractiveTaskWindow"""
    root = tk.Tk()
    root.withdraw()
    
    print("Starting unified Interactive Task window...")
    print("This will show: SANDE → OSDI-6 → MCQ Trivia all in one window")
    
    def on_ready():
        print("Interactive window is ready - recording would start here")
    
    interactive = InteractiveTaskWindow(
        root,
        trivia_file="trivia_general_knowledge.json",
        duration_seconds=600,  # 10 minutes for testing
        participant_name="TestUser",
        order_code="RVI",
        save_dir="",
        on_ready_callback=on_ready,
        enable_sande=True,
        enable_osdi=True
    )
    
    root.wait_window(interactive)
    print(f"Interactive task completed: {interactive.completed}")
    
    root.destroy()


if __name__ == "__main__":
    # Uncomment the one you want to test
    # test_questionnaires()
    # test_trivia()
    # test_full_interactive_task()
    test_unified_interactive()


