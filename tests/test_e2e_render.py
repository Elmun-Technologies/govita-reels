"""To'liq lokal render testi (Claude, ElevenLabs, internetsiz):
silent TTS → build_composition → HyperFrames render → cover → qa_check.

    pytest tests/test_e2e_render.py -m slow -s
"""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from agency.config import BANK_DIR, RUNS_DIR, RunPaths

FIX = Path(__file__).parent / "fixtures"
DATE = "2099-01-01"
CHROME = os.environ.get("CHROMIUM_PATH") or shutil.which("chromium") or shutil.which("google-chrome")

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not CHROME, reason="Chrome topilmadi")]


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


@pytest.fixture()
def run_dir():
    paths = RunPaths(DATE).ensure()
    media = BANK_DIR / "_e2e"
    media.mkdir(parents=True, exist_ok=True)
    colors = ["0x1E5631", "0x2E4057", "0x8B5E34", "0x4A2C5E", "0x0F3D2A", "0x7A1F1F"]
    for i, c in enumerate(colors):
        _ff("-f", "lavfi", "-i", f"testsrc2=size=1080x1920:rate=30:duration=6",
            "-f", "lavfi", "-i", f"color=c={c}:size=1080x1920:rate=30:duration=6",
            "-filter_complex", "[0][1]blend=all_mode=overlay:all_opacity=0.6", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "ultrafast", media / f"clip{i}.mp4")
    _ff("-f", "lavfi", "-i", "color=c=0x335544:size=1080x1920", "-frames:v", "1", media / "photo0.jpg")
    _ff("-f", "lavfi", "-i", "sine=frequency=220:duration=90", "-f", "lavfi", "-i", "sine=frequency=330:duration=90",
        "-filter_complex", "amix=inputs=2", "-q:a", "5", media / "music.mp3")
    shutil.copy2(FIX / "script.json", paths.script)
    yield paths, media
    shutil.rmtree(paths.dir, ignore_errors=True)
    shutil.rmtree(media, ignore_errors=True)


def test_full_render(run_dir, monkeypatch):
    paths, media = run_dir
    env = {**os.environ, "TTS_PROVIDER": "silent", "CHROMIUM_PATH": CHROME, "HYPERFRAMES_BROWSER_PATH": CHROME}
    subprocess.run(["python3", "-m", "agency.tools.tts", "--run", str(paths.dir)], check=True, env=env)
    alignment = json.loads(paths.alignment.read_text())
    assert alignment["provider"] == "silent" and len(alignment["scenes"]) == 7

    rel = lambda p: str(p.relative_to(BANK_DIR.parent))
    clips = [rel(media / f"clip{i}.mp4") for i in range(6)]
    motions = ["punch-in", "zoom-in", "pan-left", "zoom-out", "pan-right", "pan-up"]
    scenes = []
    k = 0
    for s in alignment["scenes"]:
        n = 2 if (s["end"] - s["start"]) > 4 else 1
        shots = []
        for j in range(n):
            shots.append({"asset": clips[k % 6], "motion": motions[k % 6], "transition": "flash" if k == 6 else "cut"})
            k += 1
        sc = next(x for x in json.loads(paths.script.read_text())["scenes"] if x["id"] == s["id"])
        scene = {"id": s["id"], "shots": shots}
        if sc["overlay_style"] != "none":
            scene["overlay"] = {"text": sc["on_screen_text"], "style": sc["overlay_style"]}
        scenes.append(scene)
    scenes[2]["shots"].append({"asset": rel(media / "photo0.jpg"), "kind": "photo", "motion": "zoom-in"})
    timeline = {"scenes": scenes, "music": {"file": rel(media / "music.mp3"), "volume": 0.12},
                "end_card": {"duration": 1.6, "text": "govita.uz", "subtext": "Vitaminlar uyingizgacha"},
                "cover": {"asset": clips[0], "frame_time": 1.0, "headline": "Charchoq *sababi* — quyosh?",
                          "subline": "3 ta belgini tekshiring", "tag": "Sizda ham bormi?"}}
    paths.timeline.write_text(json.dumps(timeline, ensure_ascii=False, indent=2))
    subprocess.run(["python3", "-m", "agency.validate", "timeline", str(paths.timeline)], check=True)

    out = subprocess.run(["python3", "-m", "agency.tools.build_composition", "--run", str(paths.dir)],
                         check=True, env=env, capture_output=True, text=True)
    built = json.loads(out.stdout)
    assert built["ok"] and built["captions"] > 20
    if os.environ.get("E2E_BUILD_ONLY"):
        shutil.copytree(paths.composition, os.environ["E2E_BUILD_ONLY"], dirs_exist_ok=True)
        return

    subprocess.run(["python3", "-m", "agency.tools.render", "--run", str(paths.dir)], check=True, env=env)
    subprocess.run(["python3", "-m", "agency.tools.cover", "--run", str(paths.dir)], check=True, env=env)
    out = subprocess.run(["python3", "-m", "agency.tools.qa_check", "--run", str(paths.dir)], check=True, env=env,
                         capture_output=True, text=True)
    qa = json.loads(out.stdout)
    print(json.dumps(qa, indent=2))
    keep = os.environ.get("E2E_KEEP")
    if keep:
        Path(keep).mkdir(parents=True, exist_ok=True)
        for f in (paths.final_video, paths.cover):
            shutil.copy2(f, Path(keep) / f.name)
        shutil.copytree(paths.qa_frames, Path(keep) / "qa_frames", dirs_exist_ok=True)
    assert qa["passed"], qa["checks"]
