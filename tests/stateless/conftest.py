"""Fixtures for stateless module test cases."""

import pathlib
import re
import shutil
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from google.api_core import exceptions
from google.cloud import compute_v1

from tests import skip_destroy_phase
from tests.stateless import DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN

DEFAULT_WAIT_FOR_TIMEOUT = timedelta(seconds=900)


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
def fixture_dir(
    tmp_path_factory: pytest.TempPathFactory,
    backend_tf_builder: Callable[..., None],
    common_fixture_dir_ignores: Callable[[Any, list[str]], set[str]],
    stateless_module_dir: pathlib.Path,
) -> Callable[[str], pathlib.Path]:
    """Return a builder that makes a copy of the stateless module with backend configured appropriately."""

    def _builder(name: str) -> pathlib.Path:
        fixture_dir = tmp_path_factory.mktemp(name)
        shutil.copytree(
            src=stateless_module_dir,
            dst=fixture_dir,
            dirs_exist_ok=True,
            ignore=common_fixture_dir_ignores,
        )
        backend_tf_builder(
            fixture_dir=fixture_dir,
            name=name,
        )
        return fixture_dir

    return _builder


@pytest.fixture(scope="session")
def runtime_init_conf() -> str:
    """Return a runtime-init configuration YAML as string."""
    runtime_init_conf = pathlib.Path(__file__).parent.joinpath("files/runtime-init-conf.yaml").resolve()
    assert runtime_init_conf.exists()
    assert runtime_init_conf.is_file()
    return runtime_init_conf.read_text()


@pytest.fixture(scope="session")
def runtime_init_conf_1nic() -> str:
    """Return a runtime-init configuration YAML for 1-nic deployment as string."""
    runtime_init_conf = pathlib.Path(__file__).parent.joinpath("files/runtime-init-conf-1nic.yaml").resolve()
    assert runtime_init_conf.exists()
    assert runtime_init_conf.is_file()
    return runtime_init_conf.read_text()


@pytest.fixture(scope="session")
def wait_for_instance_group_manager_deleted(
    region_instance_group_managers_client: compute_v1.RegionInstanceGroupManagersClient,
) -> Callable[[str, timedelta | None], None]:
    """Return a function that will wait until the instance group manager no longer exists."""

    def _exists(self_link: str) -> bool:
        assert self_link
        match = re.search(DEFAULT_INSTANCE_GROUP_MANAGER_SELF_LINK_PATTERN, self_link)
        assert match
        project, region, name = match.groups()
        try:
            _ = region_instance_group_managers_client.get(
                request=compute_v1.GetRegionInstanceGroupManagerRequest(
                    project=project,
                    region=region,
                    instance_group_manager=name,
                ),
            )
        except exceptions.NotFound:
            return False
        return True

    def _wait(
        self_link: str,
        timeout: timedelta | None = None,
    ) -> None:
        # Don't wait for destruction if it isn't going to happen
        if skip_destroy_phase():
            return
        timeout_ts = datetime.now(UTC) + (timeout if timeout is not None else DEFAULT_WAIT_FOR_TIMEOUT)
        while _exists(self_link):
            if datetime.now(UTC) > timeout_ts:
                raise TimeoutError
            time.sleep(60)

    return _wait
