"""R57 fail-closed source-only image-provenance and no-chain-start guards."""
import pathlib
import re
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=(ROOT/"scripts/r57_acquire_nonsigning_pinned_clients.sh").read_text("utf-8")
PIN=(ROOT/"config/pos_client_image_pins.json").read_text("utf-8")
import json
PINS=json.loads(PIN)["images"]

class R57ClientAcquisitionTests(unittest.TestCase):
    def test_exact_pinned_manifest_refs_are_used(self):
        for name in ("besu", "lighthouse"):
            x=PINS[name]
            self.assertIn(x["ref"],SRC)
            self.assertIn(x["tag"],SRC)
            self.assertIn(x["imageId"],SRC)
    def test_two_modes_and_operator_consent(self):
        self.assertIn('MODE="${1:---plan}"',SRC)
        self.assertIn('"--pull"',SRC)
        self.assertIn('[[ -t 0 && -t 2 ]]',SRC)
        self.assertIn('PULL-EXACT-R57-CLIENTS',SRC)
    def test_archive_and_original_signer_guards(self):
        self.assertIn('chain31340-public-native-observer-v1.tar.gz',SRC)
        self.assertIn('1d21e6bfb7609d1797edd9d36561b1dc47a520153d1c6f698f807c29266c2ce7',SRC)
        for p in ('sse-r35-chain31340-g2-private','sse-r27-bls-operator-private','sse31340-g2-vc'):
            self.assertIn(p,SRC)
    def test_actual_registry_pull_by_digest_and_pinned_image_id(self):
        self.assertIn('docker pull --platform linux/amd64 "$BESU_REF"', SRC)
        self.assertIn('docker pull --platform linux/amd64 "$LIGHTHOUSE_REF"', SRC)
        self.assertIn('verify_pulled_ref BESU "$BESU_REF" "$BESU_ID"', SRC)
        self.assertIn('verify_pulled_ref LIGHTHOUSE "$LIGHTHOUSE_REF" "$LIGHTHOUSE_ID"', SRC)
    def test_no_mutation_from_readonly_plan(self):
        before=SRC.split('if [[ "$MODE" == "--plan" ]] then')[0] if False else SRC.split('if [[ "$MODE" == "--plan" ]]; then')[0]
        for s in ("docker pull", "docker tag", "docker run", "docker network create"):
            self.assertNotIn(s,before)
        self.assertIn("R57_PLAN_READ_ONLY_COMPLETE=true", SRC)
    def test_no_launch_or_privileged_p2p_ports(self):
        for bad in ('docker compose up', 'docker run -d', '--publish ', '--network host',
                    'wallet create', 'validators-dir', 'engine.jwt', 'zerotier-cli join'):
            self.assertNotIn(bad, SRC)
    def test_offline_version_probes_preserve_security(self):
        self.assertIn('--network none --read-only', SRC)
        self.assertIn('--cap-drop ALL', SRC)
        self.assertIn('--security-opt no-new-privileges',SRC)
        self.assertIn('--entrypoint lighthouse',SRC)
        self.assertNotIn('--entrypoint besu',SRC)
    def test_existing_mismatched_tag_refused(self):
        self.assertIn('pre-existing tag has incorrect image ID or platform',SRC)
        self.assertIn('verify_existing_tag BESU "$BESU_TAG" "$BESU_ID"',SRC)
        self.assertIn('verify_existing_tag LIGHTHOUSE "$LIGHTHOUSE_TAG" "$LIGHTHOUSE_ID"',SRC)

if __name__=="__main__":
    unittest.main()
