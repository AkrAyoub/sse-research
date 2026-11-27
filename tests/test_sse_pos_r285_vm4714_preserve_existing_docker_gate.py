"""R285: real previously observed stopped VM4714 containers preserved, mocked."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
import sse_pos_r285_vm4714_preserve_existing_docker_readonly_gate as mod


class TestR285OldExitedHelloWorldCoexistenceOnly(unittest.TestCase):
    def setup_case(self,*,extra_id=None,changing_inventory=False,
                   running=False,wrong_image=False,wrong_name=False,
                   bad_exit=False,cli_failure=False):
        ids=sorted(mod.EXPECTED)
        inspect_data=[]
        for index,id_ in enumerate(ids):
            inspect_data.append({
                "Id":id_,
                "Name":"/"+(
                    "unexpected_other_container" if wrong_name and index==0
                    else mod.EXPECTED[id_]
                ),
                "Config":{"Image":
                          "busybox" if wrong_image and index==0
                          else "hello-world"},
                "State":{
                    "Status":"running" if running and index==0 else "exited",
                    "Running":True if running and index==0 else False,
                    "Paused":False,"Restarting":False,
                    "ExitCode":4 if bad_exit and index==0 else 0
                }
            })
        calls=[]
        def run(cmd,**kwargs):
            self.assertEqual(cmd[:5],[
                "sudo","-n","docker","--host",mod.ROOTFUL])
            self.assertFalse(kwargs["shell"])
            self.assertEqual(kwargs["timeout"],10)
            for key in ("DOCKER_HOST","DOCKER_CONTEXT",
                        "DOCKER_TLS_VERIFY","DOCKER_CERT_PATH"):
                self.assertNotIn(key,kwargs["env"])
            self.assertNotIn("rm",cmd)
            self.assertNotIn("stop",cmd)
            self.assertNotIn("start",cmd)
            self.assertNotIn("run",cmd)
            calls.append(cmd)
            if cli_failure:
                return subprocess.CompletedProcess(cmd,1,"","permission denied")
            if cmd[5:]==["ps","-a","--no-trunc","--format","{{.ID}}"]:
                observed=ids[:]
                if extra_id and len(calls)==1:
                    observed.append(extra_id)
                if changing_inventory and len(calls)>2:
                    observed.pop()
                return subprocess.CompletedProcess(cmd,0,"\n".join(observed)+"\n","")
            if cmd[5:]==["container","inspect"]+ids:
                return subprocess.CompletedProcess(cmd,0,json.dumps(inspect_data),"")
            raise AssertionError("unexpected read-only command "+repr(cmd))
        return run,calls

    def invoke(self,run):
        return mod.audit(run=run,uid_fn=lambda:1001,
                         username_fn=lambda uid:"ayoubakrvm4714")

    def test_exact_three_unchanged_benign_exited_image_names_allow_trial_only(self):
        run,calls=self.setup_case()
        with patch.dict(mod.os.environ,{
            "DOCKER_HOST":"tcp://remote.invalid:2375",
            "DOCKER_CONTEXT":"not-local",
            "DOCKER_TLS_VERIFY":"1",
            "DOCKER_CERT_PATH":"/tmp/not-used",
        }):
            report=self.invoke(run)
        self.assertTrue(report["exactThreeExistingContainerIdsNamesAndImagesVerified"])
        self.assertTrue(report["safeToAttemptSeparateOwnerApprovedIsolatedWorker"])
        self.assertFalse(report["newWorkerCreated"])
        self.assertFalse(report["oldContainerChanged"])
        self.assertFalse(report["transactionSignedOrSent"])
        self.assertEqual(len(report["verifiedOldContainers"]),3)
        self.assertEqual(len(calls),3)

    def test_unknown_new_fourth_container_refuses_before_inspect(self):
        run,calls=self.setup_case(extra_id="a"*64)
        with self.assertRaisesRegex(mod.Refused,"inventory DIFFERENT"):
            self.invoke(run)
        self.assertEqual(len(calls),1)

    def test_existing_running_container_refuses(self):
        run,_=self.setup_case(running=True)
        with self.assertRaisesRegex(mod.Refused,"unexpected/mutable"):
            self.invoke(run)

    def test_existing_container_wrong_image_or_name_refuses(self):
        for opts in ({"wrong_image":True},{"wrong_name":True},{"bad_exit":True}):
            with self.subTest(opts=opts):
                run,_=self.setup_case(**opts)
                with self.assertRaisesRegex(mod.Refused,"unexpected/mutable"):
                    self.invoke(run)

    def test_existing_container_changed_between_checks_refuses(self):
        run,_=self.setup_case(changing_inventory=True)
        with self.assertRaisesRegex(mod.Refused,"inventory DIFFERENT"):
            self.invoke(run)

    def test_readonly_sudo_not_available_refuses(self):
        run,_=self.setup_case(cli_failure=True)
        with self.assertRaisesRegex(mod.Refused,"access denied"):
            self.invoke(run)

    def test_wrong_owner_or_root_refuses_before_docker(self):
        def forbidden(*args,**kwargs):
            raise AssertionError("Docker must never execute")
        with self.assertRaisesRegex(mod.Refused,"dedicated VM4714"):
            mod.audit(run=forbidden,uid_fn=lambda:0,
                      username_fn=lambda uid:"root")
        with self.assertRaisesRegex(mod.Refused,"dedicated VM4714"):
            mod.audit(run=forbidden,uid_fn=lambda:1001,
                      username_fn=lambda uid:"ayoubakrvm4709")

    def test_main_requires_explicit_audit_no_mutation_mode(self):
        import contextlib,io
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main([]),2)

    def test_baseline_ids_and_names_exact_from_owner_real_inventory(self):
        self.assertEqual(mod.EXPECTED,{
            "0736e142f5d925c8a63771d6ce08d02cc2723509e06f9d3b638f35d306f88084":"serene_sammet",
            "dc71dc02b5e4375535c2fc69e90c0dc62322e72a4550b46e0c7f6d90f6e9434c":"friendly_saha",
            "ff494d7657a18a7f0a6ecce74ceb9edf97250c8ae64cacaa23aa166d8524aade":"zealous_wilson",
        })


if __name__=="__main__":
    unittest.main()
