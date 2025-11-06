# Experiment Design: Blinking Behavior Study

## Project Overview

This project is designed to study blinking behavior patterns during different cognitive tasks to understand how visual and cognitive load affects eye state and blink frequency.

## Experimental Hypothesis

Blinking patterns may vary significantly depending on the type of task being performed:
- **Reading tasks** may show different blink patterns due to eye movement and text tracking
- **Video viewing** may reduce blink frequency due to passive attention
- **Interactive tasks** (questionnaires) may show increased blink rates due to active cognitive processing

## Participant Protocol

### Session Structure

Each participant completes **three tasks** in a **randomized order**:

1. **Reading Task**
   - Participant reads text material (file selected by experimenter)
   - Duration: Configurable (1-15 minutes, default 5 minutes)
   - Data collected: Continuous eye tracking throughout reading

2. **Video Task**
   - Participant watches a video (file selected by experimenter)
   - Duration: Configurable (1-15 minutes, default 5 minutes)
   - Data collected: Continuous eye tracking during video viewing

3. **Interactive Task**
   - Participant completes activities selected by experimenter:
     - **SANDE** (Symptom Assessment in Dry Eye) - 2 visual analog scales (frequency and severity)
     - **OSDI-6** (Ocular Surface Disease Index - 6 item version) - Official questionnaire with proper response options
     - **Trivia MCQ** - Multiple choice questions from JSON file (default: 330 questions from `trivia_general_knowledge.json`)
       - Questions presented one at a time
       - 5 answer choices (shuffled to prevent position bias)
       - Countdown timer and score tracking
       - Continues until time expires
   - Duration: Configurable (1-15 minutes, default 5 minutes)
   - Data collected: 
     - Continuous eye tracking while completing tasks
     - Questionnaire responses saved to `questionnaires/` subfolder
     - Trivia responses and scores saved to `trivia/` subfolder

### Task Order Randomization

To control for **order effects**, the task sequence is automatically assigned based on existing data files:

- Task order = `(file_count % 6)` ensures balanced distribution across 6 possible permutations
- Order is encoded as three-letter code (e.g., **RVI** = Reading → Video → Interactive)
- Participant sees only the code (**blinded**), not the full task names
- Experimenter can decode using the Letter Code Mapping (see README.md)

### Blinding Strategy

- **Participant**: Sees only "Task Order: RVI" without explanation
- **Experimenter**: Has access to decoder table showing RVI = Reading → Video → Interactive
- **Purpose**: Prevents participant bias about expected difficulty or cognitive load

## Data Collection

### Recorded Measurements

For each video frame (typically 30 FPS), the system captures:

1. **Eye Aspect Ratio (EAR)** - Left and Right
   - Primary metric for detecting blinks
   - Lower EAR = more closed eye
   
2. **Vertical Distances** (4 measurements)
   - Left Eye Temporal (outer vertical pair)
   - Left Eye Nasal (inner vertical pair)
   - Right Eye Temporal (outer vertical pair)
   - Right Eye Nasal (inner vertical pair)
   
3. **Horizontal Widths** (2 measurements)
   - Left Eye Width (lateral distance)
   - Right Eye Width (lateral distance)

4. **Timestamp**
   - Time in seconds since recording started

### Output Format

**Main CSV File**: `YYYYMMDDTHHMM-ParticipantName-CODE.csv`

Example: `20251104T1430-JohnDoe-RVI.csv`

**Columns**:
```
timestamp,left_ear,right_ear,LE_temporal,LE_nasal,RE_temporal,RE_nasal,LE_width,RE_width
```

**Questionnaire Data**: `questionnaires/YYYYMMDDTHHMM-ParticipantName-CODE-questionnaires.csv`

Example format:
```
questionnaire,question,response
SANDE,frequency,50
SANDE,severity,50
OSDI6,q1,3
OSDI6,q2,2
OSDI6,q3,4
OSDI6,q4,1
OSDI6,q5,2
OSDI6,q6,3
```

**Trivia Data**: 
- CSV: `trivia/YYYYMMDDTHHMM-ParticipantName-CODE-trivia.csv`
  - Columns: question_id, question, user_answer_position, correct_answer_position, original_correct_index, is_correct, timestamp
- Summary: `trivia/YYYYMMDDTHHMM-ParticipantName-CODE-trivia-summary.txt`
  - Contains participant info, questions answered, score, and percentage

## Analysis Goals

### Primary Questions

1. **Task Effect**: Do different tasks (reading, video, interactive) produce different blinking patterns?
2. **Blink Rate**: Does blink frequency differ across tasks?
3. **Blink Duration**: Are blinks longer/shorter during different cognitive loads?
4. **Eye Asymmetry**: Do left and right eyes show different patterns?

### Secondary Questions

1. **Order Effects**: Does task order influence blinking behavior?
2. **Dry Eye Correlation**: Do SANDE/OSDI scores correlate with blink patterns?
3. **Temporal Patterns**: Do blink patterns change over the duration of a task (fatigue effects)?
4. **Individual Differences**: Are there consistent individual blinking signatures?

## Technical Implementation

### Hardware Requirements
- Webcam (built-in or external)
- Adequate lighting for face detection
- Computer capable of running Python + OpenCV + MediaPipe

### Software Architecture

1. **launcher.py** - Master control program
   - Manages experimental flow
   - Assigns task order
   - Configures session parameters
   - Spawns detector process

2. **Eye_State_Detector.py** - Data collection worker
   - Captures webcam feed
   - Detects face landmarks using MediaPipe
   - Calculates eye metrics
   - Records data continuously
   - Saves CSV on exit

3. **questionnaires.py** - Interactive task components
   - QuestionnaireWindow: Unified SANDE + OSDI-6 interface
     - Touch-friendly button-style controls (no pixelated radio buttons)
     - Horizontal layout with aligned response options
     - Smooth transitions between questionnaires
   - TriviaMCQWindow: Trivia question presenter
     - One question at a time display
     - Randomized question and choice order
     - Countdown timer with progress bar
     - Score tracking
     - Large touch-friendly buttons

4. **video_player.py** - Video task component
   - VideoPlayerWindow: OpenCV-based video player
     - Play/pause/stop controls
     - Frame-by-frame playback with proper timing
     - Aspect ratio preservation
     - Duration limiting support
     - Progress display

5. **Task Files** (provided by experimenter)
   - Reading: Text document (PDF, TXT, DOCX, etc.) - *implementation in progress*
   - Video: Video file (MP4, AVI, MOV, MKV, etc.)
   - Interactive: Trivia JSON file (defaults to `trivia_general_knowledge.json` with 330 questions)

### Session Workflow

```
1. Experimenter opens launcher.py
2. System calculates task order from existing files
3. Experimenter clicks "Setup"
   - Selects reading file (text/PDF)
   - Selects video file (MP4, AVI, MOV, etc.)
   - Selects interactive file (trivia JSON - defaults to trivia_general_knowledge.json)
   - Checks SANDE/OSDI questionnaires as needed
   - Sets save directory
   - Sets task duration (1-15 minutes)
4. Experimenter enters participant name
5. Experimenter clicks "Start"
6. System shows "Task Order: XXX" to participant
7. Tasks launch in assigned order:
   - Reading: Display text (implementation in progress)
   - Video: VideoPlayerWindow opens, participant watches video
   - Interactive: QuestionnaireWindow (SANDE/OSDI if enabled) → TriviaMCQWindow (trivia questions)
8. Eye tracker runs continuously recording data
9. After all tasks complete, experimenter stops tracker
10. Files saved automatically:
    - Main CSV: eye tracking data with order code in filename
    - questionnaires/: SANDE and OSDI-6 responses
    - trivia/: Question responses and score summary
```

## Quality Control

### Pre-Session Checklist
- [ ] Webcam working and positioned correctly
- [ ] Adequate lighting on participant's face
- [ ] Save directory configured
- [ ] Task files selected:
  - [ ] Reading file (implementation in progress)
  - [ ] Video file
  - [ ] Interactive/trivia file (or using default)
- [ ] Questionnaires selected (SANDE/OSDI if applicable)
- [ ] Duration set appropriately (1-15 minutes)
- [ ] Test that video player works with selected video file

### During Session
- Monitor video preview to ensure face tracking is stable
- Ensure participant maintains reasonable distance from camera
- Watch for "Running" status (not "Prewarming" or "Stopped")

### Post-Session
- Verify files created:
  - [ ] Main CSV in save directory root
  - [ ] Questionnaire CSV in `questionnaires/` subfolder (if SANDE/OSDI enabled)
  - [ ] Trivia CSV and summary in `trivia/` subfolder
- Check filenames include correct order code
- Verify file sizes (should be substantial for 5+ minute recording)
- Check first/last few rows for data quality
- Verify questionnaire responses are saved correctly
- Check trivia score and questions answered count

## Future Enhancements

### Potential Additions
1. **Real-time blink detection** - Alert on extended eye closure
2. **Task timing automation** - Auto-advance between tasks (partially implemented)
3. **Built-in reading task presentation** - Display text/PDF within application
4. **Real-time analysis** - Show blink rate during recording
5. **Calibration phase** - Baseline blink measurement before tasks
6. **Export to multiple formats** - JSON, Excel, etc.
7. **Automated analysis scripts** - Calculate summary statistics from CSVs
8. **Custom trivia categories** - Allow filtering by topic/difficulty

### Research Extensions
1. **Additional tasks** - Gaming, conversation, meditation
2. **Environmental variables** - Lighting, screen brightness, distance
3. **Longer sessions** - Multi-hour recordings with breaks
4. **Paired studies** - Before/after interventions (eye drops, rest, etc.)

## References

### Eye Aspect Ratio (EAR)
- Soukupová, T., & Čech, J. (2016). Real-time eye blink detection using facial landmarks. 21st computer vision winter workshop.

### Dry Eye Questionnaires
- **SANDE**: Schaumberg, D. A., et al. (2007). Development and validation of a short global dry eye symptom index. The Ocular Surface.
- **OSDI**: Schiffman, R. M., et al. (2000). Reliability and validity of the Ocular Surface Disease Index. Archives of Ophthalmology.

### MediaPipe Face Mesh
- Lugaresi, C., et al. (2019). MediaPipe: A Framework for Building Perception Pipelines. arXiv preprint arXiv:1906.08172.

---

**Document Version**: 1.1  
**Last Updated**: November 6, 2025  
**Author**: Research Team  
**Status**: Active Experiment  
**Recent Changes**: Added video player, questionnaires (SANDE/OSDI-6), and trivia MCQ components
