import base64
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest


SHA = "a" * 40
NONCE = "b" * 48
RECIPIENT = "0x" + "1" * 40
TOKEN = "0x" + "2" * 40
MOTION_URL = f"https://github.com/example/proposal/blob/{SHA}/motion.md"
BUNDLE_URL = f"https://github.com/example/proposal/blob/{SHA}/bundle.json"
MOTION = f"# Treasury payment\nOn chain 61997, send exactly 100 raw native wei to {RECIPIENT} for a test payment.\n".encode()
BUNDLE = {"schema": "proposalparity.bundle.v1", "chain_id": 61997, "actions": [{"target": RECIPIENT, "value_wei": "100", "calldata": "0x"}]}
ANSWER = {"charter_fit": True, "motion_complete": True, "findings": [{"index": 1, "assessment": "ALIGNED", "reason": "The chain, recipient, and raw amount match."}], "summary": "Written motion matches the executable native transfer."}


class TreeMap(dict):
    def __class_getitem__(cls, key):
        return cls


@pytest.fixture
def env():
    calls = []
    state = {"motion": MOTION, "bundle": json.dumps(BUNDLE).encode(), "answer": dict(ANSWER), "status": 200}

    def get(url):
        calls.append(url)
        raw = state["motion"] if "/motion.md?" in url else state["bundle"]
        envelope = {"type": "file", "encoding": "base64", "size": len(raw), "content": base64.b64encode(raw).decode()}
        return types.SimpleNamespace(status=state["status"], body=json.dumps(envelope).encode())

    gl = types.ModuleType("genlayer")
    gl.contract = types.SimpleNamespace(Contract=object)
    gl.storage = types.SimpleNamespace(TreeMap=TreeMap)
    gl.u256 = int
    gl.public = types.SimpleNamespace(write=lambda f: f, view=lambda f: f)
    gl.vm = types.SimpleNamespace(UserError=ValueError, run_nondet=lambda fn, validator: fn())
    gl.message = types.SimpleNamespace(sender_address=types.SimpleNamespace(as_hex="0xOwner"))
    gl.nondet = types.SimpleNamespace(web=types.SimpleNamespace(get=get), exec_prompt=lambda *args, **kwargs: json.dumps(state["answer"]))
    before = sys.modules.get("genlayer")
    sys.modules["genlayer"] = gl
    try:
        spec = importlib.util.spec_from_file_location("proposalparity_contract_test", Path(__file__).parents[1] / "contracts/proposalparity.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        if before is None:
            sys.modules.pop("genlayer")
        else:
            sys.modules["genlayer"] = before
    contract = module.ProposalParity()
    contract.charters = {}
    contract.attestations = {}
    contract.used_nonces = {}
    contract.charter_count = 0
    contract.attestation_count = 0
    contract.create_charter("Treasury rule", "Permit one bounded transparent test payment.", "No hidden calls, unknown recipients, or opaque delegatecalls.", 61997, RECIPIENT, TOKEN, "1000", "5000")
    return contract, state, calls, gl


def test_aligned_native_transfer_is_attested(env):
    contract, state, calls, _ = env
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "ALIGNED"
    assert receipt["motion_sha256"] == hashlib.sha256(state["motion"]).hexdigest()
    assert receipt["bundle_sha256"] == hashlib.sha256(state["bundle"]).hexdigest()
    assert receipt["effects"][0]["amount_raw"] == "100"
    assert len(receipt["action_hashes"]) == 1
    assert contract.get_counts() == {"charters": 1, "attestations": 1}
    assert len(calls) == 2


def test_non_allowlisted_recipient_is_divergent(env):
    contract, state, _, _ = env
    bundle = json.loads(state["bundle"])
    bundle["actions"][0]["target"] = "0x" + "3" * 40
    state["bundle"] = json.dumps(bundle).encode()
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "DIVERGENT"
    assert "non-allowlisted" in receipt["issues"][0]
    assert receipt["findings"] == []


def test_native_total_cap_is_enforced(env):
    contract, state, _, _ = env
    bundle = json.loads(state["bundle"])
    bundle["actions"][0]["value_wei"] = "1001"
    state["bundle"] = json.dumps(bundle).encode()
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "DIVERGENT"
    assert any("cap" in issue for issue in receipt["issues"])


def test_exact_erc20_transfer_is_decoded(env):
    contract, state, _, _ = env
    calldata = "0xa9059cbb" + "0" * 24 + RECIPIENT[2:] + f"{1234:064x}"
    bundle = json.loads(state["bundle"])
    bundle["actions"][0] = {"target": TOKEN, "value_wei": "0", "calldata": calldata}
    state["bundle"] = json.dumps(bundle).encode()
    state["motion"] = f"On chain 61997 transfer 1234 raw units of token {TOKEN} to {RECIPIENT}.".encode()
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "ALIGNED"
    assert receipt["effects"][0] == {"index": 1, "kind": "ERC20_TRANSFER", "recipient": RECIPIENT, "token": TOKEN, "amount_raw": "1234"}


def test_unsupported_call_cannot_be_aligned(env):
    contract, state, _, _ = env
    bundle = json.loads(state["bundle"])
    bundle["actions"][0]["calldata"] = "0x12345678"
    bundle["actions"][0]["value_wei"] = "0"
    state["bundle"] = json.dumps(bundle).encode()
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert "opaque" in receipt["issues"][0]


@pytest.mark.parametrize("problem", ["http_failure", "invalid_json", "wrong_chain", "blank_motion", "duplicate_key"])
def test_unverified_evidence_fails_closed(env, problem):
    contract, state, _, _ = env
    if problem == "http_failure":
        state["status"] = 503
    elif problem == "invalid_json":
        state["bundle"] = b"{"
    elif problem == "wrong_chain":
        bundle = json.loads(state["bundle"])
        bundle["chain_id"] = 1
        state["bundle"] = json.dumps(bundle).encode()
    elif problem == "blank_motion":
        state["motion"] = b"   "
    else:
        state["bundle"] = b'{"schema":"proposalparity.bundle.v1","chain_id":61997,"actions":[],"actions":[]}'
    receipt = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert receipt["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert not receipt["evidence_verified"]


def test_semantic_mismatch_is_divergent(env):
    contract, state, _, _ = env
    state["answer"] = {**ANSWER, "motion_complete": False, "findings": [{"index": 1, "assessment": "DIVERGENT", "reason": "Motion omits the actual recipient."}]}
    assert contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)["verdict"] == "DIVERGENT"


def test_unclear_token_units_are_insufficient(env):
    contract, state, _, _ = env
    state["answer"] = {**ANSWER, "findings": [{"index": 1, "assessment": "UNCLEAR", "reason": "Token decimals are not established."}]}
    assert contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)["verdict"] == "INSUFFICIENT_EVIDENCE"


@pytest.mark.parametrize("url", [
    "https://github.com/example/proposal/blob/main/bundle.json",
    f"https://github.com/example/proposal/blob/{SHA}/../bundle.json",
    f"https://github.com/example/proposal/blob/{SHA}/%2e%2e/bundle.json",
])
def test_url_must_be_immutable_and_canonical(env, url):
    contract, _, calls, _ = env
    with pytest.raises(ValueError):
        contract.attest_proposal("1", MOTION_URL, url, NONCE)
    assert calls == []


def test_sources_must_share_one_commit(env):
    contract, _, calls, _ = env
    other = f"https://github.com/example/proposal/blob/{'c' * 40}/bundle.json"
    with pytest.raises(ValueError, match="same repository commit"):
        contract.attest_proposal("1", MOTION_URL, other, NONCE)
    assert calls == []


def test_replay_and_owner_controls(env):
    contract, _, calls, gl = env
    contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    count = len(calls)
    with pytest.raises(ValueError, match="Nonce already used"):
        contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert len(calls) == count
    gl.message.sender_address.as_hex = "0xOther"
    with pytest.raises(ValueError, match="owner"):
        contract.deactivate_charter("1")
    gl.message.sender_address.as_hex = "0xOwner"
    contract.deactivate_charter("1")
    with pytest.raises(ValueError, match="inactive"):
        contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, "c" * 48)


def test_other_caller_cannot_consume_my_nonce(env):
    contract, state, _, gl = env
    gl.message.sender_address.as_hex = "0xAttacker"
    state["status"] = 503
    first = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert first["verdict"] == "INSUFFICIENT_EVIDENCE"
    gl.message.sender_address.as_hex = "0xOwner"
    state["status"] = 200
    second = contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert second["verdict"] == "ALIGNED" and second["requester"] == "0xOwner"
    assert contract.get_counts()["attestations"] == 2
    gl.message.sender_address.as_hex = "0xOWNER"
    with pytest.raises(ValueError, match="Nonce already used"):
        contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)


def test_post_consensus_forged_alignment_is_rejected(env):
    contract, state, _, gl = env
    bundle = json.loads(state["bundle"])
    bundle["actions"][0]["calldata"] = "0x12345678"
    bundle["actions"][0]["value_wei"] = "0"
    state["bundle"] = json.dumps(bundle).encode()
    def forged(fn, *args):
        row = fn()
        row["verdict"] = "ALIGNED"
        return row
    gl.vm.run_nondet = forged
    with pytest.raises(ValueError, match="ALIGNED contradicts"):
        contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)
    assert contract.get_counts()["attestations"] == 0


def test_json_fence_is_accepted(env):
    contract, state, _, gl = env
    gl.nondet.exec_prompt = lambda *args, **kwargs: "```json\n" + json.dumps(state["answer"]) + "\n```"
    assert contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)["verdict"] == "ALIGNED"


def test_semantic_assessment_requests_json(env):
    contract, state, _, gl = env
    formats = []
    def prompt(*args, **kwargs):
        formats.append(kwargs.get("response_format"))
        return dict(state["answer"])
    gl.nondet.exec_prompt = prompt
    assert contract.attest_proposal("1", MOTION_URL, BUNDLE_URL, NONCE)["verdict"] == "ALIGNED"
    assert formats == ["json"]


def test_identical_semantic_failure_needs_no_model_comparison(env):
    contract, _, _, gl = env
    def unexpected(*args, **kwargs):
        pytest.fail("Identical fail-closed results must not invoke the comparator")
    gl.nondet.exec_prompt = unexpected
    row = contract._result(
        "INSUFFICIENT_EVIDENCE", "a" * 64, "b" * 64,
        [{"target": RECIPIENT, "value_wei": "100", "calldata": "0x"}],
        [{"index": 1, "kind": "NATIVE_TRANSFER", "recipient": RECIPIENT, "token": "", "amount_raw": "100"}],
        [], [], "Semantic comparison did not produce complete, usable evidence",
    )
    assert contract._agree_results(row, dict(row), contract.get_charter("1")) is True
    assert contract._agree_results(row, {**row, "summary": "Different failure"}, contract.get_charter("1")) is False


def test_matching_unverified_results_need_no_semantic_comparison(env):
    contract, _, _, gl = env
    def unexpected(*args, **kwargs):
        pytest.fail("Canonical evidence failures must not invoke the comparator")
    gl.nondet.exec_prompt = unexpected
    result = contract._unverified()
    assert contract._agree_results(result, dict(result), contract.get_charter("1")) is True
