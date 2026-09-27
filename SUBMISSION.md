# ProposalParity — Portal draft

Category: Builder → Intelligent Contracts. This is a **draft**, not proof of deployment or acceptance.

One-liner: Consensus attestation that a written DAO motion matches its exact executable transfer bundle.

Description: ProposalParity is a reusable GenLayer contract primitive for governance transparency. A charter stores the target execution chain, exact token/recipient allowlists, raw-unit spending caps, a purpose, and prohibited effects. A proposer pins a written motion and a JSON action bundle to the same full GitHub commit. Validators independently fetch and hash both files, decode supported native and ERC-20 transfers, enforce exact allowlists and aggregate caps, and compare every executable effect with the written motion. The contract stores a nonce-bound ALIGNED, DIVERGENT, or INSUFFICIENT_EVIDENCE attestation with file hashes, action hashes, decoded effects, and per-action reasons. Unsupported calls fail closed. It neither executes transfers nor replaces governance voting or authorization.

Public repository: https://github.com/jasonmirza1/genlayer-proposalparity

Studio Next contract link: https://explorer-studio-next.genlayer.com/address/0x35A7f3d30c22DF0277c56f0fd3C1036892dbDd75

Finalized attestation transaction: https://explorer-studio-next.genlayer.com/tx/0xc18d50f722c707eac6916c2b1503b1d972c6e79f1c7a8ebfd772f105ac5c92a8

Finalized-state verification: `get_counts()` returned one charter and one attestation. `get_attestation("1")` returned `ALIGNED`, `evidence_verified: true`, no issues, and a decoded 100-raw-wei native transfer to the fixture recipient. This is one fixture demonstration, not proof that arbitrary motions are safe.

Reviewer verification: Open the Studio Next contract, call `get_counts`, `get_charter("1")`, and `get_attestation("1")`. Confirm the motion and bundle use the same full commit SHA, the stored hashes match their exact bytes, the decoded native transfer targets `0x1111111111111111111111111111111111111111` for 100 raw wei on execution chain 61997, and the receipt says ALIGNED with a per-action reason. A finalized transaction without a stored attestation is not sufficient.

Before submitting, rerun `python -m pytest tests -q -p no:cacheprovider`, run the linter, and ensure this corrected source and the fixture are public. The Studio Next deployment and fixture attestation above are already complete. Portal submission is still a separate user action.
