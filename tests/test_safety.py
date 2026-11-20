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
    ("the wire is showing through the paint", "exposed_wires"),
    ("wires are showing through the paint", "exposed_wires"),
    ("the cord is showing through the paint", "exposed_wires"),
    ("exposed copper behind the outlet", "exposed_wires"),
    ("rust is showing through the paint on the washer", None),
    ("wood is showing through the paint and a wire is poking out", "exposed_wires"),
    ("a wire is poking through the wall", "exposed_wires"),
    ("copper is protruding from the outlet", "exposed_wires"),
    ("the wires are protruding from the switch", "exposed_wires"),
    ("a nail is poking out of the shelf", None),
    ("the drawer is protruding", None),
    ("the wiring is visible behind the outlet cover", "exposed_wires"),
    ("the wiring is showing", "exposed_wires"),
    ("wire hanger poking out of the closet", None),
    ("the wire shelf is protruding from the wall", None),
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


def _rules():
    with open(ROOT / "config/safety_rules.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_refusal_message_verbatim():
    r = refusal_for(check("I smell gas"))
    assert r.message == _rules()["messages"]["gas"]
    assert r.reason == "safety"
    assert r.category == "gas"


def test_every_category_has_its_own_message():
    rules = _rules()
    cats = set(rules["patterns"]) | set(rules["alarm_active"])
    assert cats <= set(rules["messages"]), cats - set(rules["messages"])
    for cat, msg in rules["messages"].items():
        assert msg.startswith("⚠️ This could be dangerous. "), cat  # the UI card drops this opening line
        assert msg.endswith("HomeFix won't give repair steps for this situation."), cat


def _first_step(message):
    return message.lower().removeprefix("⚠️ this could be dangerous. ").split(". ")[0]


def test_gas_says_leave_and_never_touch_switches():
    msg = refusal_for(check("I smell gas in the kitchen")).message.lower()
    first = _first_step(msg)
    assert "switch" in first and ("don't" in first or "do not" in first)  # no switches is the first thing said
    assert "unplug" not in msg and "switch it off" not in msg and "turn off its breaker" not in msg
    assert "leave" in msg and "from outside" in msg


def test_co_alarm_sound_gets_the_gas_message():
    hit = check_sound(_labels("carbon monoxide alarm", 0.8), 0.5)
    assert hit is not None and hit.category == "gas"
    assert "carbon monoxide" in refusal_for(hit).message.lower()


@pytest.mark.parametrize("text,must", [
    ("smoke is coming out of the toaster", ["911", "get everyone out"]),
    ("sparks came out of the outlet", ["don't touch", "breaker"]),
    ("there are exposed wires behind the fridge", ["don't touch", "breaker"]),
    ("water is leaking onto the outlet", ["don't touch", "breaker"]),
    ("I got a shock from the toaster", ["don't touch", "911"]),
])
def test_category_messages_fit_the_danger(text, must):
    msg = refusal_for(check(text)).message.lower()
    for word in must:
        assert word in msg, (text, word)


def test_unknown_category_falls_back_to_default():
    from app.safety import SafetyHit
    assert refusal_for(SafetyHit("something_new", "x")).message == _rules()["message"]


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
