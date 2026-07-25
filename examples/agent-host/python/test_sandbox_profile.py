import unittest

from sandbox_profile import SandboxProfile


class SandboxProfileTest(unittest.TestCase):
    def test_valid_profile_is_explicit_and_fail_closed(self):
        profile = SandboxProfile(("/workspace",), ("python",), ("pypi.org",), ("API_TOKEN",), 10)
        profile.validate()
        self.assertTrue(profile.allows_process("/usr/bin/python"))
        self.assertFalse(profile.allows_process("bash"))
        self.assertTrue(profile.allows_network("pypi.org"))
        self.assertFalse(profile.allows_network("example.com"))
        self.assertFalse(profile.may_log_secret("API_TOKEN"))

    def test_dangerous_wildcards_and_relative_paths_are_rejected(self):
        with self.assertRaises(ValueError): SandboxProfile(("workspace",)).validate()
        with self.assertRaises(ValueError): SandboxProfile(("/workspace",), ("/bin/sh",)).validate()
        with self.assertRaises(ValueError): SandboxProfile(("/workspace",), network_allowlist=("*",)).validate()
