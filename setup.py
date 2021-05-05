from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

# Get the long description from the README file
long_description = (here / 'README.md').read_text(encoding='utf-8')

setup(
    name='east_asian_spacing',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    description='East Asian Contextual Spacing Build Tools',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/kojiishi/east_asian_spacing',
    packages=find_packages(where='.'),
    install_requires=['fonttools[woff]>=4.13.0'],
    entry_points={
        'console_scripts': [
            'east-asian-spacing=east_asian_spacing.__main__:main',
        ]
    }
)