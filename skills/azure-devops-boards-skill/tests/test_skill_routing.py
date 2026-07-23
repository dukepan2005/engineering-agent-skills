"""Regression tests for the semantic task-boards-ops routing contract."""
import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"


class TaskBoardsOpsRoutingTests(unittest.TestCase):
    def test_semantic_role_uses_the_local_helper_not_mcp_discovery(self):
        text = SKILL.read_text()

        self.assertIn("When the current prompt already assigns the semantic `task-boards-ops` role", text)
        self.assertRegex(text, r"first operational\s+action is to read")
        self.assertIn("Before resolving, inspecting, selecting, or testing anything", text)
        self.assertRegex(text, r"[Rr]ead \[references/commands\.md\]\(references/commands\.md\)")
        self.assertRegex(text, r"Do not use\s+`ALL_TOOLS` or the absence of an Azure MCP tool")
        self.assertIn("`sh \"$HELPER\"`", text)


if __name__ == "__main__":
    unittest.main()
