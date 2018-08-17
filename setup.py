import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="imgdupes",
    version="1.0",
    author="Jesús Jiménez",
    author_email="jesjimenez@gmail.com",
    description="Image duplicate finder that ignores metadata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jesjimher/imgdupes",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
)
