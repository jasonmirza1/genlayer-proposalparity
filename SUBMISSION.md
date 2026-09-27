# ProposalParity — Portal draft

Category: Builder → Intelligent Contracts. This is a **draft**, not proof of deployment or acceptance.

One-liner: Consensus attestation that a written DAO motion matches its exact executable transfer bundle.

Description: ProposalParity is a reusable GenLayer contract primitive for governance transparency. A charter stores the target execution chain, exact token/recipient allowlists, raw-unit spending caps, a purpose, and prohibited effects. A proposer pins a written motion and a JSON action bundle to the same full GitHub commit. Validators independently fetch and hash both files, decode supported native and ERC-20 transfers, enforce exact allowlists and aggregate caps, and compare every executable effect with the written motion. The contract stores a nonce-bound ALIGNED, DIVERGENT, or INSUFFICIENT_EVIDENCE attestation with file hashes, action hashes, decoded effects, and per-action reasons. Unsupported calls fail closed. It neither executes transfers nor replaces governance voting or authorization.

Public repository: https://github.com/jasonmirza1/genlayer-proposalparity

Studio Next contract link: **TODO — deploy and verify address**

Finalized attestation transaction: **TODO — submit one fixture attestation and verify a stored receipt**

Reviewer verification: Open the Studio Next contract, call `get_counts`, `get_charter("1")`, and `get_attestation("1")`. Confirm the motion and bundle use the same full commit SHA, the stored hashes match their exact bytes, the decoded native transfer targets `0x1111111111111111111111111111111111111111` for 100 raw wei on execution chain 61997, and the receipt says ALIGNED with a per-action reason. A finalized transaction without a stored attestation is not sufficient.

Before submitting, rerun `python -m pytest tests -q -p no:cacheprovider`, run the linter, publish source and fixture at one commit, deploy on Studio Next, make one charter and attestation transaction, and replace every TODO above with exact public links. Do not submit this draft as if those actions are complete.
