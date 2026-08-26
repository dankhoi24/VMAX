from __future__ import annotations

from app.dependency.model import DependencyReference, DependencyResolution
from app.interrupts.model import InterruptCorrelationWarning, InterruptIdentity
from app.model.devicetree import DeviceTree, DeviceTreeNode, DeviceTreeProperty
from app.runtime.model import RuntimeInterrupt


GIC_CONTROLLER_KEY = "gic"
_GIC_COMPATIBLES = {
    "arm,gic",
    "arm,gic-400",
    "arm,gic-v2",
    "arm,gic-v3",
    "arm,cortex-a7-gic",
    "arm,cortex-a9-gic",
    "arm,cortex-a15-gic",
    "arm,arm11mp-gic",
}
_GIC_SPI = 0
_GIC_PPI = 1


class InterruptIdentityExtractor:
    def dt_identities(
        self,
        reference: DependencyReference,
        tree: DeviceTree,
    ) -> tuple[tuple[InterruptIdentity, ...], tuple[InterruptCorrelationWarning, ...]]:
        if reference.resolution != DependencyResolution.RESOLVED:
            return (), (
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_DEPENDENCY_NOT_RESOLVED",
                    consumer_dt_path=reference.consumer_dt_path,
                    provider_dt_path=reference.provider_dt_path,
                    source_path=_reference_source_path(reference),
                    message=(
                        "DT interrupt dependency is not resolved, so it cannot "
                        "be correlated to runtime IRQ state"
                    ),
                ),
            )

        if reference.provider_dt_path is None:
            return (), (
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_PROVIDER_MISSING",
                    consumer_dt_path=reference.consumer_dt_path,
                    source_path=_reference_source_path(reference),
                    message="DT interrupt dependency has no provider path",
                ),
            )

        provider = tree.get_node(reference.provider_dt_path)
        if provider is None:
            return (), (
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_PROVIDER_NOT_FOUND",
                    consumer_dt_path=reference.consumer_dt_path,
                    provider_dt_path=reference.provider_dt_path,
                    source_path=_reference_source_path(reference),
                    message="DT interrupt provider is not present in the parsed tree",
                ),
            )

        controller_key = _dt_provider_controller_key(provider)
        if controller_key != GIC_CONTROLLER_KEY:
            return (), (
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_PROVIDER_UNSUPPORTED",
                    consumer_dt_path=reference.consumer_dt_path,
                    provider_dt_path=reference.provider_dt_path,
                    source_path=_reference_source_path(reference),
                    message=(
                        "DT interrupt provider is not a supported interrupt "
                        "controller for runtime IRQ correlation"
                    ),
                ),
            )

        identities = _gic_identities(reference)
        if not identities:
            return (), (
                InterruptCorrelationWarning(
                    code="DT_INTERRUPT_SPECIFIER_UNSUPPORTED",
                    consumer_dt_path=reference.consumer_dt_path,
                    provider_dt_path=reference.provider_dt_path,
                    source_path=_reference_source_path(reference),
                    message=(
                        "DT interrupt specifier is not a supported ARM GIC "
                        "specifier"
                    ),
                ),
            )

        return identities, ()

    def runtime_identity(
        self,
        interrupt: RuntimeInterrupt,
    ) -> InterruptIdentity | None:
        controller_key = _runtime_controller_key(interrupt.controller)
        if controller_key is None or interrupt.hardware_irq is None:
            return None

        source_path = _metadata_value(interrupt.metadata, "hardware_irq_source")
        if not isinstance(source_path, str):
            source_path = interrupt.source_path

        return InterruptIdentity(
            controller_key=controller_key,
            hardware_irq=interrupt.hardware_irq,
            trigger=interrupt.trigger,
            source="runtime",
            source_path=source_path,
            metadata=(
                ("linux_irq", interrupt.irq),
                ("runtime_controller", interrupt.controller),
                ("total_count", interrupt.total_count),
            ),
        )

    def dt_controller_domain_is_ambiguous(
        self,
        reference: DependencyReference,
        tree: DeviceTree,
    ) -> bool:
        if reference.provider_dt_path is None:
            return False

        provider = tree.get_node(reference.provider_dt_path)
        if provider is None:
            return False

        controller_key = _dt_provider_controller_key(provider)
        if controller_key is None:
            return False

        return len(_dt_interrupt_controller_paths(tree, controller_key)) > 1


def _gic_identities(
    reference: DependencyReference,
) -> tuple[InterruptIdentity, ...]:
    cells = reference.specifier_cells
    source_path = _reference_source_path(reference)
    if len(cells) < 3:
        return ()

    interrupt_type, interrupt_number, flags = cells[:3]
    type_name = _gic_interrupt_type_name(interrupt_type)
    if type_name is None:
        return ()

    trigger = _gic_trigger(flags)
    return (
        _gic_identity(
            hardware_irq=_gic_intid(interrupt_type, interrupt_number),
            trigger=trigger,
            source_path=source_path,
            interrupt_type=type_name,
            interrupt_number=interrupt_number,
            flags=flags,
            rule="gic_intid",
            specifier_cell_count=len(cells),
            ppi_partition_phandle=cells[3] if len(cells) >= 4 else None,
        ),
    )


def _gic_identity(
    *,
    hardware_irq: int,
    trigger: str | None,
    source_path: str | None,
    interrupt_type: str,
    interrupt_number: int,
    flags: int,
    rule: str,
    specifier_cell_count: int,
    ppi_partition_phandle: int | None,
) -> InterruptIdentity:
    metadata: list[tuple[str, str | int]] = [
        ("specifier_format", "arm,gic"),
        ("specifier_cell_count", specifier_cell_count),
        ("gic_interrupt_type", interrupt_type),
        ("gic_interrupt_number", interrupt_number),
        ("gic_flags", flags),
        ("gic_hwirq_rule", rule),
    ]
    if ppi_partition_phandle is not None:
        metadata.append(("ppi_partition_phandle", ppi_partition_phandle))

    return InterruptIdentity(
        controller_key=GIC_CONTROLLER_KEY,
        hardware_irq=hardware_irq,
        trigger=trigger,
        source="devicetree",
        source_path=source_path,
        metadata=tuple(metadata),
    )


def _gic_intid(interrupt_type: int, interrupt_number: int) -> int:
    if interrupt_type == _GIC_SPI:
        return interrupt_number + 32
    if interrupt_type == _GIC_PPI:
        return interrupt_number + 16
    return interrupt_number


def _gic_interrupt_type_name(interrupt_type: int) -> str | None:
    if interrupt_type == _GIC_SPI:
        return "spi"
    if interrupt_type == _GIC_PPI:
        return "ppi"
    return None


def _gic_trigger(flags: int) -> str | None:
    if flags & 0x4:
        return "level"
    if flags & 0x1:
        return "edge"
    return None


def _dt_provider_controller_key(provider: DeviceTreeNode) -> str | None:
    for compatible in _read_string_values(provider.get_property("compatible")):
        normalized = compatible.lower()
        if normalized in _GIC_COMPATIBLES or normalized.startswith("arm,gic-"):
            return GIC_CONTROLLER_KEY
    return None


def _runtime_controller_key(controller: str | None) -> str | None:
    if controller is None:
        return None

    normalized = controller.lower().replace("-", "")
    if normalized.startswith("gic"):
        return GIC_CONTROLLER_KEY
    return None


def _dt_interrupt_controller_paths(
    tree: DeviceTree,
    controller_key: str,
) -> tuple[str, ...]:
    return tuple(
        node.path
        for node in tree.iter_nodes()
        if node.get_property("interrupt-controller") is not None
        and _dt_provider_controller_key(node) == controller_key
    )


def _read_string_values(prop: DeviceTreeProperty | None) -> tuple[str, ...]:
    if prop is None:
        return ()

    if isinstance(prop.value, str):
        return (prop.value,)
    if isinstance(prop.value, tuple) and all(isinstance(item, str) for item in prop.value):
        return prop.value

    if not prop.raw_bytes.endswith(b"\x00"):
        return ()

    values: list[str] = []
    for chunk in prop.raw_bytes[:-1].split(b"\x00"):
        try:
            values.append(chunk.decode("utf-8"))
        except UnicodeDecodeError:
            return ()
    return tuple(value for value in values if value)


def _reference_source_path(reference: DependencyReference) -> str | None:
    for evidence in reference.evidence:
        if evidence.source_path is not None:
            return evidence.source_path
    return None


def _metadata_value(
    metadata: tuple[tuple[str, str | int | bool | None], ...],
    key: str,
) -> str | int | bool | None:
    for item_key, value in metadata:
        if item_key == key:
            return value
    return None
