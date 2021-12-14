#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = []

setup(
    author="tribe29 GmbH",
    author_email="feedback@checkmk.com",
    python_requires=">=3.9",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.9",
    ],
    description="Checkmk node and cluster collectors to monitor Kubernetes clusters.",
    entry_points={
        "console_scripts": [
            "checkmk-cluster-collector=checkmk_kube_agent.checkmk_kube_agent:main",
            "checkmk-node-collector=checkmk_kube_agent.checkmk_kube_agent:main",
        ],
    },
    install_requires=requirements,
    license="GNU General Public License v2",
    long_description=readme,
    include_package_data=True,
    keywords="checkmk_kube_agent",
    name="checkmk_kube_agent",
    packages=find_packages("src"),
    package_dir={"": "src"},
    url="https://github.com/tribe29/checkmk_kube_agent",
    version="2.1.0i1",
    zip_safe=False,
)
