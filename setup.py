#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

requirements = [
    "cachetools==5.0.0",
    "fastapi==0.70.1",
    "pydantic==1.8.2",
    "requests==2.26.0",
    "urllib3==1.26.7",
    "uvicorn==0.16.0",
]

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
            "checkmk-cluster-collector=checkmk_kube_agent.api:main",
            "checkmk-node-collector=checkmk_kube_agent.send_metrics:main",
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
