# 👁️ Eye State Detector

A real-time Eye State Detector using Mediapipe and OpenCV to identify whether eyes are open or closed from webcam footage.

## 🔍 Features
- Real-time eye detection and blink tracking
- Calculates Eye Aspect Ratio (EAR) for both eyes
- Records detailed eye measurements (temporal/nasal distances, horizontal widths)
- Visualizes eye landmarks on zoomed, stabilized video feed
- GUI launcher with automated task order assignment
- **SANDE and OSDI-6 dry eye questionnaires** with touch-friendly UI
- **Trivia MCQ task** with randomized questions and choice shuffling (330 questions)
- **Video playback** with OpenCV-based player
- CSV data export with timestamps
- Separate data folders for questionnaires and trivia results

## 🧪 Experimental Design

This tool is designed for studying blinking behavior across different tasks. Each participant performs three tasks in a randomized order:

1. **Reading Task** - Participant reads text (implementation in progress)
2. **Video Task** - Participant watches a video with OpenCV-based video player
3. **Interactive Task** - Participant completes:
   - SANDE questionnaire (2 visual analog scales for frequency and severity)
   - OSDI-6 dry eye questionnaire (6 questions, official version)
   - Trivia MCQ questions (one at a time, with countdown timer and score tracking)

### Task Order Assignment

To balance task order effects, the program automatically assigns one of 6 possible task orders based on the number of existing data files. The order is calculated as `(number of existing CSV files) % 6`, ensuring roughly equal distribution across all permutations as more participants are tested.

**Participant Blinding**: Only the three-letter code is displayed in the UI (e.g., "Task Order: RVI"), without revealing the actual task sequence to participants.

### Letter Code Mapping

The task order code uses the first letter of each task name, shown in the order they will be performed:

| Code | Task Sequence | Modulo Result |
|------|--------------|---------------|
| **RVI** | Reading → Video → Interactive | `file_count % 6 = 0` |
| **RIV** | Reading → Interactive → Video | `file_count % 6 = 1` |
| **VRI** | Video → Reading → Interactive | `file_count % 6 = 2` |
| **VIR** | Video → Interactive → Reading | `file_count % 6 = 3` |
| **IRV** | Interactive → Reading → Video | `file_count % 6 = 4` |
| **IVR** | Interactive → Video → Reading | `file_count % 6 = 5` |

**Where it appears:**
- Launcher home screen: "Task Order: RVI"
- Setup window: "Task Order: RVI"
- CSV filename: `20251104T1430-JohnDoe-RVI.csv`

## 🛠️ Technologies
- Python 3.12
- OpenCV (webcam capture, visualization, and video playback)
- Mediapipe (face mesh landmark detection)
- NumPy (geometric calculations)
- Tkinter (GUI launcher and task windows)
- Pillow/PIL (image processing for video display)

## 🚀 How to Run

1. Clone the repository:
   ```bash
   git clone https://github.com/fillupt/Eye-State-Detector
   cd Eye-State-Detector
   ```

2. Create and activate virtual environment:
   ```bash
   python -m venv eye-env
   eye-env\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the launcher:
   ```bash
   python launcher.py
   ```

5. In the launcher:
   - Click **Setup** to configure:
     - Save directory for output files
     - Reading task file (text/PDF)
     - Video task file (MP4, AVI, MOV, etc.)
     - Interactive task file (trivia JSON - defaults to `trivia_general_knowledge.json`)
     - SANDE/OSDI-6 questionnaire options (checkboxes)
     - Task duration (1-15 minutes)
   - Enter participant name
   - Click **Start** to begin recording
   - Task order is automatically assigned based on existing files

## 📊 Output Format

### Eye Tracking Data
Main eye tracking data is saved as CSV with the following columns:
- `timestamp` - Time in seconds since recording started
- `left_ear`, `right_ear` - Eye Aspect Ratio for each eye
- `LE_temporal`, `LE_nasal` - Left eye vertical distances (temporal and nasal pairs)
- `RE_temporal`, `RE_nasal` - Right eye vertical distances (temporal and nasal pairs)
- `LE_width`, `RE_width` - Horizontal eye widths

Filename format: `YYYYMMDDTHHMM-ParticipantName-XXX.csv`
- Example: `20251104T1430-JohnDoe-RVI.csv` (Reading → Video → Interactive order)

### Questionnaire Data
Saved in `questionnaires/` subfolder:
- Filename: `YYYYMMDDTHHMM-ParticipantName-XXX-questionnaires.csv`
- Format:
  ```
  questionnaire,question,response
  SANDE,frequency,50
  SANDE,severity,50
  OSDI6,q1,3
  OSDI6,q2,2
  ...
  ```

### Trivia Data
Saved in `trivia/` subfolder with two files:
1. **CSV file**: `YYYYMMDDTHHMM-ParticipantName-XXX-trivia.csv`
   - Columns: question_id, question, user_answer_position, correct_answer_position, original_correct_index, is_correct, timestamp
2. **Summary file**: `YYYYMMDDTHHMM-ParticipantName-XXX-trivia-summary.txt`
   - Contains: participant info, questions answered, score, percentage
