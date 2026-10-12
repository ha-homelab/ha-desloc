"""Regression cases for the split CodeQL updates that broke CI."""
import unittest
from check_ci_actions import validate


class CodeQLUpdateTests(unittest.TestCase):
    def line(self, action, pin="a", version="v4.38.3", quote=""):
        return f"  - uses: {quote}github/codeql-action/{action}@{pin * 40}{quote} # {version}"

    def test_all_components_and_quoted_references(self):
        for quote in ("", "'", chr(34)):
            validate({a: self.line(a, quote=quote) for a in ("init", "autobuild", "analyze", "upload-sarif")})

    def test_partial_update_across_workflows_fails(self):
        with self.assertRaises(ValueError):
            validate({"codeql.yml": self.line("init"), "scorecards.yml": self.line("upload-sarif", "b", "v4.38.2")})

    def test_missing_or_partial_release_comment_fails(self):
        for version in ("", "v4", "main"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate({"ci.yml": self.line("init", version=version)})

    def test_mutable_revision_and_empty_configuration_fail(self):
        with self.assertRaises(ValueError):
            validate({"ci.yml": "- uses: github/codeql-action/init@v4 # v4.38.3"})
        with self.assertRaises(ValueError):
            validate({})


if __name__ == "__main__":
    unittest.main()
