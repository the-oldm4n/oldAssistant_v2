from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mygui",
    version="1.0.10",
    packages=find_packages(),
    package_data={
        "mygui": [
            "resources/icons/*.svg",
            "resources/icons/*.png",
        ],
    },
    include_package_data=True,
    install_requires=[
        "PySide6>=6.5.0",
    ],
    author="Andrey",
    description="Библиотека кастомных виджетов на PySide6",
    python_requires=">=3.9",
    long_description=long_description,
    long_description_content_type="text/markdown",
)