"""Unit tests for the compliance decision engine (pure logic)."""
from app.ai.base import Detection
from app.models import PPE_ITEMS
from app.services.compliance import Requirement, evaluate, severity_for

ALL_REQUIRED = {i: Requirement(True) for i in PPE_ITEMS}


def dets(**overrides):
    out = {i: Detection(i, True, 0.95) for i in PPE_ITEMS}
    for k, v in overrides.items():
        out[k] = Detection(k, *v) if v is not None else None
    return {k: v for k, v in out.items() if v is not None}


def test_all_items_detected_passes():
    r = evaluate(dets(), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=True)
    assert r.passed and r.decision == "granted" and r.missing_items == []


def test_example_from_requirements_beard_net_missing_fails():
    r = evaluate(dets(beard_net=(False, 0.9)), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=True)
    statuses = {i.item: i.status for i in r.items}
    assert statuses == {"uniform": "pass", "hair_cap": "pass", "face_mask": "pass", "beard_net": "fail",
                        "safety_shoes": "pass"}
    assert not r.passed and r.decision == "denied" and r.missing_items == ["beard_net"]


def test_item_not_required_by_module_is_ignored():
    reqs = {**ALL_REQUIRED, "face_mask": Requirement(False)}
    r = evaluate(dets(face_mask=(False, 0.9)), reqs, default_threshold=0.6, beard_net_applicable=True)
    assert r.passed and "face_mask" not in r.required_items


def test_beard_net_not_applicable_to_employee():
    r = evaluate(dets(beard_net=(False, 0.9)), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=False)
    assert r.passed
    assert next(i for i in r.items if i.item == "beard_net").status == "not_required"


def test_unidentified_person_is_treated_conservatively_for_beard_net():
    r = evaluate(dets(beard_net=(False, 0.9)), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=None)
    assert not r.passed and r.missing_items == ["beard_net"]


def test_confidence_below_threshold_fails():
    r = evaluate(dets(hair_cap=(True, 0.55)), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=True)
    assert not r.passed and r.missing_items == ["hair_cap"]
    assert "below" in next(i for i in r.items if i.item == "hair_cap").reason


def test_per_item_threshold_overrides_default():
    reqs = {**ALL_REQUIRED, "face_mask": Requirement(True, 0.9)}
    assert not evaluate(dets(face_mask=(True, 0.8)), reqs, default_threshold=0.6, beard_net_applicable=True).passed
    assert evaluate(dets(face_mask=(True, 0.92)), reqs, default_threshold=0.6, beard_net_applicable=True).passed


def test_missing_detection_result_fails_closed():
    r = evaluate(dets(safety_shoes=None), ALL_REQUIRED, default_threshold=0.6, beard_net_applicable=True)
    assert not r.passed and r.missing_items == ["safety_shoes"]


def test_no_requirements_passes():
    assert evaluate({}, {}, default_threshold=0.6).passed


def test_severity_rules():
    assert severity_for(["face_mask"], is_repeat=False) == "medium"
    assert severity_for(["face_mask", "hair_cap"], is_repeat=False) == "high"
    assert severity_for(["uniform"], is_repeat=False) == "high"
    assert severity_for(["face_mask"], is_repeat=True) == "critical"
