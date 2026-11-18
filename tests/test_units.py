"""Tez unit testlar: schema, TTS so'z alignment, subtitr bo'laklash, g'oya reytingi."""
from pathlib import Path

import pytest

from agency.pipeline import _ranked_ideas
from agency.tools.build_composition import chunk_words
from agency.tools.tts import build_text, words_from_chars
from agency.util import read_json
from agency.validate import ContractError, validate

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name", ["brief", "script", "compliance", "qa"])
def test_fixtures_valid(name):
    validate(name, FIX / f"{name}.json")


def test_invalid_script_rejected(tmp_path):
    bad = read_json(FIX / "script.json")
    bad["scenes"][0]["role"] = "intro"
    p = tmp_path / "script.json"
    p.write_text(__import__("json").dumps(bad), encoding="utf-8")
    with pytest.raises(ContractError):
        validate("script", p)


def test_build_text_spans():
    text, spans = build_text([{"id": 1, "voiceover": "Salom dunyo."}, {"id": 2, "voiceover": "Ikkinchi gap"}])
    assert text == "Salom dunyo. Ikkinchi gap"
    assert spans == [(1, 0, 12), (2, 13, 25)]


def test_words_from_chars():
    text = "Ab cd"
    starts = [0.0, 0.1, 0.2, 0.3, 0.4]
    ends = [0.1, 0.2, 0.3, 0.4, 0.5]
    words = words_from_chars(list(text), starts, ends, [(1, 0, 2), (2, 3, 5)])
    assert words == [{"text": "Ab", "start": 0.0, "end": 0.2, "scene_id": 1},
                     {"text": "cd", "start": 0.3, "end": 0.5, "scene_id": 2}]


def test_chunk_words_breaks_on_punct_and_scene():
    w = lambda t, s, e, sc=1: {"text": t, "start": s, "end": e, "scene_id": sc}
    words = [w("Bir", 0, .2), w("ikki.", .2, .4), w("uch", .5, .7), w("to'rt", .7, .9), w("besh", .9, 1.1),
             w("olti", 1.1, 1.3, 2)]
    chunks = chunk_words(words)
    assert [[x["text"] for x in c] for c in chunks] == [["Bir", "ikki."], ["uch", "to'rt", "besh"], ["olti"]]


def test_ranked_ideas_prefers_chosen():
    brief = read_json(FIX / "brief.json")
    assert _ranked_ideas(brief)[0] == "A"
    brief["chosen"] = "C"
    assert _ranked_ideas(brief)[0] == "C"
