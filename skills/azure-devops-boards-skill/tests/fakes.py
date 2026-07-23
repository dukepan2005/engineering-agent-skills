"""Shared test doubles for the safe-mutation runner.

``FakeClient`` is an in-memory adapter implementing the runner's validate/apply/read
port. It models the Azure behaviours the safety checks depend on:

- ``validateOnly=true`` projects the would-be item. Tests can model Azure update
  responses that omit relation projections;
- ``System.Description`` is HTML-escaped (``&``, ``<``, ``>``) on output — the
  regression in commit b9232a0;
- ``/rev`` is honoured for optimistic concurrency.
"""
import copy
import html


class PatchOp:
    """Stand-in for the SDK's JsonPatchOperation (same op/path/value shape)."""

    def __init__(self, op, path, value):
        self.op, self.path, self.value = op, path, value


class FakeClient:
    """In-memory adapter implementing the runner's validate/apply/read port."""

    def __init__(self, items=None, echo_relations_on_validate=True):
        self.items = {k: copy.deepcopy(v) for k, v in (items or {}).items()}
        self.comments = {}
        self._next, self._next_comment = 1000, 1
        self.applies = 0
        self.echo_relations_on_validate = echo_relations_on_validate

    @staticmethod
    def blank(item_type):
        return {"id": None, "rev": 1, "fields": {"System.WorkItemType": item_type},
                "relations": [], "multilineFieldsFormat": {}}

    @classmethod
    def with_item(cls, item_id, rev=1, item_type="Task", **kwargs):
        item = cls.blank(item_type); item["id"], item["rev"] = item_id, rev
        return cls(items={item_id: item}, **kwargs)

    def _is_new(self, target):
        return hasattr(target, "item_type")

    def _apply(self, item, document):
        item = copy.deepcopy(item)
        for o in document:
            if o.op == "test" and o.path == "/rev":
                if item.get("rev") != o.value:
                    raise RuntimeError("rev mismatch (optimistic concurrency)")
                continue
            if o.op != "add":
                continue
            if o.path.startswith("/fields/"):
                key = o.path[len("/fields/"):]
                item["fields"][key] = html.escape(o.value, quote=False) if key == "System.Description" else o.value
            elif o.path.startswith("/multilineFieldsFormat/"):
                item["multilineFieldsFormat"][o.path[len("/multilineFieldsFormat/"):]] = o.value
            elif o.path == "/relations/-":
                item["relations"].append(copy.deepcopy(o.value))
        return item

    def validate(self, document, target):
        base = self.blank(target.item_type) if self._is_new(target) else self.items[target.item_id]
        projected = self._apply(base, document)
        if not self.echo_relations_on_validate:
            projected["relations"] = []
        return projected

    def apply(self, document, target):
        self.applies += 1
        if self._is_new(target):
            new_id = self._next; self._next += 1
            item = self._apply(self.blank(target.item_type), document)
            item["id"], item["rev"] = new_id, 2
            self.items[new_id] = item
            return new_id
        item = self._apply(self.items[target.item_id], document)
        item["rev"] = item.get("rev", 1) + 1
        self.items[target.item_id] = item
        return target.item_id

    def read(self, item_id):
        return copy.deepcopy(self.items[item_id])

    def read_comments(self, work_item_id):
        return copy.deepcopy(self.comments.get(work_item_id, []))

    def new_direct_implementation_children(self, story_id):
        children = []
        seen = set()
        for relation in self.items[story_id].get("relations", []):
            if relation.get("rel") != "System.LinkTypes.Hierarchy-Forward":
                continue
            target = relation.get("url", "").rsplit("/", 1)[-1]
            if not target.isdigit():
                continue
            item = self.items[int(target)]
            fields = item.get("fields", {})
            target_id = int(target)
            if (fields.get("System.State") == "New"
                    and fields.get("System.WorkItemType") in ("Task", "Bug")
                    and target_id not in seen):
                seen.add(target_id)
                children.append(target_id)
        return children

    def add_comment(self, work_item_id, text):
        comment_id = self._next_comment; self._next_comment += 1
        saved = {"id": comment_id, "format": "markdown", "text": html.escape(text, quote=False)}
        self.comments.setdefault(work_item_id, []).append(saved)
        return copy.deepcopy(saved)
