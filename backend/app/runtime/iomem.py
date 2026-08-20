from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.runtime.model import IomemRegion, RuntimeCollection, RuntimeWarning


PROC_IOMEM_PARSE_FAILED = "PROC_IOMEM_PARSE_FAILED"
PROC_IOMEM_ADDRESSES_REDACTED = "PROC_IOMEM_ADDRESSES_REDACTED"
_IOMEM_LINE_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<start>[0-9a-fA-F]+)-"
    r"(?P<end>[0-9a-fA-F]+)\s*:\s*(?P<name>.*?)\s*$"
)


@dataclass
class _IomemNode:
    start: int
    end: int
    name: str
    children: list["_IomemNode"] = field(default_factory=list)


def parse_proc_iomem_file(
    text: str,
    source_path: str = "/proc/iomem",
) -> RuntimeCollection[tuple[IomemRegion, ...]]:
    warnings: list[RuntimeWarning] = []
    roots: list[_IomemNode] = []
    stack: list[tuple[int, _IomemNode]] = []
    parsed_ranges: list[tuple[int, int]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        parsed = _parse_iomem_line(line, line_number, source_path, warnings)
        if parsed is None:
            continue

        indent, node = parsed
        parsed_ranges.append((node.start, node.end))
        while stack and stack[-1][0] >= indent:
            stack.pop()

        if stack:
            parent = stack[-1][1]
            if node.start < parent.start or node.end > parent.end:
                warnings.append(
                    RuntimeWarning(
                        code=PROC_IOMEM_PARSE_FAILED,
                        source_path=source_path,
                        message=(
                            f"/proc/iomem line {line_number} is outside "
                            f"parent region {parent.name!r}"
                        ),
                    )
                )
                continue

            parent.children.append(node)
        else:
            roots.append(node)

        stack.append((indent, node))

    if _addresses_are_redacted(parsed_ranges):
        return RuntimeCollection(
            data=(),
            warnings=(
                RuntimeWarning(
                    code=PROC_IOMEM_ADDRESSES_REDACTED,
                    source_path=source_path,
                    message=(
                        "/proc/iomem addresses are hidden; CAP_SYS_ADMIN "
                        "may be unavailable"
                    ),
                ),
            ),
        )

    return RuntimeCollection(
        data=tuple(_to_iomem_region(node) for node in roots),
        warnings=tuple(warnings),
    )


def _parse_iomem_line(
    line: str,
    line_number: int,
    source_path: str,
    warnings: list[RuntimeWarning],
) -> tuple[int, _IomemNode] | None:
    match = _IOMEM_LINE_RE.match(line)
    if match is None or not match.group("name").strip():
        warnings.append(
            RuntimeWarning(
                code=PROC_IOMEM_PARSE_FAILED,
                source_path=source_path,
                message=f"Malformed /proc/iomem line {line_number}",
            )
        )
        return None

    try:
        start = int(match.group("start"), 16)
        end = int(match.group("end"), 16)
    except ValueError as error:
        warnings.append(
            RuntimeWarning(
                code=PROC_IOMEM_PARSE_FAILED,
                source_path=source_path,
                message=(
                    f"Unable to parse /proc/iomem line {line_number}: "
                    f"{_format_error(error)}"
                ),
            )
        )
        return None

    if end < start:
        warnings.append(
            RuntimeWarning(
                code=PROC_IOMEM_PARSE_FAILED,
                source_path=source_path,
                message=f"Invalid /proc/iomem range on line {line_number}",
            )
        )
        return None

    return (
        _indent_width(match.group("indent")),
        _IomemNode(start=start, end=end, name=match.group("name").strip()),
    )


def _indent_width(value: str) -> int:
    width = 0
    for char in value:
        width += 8 if char == "\t" else 1
    return width


def _addresses_are_redacted(ranges: list[tuple[int, int]]) -> bool:
    return (
        len(ranges) >= 2
        and all(start == 0 and end == 0 for start, end in ranges)
    )


def _to_iomem_region(node: _IomemNode) -> IomemRegion:
    return IomemRegion(
        start=node.start,
        end=node.end,
        name=node.name,
        children=tuple(_to_iomem_region(child) for child in node.children),
    )


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)
