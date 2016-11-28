from distutils.core import setup

setup(
    name='py-helloworld',
    version='1.0',
    install_requires=[
        'mock==1.3.0',
        'requests==2.8.1',
        'six==1.10.0'
    ],
    author='Intel',
    setup_requires=['docutils'],
    license='GPL 3.0',
)
