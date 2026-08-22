"""Deterministic single-active-version Service dependency solver."""

from __future__ import annotations

from collections import defaultdict

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .models import DependencyLock, InspectedServicePackage, InstallPlan, PackageError
from .repository import PackageRepository


class ServiceDependencyResolver:
    def __init__(self, repository: PackageRepository) -> None:
        self.repository = repository

    def resolve(
        self,
        root: InspectedServicePackage,
        candidates: tuple[InspectedServicePackage, ...] = (),
    ) -> InstallPlan:
        available: dict[str, list[tuple[Version, str, object]]] = defaultdict(list)
        by_digest = {root.digest: root}
        for package in (root, *candidates):
            by_digest[package.digest] = package
            available[package.manifest.service_key].append(
                (Version(package.manifest.version), package.digest, package)
            )
        from .models import PackageStatus

        for installed in self.repository.installed():
            if installed.status is not PackageStatus.ACTIVE:
                continue
            available[installed.service_key].append(
                (
                    Version(installed.package_version),
                    installed.package_digest,
                    installed,
                )
            )
        selected: dict[str, object] = {root.manifest.service_key: root}
        locks: list[DependencyLock] = []
        visiting: list[str] = []
        install_order: list[InspectedServicePackage] = []

        def dependencies(package):
            if isinstance(package, InspectedServicePackage):
                return package.manifest.dependencies
            raw = package.manifest.get("requires", {}).get("services", [])
            from ai2apps.services import ServiceDependency

            return tuple(
                ServiceDependency(
                    item["id"],
                    str(item.get("version", "*")),
                    bool(item.get("optional", False)),
                )
                for item in raw
            )

        def required_capabilities(package, service_key: str) -> frozenset[str]:
            manifest = (
                package.manifest.raw
                if isinstance(package, InspectedServicePackage)
                else package.manifest
            )
            for item in manifest.get("requires", {}).get("services", []):
                if item.get("id") == service_key:
                    return frozenset(item.get("capabilities", []))
            return frozenset()

        def package_capabilities(package) -> frozenset[str]:
            manifest = (
                package.manifest.raw
                if isinstance(package, InspectedServicePackage)
                else package.manifest
            )
            return frozenset(manifest.get("capabilities", []))

        def walk(package) -> None:
            key = (
                package.manifest.service_key
                if isinstance(package, InspectedServicePackage)
                else package.service_key
            )
            digest = (
                package.digest
                if isinstance(package, InspectedServicePackage)
                else package.package_digest
            )
            if key in visiting:
                cycle = visiting[visiting.index(key) :] + [key]
                raise PackageError(
                    "dependency_cycle",
                    "Service dependency cycle detected",
                    details={"cycle": cycle},
                )
            visiting.append(key)
            for dependency in dependencies(package):
                if dependency.service_key in visiting:
                    cycle = visiting[visiting.index(dependency.service_key) :] + [
                        dependency.service_key
                    ]
                    raise PackageError(
                        "dependency_cycle",
                        "Service dependency cycle detected",
                        details={"cycle": cycle},
                    )
                spec = SpecifierSet(
                    "" if dependency.version_spec == "*" else dependency.version_spec
                )
                required = required_capabilities(package, dependency.service_key)
                version_choices = tuple(
                    item
                    for item in available.get(dependency.service_key, [])
                    if item[0] in spec
                )
                choices = sorted(
                    (
                        item
                        for item in version_choices
                        if not (required - package_capabilities(item[2]))
                    ),
                    key=lambda item: (item[0], item[1]),
                    reverse=True,
                )
                if not choices:
                    if dependency.optional:
                        continue
                    if version_choices and required:
                        provided = set().union(
                            *(package_capabilities(item[2]) for item in version_choices)
                        )
                        raise PackageError(
                            "dependency_capability_missing",
                            f"{dependency.service_key} lacks required capabilities",
                            details={"missing": sorted(required - provided)},
                        )
                    raise PackageError(
                        "dependency_unresolved",
                        f"No compatible version for {dependency.service_key} {dependency.version_spec}",
                    )
                version, dependency_digest, chosen = choices[0]
                existing = selected.get(dependency.service_key)
                if existing is not None:
                    existing_digest = (
                        existing.digest
                        if isinstance(existing, InspectedServicePackage)
                        else existing.package_digest
                    )
                    if existing_digest != dependency_digest:
                        raise PackageError(
                            "dependency_conflict",
                            f"Conflicting version for {dependency.service_key}",
                        )
                else:
                    selected[dependency.service_key] = chosen
                    walk(chosen)
                locks.append(
                    DependencyLock(
                        key,
                        digest,
                        dependency.service_key,
                        str(version),
                        dependency_digest,
                        dependency.optional,
                    )
                )
            visiting.pop()
            if (
                isinstance(package, InspectedServicePackage)
                and package not in install_order
            ):
                install_order.append(package)

        walk(root)
        packages = tuple(install_order)
        replacing = {
            package.manifest.service_key: active.package_digest
            for package in packages
            if (active := self.repository.active(package.manifest.service_key))
            is not None
            and active.package_digest != package.digest
        }
        return InstallPlan(root.digest, packages, tuple(locks), replacing)
