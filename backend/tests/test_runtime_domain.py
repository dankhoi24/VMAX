from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

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


class RuntimeDomainTest(unittest.TestCase):
    def test_runtime_resource_size_supports_large_addresses(self) -> None:
        resource = RuntimeResource(
            index=0,
            start=0x10_8234_5000,
            end=0x10_8234_5FFF,
            flags=0x200,
            flag_names=("MEM",),
        )

        self.assertEqual(resource.size, 0x1000)
        self.assertEqual(resource.flag_names, ("MEM",))

    def test_runtime_resource_rejects_invalid_range(self) -> None:
        with self.assertRaisesRegex(ValueError, "end must be >= start"):
            RuntimeResource(index=0, start=0x2000, end=0x1000, flags=0)

    def test_runtime_device_supports_unbound_device_and_resources(self) -> None:
        resource = RuntimeResource(index=1, start=0x1000, end=0x10FF, flags=0x200)
        device = RuntimeDevice(
            name="107d001000.serial",
            sysfs_path="/sys/bus/platform/devices/107d001000.serial",
            bus="platform",
            of_node_sysfs_path=(
                "/sys/firmware/devicetree/base/soc/serial@107d001000"
            ),
            resources=[resource],
            metadata=(("modalias_source", "sysfs"),),
        )

        self.assertIsNone(device.driver_name)
        self.assertIsNone(device.driver_path)
        self.assertEqual(
            device.of_node_sysfs_path,
            "/sys/firmware/devicetree/base/soc/serial@107d001000",
        )
        self.assertEqual(device.resources, (resource,))
        self.assertEqual(device.metadata, (("modalias_source", "sysfs"),))

    def test_runtime_device_rejects_relative_paths(self) -> None:
        with self.assertRaisesRegex(ValueError, "sysfs_path must be absolute"):
            RuntimeDevice(
                name="device",
                sysfs_path="sys/bus/platform/devices/device",
                bus="platform",
            )

        with self.assertRaisesRegex(
            ValueError,
            "of_node_sysfs_path must be absolute",
        ):
            RuntimeDevice(
                name="device",
                sysfs_path="/sys/bus/platform/devices/device",
                bus="platform",
                of_node_sysfs_path="sys/firmware/devicetree/base/device",
            )

    def test_runtime_driver_normalizes_bound_device_paths(self) -> None:
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

        self.assertEqual(
            driver.bound_device_paths,
            (
                "/sys/bus/platform/devices/107d001000.serial",
                "/sys/bus/platform/devices/107d002000.serial",
            ),
        )

    def test_iomem_region_supports_nested_hierarchy(self) -> None:
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

        self.assertEqual(ram.size, 0x8000_0000)
        self.assertEqual(ram.children, (reserved,))

    def test_iomem_region_rejects_child_outside_parent(self) -> None:
        with self.assertRaisesRegex(ValueError, "children must be inside parent range"):
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

    def test_linux_runtime_snapshot_normalizes_collections(self) -> None:
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

        self.assertEqual(snapshot.system.hostname, "pi5")
        self.assertEqual(snapshot.devices, (device,))
        self.assertEqual(snapshot.warnings, (warning,))

        with self.assertRaises(FrozenInstanceError):
            snapshot.devices = ()

    def test_runtime_provider_protocol_exposes_granular_collectors(self) -> None:
        class FakeRuntimeProvider:
            def collect_system_info(self) -> RuntimeSystemInfo:
                return RuntimeSystemInfo(hostname="test-target")

            def collect_devices(self) -> tuple[RuntimeDevice, ...]:
                return (
                    RuntimeDevice(
                        name="107d001000.serial",
                        sysfs_path="/sys/bus/platform/devices/107d001000.serial",
                        bus="platform",
                    ),
                )

            def collect_drivers(self) -> tuple[RuntimeDriver, ...]:
                return (
                    RuntimeDriver(
                        name="serial8250",
                        sysfs_path="/sys/bus/platform/drivers/serial8250",
                        bus="platform",
                    ),
                )

            def collect_iomem(self) -> tuple[IomemRegion, ...]:
                return (
                    IomemRegion(
                        start=0x0000_0000,
                        end=0x7FFF_FFFF,
                        name="System RAM",
                    ),
                )

        provider: RuntimeProvider = FakeRuntimeProvider()

        self.assertEqual(provider.collect_system_info().hostname, "test-target")
        self.assertEqual(provider.collect_devices()[0].bus, "platform")
        self.assertEqual(provider.collect_drivers()[0].name, "serial8250")
        self.assertEqual(provider.collect_iomem()[0].name, "System RAM")
