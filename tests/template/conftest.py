"""Fixtures for template module test cases."""

import base64
import gzip
import pathlib
from collections.abc import Callable

import jinja2
import pytest

from tests import cloud_config_asserter


@pytest.fixture(scope="session")
def templates_dir() -> pathlib.Path:
    """Return a Path to the directory containing Jinja2 templates for stateless test cases."""
    return pathlib.Path(__file__).parent.joinpath("templates").resolve()


@pytest.fixture(scope="session")
def files_dir() -> pathlib.Path:
    """Return a Path to the directory containing static files in stateless module."""
    files_dir = pathlib.Path(__file__).parent.parent.parent.joinpath("modules/template/files").resolve()
    assert files_dir.exists()
    assert files_dir.is_dir()
    assert files_dir.joinpath("onboard.sh").exists()
    return files_dir


@pytest.fixture(scope="session")
def cloud_init_builder(
    templates_dir: pathlib.Path,
    files_dir: pathlib.Path,
) -> Callable[[str, dict[str, str] | None], str]:
    """Return a cloud-init YAML builder from Jinja template and static files."""
    onboard_script = base64.b64encode(
        gzip.compress(
            files_dir.joinpath("onboard.sh").read_bytes(),
        ),
    ).decode("utf-8")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(templates_dir),
        autoescape=False,
    )

    def _builder(
        template_file_name: str,
        onboard_env: dict[str, str] | None = None,
    ) -> str:
        """Create a validated cloud-config YAML for with onboarding script, and return as a string."""
        template = env.get_template(template_file_name)
        cloud_config = template.render(
            onboard_script=onboard_script,
            onboard_env=onboard_env,
        )
        assert cloud_config
        cloud_config_asserter(cloud_config)
        return cloud_config

    return _builder
