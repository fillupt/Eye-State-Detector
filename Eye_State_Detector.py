import argparse
import os
import sys
import cv2
import mediapipe as mp
import numpy as np
import time

# Initialize mediapipe face mesh
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1)

# Indices for eyes (from Mediapipe's 468 landmarks)
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]

# Function to calculate eye aspect ratio
def eye_aspect_ratio(eye_points, landmarks):
    p1 = np.array(landmarks[eye_points[1]])
    p2 = np.array(landmarks[eye_points[5]])
    p3 = np.array(landmarks[eye_points[2]])
    p4 = np.array(landmarks[eye_points[4]])
    p5 = np.array(landmarks[eye_points[0]])
    p6 = np.array(landmarks[eye_points[3]])
    A = np.linalg.norm(p1 - p2)
    B = np.linalg.norm(p3 - p4)
    C = np.linalg.norm(p5 - p6)
    ear = (A + B) / (2.0 * C)
    return ear

# Draw eye landmarks on the frame
def draw_eye(frame, eye_points, landmarks, color=(0, 255, 255), thickness=1):
    points = [landmarks[i] for i in eye_points]
    for point in points:
        cv2.circle(frame, point, 2, color, -1)
    for i in range(len(points)):
        start_point = points[i]
        end_point = points[(i + 1) % len(points)]
        cv2.line(frame, start_point, end_point, color, thickness)
    
    # Draw vertical measurement lines (temporal and nasal pairs)
    # Temporal vertical: index 1 to index 5 (top_temporal to bottom_temporal)
    cv2.line(frame, points[1], points[5], (255, 0, 255), 2)
    # Nasal vertical: index 2 to index 4 (top_nasal to bottom_nasal)
    cv2.line(frame, points[2], points[4], (255, 0, 255), 2)

# EAR threshold
EAR_THRESHOLD = 0.25

# Parse optional command-line arguments (e.g., user name, output directory)
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--name", type=str, default="", help="Optional user name to display on-screen")
parser.add_argument("--outdir", type=str, default="", help="Directory to save CSV output file")
parser.add_argument("--order", type=str, default="", help="Task order code for filename")
parser.add_argument("--headless", action="store_true", help="Run without window (background mode)")
args, _ = parser.parse_known_args()
USER_NAME = args.name
OUTDIR = args.outdir if args.outdir else os.path.dirname(__file__)
TASK_ORDER = args.order
HEADLESS = args.headless

# Start webcam
cap = cv2.VideoCapture(0)

# Ready file used by launcher to detect when the tracker is initialized
READY_PATH = os.path.join(os.path.dirname(__file__), "tracker.ready")

# Command file for controlling the tracker
COMMAND_PATH = os.path.join(os.path.dirname(__file__), "tracker.cmd")

# Flag for writing ready file once initialization completes
ready_written = False

# Create window only if not in headless mode
window_closed = False
if not HEADLESS:
    cv2.namedWindow("Eye State Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Eye State Detection", 640, 480)

# Variables to track eye state
left_eye_status = "Unknown"
right_eye_status = "Unknown"

# Data recording: list of frame data rows and recording state
recorded_data = []
recording = False
current_csv_filename = None

# Stabilization: track previous crop region to reduce jitter
prev_crop = None

def process_commands():
    """Check for and process commands from the launcher."""
    global recording, recorded_data, current_csv_filename, window_closed
    
    if not os.path.exists(COMMAND_PATH):
        return True  # Continue running
    
    try:
        with open(COMMAND_PATH, "r") as f:
            command = f.read().strip()
        
        # Remove command file after reading
        os.remove(COMMAND_PATH)
        
        if command.startswith("START_RECORDING "):
            # Format: START_RECORDING <filename>
            filename = command[16:].strip()
            if not recording:
                recorded_data = []  # Clear previous data
                current_csv_filename = filename
                recording = True
                print(f"Started recording to: {filename}")
        
        elif command == "STOP_RECORDING":
            if recording:
                save_csv_data()
                recording = False
                print(f"Stopped recording, saved {len(recorded_data)} frames")
                recorded_data = []
                current_csv_filename = None
        
        elif command == "CLOSE_WINDOW":
            if not window_closed and not HEADLESS:
                window_closed = True
                cv2.destroyAllWindows()
                print("Window closed by command - continuing in background...")
        
        elif command == "SHUTDOWN":
            print("Shutdown command received")
            return False  # Stop running
        
    except Exception as e:
        print(f"Error processing command: {e}", file=sys.stderr)
    
    return True  # Continue running

def save_csv_data():
    """Save the current recorded data to CSV."""
    if not recorded_data or not current_csv_filename:
        return
    
    try:
        csv_path = os.path.join(OUTDIR, current_csv_filename)
        with open(csv_path, "w", encoding="utf-8") as csvf:
            # Write header
            csvf.write("timestamp,left_ear,right_ear,LE_temporal,LE_nasal,RE_temporal,RE_nasal,LE_width,RE_width\n")
            # Write data rows
            for row in recorded_data:
                csvf.write(",".join(map(str, row)) + "\n")
        print(f"Saved {len(recorded_data)} frames to: {csv_path}")
    except Exception as e:
        print(f"Failed to save CSV: {e}", file=sys.stderr)

try:
    while True:
        # Process commands from launcher
        if not process_commands():
            break  # Shutdown command received
        
        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = face_mesh.process(rgb_frame)

        # Write a ready file the first time processing happens successfully.
        if (not ready_written) and ret:
            try:
                with open(READY_PATH, "w") as f:
                    f.write(str(os.getpid()))
                ready_written = True
            except Exception:
                # Ignore write failures; launcher will simply keep waiting
                pass

        # Create a fixed-size display frame (640x480)
        display_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        if result.multi_face_landmarks:
            for face_landmarks in result.multi_face_landmarks:
                # Get original landmarks in original frame coordinates
                orig_landmarks = [(int(lm.x * w), int(lm.y * h)) for lm in face_landmarks.landmark]
                
                # Calculate face bounding box
                xs = [lm.x * w for lm in face_landmarks.landmark]
                ys = [lm.y * h for lm in face_landmarks.landmark]
                face_x_min, face_x_max = int(min(xs)), int(max(xs))
                face_y_min, face_y_max = int(min(ys)), int(max(ys))
                
                # Add padding and calculate crop region (reduced zoom: 1.5x instead of 2x)
                face_w = face_x_max - face_x_min
                face_h = face_y_max - face_y_min
                pad_w = int(face_w * 0.5)  # More padding = less zoom
                pad_h = int(face_h * 0.5)
                
                crop_x1 = max(0, face_x_min - pad_w)
                crop_y1 = max(0, face_y_min - pad_h)
                crop_x2 = min(w, face_x_max + pad_w)
                crop_y2 = min(h, face_y_max + pad_h)
                
                # Stabilization: only update crop if face moved significantly from previous position
                if prev_crop is not None:
                    prev_x1, prev_y1, prev_x2, prev_y2 = prev_crop
                    # Calculate center movement
                    prev_cx = (prev_x1 + prev_x2) // 2
                    prev_cy = (prev_y1 + prev_y2) // 2
                    curr_cx = (crop_x1 + crop_x2) // 2
                    curr_cy = (crop_y1 + crop_y2) // 2
                    
                    # Only update if moved more than 15% of face width/height
                    threshold_x = face_w * 0.15
                    threshold_y = face_h * 0.15
                    
                    if abs(curr_cx - prev_cx) < threshold_x and abs(curr_cy - prev_cy) < threshold_y:
                        # Use previous crop region (stabilize)
                        crop_x1, crop_y1, crop_x2, crop_y2 = prev_crop
                
                # Store current crop for next frame
                prev_crop = (crop_x1, crop_y1, crop_x2, crop_y2)
                
                # Crop the face region
                cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
                if cropped.size > 0:
                    # Scale cropped region to fit 640x480 while maintaining aspect ratio
                    crop_h, crop_w = cropped.shape[:2]
                    scale = min(640 / crop_w, 480 / crop_h) * 1.5  # 1.5x zoom instead of 2x
                    new_w = int(crop_w * scale)
                    new_h = int(crop_h * scale)
                    
                    zoomed = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                    
                    # Center the zoomed image in the display frame
                    y_offset = max(0, (480 - new_h) // 2)
                    x_offset = max(0, (640 - new_w) // 2)
                    
                    # Handle cases where zoomed image is larger than display
                    y_crop_start = 0
                    x_crop_start = 0
                    if new_h > 480:
                        y_crop_start = (new_h - 480) // 2
                        zoomed = zoomed[y_crop_start:y_crop_start + 480, :]
                        new_h = 480
                        y_offset = 0
                    if new_w > 640:
                        x_crop_start = (new_w - 640) // 2
                        zoomed = zoomed[:, x_crop_start:x_crop_start + 640]
                        new_w = 640
                        x_offset = 0
                    
                    display_frame[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = zoomed
                    
                    # Transform landmarks to display frame coordinates
                    display_landmarks = []
                    for x, y in orig_landmarks:
                        # Translate to crop coordinates
                        x_crop = x - crop_x1
                        y_crop = y - crop_y1
                        # Scale
                        x_scaled = x_crop * scale
                        y_scaled = y_crop * scale
                        # Adjust for zoom cropping
                        x_final = x_scaled - x_crop_start + x_offset
                        y_final = y_scaled - y_crop_start + y_offset
                        display_landmarks.append((int(x_final), int(y_final)))
                    
                    landmarks = display_landmarks
                    frame = display_frame
                    h, w = 480, 640
                
                left_ear = eye_aspect_ratio(LEFT_EYE, landmarks)
                right_ear = eye_aspect_ratio(RIGHT_EYE, landmarks)
                avg_ear = (left_ear + right_ear) / 2.0

                # Record frame data: timestamp, EARs, vertical distances, horizontal widths
                # LEFT_EYE = [33, 160, 158, 133, 153, 144]
                # RIGHT_EYE = [362, 385, 387, 263, 373, 380]
                # Eye structure: [temporal_corner, top_temporal, top_nasal, nasal_corner, bottom_nasal, bottom_temporal]
                # Vertical pairs: (index 1, index 5) = temporal vertical, (index 2, index 4) = nasal vertical
                # Horizontal: (index 0, index 3) = temporal to nasal

                # Left eye measurements
                le_temp_vert = np.linalg.norm(np.array(landmarks[LEFT_EYE[1]]) - np.array(landmarks[LEFT_EYE[5]]))
                le_nasal_vert = np.linalg.norm(np.array(landmarks[LEFT_EYE[2]]) - np.array(landmarks[LEFT_EYE[4]]))
                le_width = np.linalg.norm(np.array(landmarks[LEFT_EYE[0]]) - np.array(landmarks[LEFT_EYE[3]]))

                # Right eye measurements
                re_temp_vert = np.linalg.norm(np.array(landmarks[RIGHT_EYE[1]]) - np.array(landmarks[RIGHT_EYE[5]]))
                re_nasal_vert = np.linalg.norm(np.array(landmarks[RIGHT_EYE[2]]) - np.array(landmarks[RIGHT_EYE[4]]))
                re_width = np.linalg.norm(np.array(landmarks[RIGHT_EYE[0]]) - np.array(landmarks[RIGHT_EYE[3]]))

                # Record row only if recording is active
                if recording:
                    recorded_data.append([
                        time.time(),
                        left_ear,
                        right_ear,
                        le_temp_vert,
                        le_nasal_vert,
                        re_temp_vert,
                        re_nasal_vert,
                        le_width,
                        re_width
                    ])

                # Determine eye states for color coding
                if left_ear < EAR_THRESHOLD:
                    left_eye_status = "Closed"
                    left_color = (0, 0, 255)  # Red
                else:
                    left_eye_status = "Open"
                    left_color = (0, 255, 0)  # Green
                
                if right_ear < EAR_THRESHOLD:
                    right_eye_status = "Closed"
                    right_color = (0, 0, 255)  # Red
                else:
                    right_eye_status = "Open"
                    right_color = (0, 255, 0)  # Green

                # Draw eyes with color coding (no text overlay)
                draw_eye(frame, LEFT_EYE, landmarks, color=left_color)
                draw_eye(frame, RIGHT_EYE, landmarks, color=right_color)

        # Show frame only if not in headless mode and window hasn't been closed
        if not HEADLESS and not window_closed:
            cv2.imshow("Eye State Detection", frame)
            key = cv2.waitKey(1) & 0xFF
            # Check if window is closed (user clicked X) - switch to headless mode
            if cv2.getWindowProperty("Eye State Detection", cv2.WND_PROP_VISIBLE) < 1:
                window_closed = True
                cv2.destroyAllWindows()
                print("Window closed - continuing tracking in background...")
            # Exit completely on ESC key
            elif key == 27:
                break
        elif HEADLESS or window_closed:
            # In headless mode, just wait a bit to avoid busy loop
            time.sleep(0.01)
finally:
    # If still recording, save the current data
    if recording and recorded_data:
        save_csv_data()
    
    # Cleanup: remove ready and command files if they exist
    try:
        if ready_written and os.path.exists(READY_PATH):
            os.remove(READY_PATH)
    except Exception:
        pass
    
    try:
        if os.path.exists(COMMAND_PATH):
            os.remove(COMMAND_PATH)
    except Exception:
        pass
    
    cap.release()
    cv2.destroyAllWindows()
