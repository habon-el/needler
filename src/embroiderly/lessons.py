"""Lessons from earlier digitizing runs on this computer, handed to Claude on the next run.

After each Claude run Needler keeps one short record: what the file check found, grouped
by cause (export_findings.explain), and, when a later attempt passed after a failed one,
which settings changed between them. Claude reads the most recent records with the
picture, so a mistake one design taught is not repeated on the next.

Kept with the person's other decisions (work/decisions/lessons.json), never in the
repository. Records hold settings, counts and thread colours, not pictures.
"""
import json
import time
from pathlib import Path
from uuid import uuid4

KEEP = 40      # records kept on disk
HANDED = 8     # records handed to Claude with each picture
SKIP = {'edits', 'cleanup_decisions', 'rect', 'erase'}   # per-picture data, not lessons


def path_for(decisions):
    return Path(decisions) / 'lessons.json'


def load(decisions):
    try:
        rows = json.loads(path_for(decisions).read_text(encoding='utf-8'))
        return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except (OSError, ValueError):
        return []


def changed(before, after):
    """Settings that differ between two attempts, as {name: [before, after]}."""
    keys = sorted((set(before) | set(after)) - SKIP)
    return {k: [before.get(k), after.get(k)] for k in keys if before.get(k) != after.get(k)}


def lesson(kind, request, attempts):
    """One record for a finished run, or None when there is nothing to learn from it."""
    failed = [a for a in attempts if a.get('gate') or a.get('error')]
    if not failed:
        return None
    first = failed[0]
    detail = first.get('gate_detail') or {}
    row = dict(at=time.strftime('%Y-%m-%d'), kind=kind, request=(request or '')[:200],
               problem=detail.get('text') or (first.get('gate') or first.get('error') or '')[:400],
               cause=detail.get('cause'), attempts=len(attempts),
               settings_that_failed={k: v for k, v in (first.get('options') or {}).items() if k not in SKIP})
    # The first attempt that passed after a failure: what changed is what fixed it.
    for before, after in zip(attempts, attempts[1:]):
        if (before.get('gate') or before.get('error')) and not (after.get('gate') or after.get('error')):
            row['fixed_by'] = changed(before.get('options') or {}, after.get('options') or {})
            break
    else:
        row['fixed_by'] = None
        row['unchanged'] = sum(1 for a in failed if (a.get('gate_detail') or {}).get('signature') ==
                               detail.get('signature') and detail.get('signature'))
    return row


def record(decisions, kind, request, attempts):
    row = lesson(kind, request, attempts)
    if row is None:
        return None
    rows = (load(decisions) + [row])[-KEEP:]
    target = path_for(decisions)
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f'lessons.{uuid4().hex}.tmp')
    temp.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    temp.replace(target)
    return row


def for_claude(decisions):
    """The most recent lessons, in the brief Claude gets with the picture."""
    return [{k: v for k, v in r.items() if k != 'settings_that_failed' or not r.get('fixed_by')}
            for r in load(decisions)[-HANDED:]]
