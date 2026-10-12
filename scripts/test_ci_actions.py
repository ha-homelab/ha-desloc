"""Regression cases for the split CodeQL updates that broke CI."""
import textwrap
import unittest

from check_ci_actions import validate


class CodeQLUpdateTests(unittest.TestCase):
    def line(self, action, pin="a", version="v4.38.3", quote=""):
        """Build one block-form CodeQL step for a workflow fixture."""
        return f"- uses: {quote}github/codeql-action/{action}@{pin * 40}{quote} # {version}"

    def workflow(self, steps):
        """Wrap steps in the executable part of a workflow."""
        return "jobs:\n  scan:\n    steps:\n" + textwrap.indent(steps, "      ") + "\n"

    def test_all_components_and_quoted_references(self):
        """All CodeQL components may share a quoted or unquoted pin."""
        for quote in ("", "'", chr(34)):
            validate({a: self.workflow(self.line(a, quote=quote)) for a in ("init", "autobuild", "analyze", "upload-sarif")})

    def test_partial_update_across_workflows_fails(self):
        """A different SARIF upload release must fail the whole check."""
        with self.assertRaises(ValueError):
            validate({"codeql.yml": self.workflow(self.line("init")), "scorecards.yml": self.workflow(self.line("upload-sarif", "b", "v4.38.2"))})

    def test_missing_or_partial_release_comment_fails(self):
        """Renovate needs a full version token in the inline comment."""
        for version in ("", "v4", "main"):
            with self.subTest(version=version), self.assertRaises(ValueError):
                validate({"ci.yml": self.workflow(self.line("init", version=version))})

    def test_mutable_revision_and_empty_configuration_fail(self):
        """Mutable action refs and a missing CodeQL setup cannot pass."""
        with self.assertRaises(ValueError):
            validate({"ci.yml": self.workflow("- uses: github/codeql-action/init@v4 # v4.38.3")})
        with self.assertRaises(ValueError):
            validate({})

    def test_flow_mapping_cannot_hide_an_executable_reference(self):
        """Compact YAML must not bypass pin checks or Renovate extraction."""
        for pin in ("v4", "b" * 40, "a" * 40):
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, "block-form"):
                validate({"ci.yml": self.workflow(self.line("init") + f"\n- {{name: x, uses: github/codeql-action/analyze@{pin}}} # v4.38.3")})

    def test_comments_and_scalar_values_are_not_executable(self):
        """Example refs inside comments, env or shell text are ignored."""
        steps = self.line("init") + "\n" + textwrap.dedent("""\
            # - uses: github/codeql-action/analyze@v4
            - run: |
                uses: github/codeql-action/analyze@v4
                - {uses: github/codeql-action/analyze@v4}
              env:
                uses: github/codeql-action/analyze@v4
            - {run: 'echo github/codeql-action/analyze@v4'}
        """)
        validate({"ci.yml": self.workflow(steps)})

    def test_explanatory_comment_after_full_release_is_supported(self):
        """Like Renovate, read the full version token before explanation."""
        validate({"ci.yml": self.workflow(self.line("init", version="v4.38.3 security scanner"))})

    def test_repository_names_are_case_insensitive(self):
        """GitHub owner/repository casing must not bypass the pin check."""
        valid = self.line("init").replace("github/codeql-action", "GitHub/CodeQL-Action")
        validate({"ci.yml": self.workflow(valid)})
        for pin in ("v4", "b" * 40):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                extra = f"- uses: GitHub/CodeQL-Action/analyze@{pin} # v4.38.3"
                validate({"ci.yml": self.workflow(self.line("init") + "\n" + extra)})


if __name__ == "__main__":
    unittest.main()
