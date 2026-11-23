"""R178: unit test sensitive-free read-only Docker observation, no client mutation."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r178_existing_vm4709_startup_diagnostic as m

class R178Tests(unittest.TestCase):
    def test_only_docker_inspect_and_no_private_env_or_mount_source(self):
        operations=[]
        def fetch(argv):
            operations.append(argv)
            name=argv[-1]
            is_bn=name.endswith("-bn")
            return json.dumps([{
                "Name":"/"+name, "Image":"sha256:real-image-id",
                "RestartCount":6,
                "State":{"Running":False,"Restarting":True,"ExitCode":1},
                "Config":{"User":"0:0",
                          "Entrypoint":["/entrypoint.sh"],
                          "Env":["JWT_SECRET=NEVER_PRINT"],
                          "Cmd":["bn","--allow-insecure-genesis-sync"] if is_bn else ["--network-id=31340"]},
                "HostConfig":{"ReadonlyRootfs":True,"CapDrop":["ALL"],
                              "SecurityOpt":["no-new-privileges"]},
                "Mounts":[{"Destination":"/jwt/engine.jwt",
                           "Source":"/root/PRIVATE_ENG_JWT",
                           "RW":False}],
            }])
        r=m.check(fetch=fetch)
        self.assertEqual(len(operations),2)
        self.assertTrue(all(op[:2]==["docker","inspect"] for op in operations))
        self.assertTrue(r["state"]["bn"]["usesKnownGenesisOnly"])
        self.assertFalse(r["state"]["bn"]["usesCheckpointSync"])
        self.assertFalse(r["state"]["bn"]["usesIgnoreWeakSubjectivityCheck"])
        self.assertNotIn("NEVER_PRINT",json.dumps(r))
        self.assertNotIn("PRIVATE_ENG_JWT",json.dumps(r))
        self.assertTrue(r["state"]["el"]["readOnlyRootFs"])

    def test_unexpected_container_identity_refused(self):
        with self.assertRaisesRegex(m.Refused,"identity"):
            m.check(fetch=lambda argv:json.dumps([{"Name":"/not-the-real-node"}]))

if __name__=="__main__":
    unittest.main()
