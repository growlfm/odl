import setuptools

setuptools.setup(
    name='OpenDownloads',
    version='0.0.1',
    description='Open Downloads',
    packages=setuptools.find_packages(),
    package_data={
        'odl': [
            'odl/data/datacenters.csv',
            'odl/data/user-agents.json',
        ]
    },
    scripts=['odl/bin/odl'],
    entry_points={'console_scripts': [
        'odl = odl.cmdline:execute',
    ]},
    include_package_data=True,
    install_requires=[
        'apache-beam==2.41.0', 'numpy==1.22.4', 'ipaddress', 'arrow',
        'udatetime', 'pytricia==1.0.2', 'fastavro==1.6.1', 'boto3==1.24.77',
        'pandas==1.5.0'
    ])
