# Professor's Milestone III — exact submission checklist

**Required archive:** one ZIP containing (1) a PDF article of **no more than six pages** and (2) `.sol` source code. This repository contains five Solidity files; use the source-only package for the second deliverable.

| Requirement | Where satisfied/prepared | Final author action |
|---|---|---|
| Introduction revised from Milestone II | Existing `Report.pdf` (separate uploaded source) | Review feedback and integrate without unsupported additions |
| Literature Review revised from Milestone II | Existing `Report.pdf` | Keep verified references and cite properly |
| Design goals | `docs/MILESTONE3_SYSTEM_DESIGN.md` §1 | Integrate concise version |
| Threat model and assumptions | §8 | Integrate and verify fault assumptions |
| Participants, roles, responsibilities | §2 | Integrate role table |
| Ethereum nodes and consensus | §3 | State **Anvil development**, NOT deployed QBFT |
| PKI/registration | §§2–3 | Explain Ethereum keys, EIP-712 and bonded registration; no X.509 CA |
| System workflow and smart-contract logic | §§4–7 | Integrate actual vs intended flow distinction |
| System architecture figure | §4 Mermaid source | Render at legible print size |
| Sequence diagrams | §6 Mermaid source | Render at legible print size |
| Crucial contract pseudocode | §7 | Include settleEpoch and optionally admitEpoch |
| AI Usage Disclaimer immediately before references | §11 guidance | Write truthful disclaimer and place correctly |
| PDF highlights AI-generated material | Professor's instruction | Highlight actual AI-generated text in submission PDF |
| Disclose AI-generated figures | Professor's instruction | State assistance for figures used |
| References | Milestone II report | Preserve and validate citations |
| Five Solidity sources | `contracts/*.sol` | Include in submission ZIP |

**Not explicitly required:** deployment of public Ethereum validators, Besu QBFT, multiple cloud VMs, a frontend, autonomous provider/monitor agents, provider collateral or automatic deployment. These may support future research evaluation but do not replace the required article elements.

**Status warning:** This checklist and technical source are **report-ready materials**, not a completed six-page PDF. The final article must preserve the existing literature and adhere to the exact official formatting/highlighting requirements.
