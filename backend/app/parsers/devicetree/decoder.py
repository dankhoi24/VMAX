from __future__ import annotations

from collections.abc import Iterable

from app.model.devicetree import DeviceTreeProperty, PropertyKind


class PropertyDecoder:
    STRING_LIST_PROPERTIES = frozenset(
        {
            "compatible",
        }
    )
    CELL_PROPERTIES = frozenset(
        {
            "#address-cells",
            "#size-cells",
            "dma-ranges",
            "interrupt-map",
            "interrupt-parent",
            "interrupts",
            "interrupts-extended",
            "linux,phandle",
            "phandle",
            "ranges",
            "reg",
        }
    )

    def decode(self, name: str, raw_bytes: bytes) -> DeviceTreeProperty:
        if not raw_bytes:
            return DeviceTreeProperty(
                name=name,
                raw_bytes=raw_bytes,
                kind=PropertyKind.BOOLEAN,
                value=True,
            )

        strings = _decode_null_terminated_strings(raw_bytes)
        if strings is not None:
            return self._decode_strings(name, raw_bytes, strings)

        if name in self.CELL_PROPERTIES:
            return self._decode_cells(name, raw_bytes)

        if len(raw_bytes) % 4 == 0:
            return DeviceTreeProperty(
                name=name,
                raw_bytes=raw_bytes,
                kind=PropertyKind.UNKNOWN,
                value=None,
            )

        return DeviceTreeProperty(
            name=name,
            raw_bytes=raw_bytes,
            kind=PropertyKind.BYTES,
            value=tuple(raw_bytes),
        )

    def decode_many(
        self,
        properties: Iterable[tuple[str, bytes]],
    ) -> tuple[DeviceTreeProperty, ...]:
        return tuple(self.decode(name, raw_bytes) for name, raw_bytes in properties)

    def _decode_strings(
        self,
        name: str,
        raw_bytes: bytes,
        strings: tuple[str, ...],
    ) -> DeviceTreeProperty:
        if name in self.STRING_LIST_PROPERTIES or len(strings) > 1:
            return DeviceTreeProperty(
                name=name,
                raw_bytes=raw_bytes,
                kind=PropertyKind.STRING_LIST,
                value=strings,
            )

        return DeviceTreeProperty(
            name=name,
            raw_bytes=raw_bytes,
            kind=PropertyKind.STRING,
            value=strings[0],
        )

    def _decode_cells(self, name: str, raw_bytes: bytes) -> DeviceTreeProperty:
        if len(raw_bytes) % 4 != 0:
            return DeviceTreeProperty(
                name=name,
                raw_bytes=raw_bytes,
                kind=PropertyKind.UNKNOWN,
                value=None,
            )

        return DeviceTreeProperty(
            name=name,
            raw_bytes=raw_bytes,
            kind=PropertyKind.CELLS,
            value=_decode_u32_cells(raw_bytes),
        )


def _decode_null_terminated_strings(raw_bytes: bytes) -> tuple[str, ...] | None:
    if not raw_bytes.endswith(b"\x00"):
        return None

    strings: list[str] = []
    for chunk in raw_bytes[:-1].split(b"\x00"):
        try:
            text = chunk.decode("utf-8")
        except UnicodeDecodeError:
            return None
        if not _is_display_text(text):
            return None
        strings.append(text)

    return tuple(strings)


def _is_display_text(text: str) -> bool:
    return all(char.isprintable() for char in text)


def _decode_u32_cells(raw_bytes: bytes) -> tuple[int, ...]:
    return tuple(
        int.from_bytes(raw_bytes[index : index + 4], byteorder="big")
        for index in range(0, len(raw_bytes), 4)
    )
