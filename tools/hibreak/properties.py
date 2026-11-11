"""Shared property-context parsing and effective permission inspection."""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class PropertyContext:
    name: str
    label: str
    match: str
    value_type: Tuple[str, ...]
    source: str


def parse_contexts(source, text):
    entries = []
    for number, line in enumerate(text.splitlines(), 1):
        fields = line.split("#", 1)[0].split()
        if not fields:
            continue
        if len(fields) < 2:
            raise ValueError(f"Invalid property context in {source}:{number}")
        match = fields[2] if len(fields) >= 3 else "prefix"
        if match not in ("exact", "prefix"):
            raise ValueError(f"Invalid property match mode in {source}:{number}: {match}")
        entries.append(PropertyContext(
            fields[0], fields[1], match, tuple(fields[3:]) or ("string",), source,
        ))
    return entries


def resolve_context(name, entries):
    matches = [
        entry for entry in entries
        if (entry.match == "exact" and name == entry.name)
        or (entry.match == "prefix" and name.startswith(entry.name))
    ]
    if not matches:
        raise ValueError(f"No property context matches {name}")
    best_rank = max((len(entry.name), entry.match == "exact") for entry in matches)
    best = [entry for entry in matches if (len(entry.name), entry.match == "exact") == best_rank]
    if len(best) != 1:
        raise ValueError(f"Ambiguous property contexts for {name}: {[entry.source for entry in best]}")
    return best[0]


def effective_permissions(policy, target, query, not_conditional):
    permissions = set()
    for rule in query(
        policy, ruletype=["allow"], target=target,
    ).results():
        try:
            rule.conditional
        except not_conditional:
            pass
        else:
            raise ValueError(f"Conditional property permission cannot be safely preserved: {rule}")
        for source in rule.source.expand():
            permissions.update((str(source), str(rule.tclass), str(permission))
                               for permission in rule.perms)
    return permissions
