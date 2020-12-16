import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="jpegdupes",
    version="2.1.0",
    author="Jesús Jiménez",
    author_email="jesjimenez@gmail.com",
    description="Image duplicate finder that ignores JPEG metadata",
    long_description=long_description,
    long_description_content_type="text/markdown",
    keywords="image duplicate finder metadata jpeg",
    url="https://github.com/jesjimher/imgdupes",
    packages=setuptools.find_packages(),
    python_requires=">=3",
    install_requires=[
        "texttable",
        "jpegtran-cffi>0.5",
        "Pillow",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
    #    scripts=['jpegdupes/jpegdupes.py']
    entry_points={"console_scripts": ["jpegdupes=jpegdupes.jpegdupes:main"]},
)
