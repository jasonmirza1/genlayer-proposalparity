# ProposalParity

ProposalParity is a standalone GenLayer Intelligent Contract that attests whether a written governance motion matches a locked bundle of executable EVM transfers under an onchain charter. A charter fixes the target chain, exact recipient/token allowlists, raw-unit caps, purpose, and prohibitions. Validators independently fetch the motion and bundle at one GitHub commit, decode the transfers, compare them with the written text, and store a receipt.

Unlike the existing IntentScope agent-action gate, this primitive reviews a **multi-action DAO motion** and decodes raw native/ERC-20 transfer calldata before comparing every effect with the published prose.

This repository is a **local prototype, not a deployed or submitted contract**. It does not execute, sign, custody, or authorize any transfers.

## Why decentralized judgment is used

Exact byte parsing catches unsupported calls, wrong targets and spending cap violations. The harder question is whether a human-written motion truthfully discloses every action and fits the charter. The leader proposes per-action semantic findings; validators independently retrieve and hash both files, decode every action, and compare the material findings and final verdict. They must not approve based only on a well-formed JSON shape.

The custom validator checks both result schemas and requires exact equality of verification flags, motion/bundle/action hashes, ordered decoded effects, mechanical issues, verdict and per-action assessment labels. Only the narrative reasons and summary are compared semantically. AI agreement cannot override different amounts, recipients, tokens or hashes; malformed comparator responses are rejected. Two identical canonical evidence-failure results agree without a model call.

## State and methods

- `create_charter(name, purpose, prohibited_effects, chain_id, allowed_recipients_csv, allowed_tokens_csv, max_native_wei, max_token_units)` stores a policy owned by the caller. Address lists are exact EVM addresses, comma-separated; use `-` for no allowed tokens. Amount caps are nonnegative decimal strings in raw units.
- `deactivate_charter(charter_id)` is owner-only. Existing attestations remain readable.
- `attest_proposal(charter_id, motion_url, bundle_url, nonce)` records `ALIGNED`, `DIVERGENT`, or `INSUFFICIENT_EVIDENCE` and consumes a fresh lowercase hex nonce scoped to the charter and caller address. Another wallet cannot consume your nonce.
- `get_charter`, `get_attestation`, and `get_counts` expose stored state.

The two evidence URLs must be GitHub `blob` links to files in the **same repository and exact 40-character lowercase commit SHA**. GitHub API file bytes and their SHA-256 hashes are recorded. [Example motion](examples/motion.md) and [example bundle](examples/bundle.json) provide a reproducible one-transfer fixture. The `proposalparity.bundle.v1` schema has `chain_id` and 1–4 `actions`, each with `target`, decimal-string `value_wei`, and hex `calldata`.

The parser supports only plain positive native transfers (`calldata: "0x"`) and canonical ERC-20 `transfer(address,uint256)` calls. Opaque calls, approvals, multicalls, delegatecalls, zero-value transfers, malformed encodings, and any unsupported action yield `INSUFFICIENT_EVIDENCE`. Exact allowlist or cap failures yield `DIVERGENT`. Token amounts are compared as **raw onchain units**; the contract does not infer decimals, ticker symbols, off-chain identities, or future state.

## Reproduce locally

With `requirements.txt` installed:

```powershell
python -m pytest tests -q -p no:cacheprovider
$env:PYTHONIOENCODING='utf-8'; python -m genvm_linter.cli check contracts/proposalparity.py
```

The 44 local tests cover native and ERC-20 decoding, allowlists, cap enforcement, opaque calls, chain mismatch, structured discrepancy/uncertainty results, immutable URLs, replay, caller isolation, owner controls, and forged positive results. Tests in `tests/sdk/` use the real SDK with mocked web/model responses and Python execution. They explicitly invoke the captured validator callback to check independent evidence collection, exact-field mismatch rejection even with an always-agree comparator, semantic acceptance/rejection, malformed comparator output, and leader-error rejection. The external semantic comparator is mocked; these tests do not prove model judgment quality, WASM execution, or network consensus.

Full GenVM/Studio consensus verification is still pending. No local GenLayer Studio runtime was installed or running during this validation. Use the Studio Next verification path below and record a stored receipt before publishing any claim of live consensus success.

## Studio Next verification path

1. Deploy `contracts/proposalparity.py` on Studio Next with full consensus and record the address and deploy transaction.
2. Publish this directory and copy the full commit SHA containing both example files. Use GitHub `blob` links to that SHA, not a mutable branch URL.
3. Call `create_charter` with a specific purpose and prohibition, chain ID `61997`, allowed recipient `0x1111111111111111111111111111111111111111`, tokens `-`, native cap `100`, token cap `0`. These sample addresses and values are **test-only**.
4. Call `attest_proposal` for charter `1`, the locked motion and bundle URLs, and a fresh random 32–64-character lowercase hex nonce. Record its transaction hash.
5. Wait for finalization. Verify `get_counts().attestations == 1`, inspect `get_attestation("1")`, and confirm the motion/bundle hashes and `ALIGNED` verdict. A `FINALIZED` transaction alone does not prove an attestation was stored.

The public source is at https://github.com/jasonmirza1/genlayer-proposalparity. No Studio Next transaction has been submitted as part of this build. Deployment, fee approval, and Portal submission require separate user action.

## Security boundaries

The motion and charter text are untrusted data, not instructions to validators. The receipt binds a particular motion and bundle by hash. A downstream executor must independently compare the **exact same chain ID and bundle bytes/hash** before acting, and must perform its own authorization checks. `ALIGNED` is not a vote, a legal determination, or a safety guarantee. Hidden effects from supported token implementations, proxy contracts, rebasing tokens, or target-chain state cannot be proven by static calldata decoding. The source file size is capped at 9,000 bytes each; storage is capped at 10,000 charters and 10,000 attestations.
