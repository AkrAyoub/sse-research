# R19 — VM4706 GitHub read-only source checkout and exact-SHA tests

**Status:** first developer experiment instructions, source code committed but NOT yet observed executed on VM4706. Source repository `AkrAyoub/sse-research` is PRIVATE. GitHub deploy keys here are temporary SOURCE access for one *developer-operated research VM*, **never permission to join the SSE protocol**. A future independent external PC must obtain the public release/genesis from multiple mirrors with no private repo account or invitation. Refer to #33, #36, #37 and `docs/experiments/VM4706_2026-11-19.md`.

VM4706 already confirmed: Ubuntu 24.04.4; 4 vCPU/11 GiB/93 GiB available; private 10.50.56.2; working DNS and outbound HTTPS; Python 3.12.3; git 2.43.0; Docker daemon 29.1.3 via `sudo -n` and cgroup v2; AppArmor enabled and /etc/subuid/subgid 65536; no Forge/Besu/Lighthouse/Caddy, no rootless helpers yet. No permanent Docker group permission needed for this source test.

## A. Authenticate GitHub SSH host (without blindly trusting ssh-keyscan)

GitHub's published ED25519 host fingerprint as checked on 2026-11-19:

```text
SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
```

Source: https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints

From VM4706, as normal user:

```bash
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"
GITHUB_EXPECTED_ED25519='SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU'
GITHUB_KEY="$(ssh-keyscan -T 10 -t ed25519 github.com 2>/dev/null | grep '^github.com ssh-ed25519 ' | head -n 1)"
if [ -z "$GITHUB_KEY" ]; then
    echo 'STOP: GitHub SSH port 22 unavailable; do not disable host checking'
else
    GITHUB_ACTUAL="$(printf '%s\n' "$GITHUB_KEY" | ssh-keygen -lf - -E sha256 | awk '{print $2}')"
    if [ "$GITHUB_ACTUAL" = "$GITHUB_EXPECTED_ED25519" ]; then
        touch "$HOME/.ssh/known_hosts"
        chmod 600 "$HOME/.ssh/known_hosts"
        if ! grep -Fqx "$GITHUB_KEY" "$HOME/.ssh/known_hosts"; then
            printf '%s\n' "$GITHUB_KEY" >> "$HOME/.ssh/known_hosts"
        fi
        echo 'GITHUB_SSH_ED25519_HOST_AUTHENTICATED=true'
    else
        echo 'STOP: GitHub host key fingerprint MISMATCH'; exit 2
    fi
fi
```

If port 22 is blocked by infrastructure, investigate GitHub's officially documented SSH-over-HTTPS-port or approved HTTPS read-only credentials; do not disable host verification or paste secret tokens in issue/chat/logs. This optional host-key block has a limited local `known_hosts` file mutation only when verified.

## B. Generate ONE read-only development deploy key and add to private repo

Execute only when GitHub SSH access is available:

```bash
test ! -e "$HOME/.ssh/sse_vm4706_readonly" || { echo 'existing key: stop; do not overwrite'; exit 2; }
ssh-keygen -t ed25519 -a 100 -N '' \
    -f "$HOME/.ssh/sse_vm4706_readonly" \
    -C 'sse-vm4706-readonly'
chmod 600 "$HOME/.ssh/sse_vm4706_readonly"
cat "$HOME/.ssh/sse_vm4706_readonly.pub"
```

In a trusted GitHub browser session, open repository **Settings → Deploy keys → Add deploy key**, paste only the printed **PUBLIC** `.pub` key. Label `vm4706-readonly-test`. Leave **Allow write access UNCHECKED**. The private key never leaves VM4706. Do not paste the private key or add an SSE role/operator/validator approval through GitHub. Revoke the deploy key when finished. Official instructions: https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys

## C. Clone, pin a reviewed GitHub commit and run the source tests

Use the **exact** SHA recorded on current draft PR #35 when the journal and script have been committed. Example shown below is a placeholder on purpose, to prevent running a moving `main`; replace the value with the SHA displayed in the same ChatGPT experiment checkpoint or PR head.

```bash
cd "$HOME"
GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes" \
  git clone --no-checkout git@github.com:AkrAyoub/sse-research.git sse-research
cd "$HOME/sse-research"
GIT_SSH_COMMAND="ssh -i $HOME/.ssh/sse_vm4706_readonly -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes" \
  git fetch --no-tags origin feature/r19-fresh-external-node-preflight
EXPECTED_SHA=REPLACE_WITH_EXACT_PR35_HEAD_40_HEX_DIGITS
git switch --detach "$EXPECTED_SHA"
bash scripts/r19_verify_fresh_host.sh "$EXPECTED_SHA" full_node,validator
```

Never set the desired commit to `origin/main` or run unspecified latest commits. The script checks exact 40-character SHA, refuses if tracked files are modified, runs the stdlib-only unit tests and read-only inventory. No `pip install`, `sudo docker`, Foundry, VM onboarding, key generation, contracts or network calls are needed to execute the source test after clone.

## D. Evidence to send back and automate next

Report redacted `GITHUB_SSH_ED25519_HOST_AUTHENTICATED` (if performed), the Git checkout **SHA**, number of unittest tests and their pass/fail result, and the JSON inventory. If SSH port 22 or authentication fails, report the **error text only**, never a private key. This is the first source-only acceptance; it should print `SSE_R19_ACTUAL_PUBLIC_POS_JOIN_VERIFIED=false`.

**Automation debt:** one-time developer-only deploy-key registration, secure GitHub host pinning, clone, manifest verification, role choice and tests. In the **final** independent external node flow, source release is **public** and hash-pinned with several mirrors; no deploy key or GitHub member access exists, and nobody centrally approves peer joining.
