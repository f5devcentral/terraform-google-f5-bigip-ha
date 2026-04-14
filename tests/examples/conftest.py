"""Fixtures for testing the examples."""

import pathlib
import re
import shutil
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.api_core import exceptions
from google.cloud import compute_v1

from tests import DEFAULT_WAIT_FOR_TIMEOUT
from tests.examples import DEFAULT_BACKEND_SERVICE_SELF_LINK_PATTERN


@pytest.fixture(scope="session")
def stateless_module_dir() -> pathlib.Path:
    """Return the Path of the stateless module."""
    module_dir = pathlib.Path(__file__).parent.parent.parent.joinpath("modules/stateless").resolve()
    assert module_dir.exists()
    assert module_dir.is_dir()
    assert module_dir.joinpath("main.tf").exists()
    assert module_dir.joinpath("outputs.tf").exists()
    assert module_dir.joinpath("variables.tf").exists()
    return module_dir


@pytest.fixture(scope="session")
def examples_dir() -> pathlib.Path:
    """Return the Path of the examples directory."""
    examples_dir = pathlib.Path(__file__).parent.parent.parent.joinpath("examples").resolve()
    assert examples_dir.exists()
    assert examples_dir.is_dir()
    return examples_dir


@pytest.fixture(scope="session")
def fixture_dir(
    tmp_path_factory: pytest.TempPathFactory,
    backend_tf_builder: Callable[..., None],
    common_fixture_dir_ignores: Callable[[Any, list[str]], set[str]],
    root_module_dir: pathlib.Path,
    template_module_dir: pathlib.Path,
    stateless_module_dir: pathlib.Path,
    examples_dir: pathlib.Path,
) -> Callable[[str, str], pathlib.Path]:
    """Return a builder that makes a copy of the example with modified backend and module sources."""
    root_module_pattern = re.compile(
        pattern=r'source\s*=\s*"(?:(?:registry.(?:opentofu|terraform).io/)?(memes|f5devcentral)/f5-bigip-ha/google|(?:git::)?https://github\.com/(?:memes|f5devcentral)/terraform-google-f5-bigip-ha/?(?:\?ref=.*)?)"\B(?:\s*version\s*=\s*".*"\B)?',
        flags=re.MULTILINE,
    )
    template_module_pattern = re.compile(
        pattern=r'source\s*=\s*"(?:(?:registry.(?:opentofu|terraform).io/)?(memes|f5devcentral)/f5-bigip-ha/google//modules/template|(?:git::)?https://github\.com/(?:memes|f5devcentral)/terraform-google-f5-bigip-ha//modules/template/?(?:\?ref=.*)?)"\B(?:\s*version\s*=\s*".*"\B)?',
        flags=re.MULTILINE,
    )
    stateless_module_pattern = re.compile(
        pattern=r'source\s*=\s*"(?:(?:registry.(?:opentofu|terraform).io/)?(memes|f5devcentral)/f5-bigip-ha/google//modules/stateless|(?:git::)?https://github\.com/(?:memes|f5devcentral)/terraform-google-f5-bigip-ha//modules/stateless/?(?:\?ref=.*)?)"\B(?:\s*version\s*=\s*".*"\B)?',
        flags=re.MULTILINE,
    )

    def _builder(name: str, example_name: str) -> pathlib.Path:
        fixture_dir = tmp_path_factory.mktemp(name)
        source_dir = examples_dir.joinpath(example_name).resolve()
        assert source_dir.exists()
        assert source_dir.is_dir()
        shutil.copytree(
            src=source_dir,
            dst=fixture_dir,
            dirs_exist_ok=True,
            ignore=common_fixture_dir_ignores,
        )
        backend_tf_builder(
            fixture_dir=fixture_dir,
            name=name,
        )
        main_tf = fixture_dir.joinpath("main.tf").resolve()
        assert main_tf.exists()
        assert main_tf.is_file()
        with main_tf.open(mode="r+", encoding="utf-8") as f:
            original = f.read()
            modified = re.sub(
                pattern=root_module_pattern,
                repl=f'source = "{root_module_dir!s}/"',
                string=re.sub(
                    pattern=template_module_pattern,
                    repl=f'source = "{template_module_dir!s}/"',
                    string=re.sub(
                        pattern=stateless_module_pattern,
                        repl=f'source = "{stateless_module_dir!s}/"',
                        string=original,
                    ),
                ),
            )
            f.seek(0)
            f.write(modified)
            f.truncate()

        return fixture_dir

    return _builder


@pytest.fixture(scope="session")
def region_backend_services_client() -> compute_v1.RegionBackendServicesClient:
    """Return a reusable Compute Engine v1 Region Backend Services API client."""
    return compute_v1.RegionBackendServicesClient()


@pytest.fixture(scope="session")
def wait_for_backend_service_healthy(
    region_backend_services_client: compute_v1.RegionBackendServicesClient,
) -> Callable[[str, int | None, timedelta | None], None]:
    """Return a function that will wait until at least one instance in the regional backend service is healthy."""

    def _ready(self_link: str, minimum_healthy_count: int) -> bool:
        assert self_link
        match = re.search(DEFAULT_BACKEND_SERVICE_SELF_LINK_PATTERN, self_link)
        assert match
        project, region, name = match.groups()
        results: list[str] = []
        try:
            backend_service = region_backend_services_client.get(
                request=compute_v1.GetRegionBackendServiceRequest(
                    project=project,
                    region=region,
                    backend_service=name,
                ),
            )
            for backend in backend_service.backends:
                result = region_backend_services_client.get_health(
                    request=compute_v1.GetHealthRegionBackendServiceRequest(
                        project=project,
                        region=region,
                        backend_service=name,
                        resource_group_reference_resource=compute_v1.ResourceGroupReference(
                            group=backend.group,  # f"projects/{project}/regions/{region}/instanceGroups/{name}",
                        ),
                    ),
                )
                results.extend([status.health_state for status in result.health_status])
        except exceptions.NotFound:
            return False
        return Counter(results)["HEALTHY"] >= minimum_healthy_count

    def _wait(
        self_link: str,
        minimum_healthy_count: int | None = None,
        timeout: timedelta | None = None,
    ) -> None:
        if minimum_healthy_count is None:
            minimum_healthy_count = 1
        timeout_ts = datetime.now(UTC) + (timeout if timeout is not None else DEFAULT_WAIT_FOR_TIMEOUT)
        while not _ready(self_link=self_link, minimum_healthy_count=minimum_healthy_count):
            if datetime.now(UTC) > timeout_ts:
                raise TimeoutError
            time.sleep(10)

    return _wait
