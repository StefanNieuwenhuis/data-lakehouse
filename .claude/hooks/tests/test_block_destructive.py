"""Tests for the PreToolUse guard .claude/hooks/block_destructive.py (issue #13).

Every case drives the hook through its stdin JSON contract and checks the exit
code: 0 allows the command, 2 blocks it. Stdlib unittest only, Python 3.9+.
"""

import tempfile
import unittest
from unittest import mock

from hooktest import load_hook, run_entrypoint, run_hook

HOOK = "block_destructive.py"
ALLOW, BLOCK = 0, 2

# The wrappers and chain operators the hook strips or splits on.
WRAPPED = [
    "env {cmd}",
    "sudo {cmd}",
    "KUBECONFIG=/tmp/kc {cmd}",
    "env A=1 B=2 {cmd}",
    "sudo env X=1 {cmd}",
]
CHAINED = [
    "echo hi && {cmd}",
    "true; {cmd}",
    "echo hi | {cmd}",
    "false || {cmd}",
    "cd /tmp && echo ok; true | {cmd}",
    "echo start\n{cmd}",
    "(cd /tmp && {cmd})",
]


class GuardTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def payload(self, command):
        return {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "cwd": self.cwd,
        }

    def assertExit(self, command, expected):
        proc = run_hook(HOOK, self.payload(command))
        self.assertEqual(
            proc.returncode,
            expected,
            f"command {command!r}: expected exit {expected}, got "
            f"{proc.returncode}; stderr: {proc.stderr.strip()}",
        )
        return proc

    def assertAllowed(self, command):
        return self.assertExit(command, ALLOW)

    def assertBlocked(self, command):
        proc = self.assertExit(command, BLOCK)
        self.assertIn("Blocked by", proc.stderr)
        return proc

    def assertAllowedEverywhere(self, command):
        """Allowed as is, after every wrapper and inside every chain."""
        for form in ["{cmd}"] + WRAPPED + CHAINED:
            with self.subTest(form=form):
                self.assertAllowed(form.format(cmd=command))

    def assertBlockedEverywhere(self, command):
        """Blocked as is, after every wrapper and inside every chain."""
        for form in ["{cmd}"] + WRAPPED + CHAINED:
            with self.subTest(form=form):
                self.assertBlocked(form.format(cmd=command))


class HelmUninstallNamespaceTest(GuardTestCase):
    """AC: helm uninstall|delete|del|un only in a namespace matching ^lh-[a-z]+$."""

    VERBS = ("uninstall", "delete", "del", "un")
    NS_FORMS = ("-n {ns}", "-n={ns}", "--namespace {ns}", "--namespace={ns}")

    def test_allowed_in_lh_namespace_for_every_verb_and_flag_form(self):
        for verb in self.VERBS:
            for form in self.NS_FORMS:
                for ns in ("lh-storage", "lh-catalog", "lh-ops"):
                    with self.subTest(verb=verb, form=form, ns=ns):
                        flag = form.format(ns=ns)
                        self.assertAllowed(f"helm {verb} seaweedfs {flag}")

    def test_allowed_with_namespace_flag_before_the_verb(self):
        self.assertAllowed("helm -n lh-storage uninstall seaweedfs")
        self.assertAllowed("helm --namespace=lh-catalog uninstall lakekeeper --wait")

    def test_blocked_for_non_lh_namespaces(self):
        for ns in (
            "dev",
            "default",
            "kube-system",
            "lh-",
            "lh-Storage",
            "lh-storage-x",
        ):
            for verb in self.VERBS:
                for form in self.NS_FORMS:
                    with self.subTest(ns=ns, verb=verb, form=form):
                        flag = form.format(ns=ns)
                        self.assertBlocked(f"helm {verb} seaweedfs {flag}")

    def test_blocked_for_lookalike_namespaces(self):
        for ns in ("lh-storage1", "xlh-storage", "LH-storage", "lh_storage", ""):
            with self.subTest(ns=ns):
                self.assertBlocked(f"helm uninstall seaweedfs --namespace={ns}")

    def test_blocked_without_namespace(self):
        for verb in self.VERBS:
            with self.subTest(verb=verb):
                self.assertBlocked(f"helm {verb} seaweedfs")

    def test_blocked_when_namespace_flag_has_no_value(self):
        self.assertBlocked("helm uninstall seaweedfs -n")

    def test_blocked_when_any_namespace_flag_is_not_lh(self):
        # Helm uses the last flag; the guard requires every flag to pass.
        self.assertBlocked("helm uninstall x -n lh-storage -n default")
        self.assertBlocked("helm uninstall x -n default --namespace lh-storage")

    def test_block_message_names_the_rule(self):
        proc = self.assertBlocked("helm uninstall x -n default")
        self.assertIn("^lh-[a-z]+$", proc.stderr)
        self.assertIn("'default'", proc.stderr)

    def test_allowed_after_wrappers_and_in_chains(self):
        self.assertAllowedEverywhere("helm uninstall seaweedfs -n lh-storage")

    def test_blocked_after_wrappers_and_in_chains(self):
        for cmd in (
            "helm uninstall seaweedfs -n default",
            "helm uninstall seaweedfs",
            "helm del seaweedfs --namespace=lh-Storage",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlockedEverywhere(cmd)

    def test_blocked_with_full_path_to_helm(self):
        self.assertBlocked("/usr/local/bin/helm uninstall x -n dev")

    def test_other_helm_commands_are_allowed(self):
        self.assertAllowed("helm list -A")
        self.assertAllowed("helm upgrade --install x charts/x -n default")
        self.assertAllowed("helm template ci charts/seaweedfs")


class MinikubeDeleteProfileTest(GuardTestCase):
    """AC: minikube delete is blocked unless the profile is `spike`."""

    def test_allowed_for_spike_in_every_flag_form(self):
        for flag in ("-p spike", "-p=spike", "--profile spike", "--profile=spike"):
            with self.subTest(flag=flag):
                self.assertAllowed(f"minikube delete {flag}")

    def test_allowed_with_profile_before_the_verb(self):
        self.assertAllowed("minikube -p spike delete")

    def test_blocked_bare(self):
        self.assertBlocked("minikube delete")

    def test_blocked_for_other_profiles(self):
        for profile in ("dev", "minikube", "spike2", "Spike", "spike-x", ""):
            for form in ("-p {p}", "-p={p}", "--profile {p}", "--profile={p}"):
                with self.subTest(profile=profile, form=form):
                    flag = form.format(p=profile)
                    self.assertBlocked(f"minikube delete {flag}")

    def test_blocked_when_profile_flag_has_no_value(self):
        self.assertBlocked("minikube delete -p")

    def test_blocked_when_any_profile_flag_is_not_spike(self):
        self.assertBlocked("minikube delete -p spike -p dev")
        self.assertBlocked("minikube delete --profile=dev -p spike")

    def test_blocked_with_all(self):
        for cmd in (
            "minikube delete --all",
            "minikube delete --all -p spike",
            "minikube delete -p spike --all",
            "minikube delete --profile=spike --all=true",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlocked(cmd)

    def test_blocked_with_purge(self):
        # --purge removes ~/.minikube, which every profile, dev included, uses.
        self.assertBlocked("minikube delete -p spike --purge")

    def test_block_message_tells_the_agent_to_ask_the_user(self):
        for cmd in (
            "minikube delete",
            "minikube delete -p dev",
            "minikube delete --all -p spike",
        ):
            with self.subTest(cmd=cmd):
                proc = self.assertBlocked(cmd)
                self.assertIn("Ask the user", proc.stderr)

    def test_allowed_after_wrappers_and_in_chains(self):
        self.assertAllowedEverywhere("minikube delete -p spike")

    def test_blocked_after_wrappers_and_in_chains(self):
        for cmd in (
            "minikube delete",
            "minikube delete -p dev",
            "minikube delete --all -p spike",
        ):
            with self.subTest(cmd=cmd):
                self.assertBlockedEverywhere(cmd)

    def test_other_minikube_commands_are_allowed(self):
        self.assertAllowed("minikube status -p dev")
        self.assertAllowed("minikube start -p dev --cpus 6")


class FailClosedTest(GuardTestCase):
    """AC: any error in the guard blocks (exit 2); `ls` is allowed (exit 0)."""

    def assertFailsClosed(self, stdin):
        proc = run_hook(HOOK, stdin)
        self.assertEqual(proc.returncode, BLOCK, proc.stderr)
        self.assertIn("Blocked by", proc.stderr)
        self.assertIn("block_destructive.py", proc.stderr)

    def test_malformed_json_blocks(self):
        self.assertFailsClosed('{"tool_input": {"command": "ls"')

    def test_empty_stdin_blocks(self):
        self.assertFailsClosed("")

    def test_whitespace_only_stdin_blocks(self):
        self.assertFailsClosed(" \n")

    def test_payload_without_tool_input_blocks(self):
        self.assertFailsClosed({"tool_name": "Bash", "cwd": self.cwd})

    def test_payload_with_non_object_tool_input_blocks(self):
        self.assertFailsClosed({"tool_input": "ls", "cwd": self.cwd})

    def test_payload_without_command_blocks(self):
        self.assertFailsClosed({"tool_input": {}, "cwd": self.cwd})

    def test_json_that_is_not_an_object_blocks(self):
        self.assertFailsClosed("[]")

    def test_helm_uninstall_in_default_namespace_blocks(self):
        self.assertBlocked("helm uninstall x -n default")

    def test_ls_is_allowed(self):
        self.assertAllowed("ls")

    def test_internal_error_blocks(self):
        module = load_hook(HOOK)
        with mock.patch.object(
            module, "split_commands", side_effect=RuntimeError("injected")
        ):
            code, _, err = run_entrypoint(module, self.payload("ls"))
        self.assertEqual(code, BLOCK)
        self.assertIn("RuntimeError: injected", err)

    def test_unbalanced_quotes_still_check_each_command(self):
        self.assertBlocked("echo 'oops; helm uninstall x -n default")
        self.assertAllowed("echo 'oops; ls")


class ExistingRulesTest(GuardTestCase):
    """Regression: the rules that predate issue #13 still hold."""

    def test_kubectl_delete_namespace_blocked(self):
        self.assertBlocked("kubectl delete ns lh-storage")
        self.assertBlocked("kubectl delete namespace/lh-ops")
        self.assertAllowed("kubectl delete pod x -n lh-storage")

    def test_git_push_to_main_blocked(self):
        self.assertBlocked("git push origin main")
        self.assertBlocked("git push origin HEAD:main")
        self.assertBlocked("git push --mirror")
        self.assertAllowed("git push -u origin feat/13-hooks-fail-closed-py39")

    def test_rm_rf_outside_repo_blocked(self):
        self.assertBlocked("rm -rf /")
        self.assertBlocked("rm -rf ~")
        self.assertBlocked("rm -rf $UNSET_VAR_FOR_TEST/x")
        self.assertAllowed("rm -rf ./build")
        self.assertAllowed("rm -r /tmp/x")


if __name__ == "__main__":
    unittest.main()
