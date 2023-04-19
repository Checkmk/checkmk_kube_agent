#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

import re
import subprocess
from typing import Dict, Mapping, Sequence, Tuple


def _parse_run_target_args(line: str) -> Sequence[str]:
    return line[line.find("(") + 1 : line.find(")")].split(", ")


def _parse_variables(line: str) -> Tuple[str, str]:
    name, value = line.replace("def ", "").split(" = ")
    if match := re.search('sh\\(.*(".*").*\\)', value):
        value = f"$(%s)" % match.group(1).replace('"', "")
    return name, value


def _substitute_values(
    arguments: Mapping[str, str],
    variables: Mapping[str, str],
) -> Mapping[str, str]:
    substituted_args = {}
    for argument, value in arguments.items():
        for variable, definition in variables.items():
            value = value.replace("${%s}" % variable, definition)
        value = value.replace('entrypoint="', 'entrypoint=/bin/ash"')
        substituted_args[argument] = value

    return substituted_args


def main() -> None:
    repo_dir = (
        subprocess.check_output("git rev-parse --show-toplevel", shell=True)
        .decode("utf-8")
        .strip()
    )
    function_calls = []
    function_definition = None
    variables = {}
    with open(f"{repo_dir}/ci/jenkins/on-gerrit-commit.groovy", "r") as f:
        for line in f.readlines():
            stripped_line = line.strip()
            if stripped_line.startswith("run_target"):
                function_calls.append(_parse_run_target_args(line))
            elif stripped_line.startswith("def run_target"):
                function_definition = _parse_run_target_args(line)
            elif stripped_line.startswith("def") and "=" in stripped_line:
                name, value = _parse_variables(stripped_line)
                variables[name] = value

    if not function_definition:
        raise SystemExit("Unable to find function definition for function 'run_target'")

    for call in function_calls:
        function_call = _substitute_values(
            dict(zip(function_definition, call)),
            variables,
        )
        print(f'{function_call["target"]},{function_call["docker_args"]}')


if __name__ == "__main__":
    main()
