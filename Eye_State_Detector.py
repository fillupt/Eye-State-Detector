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

# EAR threshold
EAR_THRESHOLD = 0.25

# Start webcam
cap = cv2.VideoCapture(0)

# Simple stop-button state and rectangle (updated each frame)
STOP_FLAG = False
btn_rect = [0, 0, 0, 0]  # x1, y1, x2, y2
btn_w, btn_h = 100, 36

def _on_mouse(event, x, y, flags, param):
    """Mouse callback to stop the loop when the on-screen button is clicked."""
    global STOP_FLAG, btn_rect
    if event == cv2.EVENT_LBUTTONDOWN:
        x1, y1, x2, y2 = btn_rect
        if x1 <= x <= x2 and y1 <= y <= y2:
            STOP_FLAG = True

# Create a named window and attach mouse callback so button clicks work
cv2.namedWindow("Eye State Detection")
cv2.setMouseCallback("Eye State Detection", _on_mouse)

# Variables to track eye closure duration
eye_closed_start = None
last_closed_duration = 0
last_display_time = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = face_mesh.process(rgb_frame)

    if result.multi_face_landmarks:
        for face_landmarks in result.multi_face_landmarks:
            landmarks = [(int(lm.x * w), int(lm.y * h)) for lm in face_landmarks.landmark]
            left_ear = eye_aspect_ratio(LEFT_EYE, landmarks)
            right_ear = eye_aspect_ratio(RIGHT_EYE, landmarks)
            avg_ear = (left_ear + right_ear) / 2.0

            if avg_ear < EAR_THRESHOLD:
                if eye_closed_start is None:
                    eye_closed_start = time.time()
                status = "Eyes Closed"
                color = (0, 0, 255)
            else:
                if eye_closed_start is not None:
                    last_closed_duration = time.time() - eye_closed_start
                    last_display_time = time.time()
                    eye_closed_start = None
                status = "Eyes Open"
                color = (0, 255, 0)

            cv2.putText(frame, status, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

            # Show duration message for 3 seconds
            if time.time() - last_display_time < 3 and last_closed_duration > 0:
                msg = f"Eyes were closed for {last_closed_duration:.2f} sec"
                cv2.putText(frame, msg, (30, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

            draw_eye(frame, LEFT_EYE, landmarks)
            draw_eye(frame, RIGHT_EYE, landmarks)

    # Draw the stop button at top-right (so it's visible and clickable)
    x2 = w - 10
    x1 = x2 - btn_w
    y1 = 10
    y2 = y1 + btn_h
    btn_rect[0], btn_rect[1], btn_rect[2], btn_rect[3] = x1, y1, x2, y2

    # Draw button (semi-transparent effect by overlay)
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 255), -1)
    alpha = 0.6
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)
    cv2.putText(frame, "Stop", (x1 + 12, y1 + 24), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

    # Show frame and handle keypresses; ESC to exit
    cv2.imshow("Eye State Detection", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == 27 or STOP_FLAG:
        break

cap.release()
cv2.destroyAllWindows()
