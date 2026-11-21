"""R32 static/security checks only. Never create any real BLS keys here."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "r32_derive_existing_lighthouse_validators.sh"


class OfflineExistingLighthouseValidatorDerivationSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_shell_syntax_without_running_wallet_or_validators(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True)

    def test_existing_hd_wallet_only_and_no_new_wallet_seed(self):
        for text in (
            'sse-r27-bls-operator-private',
            'owner-wallet.pass',
            'recovery.mnemonic',
            'account validator --validator-dir /owner/validators create',
            '--wallets-dir /owner/wallets',
            '--wallet-password /owner/owner-wallet.pass',
        ):
            self.assertIn(text, self.source)
        self.assertNotIn('account wallet create', self.source)
        self.assertNotIn('account wallet --wallets-dir /owner/wallets create', self.source)
        self.assertNotIn('wallet new ', self.source)
        self.assertNotIn('--mnemonic-path ', self.source)

    def test_owner_acknowledges_real_backup_and_separately_authorizes_derivation(self):
        for word in (
            'BACKUP-CONFIRMED',
            'DERIVE-BLS-VALIDATORS',
            'read -r -p',
            '[[ -t 0 && -t 2 ]]',
        ):
            self.assertIn(word, self.source)
        self.assertLess(self.source.index('BACKUP-CONFIRMED'),
                        self.source.index('DERIVE-BLS-VALIDATORS'))

    def test_checksum_pinned_real_offline_lighthouse_binary(self):
        for word in (
            'tools/sse_pos_client_pins.py --refs',
            'tools/sse_pos_client_pins.py --image-ids',
            'docker image inspect',
            '[[ "$EXPECTED_ID" == "$ACTUAL_ID" ]]',
            '--pull never',
            '--network none',
            '--read-only',
            '--user "$(id -u):$(id -g)"',
            '--cap-drop ALL',
            '--security-opt no-new-privileges',
        ):
            self.assertIn(word, self.source)

    def test_chain31340_public_eoa_binding_is_not_mainnet_deposit_data(self):
        for word in (
            'sse_pos_public_keystore_export.py',
            '--withdrawal-address "$3"',
            'operator-own-one',
            'public-validator-contribution.json',
            'R32_EL_CL_GENESIS_CREATED=false',
            'R32_CHAIN31340_RUNNING=false',
            'Mainnet deposit data generated',
        ):
            self.assertIn(word, self.source)

    def test_exact_git_clean_checkout_and_create_only(self):
        for word in (
            "git rev-parse --verify HEAD^{commit}",
            'git diff --quiet --exit-code',
            'git diff --cached --quiet --exit-code',
            '! -e "$BASE/validators"',
            '! -e "$BASE/secrets"',
            'resource-limited single-host lab batch',
        ):
            self.assertIn(word, self.source)
        self.assertNotIn('git push ', self.source)
        self.assertNotIn('rm -rf ', self.source)

    def test_secret_logs_are_private_and_never_appear_on_terminal(self):
        for word in (
            'set +x',
            'umask 077',
            '> /dev/null 2> "$LOG"',
            'PRIVATE log',
            'R32_REAL_OWNER_BLS_VOTING_KEYSTORES_CREATED=true',
            'R32_INDEPENDENT_OPERATOR_FAULT_DOMAINS=1',
        ):
            self.assertIn(word, self.source)
        for forbidden in ('set -x', 'cat "$BASE/recovery.mnemonic"',
                          'tee "$LOG"', '--mnemonics '):
            self.assertNotIn(forbidden, self.source)

    def test_refuses_symlink_and_normalizes_keystore_directory_permissions(self):
        for word in (
            '-type l -print -quit',
            '-type d -exec chmod 700',
            '-type f -exec chmod 600',
            'R32_PRIVATE_SLASHING_PROTECTION_RETAINED=true',
            'slashing-protection',
        ):
            self.assertIn(word, self.source)


if __name__ == "__main__":
    unittest.main()
