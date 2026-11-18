#!/usr/bin/env python3
"""Soxta `claude` CLI — pipeline orkestratsiyasini Max limitisiz test qilish uchun.
Agent nomiga qarab fixture'larni run papkasiga yozadi va Claude Code JSON chiqishini taqlid qiladi.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
args = sys.argv[1:]
task = args[args.index("-p") + 1]
agent = args[args.index("--agent") + 1]
run = Path(re.search(r"(/[^\s]*runs/\d{4}-\d{2}-\d{2})", task).group(1))
counter = run / f".fake_{agent}"
n = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(n))

if agent == "researcher":
    shutil.copy2(FIX / "brief.json", run / "brief.json")
elif agent == "copywriter":
    shutil.copy2(FIX / "script.json", run / "script.json")
elif agent == "compliance":
    # 1-marta FIX qaytaradi (sikl testi), keyin PASS
    data = json.loads((FIX / "compliance.json").read_text())
    if n == 1:
        data = {"status": "FIX", "issues": [{"scene": 6, "problem": "test", "fix": "test"}], "checked_claims": []}
    (run / "compliance.json").write_text(json.dumps(data))
elif agent == "asset-hunter":
    clips = sorted((ROOT / "bank" / "_e2e").glob("clip*.mp4"))
    align = json.loads((run / "alignment.json").read_text())
    scenes = [{"id": s["id"], "items": [{"key": f"test:{i}", "path": str(clips[i % len(clips)].relative_to(ROOT)),
               "kind": "video", "role": "primary", "license": "test"}]} for i, s in enumerate(align["scenes"])]
    (run / "assets.json").write_text(json.dumps({"scenes": scenes}))
elif agent == "editor":
    assets = json.loads((run / "assets.json").read_text())
    tl = {"scenes": [{"id": s["id"], "shots": [{"asset": s["items"][0]["path"], "motion": "zoom-in"}]}
                     for s in assets["scenes"]],
          "music": None, "end_card": {"duration": 1.6, "text": "govita.uz"},
          "cover": {"asset": assets["scenes"][0]["items"][0]["path"], "headline": "Test *cover*"}}
    tl["scenes"][0]["overlay"] = {"text": "Bu *dangasalik* emas", "style": "hook"}
    (run / "timeline.json").write_text(json.dumps(tl))
    subprocess.run([sys.executable, "-m", "agency.tools.build_composition", "--run", str(run)], check=True, cwd=ROOT)
elif agent == "qa":
    shutil.copy2(FIX / "qa.json", run / "qa.json")

print(json.dumps({"type": "result", "subtype": "success", "is_error": False, "num_turns": 3,
                  "result": f"fake {agent} ok", "total_cost_usd": 0.01, "duration_ms": 1000,
                  "usage": {"input_tokens": 100, "output_tokens": 50}}))
