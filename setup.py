from setuptools import setup, find_packages

setup(
    name='makediscbot',
    version='0.1.4',
    description='A CLI tool to generate a discord bot template',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'makediscbot=makebot.cli:main',
        ],
    },
)
