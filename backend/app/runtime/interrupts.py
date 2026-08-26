from __future__ import annotations

import re

from app.runtime.model import RuntimeCollection, RuntimeInterrupt, RuntimeWarning


PROC_INTERRUPTS_PARSE_FAILED = "PROC_INTERRUPTS_PARSE_FAILED"
_INTERRUPT_LINE_RE = re.compile(r"^\s*(?P<irq>\d+):\s*(?P<body>.*?)\s*$")
_CPU_HEADER_RE = re.compile(r"^CPU\d+$")
_TRIGGER_TOKENS = {
    "edge",
    "level",
    "level-high",
    "level-low",
    "edge-rising",
    "edge-falling",
    "fasteoi",
}


def parse_proc_interrupts_file(
    text: str,
    source_path: str = "/proc/interrupts",
) -> RuntimeCollection[tuple[RuntimeInterrupt, ...]]:
    warnings: list[RuntimeWarning] = []
    interrupts: list[RuntimeInterrupt] = []
    cpu_count: int | None = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        if _INTERRUPT_LINE_RE.match(line) is None:
            cpu_count = _parse_cpu_header_count(line) or cpu_count
            continue

        interrupt = _parse_interrupt_line(
            line,
            line_number,
            source_path,
            warnings,
            cpu_count,
        )
        if interrupt is not None:
            interrupts.append(interrupt)

    return RuntimeCollection(data=tuple(interrupts), warnings=tuple(warnings))


def parse_interrupt_actions(value: str) -> tuple[str, ...]:
    text = value.strip()
    if not text:
        return ()

    if "," in text:
        return tuple(part.strip() for part in text.split(",") if part.strip())

    return (text,)


def _parse_interrupt_line(
    line: str,
    line_number: int,
    source_path: str,
    warnings: list[RuntimeWarning],
    cpu_count: int | None,
) -> RuntimeInterrupt | None:
    match = _INTERRUPT_LINE_RE.match(line)
    if match is None:
        return None

    tokens = match.group("body").split()
    if cpu_count is None:
        count_tokens: list[str] = []
        for token in tokens:
            if not token.isdecimal():
                break
            count_tokens.append(token)
    else:
        count_tokens = tokens[:cpu_count]
        if len(count_tokens) != cpu_count or not all(
            token.isdecimal() for token in count_tokens
        ):
            warnings.append(
                RuntimeWarning(
                    code=PROC_INTERRUPTS_PARSE_FAILED,
                    source_path=source_path,
                    message=(
                        f"Malformed /proc/interrupts line {line_number}: "
                        f"expected {cpu_count} CPU counters"
                    ),
                )
            )
            return None

    if not count_tokens:
        warnings.append(
            RuntimeWarning(
                code=PROC_INTERRUPTS_PARSE_FAILED,
                source_path=source_path,
                message=f"Malformed /proc/interrupts line {line_number}",
            )
        )
        return None

    try:
        irq = int(match.group("irq"), 10)
        counts = tuple(int(token, 10) for token in count_tokens)
    except ValueError as error:
        warnings.append(
            RuntimeWarning(
                code=PROC_INTERRUPTS_PARSE_FAILED,
                source_path=source_path,
                message=(
                    f"Unable to parse /proc/interrupts line {line_number}: "
                    f"{_format_error(error)}"
                ),
            )
        )
        return None

    description_tokens = tokens[len(count_tokens) :]
    controller, hardware_irq, trigger, actions = _parse_interrupt_description(
        description_tokens
    )
    metadata = _source_metadata(
        source_path,
        controller=controller,
        hardware_irq=hardware_irq,
        trigger=trigger,
        actions=actions,
    )

    return RuntimeInterrupt(
        irq=irq,
        counts=counts,
        controller=controller,
        hardware_irq=hardware_irq,
        trigger=trigger,
        actions=actions,
        raw_line=line,
        source_path=source_path,
        metadata=metadata,
    )


def _parse_interrupt_description(
    tokens: list[str],
) -> tuple[str | None, int | None, str | None, tuple[str, ...]]:
    if not tokens:
        return None, None, None, ()

    controller = tokens[0]
    cursor = 1
    hardware_irq = None
    trigger = None

    if cursor < len(tokens):
        hardware_irq = _parse_int_token(tokens[cursor])
        if hardware_irq is not None:
            cursor += 1

    if cursor < len(tokens) and _is_trigger_token(tokens[cursor]):
        trigger = tokens[cursor]
        cursor += 1

    actions = parse_interrupt_actions(" ".join(tokens[cursor:]))
    return controller, hardware_irq, trigger, actions


def _parse_int_token(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        return None


def _is_trigger_token(value: str) -> bool:
    return value.lower() in _TRIGGER_TOKENS


def _parse_cpu_header_count(line: str) -> int | None:
    cpu_columns = tuple(token for token in line.split() if _CPU_HEADER_RE.match(token))
    return len(cpu_columns) or None


def _source_metadata(
    source_path: str,
    *,
    controller: str | None,
    hardware_irq: int | None,
    trigger: str | None,
    actions: tuple[str, ...],
) -> tuple[tuple[str, str], ...]:
    items = [("primary_source", source_path)]
    if controller is not None:
        items.append(("controller_source", source_path))
    if hardware_irq is not None:
        items.append(("hardware_irq_source", source_path))
    if trigger is not None:
        items.append(("trigger_source", source_path))
    if actions:
        items.append(("actions_source", source_path))
    return tuple(items)


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)
