# R18 — resume existing role wallets, prove deployment finality, fund and register monitors on chain31339

**Operator evidence, 2026-11-19**. VM4705 already has our own Ethereum-PoS
research chain31339 (Besu+Lighthouse clients), 32 centrally held
bootstrap validator keys, 1M valueless genesis test ETH initially
funded to the local encrypted faucet, and **actual on-chain contracts**
at the addresses below. The upstream initial Kurtosis launch exposed
bootstrap keys in terminal output; this chain is therefore PRIVATE
DISPOSABLE SMOKE ONLY. Not public validator admission.

## Actual VM4705 result from R17

- Source checkout \`d04b749284dab4980e4428971edd7a71457458b7\`.
- 39/39 targeted Python PoS tests PASS. No Foundry change introduced.
- \`tools/sse_pos_deploy_receipts.py --require-tx-finality\` returned:
  \`deployment receipts canonical but not proven finalized\`.
  The script reached its finality gate after the seven canonical
  receipt/address/nonce/call/wiring validations. **That is NOT a
  failed transaction and does not prove finality.** It only means the
  execution client finalized tag did not verify block959.
- R18 receipt audit adds a conservative Lighthouse fallback to
  \`/eth/v2/beacon/blocks/finalized\`, requires
  \`finalized:true\`, \`execution_optimistic:false\`,
  reads the finalized *execution_payload* block hash/number,
  and independently cross-checks that hash against the corresponding
  canonical execution block in Besu. Only if that block number
  covers block959 is \`deploymentTxFinalityProved=true\`.
  If either JSON-RPC or Beacon evidence is stale/unavailable,
  the audit still reports unproven; it never invents finality.
- Consumer encrypted wallet was created successfully:
  \`0xAF810580e49809F337828391725886f40207abcC\`.
  The next role \`provider\` failed password confirmation and
  **was not created**. Restarting from \`consumer\` correctly refused
  overwrite. Keep the EXISTING consumer wallet.

## 1 — Recover wallet creation, without deleting any existing key

On VM4705 (do NOT use VM4704; it was destroyed and its keys discarded):

    cd ~/sse-pos
    source .venv-pos/bin/activate

    for role in provider monitor01 monitor02 monitor03 monitor04 monitor05; do
      python tools/sse_pos_test_wallet.py \
        --role "$role" \
        --output-dir "$HOME/sse-pos-wallets" --apply || break
    done

Every role gets a separately generated, locally encrypted EOA.
Neither those keys nor the FAUCET key must be copied into GitHub,
pasted into chat, printed or merged with validator BLS keys.
If any role has already been created in a partial later run,
skip its name rather than trying to overwrite it.
The monitor wallets are distinct *cryptographic identities* but
remain centrally hosted on ONE lab machine, not physical
operator independence.

## 2 — Update only GitHub source and verify the real finality boundary

    git fetch origin integration/r7-wp09q-wan-multivm-no-actions
    git switch --detach APPROVED_R18_SHA
    python -m unittest discover -s tests -p 'test_sse_pos_*.py' -v

    python tools/sse_pos_deploy_receipts.py \
      --rpc-url http://127.0.0.1:32770 \
      --beacon-url http://127.0.0.1:32774 \
      --require-tx-finality

If this still refuses finality, diagnose read-only:

    cast rpc eth_getBlockByNumber '"finalized"' false \
      --rpc-url http://127.0.0.1:32770
    curl -fsS http://127.0.0.1:32774/eth/v2/beacon/blocks/finalized \
      | python -c 'import json,sys; j=json.load(sys.stdin); \
        p=j.get("data",{}).get("message",{}).get("body",{}).get("execution_payload",{}); \
        print({"finalized":j.get("finalized"),"optimistic":j.get("execution_optimistic"), \
        "executionBlock":p.get("block_number"),"hash":p.get("block_hash")})'

These are public chain values, NOT key-material endpoints. Compare
reported finalized execution block height to deployment block959.
Do not claim tx finality from Beacon 'epoch finalized' alone.

## 3 — Inspect actual test ETH roles, deposit bond and register

All commands below are on the isolated OWN chain31339 RPC
\`http://127.0.0.1:32770\`. R18 GitHub-first runner:

    tools/sse_pos_live_roles.py

It independently checks pinned chain ID and original genesis,
deployment addresses and one-time bindings, exactly expected minimum
monitor bond, wallet ownership/mode and distinct account addresses
before any signing. Wallet passwords are prompted via getpass;
no private key is supplied in CLI arguments.

**Read-only, no passwords and no transactions:**

    python tools/sse_pos_live_roles.py \
      --rpc-url http://127.0.0.1:32770 \
      --wallet-dir "$HOME/sse-pos-wallets" --plan

**Explicit confirmed funding:**

    python tools/sse_pos_live_roles.py \
      --rpc-url http://127.0.0.1:32770 \
      --wallet-dir "$HOME/sse-pos-wallets" --fund

Type \`EXECUTE FUND ON 31339\` only if the plan shows EXACTLY the
expected owned role addresses. Enter faucet wallet encryption
password privately once. The script sends on-chain EIP-1559 signed
transfers with the encrypted faucet EOA, then verifies receipts:
- consumer: 1 TEST ETH
- provider: 1 TEST ETH
- monitors 01–05: 0.1 TEST ETH each
- total earmarked test funding 2.5 TEST ETH; no real ETH.

**Register monitors with positive bond:**

    python tools/sse_pos_live_roles.py \
      --rpc-url http://127.0.0.1:32770 \
      --wallet-dir "$HOME/sse-pos-wallets" --register

Type \`EXECUTE REGISTER ON 31339\` to confirm. The script prompts
for the five monitor keystore encryption passwords, signs REAL
\`OpenMonitorCommittee.register()\` transactions, sends exactly
1e15 wei (0.001 test ETH) each, and checks successful receipts.
Positive minimum bond enforces a *per-identity lab cost*, NOT
economic Sybil resistance with worthless freely provided ETH.

**Re-run a read-only check:**

    python tools/sse_pos_live_roles.py \
      --rpc-url http://127.0.0.1:32770 \
      --wallet-dir "$HOME/sse-pos-wallets" --plan

The result must show \`registeredActiveCandidateCount: 5\` and
\`allFiveDemoMonitorsRegistered: true\` before any lease creation.

### Failure handling and scope

- **NO wallet overwrite**: script refuses invalid/missing keystores.
- Funding may be partially successful. The runner skips already
  funded roles if they have positive balances and refuses anomalous
  small positive balances. Don't blindly resend uncertain TX hashes.
- Registration may be partially successful. The runner skips
  already active bonded monitor accounts; it refuses unusual
  partially registered states rather than doubling bonds.
- The on-chain contract addresses are fixed by the real deployment
  receipts; never redeploy or substitute Anvil's test accounts.
- The original R17 audit could not prove finality. Even if R18 audit
  still cannot, new transactions may be technically included;
  for publication and robust SLA experiments, require stronger
  tx finality evidence before trusting irreversible outcomes.
- Source tests are on test mocks, NOT proof the role transactions
  were run. Actual receipts and read-only plan determine acceptance.
- No settlement/HTTP delivery or physical provider-host independence
  is claimed by this tool.

## 4 — Next: actual marketplace and SLA monitoring

After 5 monitored bonds are verifiably active, R19 must execute
a real consumer request on OpenResourceBoard, provider bid,
time-gated selection and funded lease, provider acceptance,
+4 future-block delayed entropy, permissionless on-chain
committee selection, 4 selected monitor confirmations,
EIP-712 provider-signed response, independently signed
and evidence-linked monitor votes, deadline-respecting
settlement, withdrawals and actual gas/latency measurements.
Use real PoS slots, NEVER Anvil \`evm_increaseTime\` or unlocked
\`eth_sendTransaction\`, and label any simulated service response
or synthetic observations as synthetic rather than physical SLA
proof. Avoid publishing leaked bootstrap keys or opening 0.0.0.0
discovery ports on this contaminated genesis.

Actual contracts from R16:
- Committee \`0x9965bAC16C5Df538df0373a906e42eA0E0C327d9\`
- Settlement \`0x879878f7561F5a0a1f6dd22348FfdE81cD5fEe7F\`
- Board \`0xF1147CA8aC9e28F845529A6Ae5837873806C7788\`

The same exact deployment-source Git SHA is
\`cd2fe67e3031d4f25c41bfc714c6539b7ca1ebef\`.
R18 is a later source revision and does NOT alter the live contracts.
