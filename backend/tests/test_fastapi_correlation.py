import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.model.devicetree import (
    DeviceTree,
    DeviceTreeNode,
    DeviceTreeProperty,
    ParseResult,
    PropertyKind,
)
from app.runtime import (
    IomemRegion,
    RuntimeCollection,
    RuntimeDevice,
    RuntimeDriver,
    RuntimeInterrupt,
    RuntimeSystemInfo,
    RuntimeWarning,
)
from app.services.devicetree_state import DeviceTreeState


class FakeCollector:
    def __init__(self, result: ParseResult) -> None:
        self.result = result

    def collect_from_file(self, path: str | Path) -> ParseResult:
        return self.result


class FakeRuntimeProvider:
    def __init__(
        self,
        *,
        devices: RuntimeCollection[tuple[RuntimeDevice, ...]] | None = None,
        drivers: RuntimeCollection[tuple[RuntimeDriver, ...]] | None = None,
        iomem: RuntimeCollection[tuple[IomemRegion, ...]] | None = None,
        interrupts: RuntimeCollection[tuple[RuntimeInterrupt, ...]] | None = None,
    ) -> None:
        self.devices = devices or RuntimeCollection(data=())
        self.drivers = drivers or RuntimeCollection(data=())
        self.iomem = iomem or RuntimeCollection(data=())
        self.interrupts = interrupts or RuntimeCollection(data=())
        self.calls = {
            "system": 0,
            "devices": 0,
            "drivers": 0,
            "iomem": 0,
            "interrupts": 0,
        }

    def collect_system_info(self) -> RuntimeCollection[RuntimeSystemInfo]:
        self.calls["system"] += 1
        return RuntimeCollection(data=RuntimeSystemInfo())

    def collect_devices(self) -> RuntimeCollection[tuple[RuntimeDevice, ...]]:
        self.calls["devices"] += 1
        return self.devices

    def collect_drivers(self) -> RuntimeCollection[tuple[RuntimeDriver, ...]]:
        self.calls["drivers"] += 1
        return self.drivers

    def collect_iomem(self) -> RuntimeCollection[tuple[IomemRegion, ...]]:
        self.calls["iomem"] += 1
        return self.iomem

    def collect_interrupts(self) -> RuntimeCollection[tuple[RuntimeInterrupt, ...]]:
        self.calls["interrupts"] += 1
        return self.interrupts


class FastApiCorrelationTest(unittest.TestCase):
    def test_correlation_devices_returns_correlated_report_json(self) -> None:
        device = RuntimeDevice(
            name="107d001000.uart",
            sysfs_path="/sys/bus/platform/devices/107d001000.uart",
            bus="platform",
            driver_name="uart-driver",
            driver_path="/sys/bus/platform/drivers/uart-driver",
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/uart@1000",
        )
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(data=(device,)),
            drivers=RuntimeCollection(
                data=(
                    RuntimeDriver(
                        name="uart-driver",
                        sysfs_path="/sys/bus/platform/drivers/uart-driver",
                        bus="platform",
                        bound_device_paths=(device.sysfs_path,),
                    ),
                )
            ),
            iomem=RuntimeCollection(
                data=(
                    IomemRegion(
                        start=0x107D001000,
                        end=0x107D0010FF,
                        name="107d001000.uart",
                    ),
                )
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["warnings"], [])
        self.assertEqual(len(body["data"]), 1)
        correlated = body["data"][0]
        self.assertEqual(correlated["dt_node_path"], "/soc/uart@1000")
        self.assertEqual(correlated["match_method"], "exact_of_node")
        self.assertEqual(correlated["runtime_device"]["name"], "107d001000.uart")
        self.assertEqual(correlated["runtime_driver"]["name"], "uart-driver")
        self.assertEqual(
            correlated["static_regions"],
            [
                {
                    "node_path": "/soc/uart@1000",
                    "bus_address": "0x1000",
                    "cpu_start": "0x107d001000",
                    "size": "0x100",
                    "cpu_end": "0x107d0010ff",
                }
            ],
        )
        self.assertEqual(
            correlated["address_matches"],
            [
                {
                    "dt_start": "0x107d001000",
                    "dt_end": "0x107d0010ff",
                    "iomem_start": "0x107d001000",
                    "iomem_end": "0x107d0010ff",
                    "iomem_name": "107d001000.uart",
                    "match_type": "exact",
                    "candidates": [
                        {
                            "start": "0x107d001000",
                            "end": "0x107d0010ff",
                            "name": "107d001000.uart",
                        }
                    ],
                }
            ],
        )

    def test_correlation_devices_reports_unavailable_when_iomem_read_failed(
        self,
    ) -> None:
        device = RuntimeDevice(
            name="107d001000.uart",
            sysfs_path="/sys/bus/platform/devices/107d001000.uart",
            bus="platform",
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/uart@1000",
        )
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(data=(device,)),
            iomem=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="PROC_IOMEM_READ_FAILED",
                        message="Unable to read /proc/iomem",
                        source_path="/proc/iomem",
                    ),
                ),
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            body["data"][0]["address_matches"][0]["match_type"],
            "unavailable",
        )
        self.assertEqual(body["data"][0]["address_matches"][0]["candidates"], [])
        self.assertEqual(body["warnings"][0]["code"], "PROC_IOMEM_READ_FAILED")

    def test_correlation_devices_uses_partial_iomem_matches_without_reporting_none(
        self,
    ) -> None:
        provider = FakeRuntimeProvider(
            iomem=RuntimeCollection(
                data=(
                    IomemRegion(
                        start=0x107D001000,
                        end=0x107D0010FF,
                        name="107d001000.uart",
                    ),
                ),
                warnings=(
                    RuntimeWarning(
                        code="PROC_IOMEM_PARSE_FAILED",
                        message="Malformed /proc/iomem line 2",
                        source_path="/proc/iomem",
                    ),
                ),
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree_with_gpio()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        by_path = {item["dt_node_path"]: item for item in body["data"]}
        self.assertEqual(
            by_path["/soc/uart@1000"]["address_matches"][0]["match_type"],
            "exact",
        )
        self.assertEqual(
            by_path["/soc/gpio@2000"]["address_matches"][0]["match_type"],
            "unavailable",
        )
        self.assertEqual(body["warnings"][0]["code"], "PROC_IOMEM_PARSE_FAILED")

    def test_correlation_devices_reports_unavailable_when_device_scan_failed(
        self,
    ) -> None:
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DEVICES_READ_FAILED",
                        message="Unable to read devices",
                        source_path="/sys/bus/platform/devices",
                    ),
                ),
            ),
            iomem=RuntimeCollection(
                data=(
                    IomemRegion(
                        start=0x107D001000,
                        end=0x107D0010FF,
                        name="107d001000.uart",
                    ),
                )
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"][0]["match_method"], "unavailable")
        self.assertIsNone(body["data"][0]["runtime_device"])
        self.assertEqual(
            body["data"][0]["address_matches"][0]["match_type"],
            "exact",
        )
        self.assertEqual(
            body["warnings"][0]["code"],
            "SYSFS_PLATFORM_DEVICES_READ_FAILED",
        )

    def test_correlation_devices_uses_partial_device_matches_without_unmatched(
        self,
    ) -> None:
        device = RuntimeDevice(
            name="107d001000.uart",
            sysfs_path="/sys/bus/platform/devices/107d001000.uart",
            bus="platform",
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/uart@1000",
        )
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(
                data=(device,),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DEVICE_READ_FAILED",
                        message="Unable to inspect one platform device",
                        source_path="/sys/bus/platform/devices/107d002000.gpio",
                    ),
                ),
            ),
            iomem=RuntimeCollection(
                data=(
                    IomemRegion(
                        start=0x107D001000,
                        end=0x107D0010FF,
                        name="107d001000.uart",
                    ),
                    IomemRegion(
                        start=0x107D002000,
                        end=0x107D0020FF,
                        name="107d002000.gpio",
                    ),
                )
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree_with_gpio()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        by_path = {item["dt_node_path"]: item for item in body["data"]}
        self.assertEqual(by_path["/soc/uart@1000"]["match_method"], "exact_of_node")
        self.assertEqual(by_path["/soc/gpio@2000"]["match_method"], "unavailable")
        self.assertEqual(
            by_path["/soc/gpio@2000"]["address_matches"][0]["match_type"],
            "exact",
        )
        self.assertEqual(
            body["warnings"][0]["code"],
            "SYSFS_PLATFORM_DEVICE_READ_FAILED",
        )

    def test_correlation_devices_does_not_report_driver_not_found_when_driver_scan_failed(
        self,
    ) -> None:
        device = RuntimeDevice(
            name="107d001000.uart",
            sysfs_path="/sys/bus/platform/devices/107d001000.uart",
            bus="platform",
            driver_name="uart-driver",
            driver_path="/sys/bus/platform/drivers/uart-driver",
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/uart@1000",
        )
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(data=(device,)),
            drivers=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DRIVERS_READ_FAILED",
                        message="Unable to read drivers",
                        source_path="/sys/bus/platform/drivers",
                    ),
                ),
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        correlated = body["data"][0]
        self.assertEqual(correlated["match_method"], "exact_of_node")
        self.assertIsNone(correlated["runtime_driver"])
        self.assertEqual(correlated["warnings"], [])
        warning_codes = [warning["code"] for warning in body["warnings"]]
        self.assertIn("SYSFS_PLATFORM_DRIVERS_READ_FAILED", warning_codes)
        self.assertNotIn("RUNTIME_DRIVER_NOT_FOUND", warning_codes)

    def test_correlation_devices_does_not_report_driver_not_found_when_driver_scan_partial(
        self,
    ) -> None:
        device = RuntimeDevice(
            name="107d001000.uart",
            sysfs_path="/sys/bus/platform/devices/107d001000.uart",
            bus="platform",
            driver_name="uart-driver",
            driver_path="/sys/bus/platform/drivers/uart-driver",
            of_node_sysfs_path="/sys/firmware/devicetree/base/soc/uart@1000",
        )
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(data=(device,)),
            drivers=RuntimeCollection(
                data=(
                    RuntimeDriver(
                        name="other-driver",
                        sysfs_path="/sys/bus/platform/drivers/other-driver",
                        bus="platform",
                    ),
                ),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DRIVER_READ_FAILED",
                        message="Unable to inspect one platform driver",
                        source_path="/sys/bus/platform/drivers/uart-driver",
                    ),
                ),
            ),
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIsNone(body["data"][0]["runtime_driver"])
        warning_codes = [warning["code"] for warning in body["warnings"]]
        self.assertIn("SYSFS_PLATFORM_DRIVER_READ_FAILED", warning_codes)
        self.assertNotIn("RUNTIME_DRIVER_NOT_FOUND", warning_codes)

    def test_correlation_devices_preserves_runtime_warnings(self) -> None:
        provider = FakeRuntimeProvider(
            devices=RuntimeCollection(
                data=(),
                warnings=(
                    RuntimeWarning(
                        code="SYSFS_PLATFORM_DEVICES_READ_FAILED",
                        message="Unable to read devices",
                        source_path="/sys/bus/platform/devices",
                    ),
                ),
            )
        )
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["warnings"],
            [
                {
                    "code": "SYSFS_PLATFORM_DEVICES_READ_FAILED",
                    "message": "Unable to read devices",
                    "dt_node_path": None,
                    "runtime_device_path": None,
                    "source_path": "/sys/bus/platform/devices",
                }
            ],
        )

    def test_correlation_devices_returns_422_when_devicetree_parse_failed(self) -> None:
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(
                    current_path="bad.dtb",
                    collector=FakeCollector(
                        ParseResult(
                            tree=None,
                            source="bad.dtb",
                            warnings=("best effort",),
                            errors=("Failed to parse DTB",),
                        )
                    ),
                ),
                runtime_provider=FakeRuntimeProvider(),
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["detail"]["source"], "bad.dtb")
        self.assertEqual(response.json()["detail"]["warnings"], ["best effort"])
        self.assertEqual(response.json()["detail"]["errors"], ["Failed to parse DTB"])

    def test_correlation_endpoint_collects_runtime_sources_needed_for_correlation(
        self,
    ) -> None:
        provider = FakeRuntimeProvider()
        client = TestClient(
            create_app(
                devicetree_state=_devicetree_state(sample_tree()),
                runtime_provider=provider,
            )
        )

        response = client.get("/api/v1/correlation/devices")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(provider.calls["devices"], 1)
        self.assertEqual(provider.calls["drivers"], 1)
        self.assertEqual(provider.calls["iomem"], 1)
        self.assertEqual(provider.calls["system"], 0)

    def test_openapi_exposes_typed_correlation_contract(self) -> None:
        client = TestClient(
            create_app(
                devicetree_state=DeviceTreeState(),
                runtime_provider=FakeRuntimeProvider(),
            )
        )

        response = client.get("/openapi.json")

        self.assertEqual(response.status_code, 200)
        schemas = response.json()["components"]["schemas"]
        self.assertIn("CorrelationDeviceCollectionResponse", schemas)
        self.assertIn("CorrelatedDeviceResponse", schemas)
        self.assertIn("AddressCorrelationResponse", schemas)
        self.assertIn("IomemCandidateResponse", schemas)
        self.assertEqual(
            schemas["AddressCorrelationResponse"]["properties"]["dt_start"]["type"],
            "string",
        )
        self.assertEqual(
            schemas["AddressCorrelationResponse"]["properties"]["iomem_start"][
                "anyOf"
            ][0]["type"],
            "string",
        )
        self.assertEqual(
            schemas["StaticAddressRegionResponse"]["properties"]["cpu_start"][
                "anyOf"
            ][0]["type"],
            "string",
        )
        self.assertEqual(
            response.json()["paths"]["/api/v1/correlation/devices"]["get"][
                "responses"
            ]["200"]["content"]["application/json"]["schema"]["$ref"],
            "#/components/schemas/CorrelationDeviceCollectionResponse",
        )


def sample_tree() -> DeviceTree:
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
        properties=(cells("reg", 0x1000, 0x100),),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(
            cells("#address-cells", 1),
            cells("#size-cells", 1),
            cells("ranges", 0, 0x10, 0x7D000000, 0x100000),
        ),
        children=(uart,),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(soc,),
    )
    return DeviceTree(root=root)


def sample_tree_with_gpio() -> DeviceTree:
    uart = DeviceTreeNode(
        name="uart",
        path="/soc/uart@1000",
        unit_address="1000",
        parent_path="/soc",
        properties=(cells("reg", 0x1000, 0x100),),
    )
    gpio = DeviceTreeNode(
        name="gpio",
        path="/soc/gpio@2000",
        unit_address="2000",
        parent_path="/soc",
        properties=(cells("reg", 0x2000, 0x100),),
    )
    soc = DeviceTreeNode(
        name="soc",
        path="/soc",
        parent_path="/",
        properties=(
            cells("#address-cells", 1),
            cells("#size-cells", 1),
            cells("ranges", 0, 0x10, 0x7D000000, 0x100000),
        ),
        children=(uart, gpio),
    )
    root = DeviceTreeNode(
        name="/",
        path="/",
        properties=(cells("#address-cells", 2), cells("#size-cells", 1)),
        children=(soc,),
    )
    return DeviceTree(root=root)


def _devicetree_state(tree: DeviceTree) -> DeviceTreeState:
    return DeviceTreeState(
        current_path="board.dtb",
        collector=FakeCollector(ParseResult(tree=tree, source="board.dtb")),
    )


def cells(name: str, *values: int) -> DeviceTreeProperty:
    return DeviceTreeProperty(name=name, kind=PropertyKind.CELLS, value=values)


if __name__ == "__main__":
    unittest.main()
