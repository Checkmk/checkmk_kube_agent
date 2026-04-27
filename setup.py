#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

from src import checkmk_kube_agent

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = [
    "cachetools==7.0.6",
    "fastapi==0.136.1",
    "pydantic==2.13.3",
    "requests==2.33.1",
    "urllib3==2.6.3",
    "uvicorn==0.46.0",
    "gunicorn==25.3.0",
]

setup(
    author="Checkmk GmbH",
    author_email="feedback@checkmk.com",
    python_requires=">=3.14",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.14",
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
    url="https://github.com/checkmk/checkmk_kube_agent",
    version=checkmk_kube_agent.__version__,
    zip_safe=False,
)
