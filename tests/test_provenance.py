import os
import unittest
from unittest.mock import patch

from gbm_audit import __version__
from gbm_audit.provenance import runtime_provenance


class TestProvenance(unittest.TestCase):
    def test_package_version_matches_release(self):
        self.assertEqual(__version__, "0.2.0")

    def test_runtime_provenance_contains_environment_versions(self):
        provenance = runtime_provenance()
        self.assertEqual(provenance["package"], "gbm-tracking-uncertainty")
        self.assertEqual(provenance["package_version"], "0.2.0")
        self.assertTrue(provenance["python_version"])
        self.assertIn("numpy", provenance["dependencies"])
        self.assertIn("Pillow", provenance["dependencies"])
        self.assertIn("certifi", provenance["dependencies"])

    def test_explicit_git_sha_is_recorded(self):
        with patch.dict(os.environ, {"GBM_AUDIT_GIT_SHA": "abc123"}, clear=False):
            self.assertEqual(runtime_provenance()["git_sha"], "abc123")


if __name__ == "__main__":
    unittest.main()
