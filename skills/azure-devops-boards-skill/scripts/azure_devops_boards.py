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
PLANNING_TYPES = ("Task", "Bug")
PLANNING_PARENT_TYPES = ("Story", "User Story")
PLANNING_STATE = "New"
_BUG_SCOPE_FIELDS = frozenset({
    "Microsoft.VSTS.TCM.ReproSteps",
    "Microsoft.VSTS.TCM.SystemInfo",
    "Microsoft.VSTS.TCM.FoundInBuild",
    "Microsoft.VSTS.Common.AcceptanceCriteria",
    "Microsoft.VSTS.Common.Priority",
    "Microsoft.VSTS.Common.Severity",
})
_GENERIC_SCOPE_FIELDS = frozenset({
    "System.AreaPath", "System.ChangedDate", "System.CreatedDate", "System.Id",
    "System.IterationPath", "System.Rev", "System.State", "System.TeamProject",
    "System.Title", "System.WorkItemType",
})


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


def _comment_id(comment):
    """Return a comment identifier across Azure's ``id``/``commentId`` shapes."""
    for key in ("id", "commentId"):
        value = comment.get(key)
        if value is not None:
            return value
    return None


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
    WIQL_ID = "1a9c53f7-f243-4447-b110-35ef023636e4"

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
        created_id = _comment_id(created)
        if created_id is None:
            raise RuntimeError("Comments API did not return a comment id.")
        comments = self.read_comments(work_item_id)
        return next(
            (item for item in comments if str(_comment_id(item)) == str(created_id)),
            None,
        )

    def read_comments(self, work_item_id):
        comments, seen_tokens, token = [], set(), None
        while True:
            parameters = {"$expand": "all", "order": "asc"}
            if token is not None:
                if token in seen_tokens:
                    raise RuntimeError("Comments API repeated its continuation token.")
                seen_tokens.add(token)
                parameters["continuationToken"] = token
            page = self._api._send(http_method="GET", location_id=self.COMMENT_ID, version="7.1-preview.4", route_values={"project": self._project, "workItemId": work_item_id}, query_parameters=parameters).json()
            comments.extend(page.get("comments", []))
            token = page.get("continuationToken")
            if token is None:
                return comments

    def new_direct_implementation_children(self, story_id):
        query = f"""SELECT [System.Id]
FROM WorkItemLinks
WHERE ([Source].[System.Id] = {story_id})
  AND ([System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward')
  AND ([Target].[System.State] = '{PLANNING_STATE}')
  AND ([Target].[System.WorkItemType] IN ('Task', 'Bug'))
MODE (MustContain)"""
        result = self._api._send(http_method="POST", location_id=self.WIQL_ID, version="5.0",
                                 route_values={"project": self._project}, content={"query": query},
                                 media_type="application/json").json()
        relations = result.get("workItemRelations", [])
        target_ids, seen_ids = [], set()
        for relation in relations:
            target = relation.get("target")
            target_id = target.get("id") if target else None
            if target_id is not None and int(target_id) != story_id and int(target_id) not in seen_ids:
                target_id = int(target_id)
                seen_ids.add(target_id)
                target_ids.append(target_id)
        return target_ids

    def _route(self, target):
        if isinstance(target, NewItem): return {"project": self._project, "type": target.item_type}, "POST", self.CREATE_ID
        return {"project": self._project, "id": target.item_id}, "PATCH", self.ITEM_ID


def connect(args):
    get_client, cls = sdk()
    return AzureClient(get_client(args.organization), args.project), cls


def assert_description(item, text):
    stored = item["fields"].get("System.Description", "")
    if html.unescape(stored) != text or item.get("multilineFieldsFormat", {}).get("System.Description") != "markdown": raise RuntimeError("Description or Markdown metadata did not persist.")


def _relation_identity(url):
    """Return ``(org_prefix, work_item_id)`` for an Azure work-item relation URL,
    ignoring only the project segment (name vs GUID varies) — organization/host
    and the API shape must still match. ``None`` if the URL isn't shaped like a
    work-item API URL."""
    base, sep, rest = url.partition("/_apis/wit/workItems/")
    if not sep:
        return None
    target = rest.split("?", 1)[0].rstrip("/")
    if not target.isdigit():
        return None
    return base.rsplit("/", 1)[0], int(target)


def _has_relation(item, rel, url):
    expected_identity = _relation_identity(url)
    return any(
        stored.get("rel") == rel and (
            stored.get("url") == url if expected_identity is None
            else _relation_identity(stored.get("url", "")) == expected_identity
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


def _scope_summary(fields):
    """Keep structured acceptance criteria; otherwise retain authority text."""
    text = html.unescape(fields.get("System.Description", "") or "")
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
    if text.strip():
        return {"source": "description-fallback", "description": text}
    retained = {
        key: value for key, value in fields.items()
        if key not in _GENERIC_SCOPE_FIELDS and value not in (None, "")
    }
    known = {
        key: retained[key] for key in _BUG_SCOPE_FIELDS if key in retained
    }
    result = {
        "source": "type-specific-fields",
        "fields": retained,
    }
    if fields.get("System.WorkItemType") == "Bug":
        result["knownBugFields"] = known
    return result


def _attachments(item):
    return [relation for relation in item.get("relations", [])
            if relation.get("rel") == "AttachedFile"]


def _linked_references(item):
    """Return raw candidate references without claiming they are specification bodies."""
    return [relation for relation in item.get("relations", [])
            if relation.get("rel") in {"AttachedFile", "Hyperlink"}]


def _planning_item_snapshot(client, item):
    fields = item.get("fields", {})
    item_id = item.get("id")
    comments = client.read_comments(item_id)
    return {
        "id": item_id,
        "rev": item.get("rev"),
        "type": fields.get("System.WorkItemType"),
        "state": fields.get("System.State"),
        "title": fields.get("System.Title"),
        "fields": fields,
        "multilineFieldsFormat": item.get("multilineFieldsFormat", {}),
        "relations": item.get("relations", []),
        "relationSummary": _relation_summary(item),
        "attachments": _attachments(item),
        "linkedReferences": _linked_references(item),
        "comments": comments,
        "discussion": {"comments": comments},
        "scope": _scope_summary(fields),
    }


def planning_snapshot(args):
    """Emit one complete planning authority snapshot for a Story or explicit item set."""
    client = connect(args)[0]
    story_id = getattr(args, "story", None)
    item_ids = getattr(args, "item_ids", None)
    if story_id is not None:
        parent = client.read(story_id)
        parent_type = parent.get("fields", {}).get("System.WorkItemType")
        if parent_type not in PLANNING_PARENT_TYPES:
            raise RuntimeError(
                f"Planning snapshot requires a Story parent, but item {story_id} is {parent_type!r}."
            )
        target_ids = client.new_direct_implementation_children(story_id)
        source = {"kind": "story", "id": story_id}
        parent_snapshot = _planning_item_snapshot(client, parent)
    elif item_ids:
        if len(set(item_ids)) != len(item_ids):
            raise RuntimeError("Explicit planning item IDs must be unique.")
        target_ids = item_ids
        source = {"kind": "explicit", "ids": item_ids}
        parent_snapshot = None
    else:
        raise RuntimeError("Specify either --story or one or more --id values.")

    targets = []
    for item_id in target_ids:
        # Azure WIQL link results can echo the source item as a target row.
        # The Story is context and its state does not gate this read; only its
        # children are subject to the New Task/Bug planning gate.
        if story_id is not None and item_id == story_id:
            continue
        item = client.read(item_id)
        item_type = item.get("fields", {}).get("System.WorkItemType")
        item_state = item.get("fields", {}).get("System.State")
        if story_id is not None and item_state != PLANNING_STATE:
            raise RuntimeError(
                f"Planning snapshot target {item_id} changed from New to {item_state!r}."
            )
        if item_type not in PLANNING_TYPES:
            raise RuntimeError(
                f"Explicit planning item {item_id} must be Task or Bug, but is {item_type!r}."
            )
        targets.append(_planning_item_snapshot(client, item))
    emit({"source": source, "parent": parent_snapshot, "targets": targets})


def preflight(args):
    """Emit the smallest source-of-truth snapshot needed to begin one work item."""
    client = connect(args)[0]
    item = client.read(args.id)
    fields = item.get("fields", {})
    comments = client.read_comments(args.id)
    emit({"id": item.get("id", args.id), "rev": item.get("rev"),
          "type": fields.get("System.WorkItemType"), "state": fields.get("System.State"),
          "title": fields.get("System.Title"),
          "fields": fields, "multilineFieldsFormat": item.get("multilineFieldsFormat", {}),
          "scope": _scope_summary(fields), "relations": _relation_summary(item),
          "attachments": _attachments(item), "linkedReferences": _linked_references(item),
          "comments": comments,
          "discussion": {"comments": comments}})


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


def safe_mutate(*, client, target, document, expectation, apply):
    """The safe-mutation lifecycle: validate → check → apply → read-back → check.

    Returns ``{mode, id?, rev?}``; never prints. Fields and descriptions are checked
    against the validated item. Existing-item relations are checked against
    persisted read-back because Azure update validation can omit them. A stale
    ``/rev`` test (the item changed since it was read) surfaces immediately —
    the caller must re-read and reconcile before retrying.
    """
    checked = client.validate(document, target)
    _evaluate(checked, expectation, "Validation",
              check_relation=not isinstance(target, ExistingItem))
    if not apply: return {"mode": "validated"}
    new_id = client.apply(document, target)
    saved = client.read(new_id)
    _evaluate(saved, expectation, "Read-back")
    return {"mode": "applied", "id": new_id, "rev": saved["rev"]}


def relation(args, kind, target):
    return {"rel": RELATIONS[kind], "url": f"{args.organization.rstrip('/')}/{args.project}/_apis/wit/workItems/{target}", "attributes": {"comment": "Added by azure-devops-boards skill"}}


def create(args):
    client, cls = connect(args); text = args.description_file.read_text(); iteration = args.iteration or sprint(args)
    document = [op(cls, "add", "/fields/System.Title", args.title), op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown"), op(cls, "add", "/fields/System.IterationPath", iteration)]
    expected_fields = {"System.IterationPath": iteration}
    repro_steps_file = getattr(args, "repro_steps_file", None)
    system_info_file = getattr(args, "system_info_file", None)
    comment_file = getattr(args, "comment_file", None)
    initial_comment = comment_file.read_text() if comment_file is not None else None
    if initial_comment is not None and not initial_comment.strip():
        raise RuntimeError("Comment must not be empty.")
    if args.type != "Bug" and any(value is not None for value in (repro_steps_file, system_info_file)):
        raise RuntimeError("Bug-specific fields require --type Bug.")
    for option, field_name in (
        ("repro_steps_file", "Microsoft.VSTS.TCM.ReproSteps"),
        ("system_info_file", "Microsoft.VSTS.TCM.SystemInfo"),
    ):
        value_file = locals()[option]
        if value_file is not None:
            value = value_file.read_text()
            if not value.strip():
                raise RuntimeError(f"{field_name} must not be empty.")
            document.append(op(cls, "add", f"/fields/{field_name}", value))
            expected_fields[field_name] = value
    if args.type == "Bug" and initial_comment is not None and repro_steps_file is None:
        document.append(op(cls, "add", "/fields/Microsoft.VSTS.TCM.ReproSteps", initial_comment))
        expected_fields["Microsoft.VSTS.TCM.ReproSteps"] = initial_comment
        initial_comment = None
    if args.tags: document.append(op(cls, "add", "/fields/System.Tags", "; ".join(args.tags)))
    for kind in RELATIONS:
        for target in getattr(args, kind): document.append(op(cls, "add", "/relations/-", relation(args, kind, target)))
    expectation = Expectation(fields=expected_fields, description=text)
    result = safe_mutate(client=client, target=NewItem(args.type), document=document, expectation=expectation, apply=args.apply)
    if result["mode"] == "validated":
        output = {"mode": "validated", "type": args.type, "title": args.title, "iteration": iteration}
        if initial_comment is not None:
            output["comment"] = {"format": "markdown", "length": len(initial_comment)}
        return emit(output)
    if initial_comment is not None:
        saved = client.add_comment(result["id"], initial_comment)
        if saved is None or saved.get("format", "").lower() != "markdown" or html.unescape(saved.get("text", "")) != initial_comment:
            raise RuntimeError("Markdown comment did not persist after work-item creation.")
        result["commentId"] = _comment_id(saved)
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
    emit({"mode": "applied", "id": args.id, "commentId": _comment_id(saved)})


def _checklist_marker(body):
    """Return ``(marker, checked)`` for a markdown checklist line, else ``(None, False)``."""
    for marker in ("- [x]", "- [X]"):
        if body.startswith(marker): return marker, True
    if body.startswith("- [ ]"): return "- [ ]", False
    return None, False


def _check_checkboxes(description, selector):
    """Return ``description`` with matching markdown checklist lines marked checked.

    ``selector.casefold() == "all"`` matches every checklist line; otherwise
    exactly one line whose item text (case-insensitive) contains ``selector``
    must match — ambiguous or missing matches raise rather than guess. Already
    checked lines are left unchanged, so re-running the same selector is a no-op.
    """
    is_all = selector.casefold() == "all"
    matches, rendered = [], []
    for line in description.splitlines(keepends=True):
        body, indent = line.lstrip(), line[:len(line) - len(line.lstrip())]
        marker, checked = _checklist_marker(body)
        if marker is None:
            rendered.append(line); continue
        rest = body[len(marker):]
        if rest.startswith(" "): rest = rest[1:]
        if not (is_all or selector.lower() in rest.lower()):
            rendered.append(line); continue
        matches.append(rest.strip())
        rendered.append(line if checked else f"{indent}- [x] {rest}")
    if not matches:
        raise RuntimeError(f"No acceptance criteria matched {selector!r}; nothing checked.")
    if not is_all and len(matches) > 1:
        raise RuntimeError(f"Fragment {selector!r} matched {len(matches)} acceptance criteria ({'; '.join(matches)}); use a more specific fragment or --check-ac all.")
    return "".join(rendered)


def close_task(args):
    """Persist one final work-item patch and one Markdown completion comment.

    ``--check-ac`` checks acceptance-criteria checkboxes server-side (the current
    Description is read, matching unchecked lines are checked, and the full
    Description is patched back), so marking an item done no longer requires a
    separate fetch, local edit, and whole-Description rewrite. The preflight
    revision avoids a redundant pre-write read.
    """
    client, cls = connect(args)
    comment = args.comment_file.read_text()
    if not comment.strip(): raise RuntimeError("Comment must not be empty.")
    fields, text, read_rev = {}, None, None
    if args.check_ac is not None:
        item = client.read(args.id)
        read_rev = item["rev"]
        stored = item.get("fields", {}).get("System.Description", "")
        text = _check_checkboxes(html.unescape(stored), args.check_ac)
    elif args.description_file is not None:
        text = args.description_file.read_text()
    if args.state is not None: fields["System.State"] = args.state
    has_patch = text is not None or bool(fields)
    expected = args.expected_rev
    if expected is None and has_patch:
        expected = read_rev if read_rev is not None else client.read(args.id)["rev"]
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
          "fields": fields, "commentId": _comment_id(saved)})


def connection(parser, team=False):
    parser.add_argument("--organization", default=os.environ.get("AZURE_DEVOPS_ORG"), required=not os.environ.get("AZURE_DEVOPS_ORG")); parser.add_argument("--project", default=os.environ.get("AZURE_DEVOPS_PROJECT"), required=not os.environ.get("AZURE_DEVOPS_PROJECT"))
    if team: parser.add_argument("--team", default=os.environ.get("AZURE_DEVOPS_TEAM"), required=not os.environ.get("AZURE_DEVOPS_TEAM"))


def parser():
    root = argparse.ArgumentParser(description=__doc__); commands = root.add_subparsers(required=True)
    current = commands.add_parser("current-sprint"); connection(current, True); current.set_defaults(run=lambda a: print(sprint(a)))
    show = commands.add_parser("show"); connection(show); show.add_argument("--id", type=int, required=True); show.add_argument("--full", action="store_true", help="emit the full Azure JSON"); show.set_defaults(run=show_item)
    snapshot = commands.add_parser("planning-snapshot"); connection(snapshot); snapshot_ids = snapshot.add_mutually_exclusive_group(required=True); snapshot_ids.add_argument("--story", type=int); snapshot_ids.add_argument("--id", dest="item_ids", action="append", type=int, metavar="ID"); snapshot.set_defaults(run=planning_snapshot)
    preflight_p = commands.add_parser("implement-preflight"); connection(preflight_p); preflight_p.add_argument("--id", type=int, required=True); preflight_p.set_defaults(run=preflight)
    create_p = commands.add_parser("create"); connection(create_p, True); create_p.add_argument("--apply", action="store_true"); create_p.add_argument("--type", choices=("Epic", "Feature", "User Story", "Task", "Bug"), required=True); create_p.add_argument("--title", required=True); create_p.add_argument("--description-file", type=Path, required=True); create_p.add_argument("--repro-steps-file", type=Path, help="Bug-only Markdown content for Microsoft.VSTS.TCM.ReproSteps"); create_p.add_argument("--system-info-file", type=Path, help="Bug-only Markdown content for Microsoft.VSTS.TCM.SystemInfo"); create_p.add_argument("--comment-file", type=Path, help="Optional initial Markdown comment; for a Bug without --repro-steps-file it becomes Markdown Repro Steps"); create_p.add_argument("--iteration"); create_p.add_argument("--tags", action="append", default=[])
    for kind in RELATIONS: create_p.add_argument(f"--{kind}", action="append", type=int, default=[])
    create_p.set_defaults(run=create)
    update_p = commands.add_parser("update"); connection(update_p); update_p.add_argument("--apply", action="store_true"); update_p.add_argument("--id", type=int, required=True); update_p.add_argument("--description-file", type=Path); update_p.add_argument("--state"); update_p.add_argument("--iteration"); update_p.set_defaults(run=update)
    comment = commands.add_parser("add-comment"); connection(comment); comment.add_argument("--apply", action="store_true"); comment.add_argument("--id", type=int, required=True); comment.add_argument("--comment-file", type=Path, required=True); comment.set_defaults(run=add_comment)
    close = commands.add_parser("close-task"); connection(close); close.add_argument("--apply", action="store_true"); close.add_argument("--id", type=int, required=True); close.add_argument("--expected-rev", type=int); close.add_argument("--state"); close.add_argument("--comment-file", type=Path, required=True); close_body = close.add_mutually_exclusive_group(); close_body.add_argument("--description-file", type=Path); close_body.add_argument("--check-ac", metavar="all|FRAGMENT"); close.set_defaults(run=close_task)
    link = commands.add_parser("add-link"); connection(link); link.add_argument("--apply", action="store_true"); link.add_argument("--id", type=int, required=True); link.add_argument("--kind", choices=tuple(RELATIONS), required=True); link.add_argument("--target-id", type=int, required=True); link.set_defaults(run=add_link)
    return root


if __name__ == "__main__":
    args = parser().parse_args(); args.run(args)
