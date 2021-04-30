from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='east_asian_spacing',
    version='1.0.0',
    description='East Asian Contextual Spacing Build Tools',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kojiishi/east_asian_spacing',
    packages=find_packages(where='.'),
    install_requires=['fonttools[woff]>=4.13.0'],
)
