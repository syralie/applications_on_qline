"""
Setup script for QToken QLine OSS package
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="qtoken-qline-oss",
    version="1.0.0",
    author="QToken Team",
    description="Asynchronous quantum token exchange protocol implementation (Open Source)",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Physics",
        "Topic :: Security :: Cryptography",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "qtoken-alice=src.alice.alice:main",
            "qtoken-bob=src.bob.bob:main",
            "qtoken-alice-agent=src.agents.alice_agent:main",
            "qtoken-bob-agent=src.agents.bob_agent:main",
        ],
    },
    include_package_data=True,
    zip_safe=False,
)
