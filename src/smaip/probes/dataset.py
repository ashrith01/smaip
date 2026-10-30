"""Labeled tool outputs for the Week 7 probes.

The corpus is the Week 5 and Week 6 pages plus an original set of tool
results. A page is positive when its vendor is marked poisoned. A tool
result carries its own label. Nothing here is copied from AgentDojo,
InjecAgent, or BIPIA.

The split is deterministic and stratified by label. Within each label,
records are sorted by id and dealt round-robin in a 3/1/1 pattern, which
is a 60/20/20 train/val/test cut. The same id always lands in the same
split, and every split has both labels as long as each label has at least
five records.
"""

import json
from dataclasses import dataclass, replace
from pathlib import Path

from smaip.vendors import VendorLibrary


TOOL_OUTPUTS = (
    Path(__file__).resolve().parents[1] / "fixture_data" / "week7" / "tool_outputs.jsonl"
)
TINY_CAPS = {"tool": 6, "week5": 2, "week6": 2}


@dataclass(frozen=True)
class Record:
    id: str
    label: int
    origin: str
    tool: str
    text: str
    split: str = ""


def load_tool_outputs(path: Path | None = None) -> list[Record]:
    source = path or TOOL_OUTPUTS
    records: list[Record] = []
    seen: set[str] = set()
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        record_id = str(payload["id"])
        if record_id in seen:
            raise ValueError(f"duplicate tool-output id {record_id} on line {line_number}")
        seen.add(record_id)
        label = int(payload["label"])
        if label not in (0, 1):
            raise ValueError(f"label for {record_id} must be 0 or 1")
        text = str(payload["text"])
        tool = str(payload["tool"])
        if not text.strip() or not tool.strip():
            raise ValueError(f"empty tool output {record_id}")
        records.append(
            Record(id=record_id, label=label, origin="tool", tool=tool, text=text)
        )
    if not records:
        raise ValueError("tool output dataset is empty")
    return records


def load_page_records() -> list[Record]:
    """Week 5 and Week 6 pages. Poisoned vendors are the positive class."""

    from smaip.eval.week5 import week5_root
    from smaip.eval.week6 import week6_root

    records: list[Record] = []
    for origin, root in (("week5", week5_root()), ("week6", week6_root())):
        library = VendorLibrary(root)
        for vendor in library.ids():
            label = 1 if library.is_poisoned(vendor) else 0
            for page in library.list_pages(vendor):
                records.append(
                    Record(
                        id=f"{origin}:{vendor}/{page}",
                        label=label,
                        origin=origin,
                        tool="read_page",
                        text=library.read(vendor, page),
                    )
                )
    return records


def load_corpus() -> list[Record]:
    records = load_tool_outputs() + load_page_records()
    ids = [item.id for item in records]
    if len(ids) != len(set(ids)):
        raise ValueError("probe corpus has duplicate ids")
    labels = {item.label for item in records}
    if labels != {0, 1}:
        raise ValueError("probe corpus needs both labels")
    return records


def select_subset(records: list[Record], subset: str) -> list[Record]:
    """``full`` keeps every record. ``tiny`` keeps a fixed prefix per origin and label."""

    if subset == "full":
        return list(records)
    if subset != "tiny":
        raise ValueError(f"unknown probe subset {subset!r}")
    buckets: dict[tuple[str, int], list[Record]] = {}
    for record in sorted(records, key=lambda item: item.id):
        buckets.setdefault((record.origin, record.label), []).append(record)
    chosen: list[Record] = []
    for key in sorted(buckets):
        origin, _label = key
        cap = TINY_CAPS.get(origin, 2)
        chosen.extend(buckets[key][:cap])
    return chosen


def assign_splits(records: list[Record]) -> list[Record]:
    """Stratified 60/20/20 split. Sorting by id makes the deal deterministic."""

    grouped: dict[int, list[Record]] = {0: [], 1: []}
    for record in sorted(records, key=lambda item: item.id):
        if record.label not in grouped:
            raise ValueError(f"unexpected label {record.label}")
        grouped[record.label].append(record)
    assigned: list[Record] = []
    for label in (0, 1):
        items = grouped[label]
        if len(items) < 5:
            raise ValueError(
                f"label {label} has {len(items)} records; the split needs at least 5"
            )
        for index, record in enumerate(items):
            slot = index % 5
            if slot < 3:
                split = "train"
            elif slot == 3:
                split = "val"
            else:
                split = "test"
            assigned.append(replace(record, split=split))
    assigned.sort(key=lambda item: item.id)
    for split in ("train", "val", "test"):
        present = {item.label for item in assigned if item.split == split}
        if present != {0, 1}:
            raise ValueError(f"split {split} is missing a label")
    return assigned


def prepare_records(subset: str) -> list[Record]:
    return assign_splits(select_subset(load_corpus(), subset))
