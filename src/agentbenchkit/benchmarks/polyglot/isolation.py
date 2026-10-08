"""Pinned visibility policy and narrow, syntax-checked embedded-test protection.

Only inventory-reviewed regions are masked. Rust parsing is never a classifier
for arbitrary files: task, path and pristine hash must all match the catalog.
"""

import hashlib
import json
from pathlib import Path
from typing import Any

import tree_sitter_rust
from tree_sitter import Language, Node, Parser

POLICY = Path(__file__).with_name("visibility.json")
VISIBILITY: dict[str, dict[str, list[str]]] = json.loads(POLICY.read_text(encoding="utf-8"))
POLICY_HASH = hashlib.sha256(
    json.dumps(VISIBILITY, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
# One-based inclusive lines, reviewed against the pinned catalog hashes.
REGIONS = {
    ("rust--react", "src/lib.rs"): ((6, 17),),
    ("rust--doubly-linked-list", "src/pre_implemented.rs"): ((63, 67), (72, 76)),
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def visible_files(task_id: str, row: dict[str, Any]) -> set[str]:
    names = set(row["solution_files"]) | set(VISIBILITY[task_id]["support_files"])
    if not names <= row["files_sha256"].keys():
        raise ValueError("visibility policy does not match pinned catalog")
    return names


def rust_tree(data: bytes) -> Node:
    root = Parser(Language(tree_sitter_rust.language())).parse(data).root_node
    if root.has_error:
        pending = [root]
        while pending:
            node = pending.pop()
            # tree-sitter-rust 0.24 cannot parse the valid lifetime-first
            # `dyn 'a + Fn(...)` spelling used by the pinned official reference.
            # Only this apostrophe error is tolerated; rustc remains the syntax
            # and correctness authority. No source bytes are rewritten here.
            lifetime_first = (
                node.type == "ERROR"
                and node.text == b"'"
                and node.parent is not None
                and node.parent.type == "dynamic_type"
                and (node.parent.text or b"").startswith(b"dyn '")
            )
            if node.is_missing or (node.type == "ERROR" and not lifetime_first):
                raise ValueError("protected Rust solution has invalid syntax")
            pending.extend(node.children)
    return root


def anchor(data: bytes) -> tuple[Node, list[Node]]:
    root = rust_tree(data)
    nodes = root.named_children
    matches = [
        n
        for n in nodes
        if n.type == "struct_item"
        and (name := n.child_by_field_name("name")) is not None
        and name.text == b"ComputeCellId"
    ]
    if len(matches) != 1:
        raise ValueError("protected ComputeCellId must be one top-level struct")
    item = matches[0]
    if not any(n.type == "visibility_modifier" and n.text == b"pub" for n in item.named_children):
        raise ValueError("protected ComputeCellId must remain public")
    if any(n.type == "inner_attribute_item" for n in nodes):
        raise ValueError("crate attributes cannot control protected doctests")
    preceding: list[Node] = []
    for node in reversed(nodes[: nodes.index(item)]):
        if node.type not in {"attribute_item", "line_comment", "block_comment"}:
            break
        preceding.insert(0, node)
    for node in preceding:
        if node.type == "attribute_item":
            # No cfg/doc/procedural attributes can hide or transform the anchor.
            attribute = node.named_children[0]
            identifiers = [n.text for n in attribute.named_children]
            if not identifiers or identifiers[0] != b"derive":
                raise ValueError("protected anchor accepts only built-in derives")
            args = attribute.child_by_field_name("arguments")
            allowed = {
                b"Clone",
                b"Copy",
                b"Debug",
                b"PartialEq",
                b"Eq",
                b"Hash",
                b"Default",
                b"PartialOrd",
                b"Ord",
            }
            if args is None or any(
                n.type != "identifier" or n.text not in allowed for n in args.named_children
            ):
                raise ValueError("protected anchor accepts only built-in derives")
    return item, preceding


def is_doc(node: Node) -> bool:
    return any(n.type == "outer_doc_comment_marker" for n in node.named_children)


def documentation(data: bytes) -> bytes:
    _, nodes = anchor(data)
    return b"".join(data[n.start_byte : n.end_byte] for n in nodes if is_doc(n))


def mask(task_id: str, name: str, data: bytes, expected_hash: str) -> bytes:
    regions = REGIONS.get((task_id, name))
    if not regions:
        return data
    if sha(data) != expected_hash:
        raise ValueError("protected source hash differs from pinned catalog")
    root = rust_tree(data)
    if task_id == "rust--react":
        anchor(data)
    lines = data.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    spans = [(offsets[start - 1], offsets[end]) for start, end in regions]
    for start, end in spans:
        nodes = [n for n in root.named_children if start <= n.start_byte < end]
        if not nodes or any(not is_doc(n) or n.end_byte > end for n in nodes):
            raise ValueError("mask must cover only reviewed Rust doc comments")
    for start, end in reversed(spans):
        data = data[:start] + data[end:]
    rust_tree(data)
    return data


def restore_react(pristine: bytes, candidate: bytes) -> bytes:
    """Replace only the anchor's documentation; preserve all implementation bytes.

    The canonical doc block is always sourced from pristine input, never from
    candidate comments. All candidate doc comments attached to the anchor are
    discarded, preventing Markdown fences from swallowing official doctests.
    Ambiguous/non-public/conditional anchors and crate attributes fail closed.
    """
    canonical = documentation(pristine)
    if canonical.count(b"```compile_fail") != 2:
        raise ValueError("unexpected canonical doctest structure")
    item, nodes = anchor(candidate)
    edits = [(n.start_byte, n.end_byte, b"") for n in nodes if is_doc(n)]
    position = nodes[0].start_byte if nodes else item.start_byte
    # Apply removals before inserting at the original earliest prefix offset.
    for start, end, replacement in reversed(edits):
        candidate = candidate[:start] + replacement + candidate[end:]
    candidate = candidate[:position] + canonical + candidate[position:]
    if documentation(candidate) != canonical:
        raise ValueError("canonical embedded doctest restoration failed")
    return candidate
