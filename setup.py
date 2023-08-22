from setuptools import setup, find_packages
import os

with open('README.md') as readme_file:
    README = readme_file.read()

setup_args = {
    'name': 'dfbar',
    'version': os.environ['BUILD_VERSION'],
    'description': 'Dockerfile Build and Run',
    'long_description_content_type': 'text/markdown',
    'long_description': README,
    'license': 'MIT',
    'packages': find_packages(
        where='src',
        include=[
            'dfbar',
            'dfbar.*'
        ]
    ),
    'author': 'Jesse Reichman',
    'keywords': [ 'Dockerfile', 'Build', 'Run' ],
    'url': 'https://github.com/archmachina/dfbar',
    'download_url': 'https://pypi.org/project/dfbar/',
    'entry_points': {
        'console_scripts': [
            'dfbar = dfbar:main'
        ]
    },
    'package_dir': {
        '': 'src'
    }
}

install_requires = []

if __name__ == '__main__':
    setup(**setup_args, install_requires=install_requires, include_package_data=True)
