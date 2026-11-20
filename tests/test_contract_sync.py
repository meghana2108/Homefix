import re
from pathlib import Path
from typing import get_args

from app import contracts
from app.contracts import EVENT_TYPES, RefusalReason, Stage

TS = (Path(__file__).resolve().parents[1] / "frontend/src/contract.ts").read_text()

EVENT_CLASSES = [contracts.Status, contracts.Token, contracts.Transcript, contracts.SoundLabels,
                 contracts.Frames, contracts.Citation, contracts.CodeResult, contracts.Clarify,
                 contracts.Refusal,
                 contracts.Error, contracts.Final]


def _array(name: str) -> tuple[str, ...]:
    m = re.search(rf"export const {name} = \[(.*?)\] as const", TS, re.DOTALL)
    assert m, f"{name} not found in contract.ts"
    return tuple(re.findall(r'"([^"]*)"', m.group(1)))


def test_literal_lists_match():
    assert _array("STAGES") == get_args(Stage)
    assert _array("REFUSAL_REASONS") == get_args(RefusalReason)
    assert _array("EVENT_TYPES") == EVENT_TYPES


def test_event_fields_match():
    for cls in EVENT_CLASSES:
        m = re.search(rf"export interface {cls.__name__}Event \{{(.*?)\}}", TS, re.DOTALL)
        assert m, f"{cls.__name__}Event not found in contract.ts"
        fields = set(re.findall(r"^\s*(\w+)\??\s*:", m.group(1).replace(";", ";\n"), re.MULTILINE))
        assert fields == set(cls.model_fields), cls.__name__


def test_clarify_option_fields_match():
    m = re.search(r"export interface ClarifyOption \{(.*?)\}", TS, re.DOTALL)
    assert m, "ClarifyOption not found in contract.ts"
    fields = set(re.findall(r"^\s*(\w+)\??\s*:", m.group(1).replace(";", ";\n"), re.MULTILINE))
    assert fields == set(contracts.ClarifyOption.model_fields)
