import os
from terrascript.template.d import *
from terrascript import connection, function, provisioner, output

from swarm_tf.common import Node


class Worker(Node):

    def __init__(self, o, variables):
        super().__init__(o, variables)
        self.curdir = os.path.dirname(os.path.abspath(__file__))
        if not("worker_nodes" in o.shared):
            self.o.shared["worker_nodes"] = []

    def prepare_template(self):
        if "join_cluster_as_worker" in self.o.shared:
            return

        tmpl = template_file("join_cluster_as_worker",
                             template=function.file(os.path.join(self.curdir, "scripts", "join.sh")),
                             vars={
                                  "docker_cmd": self.variables.docker_cmd,
                                  "availability": self.variables.availability,
                                  "manager_private_ip": self.variables.manager_private_ip
                             })
        self.o.shared["join_cluster_as_worker"] = tmpl
        self.o.terrascript.add(tmpl)

    def node(self, number):
        conn = connection(type="ssh",
                          user=self.variables.provision_user,
                          private_key=function.file(self.variables.provision_ssh_key),
                          timeout=self.variables.connection_timeout)
        prov = list()
        prov.append(provisioner("file",
                                content=self.o.shared["join_cluster_as_worker"].rendered,
                                destination="/tmp/join_cluster_as_worker.sh"))

        prov.append(provisioner("remote-exec",
                                inline=[
                                  "chmod +x /tmp/join_cluster_as_worker.sh",
                                  "/tmp/join_cluster_as_worker.sh {}".format(self.variables.join_token)]))

        prov.append(provisioner("remote-exec",
                                when="destroy",
                                inline=[
                                  "docker swarm leave",
                                ],
                                on_failure="continue"))

        return self.create_droplet(droplet_type="manager", number=number, conn=conn, prov=prov)

    def create_workers(self):
        self.prepare_template()
        for i in range(0, self.variables.total_instances):
            self.node(i+1)


class WorkerVariables:

    # Timeout for connection to servers
    connection_timeout = "2m"

    # "Domain name used in droplet hostnames, e.g example.com"
    domain = None

    # Join token for the nodes"
    join_token = None

    # Private ip adress of a manager node, used to have a node join the existing cluster
    manager_private_ip = None

    # A list of SSH IDs or fingerprints to enable in the format [12345, 123456] that are added to worker nodes"
    ssh_keys = []

    # File path to SSH private key used to access the provisioned nodes. Ensure this key is listed in the manager
    # and work ssh keys list"
    provision_ssh_key = "~/.ssh/id_rsa"

    # User used to log in to the droplets via ssh for issueing Docker commands"
    provision_user = "root"

    # Datacenter region in which the cluster will be created"
    region = "nyc3"

    # Total number of instances of this type in cluster"
    total_instances = 1

    # Operating system for the worker nodes"
    image = "ubuntu-18-04-x64"

    # Droplet size of worker nodes
    size = "s-1vcpu-1gb"

    # Enable backups of the worker nodes"
    backups = "false"

    # Prefix for name of worker nodes"
    name = "worker"

    # "User data content for worker nodes. Use this for installing a configuration management tool, such as
    # Puppet or installing Docker"
    user_data = ""

    # Docker command
    docker_cmd = "sudo docker"

    # List of DigitalOcean tag ids
    tags = []

    # Availability of the node ('active'|'pause'|'drain')"
    availability = "active"

    # Persistent volume to attach to the Droplets (Array, one volume per droplet)"
    persistent_volumes = None
