from setuptools import setup, find_packages

setup(
    name='voice_chat_app',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'PyQt5',
        'sounddevice',
        'numpy',
        'requests',
        'keyboard'
    ],
)