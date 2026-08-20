from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from app.runtime import (
    IomemRegion,
    LinuxRuntimeSnapshot,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeProvider,
    RuntimeResource,
    RuntimeSystemInfo,
    RuntimeWarning,
)


def test_runtime_resource_size_supports_large_addresses() -> None:
    resource = RuntimeResource(
        index=0,
        start=0x10_8234_5000,
        end=0x10_8234_5FFF,
        flags=0x200,
        flag_names=("MEM",),
    )

    assert resource.size == 0x1000
    assert resource.flag_names == ("MEM",)


def test_runtime_resource_rejects_invalid_range() -> None:
    with pytest.raises(ValueError, match="end must be >= start"):
        RuntimeResource(index=0, start=0x2000, end=0x1000, flags=0)


def test_runtime_device_supports_unbound_device_and_resources() -> None:
    resource = RuntimeResource(index=1, start=0x1000, end=0x10FF, flags=0x200)
    device = RuntimeDevice(
        name="107d001000.serial",
        sysfs_path="/sys/bus/platform/devices/107d001000.serial",
        bus="platform",
        of_node_path="/sys/firmware/devicetree/base/soc/serial@107d001000",
        resources=[resource],
        metadata=(("modalias_source", "sysfs"),),
    )

    assert device.driver_name is None
    assert device.driver_path is None
    assert device.resources == (resource,)
    assert device.metadata == (("modalias_source", "sysfs"),)


def test_runtime_device_rejects_relative_paths() -> None:
    with pytest.raises(ValueError, match="sysfs_path must be absolute"):
        RuntimeDevice(
            name="device",
            sysfs_path="sys/bus/platform/devices/device",
            bus="platform",
        )


def test_runtime_driver_normalizes_bound_device_paths() -> None:
    driver = RuntimeDriver(
        name="serial8250",
        sysfs_path="/sys/bus/platform/drivers/serial8250",
        bus="platform",
        module_name="8250",
        bound_device_paths=[
            "/sys/bus/platform/devices/107d001000.serial",
            "/sys/bus/platform/devices/107d002000.serial",
        ],
    )

    assert driver.bound_device_paths == (
        "/sys/bus/platform/devices/107d001000.serial",
        "/sys/bus/platform/devices/107d002000.serial",
    )


def test_iomem_region_supports_nested_hierarchy() -> None:
    reserved = IomemRegion(
        start=0x3F00_0000,
        end=0x3FFF_FFFF,
        name="reserved",
    )
    ram = IomemRegion(
        start=0x0000_0000,
        end=0x7FFF_FFFF,
        name="System RAM",
        children=[reserved],
    )

    assert ram.size == 0x8000_0000
    assert ram.children == (reserved,)


def test_iomem_region_rejects_child_outside_parent() -> None:
    with pytest.raises(ValueError, match="children must be inside parent range"):
        IomemRegion(
            start=0x1000,
            end=0x1FFF,
            name="parent",
            children=[
                IomemRegion(
                    start=0x2000,
                    end=0x2FFF,
                    name="outside",
                ),
            ],
        )


def test_linux_runtime_snapshot_normalizes_collections() -> None:
    device = RuntimeDevice(
        name="107d001000.serial",
        sysfs_path="/sys/bus/platform/devices/107d001000.serial",
        bus="platform",
    )
    warning = RuntimeWarning(
        code="SYSFS_PERMISSION_DENIED",
        source_path="/sys/bus/platform/devices/secret",
        message="Unable to read sysfs entry",
    )
    snapshot = LinuxRuntimeSnapshot(
        system=RuntimeSystemInfo(hostname="pi5", architecture="aarch64"),
        devices=[device],
        warnings=[warning],
    )

    assert snapshot.system.hostname == "pi5"
    assert snapshot.devices == (device,)
    assert snapshot.warnings == (warning,)

    with pytest.raises(FrozenInstanceError):
        snapshot.devices = ()


def test_runtime_provider_protocol_collects_snapshot() -> None:
    class FakeRuntimeProvider:
        def collect(self) -> LinuxRuntimeSnapshot:
            return LinuxRuntimeSnapshot(
                system=RuntimeSystemInfo(hostname="test-target"),
            )

    provider: RuntimeProvider = FakeRuntimeProvider()

    assert provider.collect().system.hostname == "test-target"
