"""Security source checks for R28 recovery of existing TEST-only EOA."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "r28_verify_existing_cast_withdrawal.sh"


class ExistingEncryptedWalletRecoverySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax_valid_without_running_any_password_prompt(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_preserves_existing_path_and_never_creates_new_key(self):
        for item in (
            'DIR="$HOME/.local/share/sse-r20-operator-private/withdrawal-keystore"',
            'FILE="$DIR/sse-r20-withdrawal"',
            'R28_EXISTING_ENCRYPTED_WITHDRAWAL_KEY_PRESERVED=true',
            'R28_BLS_VALIDATOR_SIGNING_KEYS_CREATED=false',
        ):
            self.assertIn(item, self.source)
        self.assertNotIn('wallet new "', self.source)
        self.assertNotIn('mkdir -m', self.source)
        self.assertNotIn('rm -- "$FILE"', self.source)

    def test_exact_git_revision_and_pinned_cast_identity_checked(self):
        for item in (
            'git rev-parse --verify HEAD^{commit}',
            'git diff --quiet --exit-code',
            'git diff --cached --quiet --exit-code',
            'cae9d8a3e9a2c2f121879f39498472fee8a767318fc26ff7e3c73908133fdaa4',
            'sha256sum --check --status',
        ):
            self.assertIn(item, self.source)

    def test_hidden_password_only_cast_wallet_address_never_export_private_key(self):
        self.assertIn('wallet address --keystore "$FILE"', self.source)
        self.assertIn('R28_WITHDRAWAL_ADDRESS_VERIFIED_BY_PINNED_CAST=true', self.source)
        self.assertNotIn('wallet decrypt', self.source)
        self.assertNotIn('--unsafe-password', self.source)
        self.assertNotIn('cast wallet private-key', self.source)
        self.assertIn('set +x', self.source)
        self.assertNotIn('set -x', self.source)

    def test_user_expected_public_address_compared_to_real_local_key(self):
        self.assertIn('! "$2" =~ ^0x[0-9a-fA-F]{40}$', self.source)
        self.assertIn('[[ "$VERIFIED" =~ ^0x[0-9a-fA-F]{40}$ ]]', self.source)
        self.assertIn('[[ "${VERIFIED,,}" == "${2,,}" ]]', self.source)

    def test_private_owner_permission_and_real_encrypted_envelope(self):
        for item in (
            'stat -c',
            '== 700',
            '== 600',
            'tools/sse_pos_local_wallet_report.py "$DIR"',
            '[[ -t 0 && -t 2 ]]',
            'R28_NATIVE_CHAIN31340_LAUNCHED=false',
        ):
            self.assertIn(item, self.source)


if __name__ == "__main__":
    unittest.main()
