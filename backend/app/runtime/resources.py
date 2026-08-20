from __future__ import annotations

from app.runtime.model import RuntimeCollection, RuntimeResource, RuntimeWarning


IORESOURCE_TYPE_BITS = 0x00001F00
IORESOURCE_IO = 0x00000100
IORESOURCE_MEM = 0x00000200
IORESOURCE_REG = 0x00000300
IORESOURCE_IRQ = 0x00000400
IORESOURCE_DMA = 0x00000800
IORESOURCE_BUS = 0x00001000

RESOURCE_PARSE_FAILED = "LINUX_RESOURCE_PARSE_FAILED"


def parse_linux_resource_file(
    text: str,
    source_path: str,
) -> RuntimeCollection[tuple[RuntimeResource, ...]]:
    warnings: list[RuntimeWarning] = []
    resources: list[RuntimeResource] = []

    for index, line in enumerate(text.splitlines()):
        resource = _parse_resource_line(line, index, source_path, warnings)
        if resource is not None:
            resources.append(resource)

    return RuntimeCollection(data=tuple(resources), warnings=tuple(warnings))


def decode_resource_flag_names(flags: int) -> tuple[str, ...]:
    resource_type = flags & IORESOURCE_TYPE_BITS
    resource_type_name = {
        IORESOURCE_IO: "IO",
        IORESOURCE_MEM: "MEM",
        IORESOURCE_REG: "REG",
        IORESOURCE_IRQ: "IRQ",
        IORESOURCE_DMA: "DMA",
        IORESOURCE_BUS: "BUS",
    }.get(resource_type)

    return (resource_type_name,) if resource_type_name is not None else ()


def _parse_resource_line(
    line: str,
    index: int,
    source_path: str,
    warnings: list[RuntimeWarning],
) -> RuntimeResource | None:
    values = line.split()
    if len(values) != 3:
        warnings.append(
            RuntimeWarning(
                code=RESOURCE_PARSE_FAILED,
                source_path=source_path,
                message=f"Malformed resource line {index} in {source_path}",
            )
        )
        return None

    try:
        start = int(values[0], 0)
        end = int(values[1], 0)
        flags = int(values[2], 0)
        return RuntimeResource(
            index=index,
            start=start,
            end=end,
            flags=flags,
            flag_names=decode_resource_flag_names(flags),
        )
    except (TypeError, ValueError) as error:
        warnings.append(
            RuntimeWarning(
                code=RESOURCE_PARSE_FAILED,
                source_path=source_path,
                message=(
                    f"Unable to parse resource line {index} in {source_path}: "
                    f"{_format_error(error)}"
                ),
            )
        )
        return None


def _format_error(error: Exception) -> str:
    return getattr(error, "strerror", None) or str(error)
