import argparse
import math
import os
import sys
import time
import urllib.request
from collections import deque

import cv2
import mediapipe as mp
import numpy as np

# ---------------------------------------------------------------------------
# Landmark index constants
# ---------------------------------------------------------------------------

# 6-point EAR sets: [temporal_corner, top_temporal, top_nasal, nasal_corner, bottom_nasal, bottom_temporal]
LEFT_EYE_EAR  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR = [362, 385, 387, 263, 373, 380]

# Full 16-point eyelid contours for asymmetry analysis
LEFT_EYE_CONTOUR  = [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246]
RIGHT_EYE_CONTOUR = [362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398]

# Iris landmarks (indices 468-477 in the 478-point model): center + right/top/left/bottom
LEFT_IRIS  = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]

# Target blendshape names (eye & gaze, 14 total)
BLENDSHAPE_NAMES = [
    "eyeBlinkLeft",  "eyeBlinkRight",
    "eyeWideLeft",   "eyeWideRight",
    "eyeSquintLeft", "eyeSquintRight",
]

EAR_THRESHOLD = 0.25

# ---------------------------------------------------------------------------
# Face mesh connection constants for drawing tessellation
# Loaded after the tasks import block below; populated at module level.
# ---------------------------------------------------------------------------
_FACEMESH_TESSELATION = None
_FACEMESH_FACE_OVAL   = None
_FACEMESH_LEFT_EYE    = None
_FACEMESH_RIGHT_EYE   = None
_FACEMESH_LEFT_IRIS   = None
_FACEMESH_RIGHT_IRIS  = None
_connections_available = False

# ---------------------------------------------------------------------------
# Model auto-download
# ---------------------------------------------------------------------------
MODEL_FILENAME = "face_landmarker.task"
MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)


def ensure_model(model_path: str) -> None:
    if os.path.exists(model_path):
        return
    print(f"Downloading face landmark model to: {model_path}", flush=True)

    def _reporthook(count, block_size, total_size):
        if total_size > 0:
            pct = min(100, count * block_size * 100 // total_size)
            print(f"\r  {pct}%  ", end="", flush=True)

    urllib.request.urlretrieve(MODEL_URL, model_path, reporthook=_reporthook)
    print("\nDownload complete.", flush=True)


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------

def extract_blendshapes(face_blendshapes) -> dict:
    """Return {name: score} for the 14 target blendshape names."""
    bs_map = {c.category_name: c.score for c in face_blendshapes}
    return {name: bs_map.get(name, 0.0) for name in BLENDSHAPE_NAMES}


def extract_head_pose(matrix) -> tuple:
    """ZYX Euler decomposition of 4x4 transformation matrix -> (yaw, pitch, roll) degrees.
    Yaw:   +ve = turn right,  -ve = turn left
    Pitch: +ve = chin up,     -ve = chin down
    Roll:  +ve = tilt right,  -ve = tilt left (right ear toward shoulder)
    """
    R = matrix[:3, :3]
    sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
    if sy > 1e-6:
        yaw   = math.degrees(math.atan2( R[2, 0],  sy))         # left/right turn
        pitch = math.degrees(math.atan2(-R[2, 1],  R[2, 2]))    # chin up/down
        roll  = math.degrees(math.atan2( R[1, 0],  R[0, 0]))    # lean/tilt
    else:
        # Gimbal-lock fallback
        yaw   = 0.0
        pitch = math.degrees(math.atan2(-R[2, 1],  R[2, 2]))
        roll  = math.degrees(math.atan2(-R[1, 2],  R[1, 1]))
    return yaw, pitch, roll


def compute_inter_ocular_dist(landmarks, w: int, h: int) -> float:
    """Pixel distance between left (468) and right (473) iris centres."""
    if len(landmarks) < 478:
        return 0.0
    lc = landmarks[468]
    rc = landmarks[473]
    return math.sqrt(((lc.x - rc.x) * w) ** 2 + ((lc.y - rc.y) * h) ** 2)


def eye_aspect_ratio(eye_points, landmarks, w: int, h: int) -> float:
    """Compute EAR from NormalizedLandmark list + frame pixel dimensions."""
    def px(idx):
        return np.array([landmarks[eye_points[idx]].x * w,
                         landmarks[eye_points[idx]].y * h])
    A = np.linalg.norm(px(1) - px(5))
    B = np.linalg.norm(px(2) - px(4))
    C = np.linalg.norm(px(0) - px(3))
    return (A + B) / (2.0 * C) if C > 0 else 0.0


# Eyelid aperture landmark pairs (upper, lower) for temporal/central/nasal thirds
_LE_APT_PAIRS = {"temporal": (160, 163), "central": (159, 145), "nasal": (157, 153)}
_RE_APT_PAIRS = {"temporal": (384, 381), "central": (386, 374), "nasal": (388, 390)}
_LE_WIDTH_PAIR = (33, 133)    # outer → inner eye corners (left eye)
_RE_WIDTH_PAIR = (362, 263)   # outer → inner eye corners (right eye)


def compute_eyelid_apertures(landmarks, w: int, h: int) -> dict:
    """Return normalised aperture at temporal/central/nasal thirds for each eye.

    Each aperture value = vertical gap / eye-width at that position.
    Positive nt_asym means nasal aperture > temporal (nasal-wider pattern).
    """
    def px(idx):
        return np.array([landmarks[idx].x * w, landmarks[idx].y * h])

    out = {}
    for side, apt_pairs, width_pair in (
        ("LE", _LE_APT_PAIRS, _LE_WIDTH_PAIR),
        ("RE", _RE_APT_PAIRS, _RE_WIDTH_PAIR),
    ):
        width = np.linalg.norm(px(width_pair[0]) - px(width_pair[1]))
        if width < 1e-6:
            for zone in ("temporal", "central", "nasal"):
                out[f"{side}_aperture_{zone}"] = 0.0
            out[f"{side}_nt_asym"] = 0.0
            continue
        for zone in ("temporal", "central", "nasal"):
            u, lo = apt_pairs[zone]
            out[f"{side}_aperture_{zone}"] = np.linalg.norm(px(u) - px(lo)) / width
        out[f"{side}_nt_asym"] = (
            out[f"{side}_aperture_nasal"] - out[f"{side}_aperture_temporal"]
        )
    return out


# Pinhole distance constants.
# _FOCAL_PX is set dynamically after the camera opens (see _update_focal_px()).
# Override _CAMERA_HFOV_DEG if using a different camera.
# Formula: dist_cm = (FOCAL_PX × IOD_AVG_MM) / (iod_px × 10)
_IOD_AVG_MM      = 63.0   # average adult inter-pupillary distance (mm)
_FOCAL_PX        = 500.0  # updated at runtime from actual capture width
_CAMERA_HFOV_DEG = 70.0   # BRIO 4K horizontal FOV at 16:9 modes (~70°)


def _update_focal_px(capture_width: int) -> float:
    """Recompute focal length in pixels from actual capture width and camera HFOV."""
    import math
    return (capture_width / 2.0) / math.tan(math.radians(_CAMERA_HFOV_DEG / 2.0))


def compute_distance_cm(iod_px: float) -> float:
    """Estimate camera-to-face distance (cm) from inter-ocular pixel distance."""
    if iod_px < 1:
        return 0.0
    return (_FOCAL_PX * _IOD_AVG_MM) / (iod_px * 10.0)


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_connections(frame, pts, connections, color, thickness=1):
    """Draw connections; each item may be a (i,j) tuple or a Connection(start,end) object."""
    n = len(pts)
    for conn in connections:
        if hasattr(conn, 'start'):
            i, j = conn.start, conn.end
        else:
            i, j = conn
        if i < n and j < n:
            cv2.line(frame, pts[i], pts[j], color, thickness)


def draw_face_mesh(frame, display_pts: list, blink_left: float, blink_right: float):
    """Draw full tessellation + highlighted eyes + iris + blink score labels."""
    if _connections_available:
        _draw_connections(frame, display_pts, _FACEMESH_TESSELATION, (40, 40, 40),   1)
        _draw_connections(frame, display_pts, _FACEMESH_FACE_OVAL,   (80, 80, 80),   1)
        _draw_connections(frame, display_pts, _FACEMESH_LEFT_EYE,    (0, 255, 255),  1)
        _draw_connections(frame, display_pts, _FACEMESH_RIGHT_EYE,   (0, 255, 255),  1)
        _draw_connections(frame, display_pts, _FACEMESH_LEFT_IRIS,   (50, 150, 255), 1)
        _draw_connections(frame, display_pts, _FACEMESH_RIGHT_IRIS,  (50, 150, 255), 1)
    else:
        # Fallback: draw contours from hard-coded index lists
        for contour in [LEFT_EYE_CONTOUR, RIGHT_EYE_CONTOUR]:
            n = len(contour)
            for k in range(n):
                cv2.line(frame, display_pts[contour[k]], display_pts[contour[(k + 1) % n]],
                         (0, 255, 255), 1)

    # Filled circles at iris centres
    if len(display_pts) >= 478:
        l_ctr = display_pts[468]
        r_ctr = display_pts[473]
        cv2.circle(frame, l_ctr, 3, (50, 150, 255), -1)
        cv2.circle(frame, r_ctr, 3, (50, 150, 255), -1)

        # Blink score labels -- turn red when blinking
        font = cv2.FONT_HERSHEY_SIMPLEX
        l_col = (0, 60, 255) if blink_left  > 0.5 else (255, 255, 255)
        r_col = (0, 60, 255) if blink_right > 0.5 else (255, 255, 255)
        cv2.putText(frame, f"L:{blink_left:.2f}",
                    (l_ctr[0] + 6, l_ctr[1] - 6), font, 0.45, l_col, 1, cv2.LINE_AA)
        cv2.putText(frame, f"R:{blink_right:.2f}",
                    (r_ctr[0] + 6, r_ctr[1] - 6), font, 0.45, r_col, 1, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# CSV header & row helpers
# ---------------------------------------------------------------------------

def _build_csv_header() -> str:
    cols = ["timestamp"]
    cols += BLENDSHAPE_NAMES
    cols += ["blink_lr_asym"]
    cols += ["head_yaw", "head_pitch", "head_roll"]
    cols += ["face_cx", "face_cy"]
    cols += ["distance_cm"]
    cols += ["left_ear", "right_ear"]
    cols += ["LE_aperture_temporal", "LE_aperture_central", "LE_aperture_nasal", "LE_nt_asym"]
    cols += ["RE_aperture_temporal", "RE_aperture_central", "RE_aperture_nasal", "RE_nt_asym"]
    for prefix, n in [("LE_c", 16), ("LE_i", 5), ("RE_c", 16), ("RE_i", 5)]:
        for i in range(n):
            cols += [f"{prefix}{i}_x", f"{prefix}{i}_y", f"{prefix}{i}_z"]
    return ",".join(cols)


CSV_HEADER = _build_csv_header()


def _landmark_triplets(landmarks, indices) -> list:
    vals = []
    for idx in indices:
        lm = landmarks[idx]
        vals += [lm.x, lm.y, lm.z]
    return vals


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--name",     type=str, default="",  help="Participant name")
parser.add_argument("--outdir",   type=str, default="",  help="Directory to save CSV")
parser.add_argument("--order",    type=str, default="",  help="Task order code")
parser.add_argument("--headless", action="store_true",   help="Run without preview window")
args, _ = parser.parse_known_args()

USER_NAME  = args.name
OUTDIR     = args.outdir if args.outdir else os.path.dirname(os.path.abspath(__file__))
TASK_ORDER = args.order
HEADLESS   = args.headless

# ---------------------------------------------------------------------------
# Model & detector initialisation
# ---------------------------------------------------------------------------

MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), MODEL_FILENAME)
ensure_model(MODEL_PATH)

from mediapipe.tasks import python as mp_tasks          # noqa: E402
from mediapipe.tasks.python import vision as mp_vision  # noqa: E402

# Populate tessellation connection constants from the Tasks API
try:
    _C = mp_vision.FaceLandmarksConnections
    _FACEMESH_TESSELATION = _C.FACE_LANDMARKS_TESSELATION
    _FACEMESH_FACE_OVAL   = _C.FACE_LANDMARKS_FACE_OVAL
    _FACEMESH_LEFT_EYE    = _C.FACE_LANDMARKS_LEFT_EYE
    _FACEMESH_RIGHT_EYE   = _C.FACE_LANDMARKS_RIGHT_EYE
    _FACEMESH_LEFT_IRIS   = _C.FACE_LANDMARKS_LEFT_IRIS
    _FACEMESH_RIGHT_IRIS  = _C.FACE_LANDMARKS_RIGHT_IRIS
    _connections_available = True
except AttributeError:
    pass   # fallback drawing used instead

_options = mp_vision.FaceLandmarkerOptions(
    base_options=mp_tasks.BaseOptions(model_asset_path=MODEL_PATH),
    output_face_blendshapes=True,
    output_facial_transformation_matrixes=True,
    num_faces=1,
    running_mode=mp_vision.RunningMode.VIDEO,
)
detector = mp_vision.FaceLandmarker.create_from_options(_options)

# ---------------------------------------------------------------------------
# Webcam & IPC paths
# ---------------------------------------------------------------------------

# Use DirectShow on Windows to avoid MSMF resolution-negotiation hangs.
_cap_backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
cap = cv2.VideoCapture(0, _cap_backend)
cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

# Read back actual delivered resolution and calibrate focal length
_actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
_actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
_FOCAL_PX  = _update_focal_px(_actual_w)
print(f"Camera: {_actual_w}×{_actual_h}  focal_px={_FOCAL_PX:.0f}", flush=True)

READY_PATH   = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.ready")
COMMAND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tracker.cmd")

ready_written = False
window_closed = False

if not HEADLESS:
    cv2.namedWindow("Eye State Detection", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Eye State Detection", 640, 480)

# ---------------------------------------------------------------------------
# State variables
# ---------------------------------------------------------------------------

recorded_data        = []
recording            = False
current_csv_filename = None
prev_crop            = None
frame_times          = deque(maxlen=30)
_last_ts_ms          = 0   # monotonic timestamp guard for VIDEO mode

# ---------------------------------------------------------------------------
# IPC helpers
# ---------------------------------------------------------------------------

def save_csv_data():
    if not recorded_data or not current_csv_filename:
        return
    try:
        csv_path = os.path.join(OUTDIR, current_csv_filename)
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(CSV_HEADER + "\n")
            for row in recorded_data:
                f.write(",".join(map(str, row)) + "\n")
        print(f"Saved {len(recorded_data)} frames to: {csv_path}", flush=True)
    except Exception as e:
        print(f"Failed to save CSV: {e}", file=sys.stderr)


def process_commands() -> bool:
    """Check for and process commands from launcher. Returns False on SHUTDOWN."""
    global recording, recorded_data, current_csv_filename, window_closed

    if not os.path.exists(COMMAND_PATH):
        return True

    try:
        with open(COMMAND_PATH, "r") as f:
            command = f.read().strip()
        os.remove(COMMAND_PATH)

        if command.startswith("START_RECORDING "):
            filename = command[16:].strip()
            if not recording:
                recorded_data = []
                current_csv_filename = filename
                recording = True
                print(f"Started recording to: {filename}", flush=True)

        elif command == "STOP_RECORDING":
            if recording:
                save_csv_data()
                recording = False
                print(f"Stopped recording, saved {len(recorded_data)} frames", flush=True)
                recorded_data = []
                current_csv_filename = None

        elif command == "CLOSE_WINDOW":
            if not window_closed and not HEADLESS:
                window_closed = True
                cv2.destroyAllWindows()
                print("Window closed by command - continuing in background...", flush=True)

        elif command == "SHUTDOWN":
            print("Shutdown command received", flush=True)
            return False

    except Exception as e:
        print(f"Error processing command: {e}", file=sys.stderr)

    return True


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

try:
    while True:
        if not process_commands():
            break

        ret, frame = cap.read()
        if not ret:
            break

        h, w = frame.shape[:2]
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Strictly-increasing millisecond timestamp required by VIDEO running mode
        ts_ms = int(cap.get(cv2.CAP_PROP_POS_MSEC))
        if ts_ms <= _last_ts_ms:
            ts_ms = _last_ts_ms + 1
        _last_ts_ms = ts_ms

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result   = detector.detect_for_video(mp_image, ts_ms)

        # Rolling FPS
        frame_times.append(time.time())
        fps = ((len(frame_times) - 1) / (frame_times[-1] - frame_times[0])
               if len(frame_times) > 1 else 0.0)

        display_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        if result.face_landmarks:
            landmarks = result.face_landmarks[0]   # 478 NormalizedLandmark objects

            # --- Blendshapes & head pose ---
            bs = (extract_blendshapes(result.face_blendshapes[0])
                  if result.face_blendshapes else {n: 0.0 for n in BLENDSHAPE_NAMES})

            if result.facial_transformation_matrixes:
                yaw, pitch, roll = extract_head_pose(result.facial_transformation_matrixes[0])
            else:
                yaw = pitch = roll = 0.0

            # --- Face centroid & inter-ocular distance ---
            xs = [lm.x for lm in landmarks]
            ys = [lm.y for lm in landmarks]
            face_cx = (min(xs) + max(xs)) / 2.0
            face_cy = (min(ys) + max(ys)) / 2.0
            iod     = compute_inter_ocular_dist(landmarks, w, h)

            # --- EAR (computed from original frame dimensions) ---
            left_ear  = eye_aspect_ratio(LEFT_EYE_EAR,  landmarks, w, h)
            right_ear = eye_aspect_ratio(RIGHT_EYE_EAR, landmarks, w, h)

            # --- Distance, blink asymmetry, eyelid aperture ---
            dist_cm = compute_distance_cm(iod)
            blink_lr_asym = bs["eyeBlinkLeft"] - bs["eyeBlinkRight"]
            apt = compute_eyelid_apertures(landmarks, w, h)

            # --- Pixel coords in original frame ---
            orig_pts = [(int(lm.x * w), int(lm.y * h)) for lm in landmarks]

            # --- Stabilised face-crop zoom ---
            face_x_min, face_x_max = int(min(xs) * w), int(max(xs) * w)
            face_y_min, face_y_max = int(min(ys) * h), int(max(ys) * h)
            face_w = face_x_max - face_x_min
            face_h = face_y_max - face_y_min
            pad_w  = int(face_w * 1.2)
            pad_h  = int(face_h * 1.2)

            crop_x1 = max(0, face_x_min - pad_w)
            crop_y1 = max(0, face_y_min - pad_h)
            crop_x2 = min(w, face_x_max + pad_w)
            crop_y2 = min(h, face_y_max + pad_h)

            if prev_crop is not None:
                px1, py1, px2, py2 = prev_crop
                if (abs((crop_x1 + crop_x2) // 2 - (px1 + px2) // 2) < face_w * 0.15 and
                        abs((crop_y1 + crop_y2) // 2 - (py1 + py2) // 2) < face_h * 0.15):
                    crop_x1, crop_y1, crop_x2, crop_y2 = prev_crop

            prev_crop = (crop_x1, crop_y1, crop_x2, crop_y2)

            cropped = frame[crop_y1:crop_y2, crop_x1:crop_x2]
            if cropped.size > 0:
                crop_h, crop_w = cropped.shape[:2]
                scale  = min(640 / crop_w, 480 / crop_h) * 1.5
                new_w  = int(crop_w * scale)
                new_h  = int(crop_h * scale)
                zoomed = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

                y_off = max(0, (480 - new_h) // 2)
                x_off = max(0, (640 - new_w) // 2)
                ycs   = 0
                xcs   = 0

                if new_h > 480:
                    ycs    = (new_h - 480) // 2
                    zoomed = zoomed[ycs:ycs + 480, :]
                    new_h  = 480
                    y_off  = 0
                if new_w > 640:
                    xcs    = (new_w - 640) // 2
                    zoomed = zoomed[:, xcs:xcs + 640]
                    new_w  = 640
                    x_off  = 0

                display_frame[y_off:y_off + new_h, x_off:x_off + new_w] = zoomed

                # Transform all 478 landmarks to display coordinates
                display_pts = []
                for (ox, oy) in orig_pts:
                    xs_ = (ox - crop_x1) * scale - xcs + x_off
                    ys_ = (oy - crop_y1) * scale - ycs + y_off
                    display_pts.append((int(xs_), int(ys_)))

                # Draw full face mesh, iris, and blink labels
                draw_face_mesh(display_frame, display_pts,
                               bs["eyeBlinkLeft"], bs["eyeBlinkRight"])

            # Distance overlay (top-right)
            dist_col = (0, 200, 255) if dist_cm < 40 or dist_cm > 80 else (200, 255, 200)
            dist_txt = f"{dist_cm:.0f} cm"
            (tw, _th), _ = cv2.getTextSize(dist_txt, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
            cv2.putText(display_frame, dist_txt,
                        (630 - tw, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.55, dist_col, 1, cv2.LINE_AA)

            # Blink L-R asymmetry overlay
            asym_col = (0, 60, 255) if abs(blink_lr_asym) > 0.15 else (180, 180, 180)
            cv2.putText(display_frame, f"Blink L-R:{blink_lr_asym:+.2f}",
                        (10, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.44, asym_col, 1, cv2.LINE_AA)

            # NT aperture asymmetry overlay
            nt_le = apt["LE_nt_asym"]
            nt_re = apt["RE_nt_asym"]
            nt_col = (0, 60, 255) if abs(nt_le) > 0.05 or abs(nt_re) > 0.05 else (180, 180, 180)
            cv2.putText(display_frame, f"NT-asym  L:{nt_le:+.2f}  R:{nt_re:+.2f}",
                        (10, 446), cv2.FONT_HERSHEY_SIMPLEX, 0.44, nt_col, 1, cv2.LINE_AA)

            # Head pose overlay (bottom-left)
            cv2.putText(display_frame,
                        f"Yaw:{yaw:+.1f}  Pitch:{pitch:+.1f}  Roll:{roll:+.1f}",
                        (10, 462), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (180, 180, 180), 1, cv2.LINE_AA)

            # Record frame
            if recording:
                row = [
                    time.time(),
                    *[bs[n] for n in BLENDSHAPE_NAMES],
                    round(blink_lr_asym, 6),
                    round(yaw, 4), round(pitch, 4), round(roll, 4),
                    round(face_cx, 6), round(face_cy, 6),
                    round(dist_cm, 2),
                    round(left_ear, 6), round(right_ear, 6),
                    round(apt["LE_aperture_temporal"], 6), round(apt["LE_aperture_central"], 6),
                    round(apt["LE_aperture_nasal"],    6), round(apt["LE_nt_asym"],           6),
                    round(apt["RE_aperture_temporal"], 6), round(apt["RE_aperture_central"], 6),
                    round(apt["RE_aperture_nasal"],    6), round(apt["RE_nt_asym"],           6),
                    *_landmark_triplets(landmarks, LEFT_EYE_CONTOUR),
                    *_landmark_triplets(landmarks, LEFT_IRIS),
                    *_landmark_triplets(landmarks, RIGHT_EYE_CONTOUR),
                    *_landmark_triplets(landmarks, RIGHT_IRIS),
                ]
                recorded_data.append(row)

        # FPS overlay -- always top-left
        cv2.putText(display_frame, f"FPS: {fps:.1f}",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

        # --- Window display ---
        if not HEADLESS and not window_closed:
            cv2.imshow("Eye State Detection", display_frame)

            if not ready_written:
                try:
                    with open(READY_PATH, "w") as f:
                        f.write(str(os.getpid()))
                    ready_written = True
                except Exception:
                    pass

            key = cv2.waitKey(1) & 0xFF

            if cv2.getWindowProperty("Eye State Detection", cv2.WND_PROP_VISIBLE) < 1:
                window_closed = True
                cv2.destroyAllWindows()
                print("Window closed - continuing tracking in background...", flush=True)
            elif key == 27:   # ESC
                break

        elif HEADLESS or window_closed:
            time.sleep(0.01)

finally:
    if recording and recorded_data:
        save_csv_data()

    detector.close()

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
