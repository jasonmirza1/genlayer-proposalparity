import base64
import copy
import json
from pathlib import Path

import pytest


CONTRACT = str(Path(__file__).parents[2] / "contracts/proposalparity.py")
SHA = "a" * 40
NONCE = "b" * 48
RECIPIENT = "0x" + "1" * 40
TOKEN = "0x" + "2" * 40
MOTION = f"On chain 61997 transfer exactly 100 raw native wei to {RECIPIENT} for a test payment."
BUNDLE = json.dumps({"schema": "proposalparity.bundle.v1", "chain_id": 61997, "actions": [{"target": RECIPIENT, "value_wei": "100", "calldata": "0x"}]})
ANSWER = {"charter_fit": True, "motion_complete": True, "findings": [{"index": 1, "assessment": "ALIGNED", "reason": "Chain, target and raw value match."}], "summary": "Motion and transfer align."}


def _envelope(raw):
    return json.dumps({"type": "file", "encoding": "base64", "size": len(raw.encode()), "content": base64.b64encode(raw.encode()).decode()})


def test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat):
    direct_vm.mock_web(r".*api\.github\.com/repos/example/proposal/contents/motion\.md\?ref=a{40}.*", {"status": 200, "body": _envelope(MOTION)})
    direct_vm.mock_web(r".*api\.github\.com/repos/example/proposal/contents/bundle\.json\?ref=a{40}.*", {"status": 200, "body": _envelope(BUNDLE)})
    direct_vm.mock_llm(r".*Compare this written governance motion.*", json.dumps(json.dumps(ANSWER)))
    contract = direct_deploy_compat(CONTRACT)
    contract.create_charter("Treasury rule", "Permit one bounded transparent test payment.", "No hidden calls, unknown recipients, or opaque delegatecalls.", 61997, RECIPIENT, TOKEN, "1000", "5000")
    receipt = contract.attest_proposal("1", f"https://github.com/example/proposal/blob/{SHA}/motion.md", f"https://github.com/example/proposal/blob/{SHA}/bundle.json", NONCE)
    assert receipt["verdict"] == "ALIGNED"
    assert contract.get_counts()["attestations"] == 1


def _mock_comparison(direct_vm, monkeypatch, answer):
    validator = direct_vm._captured_validators[-1][2]
    calls = []
    nondet = validator.__globals__["gl"].nondet
    original = nondet.exec_prompt

    def compare(prompt, *args, **kwargs):
        if not prompt.startswith("Compare independently produced proposal attestations."):
            return original(prompt, *args, **kwargs)
        calls.append(prompt)
        return answer

    monkeypatch.setattr(nondet, "exec_prompt", compare)
    return calls


@pytest.mark.parametrize("agreement", [True, False])
def test_validator_checks_semantics_after_matching_evidence(direct_vm, direct_deploy_compat, monkeypatch, agreement):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    calls = _mock_comparison(direct_vm, monkeypatch, {"agree": agreement})
    leader = copy.deepcopy(direct_vm._captured_validators[-1][0])
    leader["summary"] = "The motion describes the same transfer."
    assert direct_vm.run_validator(leader_result=leader) is agreement
    assert len(calls) == 1
    assert leader["summary"] in calls[0] and ANSWER["summary"] in calls[0]


@pytest.mark.parametrize("field", ["motion_sha256", "bundle_sha256", "action_hash", "amount", "recipient", "token", "evidence_verified", "verdict", "issues", "assessment"])
def test_validator_rejects_exact_mismatch_even_if_comparator_agrees(direct_vm, direct_deploy_compat, monkeypatch, field):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    calls = _mock_comparison(direct_vm, monkeypatch, {"agree": True})
    leader = copy.deepcopy(direct_vm._captured_validators[-1][0])
    if field in ("motion_sha256", "bundle_sha256"):
        leader[field] = "0" * 64
    elif field == "action_hash":
        leader["action_hashes"][0] = "0" * 64
    elif field == "amount":
        leader["effects"][0]["amount_raw"] = "99"
    elif field == "recipient":
        leader["effects"][0]["recipient"] = "0x" + "3" * 40
        leader["verdict"] = "DIVERGENT"
    elif field == "token":
        leader["effects"][0].update(kind="ERC20_TRANSFER", token=TOKEN)
    elif field == "evidence_verified":
        leader[field] = False
    elif field == "verdict":
        leader[field] = "DIVERGENT"
    elif field == "issues":
        leader[field] = ["Native transfer total exceeds charter cap"]
        leader["verdict"] = "DIVERGENT"
    else:
        leader["findings"][0]["assessment"] = "UNCLEAR"
        leader["verdict"] = "INSUFFICIENT_EVIDENCE"
    assert direct_vm.run_validator(leader_result=leader) is False
    assert calls == []


def test_validator_cannot_verify_leaders_evidence(direct_vm, direct_deploy_compat, monkeypatch):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    calls = _mock_comparison(direct_vm, monkeypatch, {"agree": True})
    direct_vm.clear_mocks()
    direct_vm.mock_web(r".*api\.github\.com/.*", {"status": 503, "body": "unavailable"})
    assert direct_vm.run_validator() is False
    assert calls == []


@pytest.mark.parametrize("answer", [None, {}, {"agree": "true"}, {"agree": 1}, {"agree": True, "extra": 1}, "not json", '{"agree":false,"agree":true}'])
def test_validator_rejects_malformed_comparison(direct_vm, direct_deploy_compat, monkeypatch, answer):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    calls = _mock_comparison(direct_vm, monkeypatch, answer)
    assert direct_vm.run_validator() is False
    assert len(calls) == 1


def test_validator_rejects_leader_error(direct_vm, direct_deploy_compat):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    assert direct_vm.run_validator(leader_error=ValueError("leader failed")) is False


def test_comparison_uses_sdk_json_response(direct_vm, direct_deploy_compat):
    test_locked_motion_and_bundle_in_sdk(direct_vm, direct_deploy_compat)
    direct_vm.mock_llm(r".*Compare independently produced proposal attestations.*", json.dumps(json.dumps({"agree": True})))
    assert direct_vm.run_validator() is True
