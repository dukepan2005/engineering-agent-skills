"""Regression tests for HTML-entity handling in description/comment read-back.

Azure DevOps HTML-escapes ``&``, ``<``, ``>`` in work-item Description (and
comment text) on API output. The read-back comparison must ``html.unescape()``
the stored value before comparing it to the input, or any description that
contains these characters (``a && b``, ``n < m``, shell ``>`` redirects) is
falsely rejected as "Description ... did not persist" before the write ever
lands.
"""
import html
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from azure_devops_boards import assert_description  # noqa: E402


def _item(description, fmt="markdown"):
    return {
        "fields": {"System.Description": description},
        "multilineFieldsFormat": {"System.Description": fmt},
    }


class AssertDescriptionTests(unittest.TestCase):
    def test_html_entities_round_trip(self):
        # Azure escapes &, <, > on output; the read-back must recover the input.
        # This mirrors the exact failing case: `run \`a && b < c > d\` & repeat.`
        text = "run `a && b < c > d` & repeat."
        assert_description(_item(html.escape(text, quote=False)), text)  # must not raise

    def test_plain_text_matches(self):
        assert_description(_item("plain description"), "plain description")

    def test_non_markdown_format_raises(self):
        with self.assertRaises(RuntimeError):
            assert_description(_item("x", fmt=None), "x")

    def test_mismatched_text_raises(self):
        with self.assertRaises(RuntimeError):
            assert_description(_item("stored"), "expected")


if __name__ == "__main__":
    unittest.main()
