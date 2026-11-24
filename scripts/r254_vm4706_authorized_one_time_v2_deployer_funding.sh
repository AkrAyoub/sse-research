#!/usr/bin/env bash
# R254: owner-authorized ONE real worthless native TEST ETH transfer.
# This is not an unattended funding service or an authorization for deployment.
# No mnemonic/key/password/plaintext file is printed or sent to GitHub.
set -euo pipefail
set +x
umask 077

refuse() { echo "R254_ONE_TIME_TEST_ETH_FUNDING_REFUSED: $*" >&2; exit 2; }
[[ $# -eq 2 && "$1" =~ ^[0-9a-f]{40}$ && "$2" == "--send-one" ]] ||
  refuse "exact immutable Git SHA and --send-one required"
[[ "$(id -un)" == "ayoubakrvm4706" && "$(id -u)" != 0 ]] ||
  refuse "run only as original non-root VM4706 owner"
[[ -t 0 && -t 2 ]] || refuse "interactive owner TTY required"

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ "$(git rev-parse HEAD)" == "$1" ]] ||
  refuse "reviewed source Git SHA mismatch"
[[ -z "$(git status --porcelain --untracked-files=no)" ]] ||
  refuse "tracked source changes found"

CAST="$HOME/.local/share/sse-r19-toolchains/foundry-v1.9.0/cast"
CAST_SHA="cae9d8a3e9a2c2f121879f39498472fee8a767318fc26ff7e3c73908133fdaa4"
KEYDIR="$HOME/.local/share/sse-r20-operator-private/withdrawal-keystore"
KEY="$KEYDIR/sse-r20-withdrawal"
SOURCE="0x13fb73aace8A11Be2899D047635A757a224Ce00B"
DEST="0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0"
RPC="http://127.0.0.1:18545"
APPROVAL="SEND-ONE-CHAIN31340-1-TEST-ETH"
# Create-only marker prevents accidentally rerunning this authorization.
SENTINEL="$HOME/.local/share/sse-r20-operator-private/.r254-one-time-v2-deployer-funding-attempted"

[[ -f "$CAST" && -x "$CAST" && ! -L "$CAST" ]] ||
  refuse "pinned Cast binary unavailable"
printf '%s  %s\n' "$CAST_SHA" "$CAST" | sha256sum --check --status ||
  refuse "Cast executable SHA256 does not match reviewed v1.9.0"
[[ -d "$KEYDIR" && ! -L "$KEYDIR" &&
   -f "$KEY" && ! -L "$KEY" ]] || refuse "existing encrypted owner keystore missing"
[[ "$(stat -c '%a' "$KEYDIR")" == 700 &&
   "$(stat -c '%a' "$KEY")" == 600 &&
   "$(stat -c '%u' "$KEYDIR")" == "$(id -u)" &&
   "$(stat -c '%u' "$KEY")" == "$(id -u)" ]] ||
  refuse "encrypted owner keystore ownership or permissions invalid"
[[ ! -e "$SENTINEL" && ! -L "$SENTINEL" ]] ||
  refuse "this one-time authorization was already attempted; investigate hash/nonce first"

SEND_HELP="$("$CAST" send --help)"
for option in --keystore --async --legacy --gas-limit --gas-price --value --nonce --rpc-url --chain --from; do
  grep -Fq -- "$option" <<< "$SEND_HELP" ||
    refuse "pinned Cast send does not support $option"
done

# Fresh exact-chain and transaction bounds. Every RPC request below is
# READ-ONLY, over fixed owner-VM localhost, with no proxy and no private key.
python3 -B - <<'PY'
import json, urllib.request

RPC="http://127.0.0.1:18545"
SRC="0x13fb73aace8A11Be2899D047635A757a224Ce00B"
DST="0xED0ED5E0526898c6E0e3C83140efcA12672E7ff0"
GENESIS="0x5f7cbcd4f1ddfbbedbdd2b180b83d9eff49d4b7263643858d7be2e9c243936bf"
VALUE=10**18
GAS_LIMIT=21_000
MAX_GAS_PRICE=1_000

def rpc(method, params):
    body=json.dumps({"jsonrpc":"2.0","id":1,"method":method,"params":params}).encode()
    req=urllib.request.Request(RPC,data=body,method="POST",
        headers={"Content-Type":"application/json"})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=8) as response:
        if response.status!=200:
            raise SystemExit("R254_REFUSED: RPC HTTP failure")
        blob=response.read(131073)
    if len(blob)>131072:
        raise SystemExit("R254_REFUSED: RPC response too large")
    obj=json.loads(blob)
    if type(obj) is not dict or obj.get("jsonrpc")!="2.0" or obj.get("id")!=1 or "error" in obj or "result" not in obj:
        raise SystemExit("R254_REFUSED: RPC error or malformed response")
    return obj["result"]

def quantity(value):
    if type(value) is not str or not value.startswith("0x"):
        raise SystemExit("R254_REFUSED: invalid RPC quantity")
    return int(value,16)

if quantity(rpc("eth_chainId",[]))!=31340:
    raise SystemExit("R254_REFUSED: wrong native blockchain")
genesis=rpc("eth_getBlockByNumber",["0x0",False])
if type(genesis) is not dict or str(genesis.get("hash","")).lower()!=GENESIS:
    raise SystemExit("R254_REFUSED: wrong original execution genesis")
latest=rpc("eth_getBlockByNumber",["latest",False])
if type(latest) is not dict or quantity(latest.get("gasLimit"))<GAS_LIMIT:
    raise SystemExit("R254_REFUSED: insufficient current block gas limit")
base=latest.get("baseFeePerGas")
if base is not None and quantity(base)>MAX_GAS_PRICE:
    raise SystemExit("R254_REFUSED: base fee exceeds authorized cap")
if quantity(rpc("eth_getTransactionCount",[SRC,"pending"]))!=0:
    raise SystemExit("R254_REFUSED: original owner nonce no longer zero (possible already sent)")
if quantity(rpc("eth_getBalance",[DST,"latest"]))!=0:
    raise SystemExit("R254_REFUSED: recipient already funded; do not double transfer")
if rpc("eth_getCode",[DST,"latest"])!="0x":
    raise SystemExit("R254_REFUSED: recipient has deployed code, not an empty EOA")
if rpc("eth_getCode",[SRC,"latest"])!="0x":
    raise SystemExit("R254_REFUSED: original source is not an ordinary EOA")
if quantity(rpc("eth_getBalance",[SRC,"pending"]))<VALUE+GAS_LIMIT*MAX_GAS_PRICE:
    raise SystemExit("R254_REFUSED: source cannot pay amount plus maximal gas")
estimated=quantity(rpc("eth_estimateGas",[{"from":SRC,"to":DST,
                              "value":hex(VALUE),"data":"0x"}]))
if estimated!=GAS_LIMIT:
    raise SystemExit("R254_REFUSED: actual transaction gas estimate not exactly 21000")
price=quantity(rpc("eth_gasPrice",[]))
if not 0<price<=MAX_GAS_PRICE:
    raise SystemExit("R254_REFUSED: current suggested gas price exceeds cap")
print("R254_ORIGINAL_CHAIN_GENESIS_AND_FUNDED_NONCE_ZERO_VERIFIED=true")
print("R254_NEW_V2_DEPLOYER_ZERO_BALANCE_AND_NO_CODE_VERIFIED=true")
print("R254_EXPECTED_GAS=21000")
print("R254_FIXED_MAX_GAS_PRICE_WEI=1000")
print("R254_TRANSFER_VALUE_WEI=1000000000000000000")
print("R254_MAX_TOTAL_COST_WEI=1000000000021000000")
print("R254_NO_TRANSACTION_YET=true",flush=True)
PY

echo "== Verify EXISTING encrypted owner's PUBLIC signing address ONLY =="
echo "Cast will request the EXISTING keystore password privately."
VERIFIED="$(env -u ETH_PASSWORD -u CAST_UNSAFE_PASSWORD -u CAST_PASSWORD -u ETH_PRIVATE_KEY -u PRIVATE_KEY \
  "$CAST" wallet address --keystore "$KEY")" ||
  refuse "existing encrypted owner keystore could not be unlocked"
[[ "$VERIFIED" =~ ^0x[0-9a-fA-F]{40}$ && "${VERIFIED,,}" == "${SOURCE,,}" ]] ||
  refuse "encrypted key signer DOES NOT match actual funded genesis EOA"
echo "R254_ENCRYPTED_OWNER_SIGNER_PUBLIC_ADDRESS_MATCHED=true"
echo
echo "Authorize EXACTLY ONE native test-only transaction:"
echo "Chain: 31340 (pinned original genesis); source nonce: 0"
echo "From: $SOURCE"
echo "To:   $DEST"
echo "Value: 1 TEST ETH (1000000000000000000 wei)"
echo "Legacy gas limit: 21000; FIXED gas price: 1000 wei per gas"
echo "Maximum gas fee: 21000000 wei; maximum total 1000000000021000000 wei"
read -r -p "Type $APPROVAL to allow ONE signed broadcast: " ANSWER
[[ "$ANSWER" == "$APPROVAL" ]] || refuse "owner did not authorize this one live transaction"

# Consume the attempt BEFORE touching the broadcast API. If Cast errors or
# times out, DO NOT rerun or delete marker without investigating chain state.
( set -C; : > "$SENTINEL" ) ||
  refuse "one-time attempt marker exists; refusing any retry"
chmod 600 "$SENTINEL"

echo "R254_BROADCAST_ATTEMPT_CONSUMED=true"
echo "== SINGLE CAST SEND; hidden keystore password prompt; NO automatic retry =="
env -u ETH_PASSWORD -u ETH_KEYSTORE -u ETH_KEYSTORE_ACCOUNT \
    -u ETH_PRIVATE_KEY -u PRIVATE_KEY -u CAST_UNSAFE_PASSWORD -u CAST_PASSWORD \
    -u ETH_GAS_PRICE -u ETH_GAS_LIMIT -u ETH_FROM -u CHAIN -u ETH_RPC_URL \
    -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u http_proxy -u https_proxy -u all_proxy \
    "$CAST" send "$DEST" \
       --value 1ether \
       --legacy --gas-limit 21000 --gas-price 1000wei \
       --nonce 0 --chain 31340 --from "$SOURCE" \
       --keystore "$KEY" --rpc-url "$RPC" --async

echo "R254_SINGLE_CAST_SEND_RETURNED=true"
echo "R254_DO_NOT_RERUN_THIS_SCRIPT=true"
echo "Record ONLY the public transaction hash printed by Cast; verify receipt independently."
