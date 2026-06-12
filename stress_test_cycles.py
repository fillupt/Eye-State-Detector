"""
Automated stress test runner for Video and Interactive task windows.

Runs multiple unattended cycles and records pass/fail with timings.

Examples:
  python stress_test_cycles.py --cycles 10 --tasks both
  python stress_test_cycles.py --tasks video --video-file C:\\path\\to\\video.mp4
  python stress_test_cycles.py --tasks interactive --duration-interactive 8
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time
import traceback
import tkinter as tk
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from video_player import VideoPlayerWindow
from questionnaires import InteractiveTaskWindow
from reading_window import show_reading_window


@dataclass
class CycleResult:
    cycle: int
    task: str
    status: str
    elapsed_seconds: float
    detail: str


def _tracker_ready_path(repo_root: str) -> str:
    return os.path.join(repo_root, "tracker.ready")


def _tracker_command_path(repo_root: str) -> str:
    return os.path.join(repo_root, "tracker.cmd")


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _cleanup_stale_tracker_state(repo_root: str) -> None:
    ready_path = _tracker_ready_path(repo_root)
    command_path = _tracker_command_path(repo_root)

    stale_pid = None
    if os.path.exists(ready_path):
        try:
            with open(ready_path, "r", encoding="utf-8") as f:
                raw = (f.read() or "").strip()
            stale_pid = int(raw) if raw.isdigit() else None
        except Exception:
            stale_pid = None

    if stale_pid and _pid_exists(stale_pid):
        try:
            with open(command_path, "w", encoding="utf-8") as f:
                f.write("SHUTDOWN")
        except Exception:
            pass

        deadline = time.time() + 2.0
        while time.time() < deadline and _pid_exists(stale_pid):
            time.sleep(0.1)

        if _pid_exists(stale_pid):
            subprocess.run(
                ["taskkill", "/PID", str(stale_pid), "/T", "/F"],
                check=False,
                capture_output=True,
                text=True,
            )

    for path in (command_path, ready_path):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


def _send_tracker_command(repo_root: str, command: str) -> None:
    with open(_tracker_command_path(repo_root), "w", encoding="utf-8") as f:
        f.write(command)


def _wait_for_tracker_ready(repo_root: str, process: subprocess.Popen, timeout_seconds: float) -> tuple[bool, str]:
    ready_path = _tracker_ready_path(repo_root)
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if process.poll() is not None:
            return False, f"tracker exited early with code {process.returncode}"
        if os.path.exists(ready_path):
            return True, ""
        time.sleep(0.1)
    return False, f"tracker not ready within {timeout_seconds:.1f}s"


def _shutdown_tracker(repo_root: str, process: Optional[subprocess.Popen], timeout_seconds: float) -> tuple[bool, str]:
    if process is None:
        _cleanup_stale_tracker_state(repo_root)
        return True, ""

    try:
        if process.poll() is None:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
            try:
                _send_tracker_command(repo_root, "SHUTDOWN")
            except Exception:
                pass

            try:
                process.wait(timeout=timeout_seconds)
            except Exception:
                try:
                    process.kill()
                    process.wait(timeout=2)
                except Exception as e:
                    _cleanup_stale_tracker_state(repo_root)
                    return False, f"tracker kill failed: {e}"
    finally:
        _cleanup_stale_tracker_state(repo_root)

    return True, ""


def _launch_tracker(
    repo_root: str,
    participant_name: str,
    order_code: str,
    out_dir: str,
    timeout_seconds: float,
    visible: bool,
) -> tuple[Optional[subprocess.Popen], str]:
    _cleanup_stale_tracker_state(repo_root)

    python_exe = sys.executable
    cmd = [python_exe, os.path.join(repo_root, "Eye_State_Detector.py"), "--ipcdir", repo_root]
    if not visible:
        cmd.append("--headless")
    if participant_name:
        cmd += ["--name", participant_name]
    if out_dir:
        cmd += ["--outdir", out_dir]
    if order_code:
        cmd += ["--order", order_code]

    try:
        process = subprocess.Popen(cmd, cwd=repo_root)
    except Exception as e:
        return None, f"failed to launch tracker: {e}"

    ready_ok, ready_msg = _wait_for_tracker_ready(repo_root, process, timeout_seconds)
    if not ready_ok:
        _shutdown_tracker(repo_root, process, timeout_seconds=3.0)
        return None, ready_msg
    return process, ""


def _recording_name(cycle: int, order_code: str, suffix: str) -> str:
    return f"stress-{cycle:02d}-{order_code}-{suffix}.csv"


def _now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_launcher_config(repo_root: str) -> dict:
    cfg_path = os.path.join(repo_root, "launcher_config.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _resolve_default_paths(
    repo_root: str,
    cli_video: Optional[str],
    cli_trivia: Optional[str],
    cli_reading: Optional[str],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    cfg = _load_launcher_config(repo_root)

    reading_source = cli_reading or cfg.get("task_reading") or ""
    video_file = cli_video or cfg.get("task_video") or ""
    trivia_file = cli_trivia or cfg.get("task_interactive") or os.path.join(repo_root, "trivia_general_knowledge.json")

    if reading_source and not reading_source.startswith(("http://", "https://")) and not os.path.isabs(reading_source):
        candidate_root = os.path.join(repo_root, reading_source)
        candidate_stories = os.path.join(repo_root, "stories", reading_source)
        if os.path.exists(candidate_root):
            reading_source = candidate_root
        elif os.path.exists(candidate_stories):
            reading_source = candidate_stories
        else:
            # Keep previous behavior for clearer error reporting downstream.
            reading_source = candidate_root
    if video_file and not os.path.isabs(video_file):
        video_file = os.path.join(repo_root, video_file)
    if trivia_file and not os.path.isabs(trivia_file):
        trivia_file = os.path.join(repo_root, trivia_file)

    if reading_source and not reading_source.startswith(("http://", "https://")) and not os.path.exists(reading_source):
        reading_source = None
    video_file = video_file if (video_file and os.path.exists(video_file)) else None
    trivia_file = trivia_file if (trivia_file and os.path.exists(trivia_file)) else None

    return reading_source, video_file, trivia_file


def _resolve_local_story_files(repo_root: str, reading_source: str) -> list[str]:
    source = reading_source.strip()
    if not source or source.startswith(("http://", "https://")):
        return []

    if not os.path.isabs(source):
        source = os.path.join(repo_root, source)
    source = os.path.abspath(source)
    if not os.path.exists(source):
        return []

    story_dir = os.path.dirname(source)
    story_files = sorted(
        [
            os.path.join(story_dir, f)
            for f in os.listdir(story_dir)
            if f.lower().endswith(".html")
        ],
        key=lambda p: os.path.basename(p).lower(),
    )
    return story_files


def _run_reading_cycle(
    cycle: int,
    reading_source: str,
    total_stories: int,
    duration_seconds: int,
    auto_advance_seconds: float,
    repo_root: str,
    tracker_enabled: bool,
    order_code: str,
) -> CycleResult:
    started = time.time()
    try:
        on_ready = None
        if tracker_enabled:
            csv_name = _recording_name(cycle, order_code, "R")
            on_ready = lambda name=csv_name: _send_tracker_command(repo_root, f"START_RECORDING {name}")

        show_reading_window(
            reading_source,
            on_ready_callback=on_ready,
            duration_seconds=duration_seconds,
            save_dir="",
            participant_name=f"StressUser{cycle:02d}",
            order_code="RTEST",
            auto_advance_seconds=auto_advance_seconds,
            total_stories=total_stories,
        )
        if tracker_enabled:
            _send_tracker_command(repo_root, "STOP_RECORDING")
        elapsed = time.time() - started
        return CycleResult(cycle, "reading", "PASS", elapsed, "completed")
    except Exception as e:
        if tracker_enabled:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
        elapsed = time.time() - started
        return CycleResult(cycle, "reading", "FAIL", elapsed, f"exception: {e}")


def _mk_root() -> tk.Tk:
    root = tk.Tk()
    root.withdraw()
    return root


def _run_video_cycle(
    cycle: int,
    video_file: str,
    duration_seconds: int,
    timeout_seconds: int,
    repo_root: str,
    tracker_enabled: bool,
    order_code: str,
) -> CycleResult:
    started = time.time()
    root = _mk_root()

    timed_out = {"value": False}

    try:
        window = VideoPlayerWindow(
            root,
            video_file=video_file,
            participant_name=f"StressUser{cycle:02d}",
            order_code="VTEST",
            duration_seconds=duration_seconds,
            save_dir="",
            on_ready_callback=(
                (lambda name=_recording_name(cycle, order_code, "V"):
                    _send_tracker_command(repo_root, f"START_RECORDING {name}"))
                if tracker_enabled else None
            ),
        )

        def on_timeout() -> None:
            timed_out["value"] = True
            if window.winfo_exists():
                try:
                    window.destroy()
                except Exception:
                    pass

        timeout_id = root.after(timeout_seconds * 1000, on_timeout)
        root.wait_window(window)
        try:
            root.after_cancel(timeout_id)
        except Exception:
            pass

        elapsed = time.time() - started
        if tracker_enabled:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
        if timed_out["value"]:
            return CycleResult(cycle, "video", "FAIL", elapsed, f"timeout>{timeout_seconds}s")
        return CycleResult(cycle, "video", "PASS", elapsed, "completed")

    except Exception as e:
        if tracker_enabled:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
        elapsed = time.time() - started
        return CycleResult(cycle, "video", "FAIL", elapsed, f"exception: {e}")
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def _iter_descendants(widget: tk.Misc):
    for child in widget.winfo_children():
        yield child
        yield from _iter_descendants(child)


def _drive_interactive(
    window: InteractiveTaskWindow,
    drive_state: dict,
    answer_delay_seconds: float,
) -> None:
    if not window.winfo_exists() or getattr(window, "_completion_started", False):
        return

    section = getattr(window, "current_section", None)

    if section == "demographics":
        if hasattr(window, "_age_var"):
            window._age_var.set("30")
        if hasattr(window, "_gender_var"):
            window._gender_var.set("Prefer not to say")
        if hasattr(window, "_contacts_var"):
            window._contacts_var.set("No")
        if hasattr(window, "_glasses_var"):
            window._glasses_var.set("No")
        window._demographics_next()

    elif section == "sande":
        now_ms = int((time.time() - window.start_time) * 1000) if window.start_time else 0
        window.sande_responses["frequency"] = 40
        window.sande_responses["severity"] = 35
        window.sande_time["frequency"] = now_ms
        window.sande_time["severity"] = now_ms
        window._sande_next()

    elif section == "osdi":
        now_ms = int((time.time() - window.start_time) * 1000) if window.start_time else 0
        for i in range(1, 7):
            key = f"osdi_{i}"
            window.osdi_responses[key] = 1
            window.osdi_time[key] = now_ms
        window._osdi_next()

    elif section == "trivia":
        q_idx = getattr(window, "current_question_index", -1)
        now = time.time()

        if drive_state.get("last_question_index") != q_idx:
            drive_state["last_question_index"] = q_idx
            drive_state["question_seen_at"] = now
            return

        if (now - drive_state.get("question_seen_at", now)) < max(0.0, answer_delay_seconds):
            return

        buttons = []
        for w in _iter_descendants(window.content_container):
            if isinstance(w, tk.Button):
                try:
                    state = str(w.cget("state"))
                    if state != "disabled":
                        buttons.append(w)
                except Exception:
                    continue

        if buttons:
            # Pick one valid option each question to exercise MCQ response path.
            random.choice(buttons).invoke()
            drive_state["question_seen_at"] = now


def _run_interactive_cycle(
    cycle: int,
    trivia_file: str,
    duration_seconds: int,
    timeout_seconds: int,
    enable_demographics: bool,
    enable_sande: bool,
    enable_osdi: bool,
    answer_delay_seconds: float,
    repo_root: str,
    tracker_enabled: bool,
    order_code: str,
) -> CycleResult:
    started = time.time()
    root = _mk_root()

    timed_out = {"value": False}
    drive_error = {"value": ""}
    drive_state = {"last_question_index": None, "question_seen_at": 0.0}

    try:
        window = InteractiveTaskWindow(
            root,
            trivia_file=trivia_file,
            duration_seconds=duration_seconds,
            participant_name=f"StressUser{cycle:02d}",
            order_code="ITEST",
            save_dir="",
            on_ready_callback=(
                (lambda name=_recording_name(cycle, order_code, "I"):
                    _send_tracker_command(repo_root, f"START_RECORDING {name}"))
                if tracker_enabled else None
            ),
            enable_sande=enable_sande,
            enable_osdi=enable_osdi,
            enable_demographics=enable_demographics,
        )

        def step_drive() -> None:
            if not window.winfo_exists():
                return
            try:
                _drive_interactive(window, drive_state, answer_delay_seconds)
            except Exception as e:
                drive_error["value"] = f"autodrive exception: {e}"
                try:
                    window.destroy()
                except Exception:
                    pass
                return
            root.after(120, step_drive)

        def on_timeout() -> None:
            timed_out["value"] = True
            if window.winfo_exists():
                try:
                    window.destroy()
                except Exception:
                    pass

        root.after(250, step_drive)
        timeout_id = root.after(timeout_seconds * 1000, on_timeout)
        root.wait_window(window)
        try:
            root.after_cancel(timeout_id)
        except Exception:
            pass

        elapsed = time.time() - started
        if tracker_enabled:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
        if drive_error["value"]:
            return CycleResult(cycle, "interactive", "FAIL", elapsed, drive_error["value"])
        if timed_out["value"]:
            return CycleResult(cycle, "interactive", "FAIL", elapsed, f"timeout>{timeout_seconds}s")
        return CycleResult(cycle, "interactive", "PASS", elapsed, "completed")

    except Exception as e:
        if tracker_enabled:
            try:
                _send_tracker_command(repo_root, "STOP_RECORDING")
            except Exception:
                pass
        elapsed = time.time() - started
        return CycleResult(cycle, "interactive", "FAIL", elapsed, f"exception: {e}")
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def _write_reports(results: list[CycleResult], out_dir: str) -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    stamp = _now_stamp()

    csv_path = os.path.join(out_dir, f"{stamp}-stress-results.csv")
    txt_path = os.path.join(out_dir, f"{stamp}-stress-summary.txt")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["cycle", "task", "status", "elapsed_seconds", "detail"])
        for r in results:
            writer.writerow([r.cycle, r.task, r.status, f"{r.elapsed_seconds:.3f}", r.detail])

    total = len(results)
    passed = len([r for r in results if r.status == "PASS"])
    failed = total - passed

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("Stress Test Summary\n")
        f.write("===================\n\n")
        f.write(f"Total cycles: {total}\n")
        f.write(f"Passed: {passed}\n")
        f.write(f"Failed: {failed}\n\n")

        by_task: dict[str, list[CycleResult]] = {}
        for r in results:
            by_task.setdefault(r.task, []).append(r)

        for task_name, task_results in by_task.items():
            t_total = len(task_results)
            t_pass = len([r for r in task_results if r.status == "PASS"])
            t_fail = t_total - t_pass
            avg_elapsed = sum(r.elapsed_seconds for r in task_results) / t_total if t_total else 0
            f.write(f"Task: {task_name}\n")
            f.write(f"  total={t_total}, pass={t_pass}, fail={t_fail}, avg_elapsed={avg_elapsed:.2f}s\n")

        f.write("\nFailures\n")
        f.write("--------\n")
        failures = [r for r in results if r.status != "PASS"]
        if not failures:
            f.write("None\n")
        else:
            for r in failures:
                f.write(f"Cycle {r.cycle} [{r.task}] {r.detail}\n")

    return csv_path, txt_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Automated stress test cycles for Video/Interactive task windows")
    parser.add_argument("--cycles", type=int, default=10, help="Number of cycles to run per selected task")
    parser.add_argument("--tasks", choices=["reading", "video", "interactive", "both", "all"], default="all")

    parser.add_argument("--reading-source", type=str, default="", help="Reading URL or first local story file path")
    parser.add_argument("--video-file", type=str, default="", help="Path to video file (optional; falls back to launcher_config)")
    parser.add_argument("--trivia-file", type=str, default="", help="Path to trivia JSON (optional; falls back to launcher_config/default)")

    parser.add_argument("--task-duration", type=int, default=20, help="Duration in seconds used for every task in each cycle")
    parser.add_argument("--reading-auto-advance", type=float, default=1.5, help="Auto-next interval seconds during reading stress")
    parser.add_argument("--interactive-answer-delay", type=float, default=0.8, help="Delay before auto-answering each trivia MCQ")

    parser.add_argument("--timeout-video", type=int, default=20, help="Per-cycle hard timeout for video")
    parser.add_argument("--timeout-interactive", type=int, default=25, help="Per-cycle hard timeout for interactive")

    parser.add_argument("--out-dir", type=str, default="", help="Directory for stress reports")
    parser.add_argument("--with-tracker", action="store_true", help="Run the real eye tracker and recording IPC during each stress cycle")
    parser.add_argument("--tracker-visible", action="store_true", help="Keep the tracker preview window visible instead of running headless")
    parser.add_argument("--tracker-ready-timeout", type=float, default=12.0, help="Seconds to wait for tracker ready file")
    parser.add_argument("--tracker-shutdown-timeout", type=float, default=6.0, help="Seconds to wait for tracker shutdown before force kill")

    parser.add_argument("--disable-demographics", action="store_true")
    parser.add_argument("--disable-sande", action="store_true")
    parser.add_argument("--disable-osdi", action="store_true")

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = os.path.dirname(os.path.abspath(__file__))

    out_dir = args.out_dir or os.path.join(repo_root, "stress_reports")

    reading_source, video_file, trivia_file = _resolve_default_paths(
        repo_root,
        args.video_file.strip() or None,
        args.trivia_file.strip() or None,
        args.reading_source.strip() or None,
    )

    reading_source = reading_source or ""
    video_file = video_file or ""
    trivia_file = trivia_file or ""

    run_reading = args.tasks in ("reading", "all")
    run_video = args.tasks in ("video", "both", "all")
    run_interactive = args.tasks in ("interactive", "both", "all")

    task_duration = max(1, int(args.task_duration))

    if run_reading and not reading_source:
        print("[ERROR] Reading source not found. Provide --reading-source or set task_reading in launcher_config.json")
        return 2

    reading_story_files: list[str] = []
    if run_reading:
        if reading_source.startswith(("http://", "https://")):
            print("[ERROR] Reading stress requires downloaded local stories (.html), not a URL source")
            return 2
        reading_story_files = _resolve_local_story_files(repo_root, reading_source)
        if not reading_story_files:
            print("[ERROR] No local .html stories found for reading stress run")
            return 2
        if len(reading_story_files) < 2:
            print("[ERROR] Reading stress needs at least 2 local stories to verify next-story advancement")
            return 2
        # Always start from the first local story for deterministic progression checks.
        reading_source = reading_story_files[0]

    if run_video and not video_file:
        print("[ERROR] Video file not found. Provide --video-file or set task_video in launcher_config.json")
        return 2

    if run_interactive and not trivia_file:
        print("[ERROR] Trivia file not found. Provide --trivia-file or set task_interactive in launcher_config.json")
        return 2

    enable_demographics = not args.disable_demographics
    enable_sande = not args.disable_sande
    enable_osdi = not args.disable_osdi

    if run_interactive and not (enable_demographics or enable_sande or enable_osdi):
        print("[WARN] All questionnaire sections are disabled; interactive run will start directly at trivia")

    results: list[CycleResult] = []
    tracker_out_dir = os.path.join(out_dir, "tracker_csv")
    if args.with_tracker:
        os.makedirs(tracker_out_dir, exist_ok=True)

    enabled_tasks = []
    if run_reading:
        enabled_tasks.append("reading")
    if run_video:
        enabled_tasks.append("video")
    if run_interactive:
        enabled_tasks.append("interactive")

    print("Starting stress test...")
    print(f"  cycles={args.cycles}, tasks={args.tasks}")
    print(f"  task_duration={task_duration}s")
    print(f"  tracker={'on' if args.with_tracker else 'off'}")
    if run_reading:
        print(f"  reading_source={reading_source}")
        print(f"  reading_story_count={len(reading_story_files)}")
        print(f"  reading_auto_advance={args.reading_auto_advance}s")
    if run_video:
        print(f"  video_file={video_file}")
    if run_interactive:
        print(f"  trivia_file={trivia_file}")

    for cycle in range(1, args.cycles + 1):
        cycle_tasks = list(enabled_tasks)
        random.shuffle(cycle_tasks)
        cycle_order_code = "".join(task[0].upper() for task in cycle_tasks) or "STRESS"
        print(f"[cycle {cycle:02d}] order={cycle_order_code} ({', '.join(cycle_tasks)})")

        tracker_process = None
        if args.with_tracker:
            participant_name = f"StressUser{cycle:02d}"
            tracker_process, tracker_err = _launch_tracker(
                repo_root=repo_root,
                participant_name=participant_name,
                order_code=cycle_order_code,
                out_dir=tracker_out_dir,
                timeout_seconds=args.tracker_ready_timeout,
                visible=args.tracker_visible,
            )
            if tracker_process is None:
                results.append(CycleResult(cycle, "tracker", "FAIL", 0.0, tracker_err))
                print(f"[cycle {cycle:02d}] tracker: FAIL - {tracker_err}")
                continue

        for task in cycle_tasks:
            if task == "reading":
                r = _run_reading_cycle(
                    cycle=cycle,
                    reading_source=reading_source,
                    total_stories=len(reading_story_files),
                    duration_seconds=task_duration,
                    auto_advance_seconds=args.reading_auto_advance,
                    repo_root=repo_root,
                    tracker_enabled=args.with_tracker,
                    order_code=cycle_order_code,
                )
            elif task == "video":
                r = _run_video_cycle(
                    cycle=cycle,
                    video_file=video_file,
                    duration_seconds=task_duration,
                    timeout_seconds=args.timeout_video,
                    repo_root=repo_root,
                    tracker_enabled=args.with_tracker,
                    order_code=cycle_order_code,
                )
            else:
                r = _run_interactive_cycle(
                    cycle=cycle,
                    trivia_file=trivia_file,
                    duration_seconds=task_duration,
                    timeout_seconds=args.timeout_interactive,
                    enable_demographics=enable_demographics,
                    enable_sande=enable_sande,
                    enable_osdi=enable_osdi,
                    answer_delay_seconds=args.interactive_answer_delay,
                    repo_root=repo_root,
                    tracker_enabled=args.with_tracker,
                    order_code=cycle_order_code,
                )
            results.append(r)
            print(f"[cycle {cycle:02d}] {task}: {r.status} ({r.elapsed_seconds:.2f}s) - {r.detail}")

        if args.with_tracker:
            ok, shutdown_msg = _shutdown_tracker(repo_root, tracker_process, args.tracker_shutdown_timeout)
            if not ok:
                results.append(CycleResult(cycle, "tracker", "FAIL", 0.0, shutdown_msg))
                print(f"[cycle {cycle:02d}] tracker-shutdown: FAIL - {shutdown_msg}")
            else:
                print(f"[cycle {cycle:02d}] tracker-shutdown: PASS - cleaned up")

    csv_path, txt_path = _write_reports(results, out_dir)

    failed = len([r for r in results if r.status != "PASS"])
    print("\nStress test complete.")
    print(f"  CSV: {csv_path}")
    print(f"  Summary: {txt_path}")
    print(f"  Failures: {failed}/{len(results)}")

    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print("[FATAL] Unhandled exception in stress runner")
        print(traceback.format_exc())
        sys.exit(99)
