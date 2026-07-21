#!/usr/bin/env python3
"""Safe, project-neutral Azure Boards work-item operations."""

import argparse
import html
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import sys

RELATIONS = {"parent": "System.LinkTypes.Hierarchy-Reverse", "predecessor": "System.LinkTypes.Dependency-Reverse", "related": "System.LinkTypes.Related"}


@dataclass(frozen=True)
class NewItem:
    """Operation-kind: create (POST CREATE_ID, create_work_item)."""
    item_type: str


@dataclass(frozen=True)
class ExistingItem:
    """Operation-kind: update an existing item (PATCH ITEM_ID, update_work_item)."""
    item_id: int


@dataclass
class Expectation:
    """Declarative post-condition the runner checks against the validated item
    (always) and the read-back item (when applying)."""
    fields: dict = field(default_factory=dict)
    description: str = None
    relation: tuple = None


def sdk():
    root = Path(os.environ.get("AZURE_CONFIG_DIR", Path.home() / ".azure")) / "cliextensions" / "azure-devops"
    if not root.is_dir(): raise RuntimeError("Install the azure-devops CLI extension first.")
    sys.path.insert(0, str(root))
    from azext_devops.dev.common.services import get_work_item_tracking_client
    from azext_devops.devops_sdk.v5_0.work_item_tracking.models import JsonPatchOperation
    return get_work_item_tracking_client, JsonPatchOperation


def op(cls, verb, path, value): return cls(op=verb, path=path, value=value)
def emit(value): print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def sprint(args):
    command = ["az", "boards", "iteration", "team", "list", "--org", args.organization, "--project", args.project, "--team", args.team, "--timeframe", "current", "--query", "[0].path", "-o", "tsv"]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode: raise RuntimeError(result.stderr.strip() or "Current Sprint query failed.")
    value = result.stdout.strip()
    if not value or value == args.project: raise RuntimeError("No concrete current Sprint is configured.")
    return value


class AzureClient:
    """Adapter over the Azure SDK: the single home for Boards transport.

    validate / apply / read are the port the safe-mutation runner depends on;
    add_comment serves the comment endpoint (which has no validate-only, so it stays
    outside the runner). The location GUIDs, the private ``_send`` ceremony and the
    create-vs-update routing all live here, so callers stay Azure-agnostic (and
    testable with a fake).
    """

    CREATE_ID = "62d3d110-0047-428c-ad3c-4fe872c91c74"
    ITEM_ID = "72c7ddf8-2cdc-4f60-90cd-ab71c14a399b"
    COMMENT_ID = "608aac0a-32e1-4493-a863-b9cf4566d257"

    def __init__(self, api, project):
        self._api = api
        self._project = project

    def validate(self, document, target):
        route, method, location = self._route(target)
        return self._api._send(http_method=method, location_id=location, version="5.0", route_values=route, query_parameters={"validateOnly": "true"}, content=self._api._serialize.body(document, "[JsonPatchOperation]"), media_type="application/json-patch+json").json()

    def apply(self, document, target):
        if isinstance(target, NewItem):
            return self._api.create_work_item(document=document, project=self._project, type=target.item_type, validate_only=False).id
        self._api.update_work_item(document=document, id=target.item_id, project=self._project, validate_only=False)
        return target.item_id

    def read(self, item_id):
        return self._api._send(http_method="GET", location_id=self.ITEM_ID, version="5.0", route_values={"project": self._project, "id": item_id}, query_parameters={"$expand": "All"}).json()

    def add_comment(self, work_item_id, text):
        created = self._api._send(http_method="POST", location_id=self.COMMENT_ID, version="7.1-preview.4", route_values={"project": self._project, "workItemId": work_item_id}, query_parameters={"format": "markdown"}, content={"text": text}, media_type="application/json").json()
        comments = self._api._send(http_method="GET", location_id=self.COMMENT_ID, version="7.1-preview.4", route_values={"project": self._project, "workItemId": work_item_id}, query_parameters={"$expand": "all", "order": "asc"}).json().get("comments", [])
        return next((item for item in comments if item.get("id") == created.get("id")), None)

    def _route(self, target):
        if isinstance(target, NewItem): return {"project": self._project, "type": target.item_type}, "POST", self.CREATE_ID
        return {"project": self._project, "id": target.item_id}, "PATCH", self.ITEM_ID


def connect(args):
    get_client, cls = sdk()
    return AzureClient(get_client(args.organization), args.project), cls


def assert_description(item, text):
    stored = item["fields"].get("System.Description", "")
    if html.unescape(stored) != text or item.get("multilineFieldsFormat", {}).get("System.Description") != "markdown": raise RuntimeError("Description or Markdown metadata did not persist.")


def _relation_work_item_id(url):
    """Return the stable work-item ID from an Azure relation URL, if present."""
    target = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
    return int(target) if target.isdigit() else None


def _has_relation(item, rel, url):
    expected_id = _relation_work_item_id(url)
    return any(
        stored.get("rel") == rel and (
            stored.get("url") == url if expected_id is None
            else _relation_work_item_id(stored.get("url", "")) == expected_id
        )
        for stored in item.get("relations", [])
    )


def _relation_summary(item):
    """Return relation identities only; never expand linked work items."""
    result = []
    for relation in item.get("relations", []):
        target = relation.get("url", "").rsplit("/", 1)[-1]
        result.append({"rel": relation.get("rel"), "targetId": int(target) if target.isdigit() else target})
    return result


def _scope_summary(description):
    """Keep structured acceptance criteria; otherwise retain authority text."""
    text = html.unescape(description or "")
    lines = text.splitlines()
    checklist = [line.strip() for line in lines if line.lstrip().startswith(("- [ ]", "- [x]", "- [X]"))]
    if checklist:
        return {"source": "markdown-checklist", "acceptanceCriteria": checklist}
    heading = next((index for index, line in enumerate(lines)
                    if line.strip().lower().lstrip("#").strip() in {"acceptance criteria", "acceptance", "验收标准"}), None)
    if heading is not None:
        body = []
        for line in lines[heading + 1:]:
            if line.startswith("#"):
                break
            body.append(line)
        return {"source": "acceptance-heading", "acceptanceCriteria": "\n".join(body).strip()}
    return {"source": "description-fallback", "description": text}


def preflight(args):
    """Emit the smallest source-of-truth snapshot needed to begin one work item."""
    item = connect(args)[0].read(args.id)
    fields = item.get("fields", {})
    emit({"id": item.get("id", args.id), "rev": item.get("rev"),
          "type": fields.get("System.WorkItemType"), "state": fields.get("System.State"),
          "title": fields.get("System.Title"),
          "scope": _scope_summary(fields.get("System.Description", "")),
          "relations": _relation_summary(item)})


def show_item(args):
    """Emit a work item. Default is compact (id/rev/type/state/title/relations);
    pass ``--full`` for the raw Azure JSON."""
    item = connect(args)[0].read(args.id)
    if args.full: return emit(item)
    fields = item.get("fields", {})
    emit({"id": item.get("id", args.id), "rev": item.get("rev"),
          "type": fields.get("System.WorkItemType"), "state": fields.get("System.State"),
          "title": fields.get("System.Title"), "relations": _relation_summary(item)})


def _evaluate(item, expectation, phase, *, check_relation=True):
    if expectation.description is not None: assert_description(item, expectation.description)
    fields = item.get("fields", {})
    for field, value in expectation.fields.items():
        actual = fields.get(field)
        if actual != value:
            requested = json.dumps(value, ensure_ascii=False)
            returned = json.dumps(actual, ensure_ascii=False)
            raise RuntimeError(
                f"{phase} failed for {field}: requested {requested}, "
                f"but Azure returned {returned}."
            )
    if check_relation and expectation.relation is not None:
        rel, url = expectation.relation
        if not _has_relation(item, rel, url): raise RuntimeError(f"{phase} failed for relation {rel}.")


def _rev_test(document):
    """The ``/rev`` optimistic-concurrency test op, if the document carries one."""
    for operation in document:
        if getattr(operation, "op", None) == "test" and getattr(operation, "path", None) == "/rev":
            return operation
    return None


def _reconcile_rev(client, target, document, exc):
    """Return a refreshed document when ``exc`` is a stale-rev conflict the server
    can reconcile, else ``None`` so the caller surfaces the original error.

    Optimistic concurrency only: re-read the item and retry solely when its rev
    has moved strictly forward from the value the caller held (the real signal
    that the item changed, e.g. a commit auto-link bumping the rev). A rev that
    did not advance — a caller-supplied value that was never live, or a field or
    description expectation failure — is not a recoverable conflict.
    """
    if not isinstance(target, ExistingItem):
        return None
    held_op = _rev_test(document)
    if held_op is None:
        return None
    held, current = held_op.value, client.read(target.item_id).get("rev")
    if not (isinstance(held, int) and isinstance(current, int) and current > held):
        return None
    rebuilt = []
    for operation in document:
        if getattr(operation, "op", None) == "test" and getattr(operation, "path", None) == "/rev":
            rebuilt.append(type(held_op)(op=held_op.op, path=held_op.path, value=current))
        else:
            rebuilt.append(operation)
    return rebuilt


def safe_mutate(*, client, target, document, expectation, apply):
    """The safe-mutation lifecycle: validate → check → apply → read-back → check.

    Returns ``{mode, id?, rev?}``; never prints. Fields and descriptions are checked
    against the validated item. Existing-item relations are checked against
    persisted read-back because Azure update validation can omit them. A stale-rev
    conflict is retried once after re-reading the advanced revision; any other
    failure, or a second conflict, surfaces immediately.
    """
    for attempt in (0, 1):
        try:
            checked = client.validate(document, target)
            # Azure update validateOnly responses can omit relations even when the
            # JSON Patch is accepted. Relation presence is a persisted-state check.
            _evaluate(checked, expectation, "Validation",
                      check_relation=not isinstance(target, ExistingItem))
            if not apply: return {"mode": "validated"}
            new_id = client.apply(document, target)
            saved = client.read(new_id)
            _evaluate(saved, expectation, "Read-back")
            return {"mode": "applied", "id": new_id, "rev": saved["rev"]}
        except Exception as exc:
            refreshed = _reconcile_rev(client, target, document, exc)
            if refreshed is None or attempt:
                raise
            document = refreshed
    raise RuntimeError("safe_mutate exited without producing a result")


def relation(args, kind, target):
    return {"rel": RELATIONS[kind], "url": f"{args.organization.rstrip('/')}/{args.project}/_apis/wit/workItems/{target}", "attributes": {"comment": "Added by azure-devops-boards skill"}}


def create(args):
    client, cls = connect(args); text = args.description_file.read_text(); iteration = args.iteration or sprint(args)
    document = [op(cls, "add", "/fields/System.Title", args.title), op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown"), op(cls, "add", "/fields/System.IterationPath", iteration)]
    if args.tags: document.append(op(cls, "add", "/fields/System.Tags", "; ".join(args.tags)))
    for kind in RELATIONS:
        for target in getattr(args, kind): document.append(op(cls, "add", "/relations/-", relation(args, kind, target)))
    expectation = Expectation(fields={"System.IterationPath": iteration}, description=text)
    result = safe_mutate(client=client, target=NewItem(args.type), document=document, expectation=expectation, apply=args.apply)
    if result["mode"] == "validated": return emit({"mode": "validated", "type": args.type, "title": args.title, "iteration": iteration})
    emit(result)


def update(args):
    client, cls = connect(args); before = client.read(args.id); document = [op(cls, "test", "/rev", before["rev"])]; expected = {}; text = None
    if args.description_file:
        text = args.description_file.read_text(); document += [op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
    for field, value in (("System.State", args.state), ("System.IterationPath", args.iteration)):
        if value is not None: document.append(op(cls, "add", f"/fields/{field}", value)); expected[field] = value
    if len(document) == 1: raise RuntimeError("Specify a field to update.")
    expectation = Expectation(fields=expected, description=text)
    result = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=expectation, apply=args.apply)
    emit({**result, "id": args.id, "fields": expected})


def add_link(args):
    client, cls = connect(args); before = client.read(args.id); value = relation(args, args.kind, args.target_id)
    if _has_relation(before, value["rel"], value["url"]): return emit({"mode": "unchanged", "id": args.id})
    document = [op(cls, "test", "/rev", before["rev"]), op(cls, "add", "/relations/-", value)]
    result = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(relation=(value["rel"], value["url"])), apply=args.apply)
    emit({"mode": result["mode"], "id": args.id, "kind": args.kind, "targetId": args.target_id})


def add_comment(args):
    client, _ = connect(args); text = args.comment_file.read_text()
    if not text.strip(): raise RuntimeError("Comment must not be empty.")
    if not args.apply: return emit({"mode": "validated", "id": args.id, "format": "markdown", "length": len(text)})
    saved = client.add_comment(args.id, text)
    if saved is None or saved.get("format", "").lower() != "markdown" or html.unescape(saved.get("text", "")) != text: raise RuntimeError("Markdown comment did not persist.")
    emit({"mode": "applied", "id": args.id, "commentId": saved.get("id")})


def _checklist_marker(body):
    """Return ``(marker, checked)`` for a markdown checklist line, else ``(None, False)``."""
    for marker in ("- [x]", "- [X]"):
        if body.startswith(marker): return marker, True
    if body.startswith("- [ ]"): return "- [ ]", False
    return None, False


def _toggle_checkboxes(description, selector):
    """Return ``description`` with matching markdown checklist lines toggled.

    ``selector == "all"`` toggles every checklist line; otherwise lines whose
    item text (case-insensitive) contains ``selector`` are toggled. Raises when
    nothing matched, so a typo cannot silently close an item.
    """
    matched, rendered = 0, []
    for line in description.splitlines(keepends=True):
        body, indent = line.lstrip(), line[:len(line) - len(line.lstrip())]
        marker, checked = _checklist_marker(body)
        if marker is None:
            rendered.append(line); continue
        rest = body[len(marker):]
        if rest.startswith(" "): rest = rest[1:]
        if selector == "all" or selector.lower() in rest.lower():
            matched += 1
            rendered.append(f"{indent}{'- [ ]' if checked else '- [x]'} {rest}")
        else:
            rendered.append(line)
    if not matched:
        raise RuntimeError(f"No acceptance criteria matched {selector!r}; nothing toggled.")
    return "".join(rendered)


def close_task(args):
    """Persist one final work-item patch and one Markdown completion comment.

    ``--check-ac`` toggles acceptance-criteria checkboxes server-side (the current
    Description is read, matching lines are toggled, and the full Description is
    patched back), so flipping a checklist no longer requires a separate fetch,
    local edit, and whole-Description rewrite. The preflight revision avoids a
    redundant pre-write read; a stale-rev conflict auto-reconciles once.
    """
    client, cls = connect(args)
    comment = args.comment_file.read_text()
    if not comment.strip(): raise RuntimeError("Comment must not be empty.")
    fields, text = {}, None
    if args.check_ac is not None:
        stored = client.read(args.id).get("fields", {}).get("System.Description", "")
        text = _toggle_checkboxes(html.unescape(stored), args.check_ac)
    elif args.description_file is not None:
        text = args.description_file.read_text()
    if args.state is not None: fields["System.State"] = args.state
    has_patch = text is not None or bool(fields)
    expected = args.expected_rev
    if expected is None and has_patch:
        expected = client.read(args.id)["rev"]
    if not args.apply:
        if has_patch:
            document = [op(cls, "test", "/rev", expected)]
            if text is not None: document += [op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
            for field, value in fields.items(): document.append(op(cls, "add", f"/fields/{field}", value))
            safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(fields=fields, description=text), apply=False)
        emit({"mode": "validated", "id": args.id, "fields": fields, "comment": {"format": "markdown", "length": len(comment)}})
        return
    mutation = None
    if has_patch:
        document = [op(cls, "test", "/rev", expected)]
        if text is not None: document += [op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
        for field, value in fields.items(): document.append(op(cls, "add", f"/fields/{field}", value))
        mutation = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(fields=fields, description=text), apply=True)
    saved = client.add_comment(args.id, comment)
    if saved is None or saved.get("format", "").lower() != "markdown" or html.unescape(saved.get("text", "")) != comment:
        raise RuntimeError("Markdown comment did not persist.")
    emit({"mode": "applied", "id": args.id, "rev": mutation.get("rev") if mutation else None,
          "fields": fields, "commentId": saved.get("id")})


def connection(parser, team=False):
    parser.add_argument("--organization", default=os.environ.get("AZURE_DEVOPS_ORG"), required=not os.environ.get("AZURE_DEVOPS_ORG")); parser.add_argument("--project", default=os.environ.get("AZURE_DEVOPS_PROJECT"), required=not os.environ.get("AZURE_DEVOPS_PROJECT"))
    if team: parser.add_argument("--team", default=os.environ.get("AZURE_DEVOPS_TEAM"), required=not os.environ.get("AZURE_DEVOPS_TEAM"))


def parser():
    root = argparse.ArgumentParser(description=__doc__); commands = root.add_subparsers(required=True)
    current = commands.add_parser("current-sprint"); connection(current, True); current.set_defaults(run=lambda a: print(sprint(a)))
    show = commands.add_parser("show"); connection(show); show.add_argument("--id", type=int, required=True); show.add_argument("--full", action="store_true", help="emit the full Azure JSON"); show.set_defaults(run=show_item)
    preflight_p = commands.add_parser("implement-preflight"); connection(preflight_p); preflight_p.add_argument("--id", type=int, required=True); preflight_p.set_defaults(run=preflight)
    create_p = commands.add_parser("create"); connection(create_p, True); create_p.add_argument("--apply", action="store_true"); create_p.add_argument("--type", choices=("Epic", "Feature", "User Story", "Task", "Bug"), required=True); create_p.add_argument("--title", required=True); create_p.add_argument("--description-file", type=Path, required=True); create_p.add_argument("--iteration"); create_p.add_argument("--tags", action="append", default=[])
    for kind in RELATIONS: create_p.add_argument(f"--{kind}", action="append", type=int, default=[])
    create_p.set_defaults(run=create)
    update_p = commands.add_parser("update"); connection(update_p); update_p.add_argument("--apply", action="store_true"); update_p.add_argument("--id", type=int, required=True); update_p.add_argument("--description-file", type=Path); update_p.add_argument("--state"); update_p.add_argument("--iteration"); update_p.set_defaults(run=update)
    comment = commands.add_parser("add-comment"); connection(comment); comment.add_argument("--apply", action="store_true"); comment.add_argument("--id", type=int, required=True); comment.add_argument("--comment-file", type=Path, required=True); comment.set_defaults(run=add_comment)
    close = commands.add_parser("close-task"); connection(close); close.add_argument("--apply", action="store_true"); close.add_argument("--id", type=int, required=True); close.add_argument("--expected-rev", type=int); close.add_argument("--state"); close.add_argument("--comment-file", type=Path, required=True); close_body = close.add_mutually_exclusive_group(); close_body.add_argument("--description-file", type=Path); close_body.add_argument("--check-ac", metavar="all|FRAGMENT"); close.set_defaults(run=close_task)
    link = commands.add_parser("add-link"); connection(link); link.add_argument("--apply", action="store_true"); link.add_argument("--id", type=int, required=True); link.add_argument("--kind", choices=tuple(RELATIONS), required=True); link.add_argument("--target-id", type=int, required=True); link.set_defaults(run=add_link)
    return root


if __name__ == "__main__":
    args = parser().parse_args(); args.run(args)
