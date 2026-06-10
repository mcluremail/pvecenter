from setuptools import setup, find_packages
setup(
    name="pvecenter",
    version="1.0.0",
    packages=find_packages(include=["pve_center", "pve_center.*"]),
    entry_points={"console_scripts": ["pvecenter=pve_center.main:main"]},
)