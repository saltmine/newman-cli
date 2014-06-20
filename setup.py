"""
Install instructions for newman package
"""
from setuptools import setup, find_packages

print find_packages()

setup(
    name='newman',
    version='1.2.1',
    author='Keep Dev Team',
    author_email='opensource@keep.com',
    packages=find_packages(),
    include_package_data=True,
    url='http://keep.com',
    license="License :: OSI Approved :: MIT License",
    description='lightweight CLI creator for python functions',
    long_description=open('README').read(),
    install_requires=open('pip_requirements.txt').readlines(),
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX',
    ],
)
