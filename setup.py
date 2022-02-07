#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = [
    "cachetools==5.0.0",
    "fastapi==0.73.0",
    "pydantic==1.9.0",
    "requests==2.27.1",
    "urllib3==1.26.8",
    "uvicorn==0.17.1",
]

setup(
    author="tribe29 GmbH",
    author_email="feedback@checkmk.com",
    python_requires=">=3.10",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.10",
    ],
    description="Checkmk node and cluster collectors to monitor Kubernetes clusters.",
    entry_points={
        "console_scripts": [
            "checkmk-cluster-collector=checkmk_kube_agent.api:main",
            (
                "checkmk-container-metrics-collector"
                "=checkmk_kube_agent.send_metrics:main_container_metrics"
            ),
            (
                "checkmk-machine-sections-collector"
                "=checkmk_kube_agent.send_metrics:main_machine_sections"
            ),
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
    version="0.1.0",
    zip_safe=False,
)
