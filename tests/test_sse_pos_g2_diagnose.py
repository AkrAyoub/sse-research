"""R37 classification only; must not echo dangerous raw Docker log content."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from sse_pos_g2_diagnose import categorize, CONTAINERS, MAX_LOG_BYTES

class R37SafeExistingG2DiagnosticTests(unittest.TestCase):
    def test_fixed_container_names_no_legacy_chains(self):
        self.assertEqual(CONTAINERS, ("sse31340-g2-el", "sse31340-g2-bn", "sse31340-g2-vc"))

    def test_lighthouse_config_and_genesis_error_classifications(self):
        c = categorize("Failed to load genesis state: InvalidSsz\nUnsupported fork version in config.yaml")
        self.assertIn("GENESIS_SSZ_OR_STATE_REJECTED", [x["category"] for x in c["errorClassifications"]])
        self.assertIn("CONFIG_OR_FORK_REJECTED", [x["category"] for x in c["errorClassifications"]])

    def test_permission_failure_distinct_from_engine_connection(self):
        c = categorize("CRIT Failed to start beacon reason: Permission denied\nERROR execution endpoint connection refused")
        d = [x["category"] for x in c["errorClassifications"]]
        self.assertIn("READ_ONLY_OR_PERMISSION_FAILURE", d)
        self.assertIn("EXECUTION_ENDPOINT_UNAVAILABLE", d)

    def test_never_echo_secret_bearing_log_strings(self):
        private = "password MYSECRET_PHRASE x y z key 0x" + "ab" * 32
        c = categorize("ERROR genesis with " + private)
        self.assertNotIn("MYSECRET_PHRASE", str(c))
        self.assertNotIn("0xabab", str(c))
        self.assertFalse(c["rawLogTextEmitted"])
        self.assertFalse(c["secretsOrKeystoreContentEmitted"])

    def test_unknown_error_not_dropped_or_reproduced(self):
        c = categorize("ERROR VioletDragonEngineException: purposefully arbitrary content")
        self.assertEqual(c["unclassifiedPossibleErrorLines"], 1)
        self.assertNotIn("VioletDragonEngineException", str(c))


    def test_besu_java_exception_names_are_static_and_no_message_is_ever_output(self):
        from sse_pos_g2_diagnose import safe_besu_exception_signatures
        secret = "DO_NOT_EMIT_RANDOM_SENTENCE_2026_987612"
        raw = (
            "ERROR Exception in thread main java.lang.NullPointerException: " + secret + "\n"
            "Caused by: java.lang.UnsupportedOperationException: " + secret + "\n"
            "ERROR Unrecognized field `foo` in genesis.json: " + secret + "\n"
        )
        report = safe_besu_exception_signatures(raw)
        classes = [x["class"] for x in report["knownJavaExceptionNames"]]
        self.assertIn("NullPointerException", classes)
        self.assertIn("UnsupportedOperationException", classes)
        signatures = [x["signature"] for x in report["fixedBesuStartupSignatureCounts"]]
        self.assertIn("GENESIS_FIELD_NOT_RECOGNIZED", signatures)
        self.assertNotIn(secret, str(report))
        self.assertFalse(report["rawErrorMessagesEmitted"])
        self.assertFalse(report["unrecognizedExceptionNamesEmitted"])

    def test_unknown_exception_class_never_echoed(self):
        from sse_pos_g2_diagnose import safe_besu_exception_signatures
        secret = "SecretNameThatLooksLikeAnException"
        data = safe_besu_exception_signatures("ERROR java.lang." + secret + ": reason")
        self.assertNotIn(secret, str(data))
        self.assertEqual(data["knownJavaExceptionNames"], [])

    def test_besu_static_signature_classes_do_not_require_error_keyword(self):
        from sse_pos_g2_diagnose import safe_besu_exception_signatures
        r = safe_besu_exception_signatures(
            "Caused by: java.lang.IllegalStateException: this is private\n"
            "at org.hyperledger.besu.crypto.UnsupportedOperationException"
        )
        names = [x["class"] for x in r["knownJavaExceptionNames"]]
        self.assertIn("IllegalStateException", names)
        self.assertIn("UnsupportedOperationException", names)

    def test_diagnostics_read_bounded_logs_only(self):
        script = (ROOT / "tools/sse_pos_g2_diagnose.py").read_text("utf-8")
        self.assertIn('"--tail", "160"', script)
        self.assertLessEqual(MAX_LOG_BYTES, 300_000)
        self.assertNotIn("print(logs)", script)
        self.assertNotIn("print(raw)", script)

if __name__ == "__main__":
    unittest.main()
