import unittest

from fastapi.testclient import TestClient

from app.main import create_app
from app.runtime import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeResource,
    RuntimeSystemInfo,
    RuntimeWarning,
)


class FakeRuntimeProvider:
    def __init__(
        self,
        *,
        system: RuntimeCollection[RuntimeSystemInfo] | None = None,
        devices: RuntimeCollection[tuple[RuntimeDevice, ...]] | None = None,
        drivers: RuntimeCollection[tuple[RuntimeDriver, ...]] | None = None,
        iomem: RuntimeCollection[tuple[IomemRegion, ...]] | None = None,
    ) -> None:
        self.system = system or RuntimeCollection(data=RuntimeSystemInfo())
        self.devices = devices or RuntimeCollection(data=())
        self.drivers = drivers or RuntimeCollection(data=())
        self.iomem = iomem or RuntimeCollection(data=())
        self.calls = {
            "system": 0,
            "devices": 0,
            "drivers": 0,
            "iomem": 0,
        }

    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        self.calls["system"] += 1
        return self.system

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        self.calls["devices"] += 1
        return self.devices

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        self.calls["drivers"] += 1
        return self.drivers

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        self.calls["iomem"] += 1
        return self.iomem


class FastApiRuntimeTest(unittest.TestCase):
    def test_runtime_metadata_returns_system_info_json(self) -> None:
        provider = FakeRuntimeProvider(
            system=RuntimeCollection(
                data=RuntimeSystemInfo(
                    hostname="pi5",
                    kernel_name="Linux",
                    kernel_release="6.12.80-v8",
                    kernel_version="#1 SMP PREEMPT",
                    machine="aarch64",
                    architecture="arm64",
                    cmdline="console=ttyAMA10",
                )
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/metadata")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "data": {
                    "hostname": "pi5",
                    "kernel_name": "Linux",
                    "kernel_release": "6.12.80-v8",
                    "kernel_version": "#1 SMP PREEMPT",
                    "machine": "aarch64",
                    "architecture": "arm64",
                    "cmdline": "console=ttyAMA10",
                },
                "warnings": [],
            },
        )

    def test_runtime_devices_returns_bound_and_unbound_devices(self) -> None:
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(
                data=(
                    RuntimeDevice(
                        name="107d001000.serial",
                        sysfs_path="/sys/bus/platform/devices/107d001000.serial",
                        bus="platform",
                        driver_name="serial8250",
                        driver_path="/sys/bus/platform/drivers/serial8250",
                        of_node_sysfs_path=(
                            "/sys/firmware/devicetree/base/soc/serial@107d001000"
                        ),
                        resources=(
                            RuntimeResource(
                                index=0,
                                start=0x107D001000,
                                end=0x107D0011FF,
                                flags=0x200,
                                flag_names=("MEM",),
                            ),
                        ),
                    ),
                    RuntimeDevice(
                        name="fixedregulator_3v3",
                        sysfs_path="/sys/bus/platform/devices/fixedregulator_3v3",
                        bus="platform",
                    ),
                )
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(len(body["data"]), 2)
        self.assertEqual(body["data"][0]["driver_name"], "serial8250")
        self.assertEqual(
            body["data"][0]["driver_path"],
            "/sys/bus/platform/drivers/serial8250",
        )
        self.assertEqual(
            body["data"][0]["of_node_sysfs_path"],
            "/sys/firmware/devicetree/base/soc/serial@107d001000",
        )
        self.assertEqual(body["data"][0]["resources"][0]["start"], 0x107D001000)
        self.assertEqual(body["data"][0]["resources"][0]["end"], 0x107D0011FF)
        self.assertEqual(body["data"][0]["resources"][0]["size"], 0x200)
        self.assertEqual(body["data"][0]["resources"][0]["flag_names"], ["MEM"])
        self.assertIsNone(body["data"][1]["driver_name"])
        self.assertIsNone(body["data"][1]["driver_path"])

    def test_runtime_drivers_returns_bound_device_paths(self) -> None:
        provider = FakeRuntimeProvider(
            drivers=RuntimeCollection(
                data=(
                    RuntimeDriver(
                        name="serial8250",
                        sysfs_path="/sys/bus/platform/drivers/serial8250",
                        bus="platform",
                        bound_device_paths=(
                            "/sys/bus/platform/devices/107d001000.serial",
                        ),
                    ),
                )
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/drivers")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["data"],
            [
                {
                    "name": "serial8250",
                    "sysfs_path": "/sys/bus/platform/drivers/serial8250",
                    "bus": "platform",
                    "module_name": None,
                    "bound_device_paths": [
                        "/sys/bus/platform/devices/107d001000.serial",
                    ],
                    "metadata": [],
                }
            ],
        )

    def test_runtime_iomem_returns_nested_hierarchy(self) -> None:
        provider = FakeRuntimeProvider(
            iomem=RuntimeCollection(
                data=(
                    IomemRegion(
                        start=0,
                        end=0x3FFFFFFF,
                        name="System RAM",
                        children=(
                            IomemRegion(
                                start=0x80000,
                                end=0x1FFFFF,
                                name="Kernel code",
                            ),
                        ),
                    ),
                )
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/iomem")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(body["data"][0]["name"], "System RAM")
        self.assertEqual(body["data"][0]["size"], 0x40000000)
        self.assertEqual(body["data"][0]["children"][0]["name"], "Kernel code")
        self.assertEqual(body["data"][0]["children"][0]["size"], 0x180000)

    def test_runtime_warnings_are_http_200_partial_success(self) -> None:
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(
                data=(
                    RuntimeDevice(
                        name="device-a",
                        sysfs_path="/sys/bus/platform/devices/device-a",
                        bus="platform",
                    ),
                ),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
                        message="driver symlink read failed",
                        source_path="/sys/bus/platform/devices/device-a/driver",
                    ),
                ),
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/devices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["data"]), 1)
        self.assertEqual(
            response.json()["warnings"],
            [
                {
                    "code": "SYSFS_PLATFORM_DEVICE_DRIVER_READ_FAILED",
                    "message": "driver symlink read failed",
                    "source_path": "/sys/bus/platform/devices/device-a/driver",
                }
            ],
        )

    def test_runtime_iomem_redacted_warning_is_http_200(self) -> None:
        provider = FakeRuntimeProvider(
            iomem=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="PROC_IOMEM_ADDRESSES_REDACTED",
                        message="/proc/iomem addresses are hidden",
                        source_path="/proc/iomem",
                    ),
                ),
            )
        )
        client = TestClient(create_app(runtime_provider=provider))

        response = client.get("/api/v1/runtime/iomem")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"], [])
        self.assertEqual(
            response.json()["warnings"][0]["code"],
            "PROC_IOMEM_ADDRESSES_REDACTED",
        )

    def test_runtime_endpoints_call_only_matching_collector(self) -> None:
        cases = (
            ("/api/v1/runtime/metadata", "system"),
            ("/api/v1/runtime/devices", "devices"),
            ("/api/v1/runtime/drivers", "drivers"),
            ("/api/v1/runtime/iomem", "iomem"),
        )

        for path, expected_call in cases:
            with self.subTest(path=path):
                provider = FakeRuntimeProvider()
                client = TestClient(create_app(runtime_provider=provider))

                response = client.get(path)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(provider.calls[expected_call], 1)
                for name, count in provider.calls.items():
                    if name != expected_call:
                        self.assertEqual(count, 0)

    def test_openapi_exposes_typed_runtime_contract(self) -> None:
        client = TestClient(create_app(runtime_provider=FakeRuntimeProvider()))

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("RuntimeMetadataCollectionResponse", schemas)
        self.assertIn("RuntimeDeviceCollectionResponse", schemas)
        self.assertIn("RuntimeDriverCollectionResponse", schemas)
        self.assertIn("RuntimeIomemCollectionResponse", schemas)
        self.assertIn("RuntimeWarningResponse", schemas)
        self.assertEqual(
            schemas["RuntimeResourceResponse"]["properties"]["start"]["type"],
            "integer",
        )
        self.assertEqual(
            schemas["IomemRegionResponse"]["properties"]["end"]["type"],
            "integer",
        )
        self.assertEqual(
            response.json()["paths"]["/api/v1/runtime/devices"]["get"][
                "responses"
            ]["200"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/RuntimeDeviceCollectionResponse",
        )


if __name__ == "__main__":
    unittest.main()
