"""Assignment follows the existing safe-mutation lifecycle."""
import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "scripts"))

from fakes import FakeClient, PatchOp
from azure_devops_boards import parser, update


class IdentityClient(FakeClient):
    def _apply(self, item, document):
        result = super()._apply(item, document)
        if "System.AssignedTo" in result["fields"]:
            result["fields"]["System.AssignedTo"] = {
                "displayName": "Example User", "uniqueName": "user@example.com",
            }
        return result


class AssigneeCommandTests(unittest.TestCase):
    def args(self, apply=False, identity="user@example.com"):
        command = ["update", "--organization", "https://dev.azure.com/o",
                   "--project", "P", "--id", "42", "--assigned-to", identity]
        if apply:
            command.append("--apply")
        return parser().parse_args(command)

    def run_update(self, client, args):
        with redirect_stdout(io.StringIO()) as output, mock.patch(
                "azure_devops_boards.connect", return_value=(client, PatchOp)):
            update(args)
        return json.loads(output.getvalue())

    def seeded(self, client_type=IdentityClient):
        client = client_type.with_item(42, rev=3, item_type="User Story")
        client.items[42]["fields"].update({"System.State": "New", "System.Description": "Keep scope"})
        client.items[42]["relations"] = [{"rel": "parent", "url": "keep-parent"}]
        return client

    def test_validate_resolves_identity_without_persisting(self):
        client = self.seeded()
        result = self.run_update(client, self.args())
        self.assertEqual(result["mode"], "validated")
        self.assertEqual(client.applies, 0)
        self.assertNotIn("System.AssignedTo", client.read(42)["fields"])

    def test_apply_preserves_scope_state_and_relations(self):
        client = self.seeded()
        result = self.run_update(client, self.args(True, " User@Example.com "))
        saved = client.read(42)
        self.assertEqual(result["rev"], 4)
        self.assertEqual(client.applies, 1)
        self.assertEqual(saved["fields"]["System.AssignedTo"]["uniqueName"], "user@example.com")
        self.assertEqual(saved["fields"]["System.State"], "New")
        self.assertEqual(saved["fields"]["System.Description"], "Keep scope")
        self.assertEqual(saved["relations"], [{"rel": "parent", "url": "keep-parent"}])

    def test_wrong_identity_fails_before_apply(self):
        client = self.seeded()
        with self.assertRaisesRegex(RuntimeError, "Validation failed for System.AssignedTo"):
            self.run_update(client, self.args(True, "other@example.com"))
        self.assertEqual(client.applies, 0)

    def test_wrong_identity_in_readback_fails(self):
        class WrongReadback(IdentityClient):
            def read(self, item_id):
                item = super().read(item_id)
                if self.applies:
                    item["fields"]["System.AssignedTo"]["uniqueName"] = "other@example.com"
                return item

        client = self.seeded(WrongReadback)
        with self.assertRaisesRegex(RuntimeError, "Read-back failed for System.AssignedTo"):
            self.run_update(client, self.args(True))

    def test_blank_identity_rejected_before_connect(self):
        with mock.patch("azure_devops_boards.connect") as connect:
            with self.assertRaisesRegex(RuntimeError, "AssignedTo must not be empty"):
                update(self.args(True, "   "))
        connect.assert_not_called()
