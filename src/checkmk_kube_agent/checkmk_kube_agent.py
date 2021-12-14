#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2021 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the
# terms and conditions defined in the file COPYING, which is part of this
# source code package.

"""Hello world: validate CI/CD for `checkmk_kube_agent` package."""


def hello_world() -> bool:
    """hello world
    >>> hello_world()
    Hello world
    True
    """
    print("Hello world")
    return True


def main():
    """hello world main function"""
    hello_world()


if __name__ == "__main__":
    main()
