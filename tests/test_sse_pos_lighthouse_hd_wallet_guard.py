"""Static defensive regression for owner-private Lighthouse wallet script.

These checks DO NOT generate a mnemonic, wallet, signing key, or validator.
A source-only test cannot establish cryptographic custody or Docker safety.
"""
from pathlib import Path
import re
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "r27_create_local_lighthouse_hd_wallet.sh"


class LighthouseHdWalletSourceGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax_is_valid_without_running_keygen(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_explicit_exact_commit_clean_tree_and_owner_tty_consent(self):
        for required in (
            '[[ $# -ne 1',
            'git rev-parse --verify HEAD^{commit}',
            'git diff --quiet --exit-code',
            'git diff --cached --quiet --exit-code',
            '[[ -t 0 && -t 2 ]]',
            'CREATE-BLS-HD-WALLET',
        ):
            with self.subTest(check=required):
                self.assertIn(required, self.src)

    def test_cryptographic_artifacts_never_printed_to_terminal(self):
        self.assertIn('--mnemonic-output-path /owner/recovery.mnemonic', self.src)
        self.assertIn('> /dev/null 2> "$LOG"', self.src)
        self.assertIn('chmod 0600 "$LOG"', self.src)
        self.assertNotIn('tee ', self.src)
        self.assertNotIn('cat "$BASE/recovery.mnemonic"', self.src)
        self.assertIn('set +x', self.src)
        self.assertNotIn("set -x", self.src)

    def test_no_public_network_or_privileged_key_generation_container(self):
        for flag in (
            "--network none", "--read-only", "--pull never",
            "--pids-limit 128", "--cap-drop ALL",
            "--security-opt no-new-privileges", '--user "$(id -u):$(id -g)"'
        ):
            self.assertIn(flag, self.src)

    def test_real_pinned_lighthouse_docker_identity_preflight(self):
        for flag in (
            "sse_pos_client_pins.py --refs",
            "sse_pos_client_pins.py --image-ids",
            "sudo -n docker image inspect",
            '[[ "$ACTUAL_ID" == "$EXPECTED_ID" ]]',
        ):
            self.assertIn(flag, self.src)

    def test_random_hd_wallet_not_reused_or_initialized_twice(self):
        self.assertIn('[[ ! -e "$BASE" && ! -L "$BASE" ]]', self.src)
        self.assertIn('mkdir -m 0700 -- "$BASE"', self.src)
        self.assertIn('--password-file /owner/owner-wallet.pass', self.src)
        self.assertIn('--name sse31340-operator', self.src)
        self.assertNotIn('--mnemonics ', self.src)
        self.assertNotIn('--seed ', self.src)

    def test_all_created_secrets_owner_only_and_scope_labels_honest(self):
        for text in (
            '"$BASE/owner-wallet.pass"',
            '"$BASE/recovery.mnemonic"',
            'stat -c',
            'R27_BLS_VALIDATOR_SIGNING_KEYS_CREATED=false',
            'R27_CHAIN31340_GENESIS_GENERATED=false',
            'R27_PUBLIC_POS_NETWORK_DEPLOYED=false',
        ):
            self.assertIn(text, self.src)


if __name__ == "__main__":
    unittest.main()
