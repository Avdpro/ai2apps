"""Independent Service Packages may start together, after their dependencies."""

import asyncio
from types import SimpleNamespace as NS

from ai2apps.packages.manager import ServicePackageManager
from ai2apps.packages.models import PackageStatus
from ai2apps.services import ServiceStatus


def test_startup_bounds_concurrency_and_waits_for_dependencies():
    packages = [
        NS(service_key=key, package_digest=key, manifest={}, status=PackageStatus.ACTIVE)
        for key in ("runtime", *(f"worker-{index}" for index in range(12)))
    ]
    dependencies = {package.package_digest: [NS(dependency_key="runtime")]
                    for package in packages[1:]}
    active = 0
    peak = 0
    completed = set()

    async def start(package):
        nonlocal active, peak
        if package.service_key != "runtime":
            assert "runtime" in completed
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        completed.add(package.service_key)

    manager = object.__new__(ServicePackageManager)
    manager.packages = NS(installed=lambda: packages,
                          locks=lambda digest: dependencies.get(digest, []))
    manager.services = NS(get_service=lambda key: NS(status=ServiceStatus.ENABLED))
    manager.supervisor = NS(recover_orphans=lambda: None)
    manager.runtime = NS(start=start)
    manager._active_start_order = lambda: tuple(packages)
    manager._activate_staged_inference_runtimes = lambda: ()
    manager._validate_installed = lambda package: None

    asyncio.run(manager.startup())

    assert completed == {package.service_key for package in packages}
    assert peak == 8
