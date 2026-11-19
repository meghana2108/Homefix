import time

import pytest
import yaml

from app.contracts import SoundLabel
from app.safety import check, check_sound, refusal_for
from app.settings import ROOT

CASES = [
    ("smoke detector keeps chirping", None),
    ("fire alarm battery is low", None),
    ("my Fire TV stick froze", None),
    ("burnt toast smell", None),
    ("water dripping from the outlet hose of the washer", None),
    ("gas stove recipe", None),
    ("Does this sofa spark joy", None),
    ("smoke detector, the battery keeps dying", None),
    ("my smoke detector. it chirps every minute", None),
    ("smoke alarm is going off and won't stop", "smoke_fire"),
    ("I smell burning plastic from the dryer", "smoke_fire"),
    ("the smoke detector chirps and I smell gas", "gas"),
    ("sparks came out of the outlet", "sparks"),
    ("frayed wire behind the fridge", "exposed_wires"),
    ("water on the floor near the outlet", "water_electric"),
    ("I got a shock from the fridge door", "shock"),
    ("the fire alarm is going off", "smoke_fire"),
    ("smoke alarm is going off, check the battery", "smoke_fire"),
    ("the fire alarm is going off. battery is low", "smoke_fire"),
    ("smoke alarm is going off. it chirps", "smoke_fire"),
    ("the fire alarm is going off, is it the battery?", "smoke_fire"),
    ("is there smoke near my smoke detector", "smoke_fire"),
    ("the co alarm went off", "gas"),
    ("my carbon monoxide detector keeps beeping", "gas"),
    ("smoke detector beeps once a minute", None),
    ("the wires are exposed behind the stove", "exposed_wires"),
    ("the cord is frayed", "exposed_wires"),
    ("my dryer smells burnt", "smoke_fire"),
    ("it smells like something is burning", "smoke_fire"),
    ("the smoke detector is burning", "smoke_fire"),
    ("the outlet is burnt and black", "smoke_fire"),
    ("the microwave keeps shorting", "sparks"),
    ("the outlet shorted out", "sparks"),
    ("I think there's a short circuit in the plug", "sparks"),
    ("the heater short-circuited", "sparks"),
    ("the power cord is too short", None),
    ("my dryer has a short cycle setting", None),
    ("can I bake shortbread in this oven", None),
    ("I burnt rice in the pot", None),
    ("how long is the washer drain hose", None),
    ('the extension cord is showing copper', "exposed_wires"),
    ('the wire is showing', "exposed_wires"),
    ('the cord looks worn and the wire is visible', "exposed_wires"),
    ('the plug is bare', "exposed_wires"),
    ('fire tv cord frayed', "exposed_wires"),
    ('the charger is burning hot', "smoke_fire"),
    ('the outlet is burning hot', "smoke_fire"),
    ('the smoke detector is burning hot', "smoke_fire"),
    ('something is burning', "smoke_fire"),
    ('smell of burning rubber', "smoke_fire"),
    ('outlet has a burn mark', "smoke_fire"),
    ('scorch marks on the outlet', "smoke_fire"),
    ('the plug is hot and discolored', "smoke_fire"),
    ('the dryer is burning', "smoke_fire"),
    ('the fridge shorted the breaker', "sparks"),
    ('my dryer shorts out', "sparks"),
    ('it short circuited my laptop', "sparks"),
    ('the wiring diagram is showing on page 4', None),
    ('the cable box is showing an error', None),
    ('cable internet is showing no signal', None),
    ('my toaster burned the bread', None),
    ('the oven burnt my cookies', None),
    ('the dryer burned my shirt', None),
    ('the dryer burnt out', None),
    ('kettle burnt the water taste', None),
    ('the stove burner is burning blue', None),
    ('the washer keeps burning through detergent', None),
    ('short on time, how do I reset the washer', None),
    ('shortest wash cycle', None),
    ('I burned dinner in the oven', None),
    ("there's a blackened spot near the plug", "smoke_fire"),
    ("copper pipes showing under the sink", None),
    ("the metal is showing through the paint on the fridge", None),
    ("there's a copper pipe visible behind the washer", None),
    ("exposed wires near the copper pipe", "exposed_wires"),
    ("the wire is showing", "exposed_wires"),
    ("the extension cord is showing copper", "exposed_wires"),
    ("bare wire touching the copper pipe", "exposed_wires"),
]


@pytest.mark.parametrize("text,category", CASES)
def test_check(text, category):
    hit = check(text)
    if category is None:
        assert hit is None
    else:
        assert hit is not None and hit.category == category


@pytest.mark.parametrize("text,category", [
    ("smoke alarm sparked and the battery is hot", "sparks"),
    ("smoke detector smells like gas, battery dead", "gas"),
    ("fire alarm: i smell gas, battery low", "gas"),
])
def test_benign_cannot_hide_danger(text, category):
    hit = check(text)
    assert hit is not None and hit.category == category


def test_refusal_message_verbatim():
    r = refusal_for(check("I smell gas"))
    with open(ROOT / "config/safety_rules.yaml", encoding="utf-8") as f:
        assert r.message == yaml.safe_load(f)["message"]
    assert r.reason == "safety"
    assert r.category == "gas"


def _labels(top, score):
    return [SoundLabel(label=top, score=score), SoundLabel(label="beep", score=0.1),
            SoundLabel(label="alarm", score=0.05)]


def test_check_sound():
    hit = check_sound(_labels("smoke alarm beeping loudly", 0.71), 0.5)
    assert hit is not None and hit.category == "smoke_fire"
    assert check_sound(_labels("smoke alarm beeping loudly", 0.32), 0.5) is None
    assert check_sound(_labels("washing machine beeping", 0.9), 0.5) is None
    assert check_sound([], 0.5) is None


def test_check_is_fast():
    t = time.perf_counter()
    for _ in range(1000):
        check("how many mugs are on the shelf")
    assert time.perf_counter() - t < 0.5
