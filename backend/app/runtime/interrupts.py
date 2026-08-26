from __future__ import annotations

import re

from app.runtime.model import RuntimeCollection, RuntimeInterrupt, RuntimeWarning


PROC_INTERRUPTS_PARSE_FAILED = "PROC_INTERRUPTS_PARSE_FAILED"
_INTERRUPT_LINE_RE = re.compile(r"^\s*(?P<irq>\d+):\s*(?P<body>.*?)\s*$")
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

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        interrupt = _parse_interrupt_line(
            line,
            line_number,
            source_path,
            warnings,
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
) -> RuntimeInterrupt | None:
    match = _INTERRUPT_LINE_RE.match(line)
    if match is None:
        return None

    tokens = match.group("body").split()
    count_tokens: list[str] = []
    for token in tokens:
        if not token.isdecimal():
            break
        count_tokens.append(token)

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

    return RuntimeInterrupt(
        irq=irq,
        counts=counts,
        controller=controller,
        hardware_irq=hardware_irq,
        trigger=trigger,
        actions=actions,
        raw_line=line,
        source_path=source_path,
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


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)
