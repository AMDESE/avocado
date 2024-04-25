# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright: Red Hat Inc. 2021
# Authors: Willian Rampazzo <willianr@redhat.com>
import json

from avocado.core.dependencies.dependency import Dependency
from avocado.core.exceptions import JobBaseException
from avocado.core.plugin_interfaces import JobPre, PreTest


class DependencyResolverError(JobBaseException):
    """
    Error raised when issue occurred during dependency file resolution.
    """


class DependencyResolver(PreTest):
    """Implements the dependency pre tests plugin.

    It will create pre-test tasks for managing dependencies based on the
    `:avocado: dependency=` definition inside the test’s docstring.

    """

    name = "dependency"
    description = "Dependency resolver for tests with dependencies"
    is_cacheable = True

    @staticmethod
    def pre_test_runnables(test_runnable, suite_config=None):  # pylint: disable=W0221
        if not test_runnable.dependencies:
            return []
        dependency_runnables = []
        unique_dependencies = list(dict.fromkeys(test_runnable.dependencies))
        for dependency in unique_dependencies:
            dependency_runnables.append(dependency.to_runnable(test_runnable.config))
        return dependency_runnables


class SuiteDependency(JobPre):
    name = "suite-dependency"
    description = "Applies a set of dependencies to every test within the suite"

    def pre(self, job):
        for suite in job.test_suites:
            dependency_file_path = suite.config.get("job.run.dependency")
            if dependency_file_path:
                try:
                    with open(
                        dependency_file_path, encoding="utf-8"
                    ) as dependency_file:
                        try:
                            dependencies_dict = json.load(dependency_file)
                        except json.JSONDecodeError as e:
                            raise DependencyResolverError(
                                f"Issue with parsing dependency file at {dependency_file_path}: {e}"
                            )
                except FileNotFoundError as e:
                    raise DependencyResolverError(
                        f"Dependency file not found at {dependency_file_path}: {e}"
                    )
                dependencies = []
                for dependency in dependencies_dict:
                    dependencies.append(Dependency.from_dictionary(dependency))
                for runnable in suite.tests:
                    dependencies.extend(runnable.dependencies)
                    runnable.dependencies = dependencies
