# Bad Apple text-mask terminal renderer

This project renders a Bad Apple-style silhouette animation using a repeating `bad apple` text field, turning the subject into negative space instead of drawing the silhouette with ASCII glyphs.

## Features

- Decodes a source video with OpenCV
- Resizes frames to the terminal dimensions while maintaining aspect ratio
- Uses a border-based polarity heuristic to keep the silhouette consistent
- Converts the frame to a binary mask and renders it as empty holes in a repeating stream of `bad apple`
- Updates the terminal in place with ANSI cursor positioning
- Falls back to a synthetic demo animation if no source video is present

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Place your source video somewhere such as `assets/bad_apple.mp4` and run:

```bash
python main.py --video assets/bad_apple.mp4 --fps 30
```

Audio is played in sync with the terminal animation through `ffplay` when it is available on the system. To disable audio explicitly:

```bash
python main.py --video assets/bad_apple.mp4 --fps 30 --no-audio
```

If you do not have a source video yet, run the built-in demo instead:

```bash
python main.py --demo --fps 18 --frames 60
```

For CI or smoke testing without cursor-control escapes:

```bash
python main.py --demo --headless --frames 3
```

## Notes

- The text stream repeats continuously as `bad apple`, and the mask blanks out the silhouette regions.
- The terminal is resized automatically at render time.
- Audio playback is handled externally via `ffplay` for synchronized source-video playback; if `ffplay` is missing, the renderer still works without sound.

## Sample output

```text
bad applebad applebad applebad applebad apple
bad applebad apple       lebad applebad apple
bad applebad ap             applebad applebad
bad applebad                   bad applebad ap
bad applebad app             applebad applebad
bad applebad appleba       applebad applebad ap
bad applebad applebad applebad applebad apple
```
