from setuptools import find_packages, setup


with open("README.md") as f:
    long_description = f.read()


setup(
    name="hkfireplace",
    url="https://github.com/willbarton/hkfireplace",
    author="Will Barton",
    license="MIT",
    version="1.0.0",
    description='Raspberry Pi HomeKit NeoPixel "fireplace"',
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    py_modules=["hkfireplace"],
    install_requires=[
        "adafruit-circuitpython-neopixel",
        "adafruit-circuitpython-fancyled",
        "colour",
        "HAP-python>=3.0.0",
        "RPi.GPIO",
    ],
    extras_require={
        "testing": [
            "flake8",
        ],
    },
    # test_suite="hkfireplace.tests",
    entry_points={
        "console_scripts": [
            "hkfireplace = hkfireplace:main",
        ]
    },
)
