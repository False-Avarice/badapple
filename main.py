#!/usr/bin/env python3
import argparse
import math
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

TEXT_STREAM = "bad apple"


class PlaybackInterrupted(Exception):
    pass


def start_audio_player(video_path: str) -> subprocess.Popen | None:
    ffplay = shutil.which("ffplay")
    if ffplay is None:
        return None

    try:
        proc = subprocess.Popen(
            [ffplay, "-nodisp", "-loglevel", "quiet", "-autoexit", video_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        return proc
    except OSError:
        return None


def handle_broken_pipe() -> None:
    try:
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull_fd, sys.stdout.fileno())
    except Exception:
        pass
    try:
        sys.stdout.close()
    except Exception:
        pass


def terminal_size() -> tuple[int, int]:
    cols, rows = shutil.get_terminal_size(fallback=(100, 30))
    return max(20, cols), max(10, rows)


def build_text_frame(mask: np.ndarray, offset: int = 0, row_stride: int = 7) -> list[str]:
    """Convert a binary silhouette mask into a repeating bad-apple text field."""
    height, width = mask.shape
    stream = (TEXT_STREAM * (height * width + len(TEXT_STREAM) * 4))
    rows: list[str] = []

    for y in range(height):
        chars: list[str] = []
        row_offset = offset
        for x in range(width):
            if mask[y, x] > 0:
                chars.append(" ")
            else:
                idx = (row_offset + x) % len(stream)
                chars.append(stream[idx])
        rows.append("".join(chars))

    return rows


def resize_to_terminal(gray: np.ndarray, width: int, height: int) -> np.ndarray:
    if gray.ndim != 2:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    frame_h, frame_w = gray.shape[:2]
    if frame_h == 0 or frame_w == 0:
        return np.zeros((height, width), dtype=np.uint8)

    if width <= 0 or height <= 0:
        return gray

    char_aspect = 1.7
    target_w = max(1, width)
    target_h = max(1, int(height * 0.9))
    scale = min((target_w * 0.95) / frame_w, (target_h * char_aspect * 0.95) / frame_h)
    new_w = max(1, int(frame_w * scale))
    new_h = max(1, int(frame_h * scale))

    resized = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((height, width), dtype=np.uint8)
    y0 = max(0, (height - new_h) // 2)
    x0 = max(0, (width - new_w) // 2)
    canvas[y0 : y0 + new_h, x0 : x0 + new_w] = resized
    return canvas


def compute_silhouette_mask(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray = resize_to_terminal(gray, width, height)

    border = np.concatenate((gray[0, :], gray[-1, :], gray[:, 0], gray[:, -1]))
    bg_value = float(np.mean(border))
    threshold_value, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    if bg_value > 127:
        mask = gray < threshold_value
    else:
        mask = gray > threshold_value

    mask = mask.astype(np.uint8)
    mask = cv2.medianBlur(mask, 3)
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    return mask > 0


def build_demo_mask(width: int, height: int, frame_index: int) -> np.ndarray:
    y_coords, x_coords = np.indices((height, width), dtype=np.float32)
    cx = width / 2.0 + 12.0 * math.sin(frame_index / 12.0)
    cy = height / 2.0 + 6.0 * math.cos(frame_index / 10.0)
    r = 6.0 + 4.0 * math.sin(frame_index / 8.0)
    mask = ((x_coords - cx) ** 2 + (y_coords - cy) ** 2) <= (r**2)
    mask = mask | (((x_coords - (width * 0.35 + 10 * math.sin(frame_index / 9.0))) ** 2 + (y_coords - (height * 0.7)) ** 2) <= 24**2)
    mask = mask | (((x_coords - (width * 0.65 - 10 * math.sin(frame_index / 9.0))) ** 2 + (y_coords - (height * 0.7)) ** 2) <= 24**2)
    return mask.astype(np.uint8)


def render_frame(mask: np.ndarray, offset: int = 0) -> str:
    rows = build_text_frame(mask, offset=offset)
    return "\n".join(rows)


def play_video(video_path: str, fps: float, headless: bool = False, loop: bool = True, max_frames: int | None = None, audio_enabled: bool = True):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video: {video_path}")

    if fps <= 0:
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)

    audio_proc = start_audio_player(video_path) if audio_enabled else None
    cols, rows = terminal_size()
    frame_count = 0
    start_monotonic = time.monotonic()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                if not loop:
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            if max_frames is not None and frame_count >= max_frames:
                break

            target_time = start_monotonic + (frame_count / fps)
            now = time.monotonic()
            if now < target_time:
                time.sleep(target_time - now)

            cols, rows = terminal_size()
            mask = compute_silhouette_mask(frame, cols, rows)
            rendered_lines = build_text_frame(mask, offset=frame_count * 3)
            rendered = "\n".join(rendered_lines[:rows])
            if not headless:
                sys.stdout.write("\x1b[H\x1b[2J")
                sys.stdout.write(rendered)
                sys.stdout.write("\n")
                sys.stdout.flush()
            else:
                sys.stdout.write(rendered)
                sys.stdout.write("\n---\n")
                sys.stdout.flush()

            frame_count += 1
    finally:
        cap.release()
        if audio_proc is not None:
            try:
                audio_proc.terminate()
                audio_proc.wait(timeout=2)
            except Exception:
                try:
                    audio_proc.kill()
                except Exception:
                    pass
        if not headless:
            try:
                sys.stdout.write("\x1b[?25h\x1b[0m\n")
                sys.stdout.flush()
            except BrokenPipeError:
                handle_broken_pipe()


def play_demo(fps: float, frame_limit: int | None = None, headless: bool = False):
    cols, rows = terminal_size()
    frame_count = 0
    start_monotonic = time.monotonic()

    try:
        while frame_limit is None or frame_count < frame_limit:
            mask = build_demo_mask(cols, rows, frame_count)
            rendered_lines = build_text_frame(mask, offset=frame_count * 3)
            rendered = "\n".join(rendered_lines[:rows])
            if not headless:
                sys.stdout.write("\x1b[H\x1b[2J")
                sys.stdout.write(rendered)
                sys.stdout.write("\n")
                sys.stdout.flush()
            else:
                sys.stdout.write(rendered)
                sys.stdout.write("\n---\n")
                sys.stdout.flush()

            frame_count += 1
            elapsed = time.monotonic() - start_monotonic
            target_elapsed = frame_count / fps
            if target_elapsed > elapsed:
                time.sleep(target_elapsed - elapsed)
    finally:
        if not headless:
            try:
                sys.stdout.write("\x1b[?25h\x1b[0m\n")
                sys.stdout.flush()
            except BrokenPipeError:
                handle_broken_pipe()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Play the Bad Apple silhouette as a negative-space text mask.")
    parser.add_argument("--video", default="assets/bad_apple.mp4", help="Path to a Bad Apple video file. Falls back to demo mode if it is missing.")
    parser.add_argument("--fps", type=float, default=30.0, help="Playback rate in frames per second.")
    parser.add_argument("--demo", action="store_true", help="Render a synthetic demo animation even if a video file is missing.")
    parser.add_argument("--frames", type=int, default=None, help="Limit the number of frames for demo playback or a single pass of the source video.")
    parser.add_argument("--headless", action="store_true", help="Print frames without terminal cursor control for CI or smoke tests.")
    parser.add_argument("--audio", dest="audio", action=argparse.BooleanOptionalAction, default=True, help="Play the source video's audio via ffplay while the terminal frames advance.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.headless:
        sys.stdout.write("\x1b[?25l")
        sys.stdout.flush()

    video_path = Path(args.video)
    should_demo = args.demo or not video_path.exists()

    try:
        if should_demo:
            play_demo(args.fps, frame_limit=args.frames, headless=args.headless)
        else:
            play_video(str(video_path), fps=args.fps, headless=args.headless, max_frames=args.frames, audio_enabled=args.audio)
    except KeyboardInterrupt:
        return 0
    except BrokenPipeError:
        handle_broken_pipe()
        return 0
    except FileNotFoundError as exc:
        print(f"Video file not found: {exc}")
        return 1
    finally:
        if not args.headless:
            try:
                sys.stdout.write("\x1b[?25h\x1b[0m\n")
                sys.stdout.flush()
            except BrokenPipeError:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
