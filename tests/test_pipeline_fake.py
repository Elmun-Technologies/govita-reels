"""Pipeline orkestratsiyasi: soxta claude + silent TTS + draft render + soxta Telegram.
Tekshiriladi: bosqichlar ketma-ketligi, compliance FIX sikli, resume marker'lar, Telegram yuborish.

    pytest tests/test_pipeline_fake.py -m slow -s
"""
import os
import shutil
from pathlib import Path

import pytest

from agency import pipeline, telegram
from agency.config import RunPaths
from tests.test_e2e_render import CHROME, run_dir  # noqa: F401  (fixture: test media)

pytestmark = [pytest.mark.slow, pytest.mark.skipif(not CHROME, reason="Chrome topilmadi")]


def test_pipeline_end_to_end(run_dir, monkeypatch, tmp_path):  # noqa: F811
    paths, _media = run_dir
    paths.script.unlink()
    monkeypatch.setenv("CLAUDE_BIN", str(Path(__file__).parent / "fake_claude.py"))
    monkeypatch.setenv("TTS_PROVIDER", "silent")
    monkeypatch.setenv("RENDER_QUALITY", "draft")
    monkeypatch.setenv("CHROMIUM_PATH", CHROME)
    monkeypatch.setenv("HYPERFRAMES_BROWSER_PATH", CHROME)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "1")
    sent = []
    monkeypatch.setattr(telegram, "send_video", lambda *a, **k: sent.append(("video", a)))
    monkeypatch.setattr(telegram, "send_document", lambda *a, **k: sent.append(("doc", a)))
    monkeypatch.setattr(telegram, "send_message", lambda text, **k: sent.append(("msg", text)))

    pipeline.run_pipeline(paths.date)

    for st in pipeline.STAGES:
        assert paths.done(st).exists(), st
    assert (paths.dir / ".fake_compliance").read_text() == "2"  # FIX → qayta copy → PASS
    assert (paths.dir / ".fake_copywriter").read_text() == "2"
    assert [k for k, _ in sent] == ["video", "doc", "msg", "msg", "msg"]
    report = sent[-1][1]
    assert "Hisobot" in report and "Compliance:</b> PASS" in report
    if os.environ.get("E2E_KEEP"):
        shutil.copy2(paths.final_video, Path(os.environ["E2E_KEEP"]) / "pipeline_final.mp4")
