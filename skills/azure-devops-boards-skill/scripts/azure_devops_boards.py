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
SEARCH_TYPES = ("Epic", "Feature", "User Story", "Task", "Bug")
SEARCH_FIELDS = ("System.Title", "System.WorkItemType", "System.State", "System.Tags")
SEARCH_LIMIT_MAX = 100
ACCEPTANCE_CRITERIA_FIELD = "Microsoft.VSTS.Common.AcceptanceCriteria"
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
    multiline_formats: dict = field(default_factory=dict)
    description: str = None
    relation: tuple = None
    removed_relation: tuple = None


def sdk():
    root = Path(os.environ.get("AZURE_CONFIG_DIR", Path.home() / ".azure")) / "cliextensions" / "azure-devops"
    if not root.is_dir(): raise RuntimeError("Install the azure-devops CLI extension first.")
    sys.path.insert(0, str(root))
    from azext_devops.dev.common.services import get_work_item_tracking_client
    from azext_devops.devops_sdk.v5_0.work_item_tracking.models import JsonPatchOperation
    return get_work_item_tracking_client, JsonPatchOperation


def op(cls, verb, path, value): return cls(op=verb, path=path, value=value)
def emit(value): print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def _read_markdown_field(value_file, field_name):
    markdown = value_file.read_text()
    if not markdown.strip():
        raise RuntimeError(f"{field_name} must not be empty.")
    return markdown


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

    def search_item_ids_by_title(self, title_contains, item_types, top):
        title_contains, item_types = _validate_search_filters(title_contains, item_types)
        if not isinstance(top, int) or not 2 <= top <= SEARCH_LIMIT_MAX + 1:
            raise RuntimeError(f"Search result cap must be between 2 and {SEARCH_LIMIT_MAX + 1}.")
        type_literals = ", ".join(f"'{item_type}'" for item_type in item_types)
        query = f"""SELECT [System.Id]
FROM WorkItems
WHERE [System.TeamProject] = @project
  AND [System.Title] CONTAINS '{title_contains}'
  AND [System.WorkItemType] IN ({type_literals})
ORDER BY [System.Id]"""
        result = self._api._send(http_method="POST", location_id=self.WIQL_ID, version="5.0",
                                 route_values={"project": self._project}, query_parameters={"$top": top},
                                 content={"query": query}, media_type="application/json").json()
        ids, seen = [], set()
        for item in result.get("workItems", []):
            item_id = item.get("id")
            if item_id is not None and int(item_id) not in seen:
                seen.add(int(item_id))
                ids.append(int(item_id))
        return ids

    def read_work_item_summaries(self, item_ids):
        if not item_ids:
            return []
        items = self._api.get_work_items(ids=item_ids, project=self._project, fields=list(SEARCH_FIELDS))
        by_id = {}
        for item in items:
            fields = item.fields or {}
            by_id[item.id] = {
                "id": item.id,
                "title": fields.get("System.Title"),
                "type": fields.get("System.WorkItemType"),
                "state": fields.get("System.State"),
                "tags": fields.get("System.Tags"),
            }
        missing = [item_id for item_id in item_ids if item_id not in by_id]
        if missing:
            raise RuntimeError(f"Work-item search read-back missed requested IDs: {missing}.")
        return [by_id[item_id] for item_id in item_ids]

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
    """Keep native acceptance criteria separate from Description authority."""
    text = html.unescape(fields.get("System.Description", "") or "")
    acceptance_criteria = html.unescape(fields.get(ACCEPTANCE_CRITERIA_FIELD, "") or "")
    if acceptance_criteria.strip():
        result = {"source": "acceptance-criteria-field", "acceptanceCriteria": acceptance_criteria}
        if text.strip():
            result["description"] = text
        return result
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


def _validate_search_filters(title_contains, item_types):
    if not isinstance(title_contains, str):
        raise RuntimeError("Title search text must be a string.")
    title_contains = title_contains.strip()
    if (not title_contains or len(title_contains) > 128
            or any(ord(char) < 32 or ord(char) == 127 for char in title_contains)):
        raise RuntimeError("Title search text must contain 1 to 128 printable characters.")
    if "'" in title_contains or '"' in title_contains:
        raise RuntimeError("Title search text must not contain single or double quotes.")
    item_types = tuple(dict.fromkeys(item_types or []))
    if not item_types or any(item_type not in SEARCH_TYPES for item_type in item_types):
        raise RuntimeError("Choose one or more supported work-item types.")
    return title_contains, item_types


def search_items(args):
    title_contains, item_types = _validate_search_filters(args.title_contains, args.types)
    if not 1 <= args.limit <= SEARCH_LIMIT_MAX:
        raise RuntimeError(f"Search limit must be between 1 and {SEARCH_LIMIT_MAX}.")
    client = connect(args)[0]
    matched_ids = client.search_item_ids_by_title(title_contains, item_types, args.limit + 1)
    truncated = len(matched_ids) > args.limit
    items = client.read_work_item_summaries(matched_ids[:args.limit])
    emit({"mode": "read", "project": args.project, "titleContains": title_contains,
          "types": list(item_types), "limit": args.limit, "returned": len(items),
          "possiblyTruncated": truncated, "items": items})


def show_item(args):
    """Emit a work item. Default is compact (id/rev/type/state/title/relations);
    pass ``--full`` for the raw Azure JSON."""
    item = connect(args)[0].read(args.id)
    if args.full: return emit(item)
    fields = item.get("fields", {})
    emit({"id": item.get("id", args.id), "rev": item.get("rev"),
          "type": fields.get("System.WorkItemType"), "state": fields.get("System.State"),
          "title": fields.get("System.Title"), "relations": _relation_summary(item)})


def _evaluate(item, expectation, phase, *, check_relation=True, check_description=True):
    if check_description and expectation.description is not None:
        try:
            assert_description(item, expectation.description)
        except RuntimeError:
            if phase == "Validation":
                raise RuntimeError("Validation failed for Description or Markdown metadata.") from None
            raise
    fields = item.get("fields", {})
    for field, value in expectation.fields.items():
        actual = fields.get(field)
        matches = actual == value
        if field == "System.AssignedTo" and isinstance(value, str):
            identity_name = actual.get("uniqueName") if isinstance(actual, dict) else actual
            matches = isinstance(identity_name, str) and identity_name.casefold() == value.casefold()
        if not matches:
            requested = json.dumps(value, ensure_ascii=False)
            returned = json.dumps(actual, ensure_ascii=False)
            raise RuntimeError(
                f"{phase} failed for {field}: requested {requested}, "
                f"but Azure returned {returned}."
            )
    formats = item.get("multilineFieldsFormat", {})
    for field, value in expectation.multiline_formats.items():
        if formats.get(field) != value:
            raise RuntimeError(
                f"{phase} failed for {field} format: requested {value!r}, "
                f"but Azure returned {formats.get(field)!r}."
            )
    if check_relation and expectation.relation is not None:
        rel, url = expectation.relation
        if not _has_relation(item, rel, url): raise RuntimeError(f"{phase} failed for relation {rel}.")
    if check_relation and expectation.removed_relation is not None:
        rel, url = expectation.removed_relation
        if _has_relation(item, rel, url): raise RuntimeError(f"{phase} failed for removed relation {rel}.")


def safe_mutate(*, client, target, document, expectation, apply):
    """The safe-mutation lifecycle: validate → check → apply → read-back → check.

    Returns ``{mode, id?, rev?}``; never prints. Fields are checked against the
    validated item. Existing-item descriptions and relations are checked only
    against persisted read-back because Azure update validation can omit their
    projections; new-item validation still checks every expectation. A stale
    ``/rev`` test (the item changed since it was read) surfaces immediately — the
    caller must re-read and reconcile before retrying.
    """
    checked = client.validate(document, target)
    _evaluate(checked, expectation, "Validation",
              check_relation=not isinstance(target, ExistingItem),
              check_description=not isinstance(target, ExistingItem))
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
    expected_fields = {"System.IterationPath": iteration}; expected_formats = {}
    repro_steps_file = getattr(args, "repro_steps_file", None)
    system_info_file = getattr(args, "system_info_file", None)
    acceptance_criteria_file = getattr(args, "acceptance_criteria_file", None)
    comment_file = getattr(args, "comment_file", None)
    initial_comment = comment_file.read_text() if comment_file is not None else None
    if initial_comment is not None and not initial_comment.strip():
        raise RuntimeError("Comment must not be empty.")
    if args.type != "Bug" and any(value is not None for value in (repro_steps_file, system_info_file)):
        raise RuntimeError("Bug-specific fields require --type Bug.")
    if acceptance_criteria_file is not None:
        if args.type not in PLANNING_TYPES:
            raise RuntimeError("Acceptance Criteria requires --type Task or Bug.")
        value = _read_markdown_field(acceptance_criteria_file, ACCEPTANCE_CRITERIA_FIELD)
        document.append(op(cls, "add", f"/fields/{ACCEPTANCE_CRITERIA_FIELD}", value))
        document.append(op(cls, "add", f"/multilineFieldsFormat/{ACCEPTANCE_CRITERIA_FIELD}", "markdown"))
        expected_fields[ACCEPTANCE_CRITERIA_FIELD] = value
        expected_formats[ACCEPTANCE_CRITERIA_FIELD] = "markdown"
    for option, field_name in (
        ("repro_steps_file", "Microsoft.VSTS.TCM.ReproSteps"),
        ("system_info_file", "Microsoft.VSTS.TCM.SystemInfo"),
    ):
        value_file = locals()[option]
        if value_file is not None:
            value = _read_markdown_field(value_file, field_name)
            document.append(op(cls, "add", f"/fields/{field_name}", value))
            document.append(op(cls, "add", f"/multilineFieldsFormat/{field_name}", "markdown"))
            expected_fields[field_name] = value
            expected_formats[field_name] = "markdown"
    if args.type == "Bug" and initial_comment is not None and repro_steps_file is None:
        repro_steps = initial_comment
        document.append(op(cls, "add", "/fields/Microsoft.VSTS.TCM.ReproSteps", repro_steps))
        document.append(op(cls, "add", "/multilineFieldsFormat/Microsoft.VSTS.TCM.ReproSteps", "markdown"))
        expected_fields["Microsoft.VSTS.TCM.ReproSteps"] = repro_steps
        expected_formats["Microsoft.VSTS.TCM.ReproSteps"] = "markdown"
        initial_comment = None
    if args.tags: document.append(op(cls, "add", "/fields/System.Tags", "; ".join(args.tags)))
    for kind in RELATIONS:
        for target in getattr(args, kind): document.append(op(cls, "add", "/relations/-", relation(args, kind, target)))
    expectation = Expectation(fields=expected_fields, multiline_formats=expected_formats, description=text)
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
    expected_rev = getattr(args, "expected_rev", None)
    if expected_rev is not None and expected_rev < 1:
        raise RuntimeError("Expected revision must be a positive integer.")
    assigned_to = getattr(args, "assigned_to", None)
    if assigned_to is not None:
        assigned_to = assigned_to.strip()
        if not assigned_to:
            raise RuntimeError("AssignedTo must not be empty; use an Azure identity uniqueName.")
    client, cls = connect(args); before = client.read(args.id)
    if expected_rev is not None and before["rev"] != expected_rev:
        raise RuntimeError(
            f"Revision mismatch for work item {args.id}: expected {expected_rev}, "
            f"current {before['rev']}; re-read and reconcile before retrying."
        )
    document = [op(cls, "test", "/rev", expected_rev if expected_rev is not None else before["rev"])]; expected = {}; expected_formats = {}; text = None
    if args.description_file:
        text = args.description_file.read_text(); document += [op(cls, "add", "/fields/System.Description", text), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
    for field, value in (("System.State", args.state), ("System.IterationPath", args.iteration),
                         ("System.AssignedTo", assigned_to)):
        if value is not None: document.append(op(cls, "add", f"/fields/{field}", value)); expected[field] = value
    bug_files = ((getattr(args, "repro_steps_file", None), "Microsoft.VSTS.TCM.ReproSteps"),
                 (getattr(args, "system_info_file", None), "Microsoft.VSTS.TCM.SystemInfo"))
    if any(value_file is not None for value_file, _ in bug_files):
        if before.get("fields", {}).get("System.WorkItemType") != "Bug":
            raise RuntimeError("Bug-specific fields require a Bug work item.")
        for value_file, field_name in bug_files:
            if value_file is not None:
                value = _read_markdown_field(value_file, field_name)
                document.append(op(cls, "add", f"/fields/{field_name}", value))
                document.append(op(cls, "add", f"/multilineFieldsFormat/{field_name}", "markdown"))
                expected[field_name] = value
                expected_formats[field_name] = "markdown"
    acceptance_criteria_file = getattr(args, "acceptance_criteria_file", None)
    if acceptance_criteria_file is not None:
        item_type = before.get("fields", {}).get("System.WorkItemType")
        if item_type not in PLANNING_TYPES:
            raise RuntimeError("Acceptance Criteria requires a Task or Bug work item.")
        value = _read_markdown_field(acceptance_criteria_file, ACCEPTANCE_CRITERIA_FIELD)
        document.append(op(cls, "add", f"/fields/{ACCEPTANCE_CRITERIA_FIELD}", value))
        document.append(op(cls, "add", f"/multilineFieldsFormat/{ACCEPTANCE_CRITERIA_FIELD}", "markdown"))
        expected[ACCEPTANCE_CRITERIA_FIELD] = value
        expected_formats[ACCEPTANCE_CRITERIA_FIELD] = "markdown"
    if getattr(args, "tags", None):
        existing = before.get("fields", {}).get("System.Tags", "") or ""
        merged = [t.strip() for t in existing.split(";") if t.strip()]
        for tag in args.tags:
            if tag not in merged:
                merged.append(tag)
        tag_value = "; ".join(merged)
        document.append(op(cls, "add", "/fields/System.Tags", tag_value))
        expected["System.Tags"] = tag_value
    if len(document) == 1: raise RuntimeError("Specify a field to update.")
    expectation = Expectation(fields=expected, multiline_formats=expected_formats, description=text)
    result = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=expectation, apply=args.apply)
    emit({**result, "id": args.id, "fields": expected})


def add_link(args):
    client, cls = connect(args); before = client.read(args.id); value = relation(args, args.kind, args.target_id)
    if _has_relation(before, value["rel"], value["url"]): return emit({"mode": "unchanged", "id": args.id})
    document = [op(cls, "test", "/rev", before["rev"]), op(cls, "add", "/relations/-", value)]
    result = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(relation=(value["rel"], value["url"])), apply=args.apply)
    emit({"mode": result["mode"], "id": args.id, "kind": args.kind, "targetId": args.target_id})


def remove_link(args):
    for option in ("id", "target_id", "expected_rev"):
        value = getattr(args, option, None)
        if type(value) is not int or value < 1:
            raise RuntimeError(f"--{option.replace('_', '-')} must be a positive integer.")
    client, cls = connect(args)
    before = client.read(args.id)
    if before["rev"] != args.expected_rev:
        raise RuntimeError(
            f"Revision mismatch for work item {args.id}: expected {args.expected_rev}, "
            f"found {before['rev']}. Re-read and reconcile before retrying."
        )
    value = relation(args, args.kind, args.target_id)
    matches = [index for index, stored in enumerate(before.get("relations", []))
               if stored.get("rel") == value["rel"]
               and _relation_identity(stored.get("url", "")) == _relation_identity(value["url"])]
    if not matches:
        raise RuntimeError(f"No {args.kind} relation from work item {args.id} to {args.target_id}.")
    if len(matches) != 1:
        raise RuntimeError(f"Ambiguous {args.kind} relation from work item {args.id} to {args.target_id}: {len(matches)} matches.")
    document = [op(cls, "test", "/rev", args.expected_rev),
                op(cls, "remove", f"/relations/{matches[0]}", None)]
    result = safe_mutate(client=client, target=ExistingItem(args.id), document=document,
                         expectation=Expectation(removed_relation=(value["rel"], value["url"])), apply=args.apply)
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


def _check_checkboxes(criteria, selector):
    """Return acceptance criteria with matching checklist lines checked.

    ``selector.casefold() == "all"`` matches every checklist line; otherwise
    exactly one line whose item text (case-insensitive) contains ``selector``
    must match — ambiguous or missing matches raise rather than guess. Already
    checked lines are left unchanged, so re-running the same selector is a no-op.
    """
    is_all = selector.casefold() == "all"
    matches, rendered = [], []
    for line in criteria.splitlines(keepends=True):
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

    ``--check-ac`` checks the native Acceptance Criteria field; it never edits
    Description. The preflight revision avoids a redundant pre-write read.
    """
    acceptance_criteria_file = getattr(args, "acceptance_criteria_file", None)
    if args.expected_rev is None and (args.description_file is not None or acceptance_criteria_file is not None):
        raise RuntimeError("File-based closeout requires --expected-rev from the source work item.")
    client, cls = connect(args)
    comment = args.comment_file.read_text()
    if not comment.strip(): raise RuntimeError("Comment must not be empty.")
    fields, multiline_formats, description, read_rev = {}, {}, None, None
    if args.check_ac is not None or acceptance_criteria_file is not None:
        item = client.read(args.id)
        read_rev = item["rev"]
        item_type = item.get("fields", {}).get("System.WorkItemType")
        if item_type not in PLANNING_TYPES:
            raise RuntimeError("Acceptance Criteria requires a Task or Bug work item.")
    if args.check_ac is not None:
        stored = item.get("fields", {}).get(ACCEPTANCE_CRITERIA_FIELD, "")
        fields[ACCEPTANCE_CRITERIA_FIELD] = _check_checkboxes(html.unescape(stored or ""), args.check_ac)
        multiline_formats[ACCEPTANCE_CRITERIA_FIELD] = "markdown"
    elif acceptance_criteria_file is not None:
        fields[ACCEPTANCE_CRITERIA_FIELD] = _read_markdown_field(
            acceptance_criteria_file, ACCEPTANCE_CRITERIA_FIELD,
        )
        multiline_formats[ACCEPTANCE_CRITERIA_FIELD] = "markdown"
    if args.description_file is not None:
        description = args.description_file.read_text()
    if args.state is not None: fields["System.State"] = args.state
    has_patch = description is not None or bool(fields)
    expected = args.expected_rev
    if expected is None and has_patch:
        expected = read_rev if read_rev is not None else client.read(args.id)["rev"]
    if not args.apply:
        if has_patch:
            document = [op(cls, "test", "/rev", expected)]
            if description is not None: document += [op(cls, "add", "/fields/System.Description", description), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
            for field, value in fields.items(): document.append(op(cls, "add", f"/fields/{field}", value))
            for field, value in multiline_formats.items(): document.append(op(cls, "add", f"/multilineFieldsFormat/{field}", value))
            safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(fields=fields, multiline_formats=multiline_formats, description=description), apply=False)
        emit({"mode": "validated", "id": args.id, "fields": fields, "comment": {"format": "markdown", "length": len(comment)}})
        return
    mutation = None
    if has_patch:
        document = [op(cls, "test", "/rev", expected)]
        if description is not None: document += [op(cls, "add", "/fields/System.Description", description), op(cls, "add", "/multilineFieldsFormat/System.Description", "markdown")]
        for field, value in fields.items(): document.append(op(cls, "add", f"/fields/{field}", value))
        for field, value in multiline_formats.items(): document.append(op(cls, "add", f"/multilineFieldsFormat/{field}", value))
        mutation = safe_mutate(client=client, target=ExistingItem(args.id), document=document, expectation=Expectation(fields=fields, multiline_formats=multiline_formats, description=description), apply=True)
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
    search = commands.add_parser("search", help="read-only project-scoped search by title")
    search.add_argument("--organization", required=True); search.add_argument("--project", required=True)
    search.add_argument("--title-contains", required=True); search.add_argument("--type", dest="types", choices=SEARCH_TYPES, action="append", required=True)
    search.add_argument("--limit", type=int, default=50); search.set_defaults(run=search_items)
    snapshot = commands.add_parser("planning-snapshot"); connection(snapshot); snapshot_ids = snapshot.add_mutually_exclusive_group(required=True); snapshot_ids.add_argument("--story", type=int); snapshot_ids.add_argument("--id", dest="item_ids", action="append", type=int, metavar="ID"); snapshot.set_defaults(run=planning_snapshot)
    preflight_p = commands.add_parser("implement-preflight"); connection(preflight_p); preflight_p.add_argument("--id", type=int, required=True); preflight_p.set_defaults(run=preflight)
    create_p = commands.add_parser("create"); connection(create_p, True); create_p.add_argument("--apply", action="store_true"); create_p.add_argument("--type", choices=("Epic", "Feature", "User Story", "Task", "Bug"), required=True); create_p.add_argument("--title", required=True); create_p.add_argument("--description-file", type=Path, required=True); create_p.add_argument("--acceptance-criteria-file", type=Path, help="Task- or Bug-only Markdown for Microsoft.VSTS.Common.AcceptanceCriteria"); create_p.add_argument("--repro-steps-file", type=Path, help="Bug-only Markdown rendered as HTML for Microsoft.VSTS.TCM.ReproSteps"); create_p.add_argument("--system-info-file", type=Path, help="Bug-only Markdown rendered as HTML for Microsoft.VSTS.TCM.SystemInfo"); create_p.add_argument("--comment-file", type=Path, help="Optional initial Markdown comment; for a Bug without --repro-steps-file it becomes HTML Repro Steps"); create_p.add_argument("--iteration"); create_p.add_argument("--tags", action="append", default=[])
    for kind in RELATIONS: create_p.add_argument(f"--{kind}", action="append", type=int, default=[])
    create_p.set_defaults(run=create)
    update_p = commands.add_parser("update"); connection(update_p); update_p.add_argument("--apply", action="store_true"); update_p.add_argument("--id", type=int, required=True); update_p.add_argument("--description-file", type=Path); update_p.add_argument("--acceptance-criteria-file", type=Path, help="Task- or Bug-only Markdown for Microsoft.VSTS.Common.AcceptanceCriteria"); update_p.add_argument("--repro-steps-file", type=Path, help="Bug-only Markdown rendered as HTML Repro Steps"); update_p.add_argument("--system-info-file", type=Path, help="Bug-only Markdown rendered as HTML System Info"); update_p.add_argument("--state"); update_p.add_argument("--iteration"); update_p.add_argument("--tags", action="append", default=[]); update_p.set_defaults(run=update)
    update_p.add_argument("--assigned-to", metavar="UNIQUE_NAME", help="Assign by Azure identity uniqueName (usually email); blank values are rejected")
    update_p.add_argument("--expected-rev", type=int, help="Revision used to prepare the update; stale revisions are rejected without retry")
    comment = commands.add_parser("add-comment"); connection(comment); comment.add_argument("--apply", action="store_true"); comment.add_argument("--id", type=int, required=True); comment.add_argument("--comment-file", type=Path, required=True); comment.set_defaults(run=add_comment)
    close = commands.add_parser("close-task"); connection(close); close.add_argument("--apply", action="store_true"); close.add_argument("--id", type=int, required=True); close.add_argument("--expected-rev", type=int); close.add_argument("--state"); close.add_argument("--comment-file", type=Path, required=True); close.add_argument("--description-file", type=Path); close_ac = close.add_mutually_exclusive_group(); close_ac.add_argument("--acceptance-criteria-file", type=Path, help="Task- or Bug-only Markdown for Microsoft.VSTS.Common.AcceptanceCriteria"); close_ac.add_argument("--check-ac", metavar="all|FRAGMENT", help="Check matching Markdown boxes in the native Acceptance Criteria field"); close.set_defaults(run=close_task)
    link = commands.add_parser("add-link"); connection(link); link.add_argument("--apply", action="store_true"); link.add_argument("--id", type=int, required=True); link.add_argument("--kind", choices=tuple(RELATIONS), required=True); link.add_argument("--target-id", type=int, required=True); link.set_defaults(run=add_link)
    remove = commands.add_parser("remove-link"); connection(remove); remove.add_argument("--apply", action="store_true"); remove.add_argument("--id", type=int, required=True); remove.add_argument("--kind", choices=tuple(RELATIONS), required=True); remove.add_argument("--target-id", type=int, required=True); remove.add_argument("--expected-rev", type=int, required=True); remove.set_defaults(run=remove_link)
    return root


if __name__ == "__main__":
    args = parser().parse_args(); args.run(args)
