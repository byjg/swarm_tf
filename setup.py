import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="swarm_tf",
    version="0.1.0",
    scripts=["scripts/terrascript", "scripts/connect_to_manager"],
    author="Joao Gilberto Magalhaes",
    author_email="joao@byjg.com.br",
    description="Create a Swarm Cluster on Digital Ocean using Terraform Wrapped by Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/byjg/swarm_tf",
    packages=[
        'swarm_tf',
        'swarm_tf.common',
        'swarm_tf.managers',
        'swarm_tf.workers',
    ],
    package_dir={
        'swarm_tf': 'src/swarm_tf',
        'swarm_tf.common': 'src/swarm_tf/common',
        'swarm_tf.managers': 'src/swarm_tf/managers',
        'swarm_tf.workers': 'src/swarm_tf/workers',
    },
    package_data={
        'swarm_tf.common': ['scripts/*.sh'],
        'swarm_tf.managers': ['scripts/*.sh', 'scripts/*.yml', 'scripts/certs/*'],
        'swarm_tf.workers': ['scripts/*.sh'],
    },
    include_package_data=True,
    license="MIT",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'terraobject==0.0.1'
    ],
    dependency_links=['git://github.com/mjuenema/python-terrascript.git@develop#egg=terrascript']
)
