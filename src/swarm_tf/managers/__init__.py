import os
from terrascript.template.d import *
from terrascript import connection, function, provisioner, output, resource, data
from swarm_tf.common import Node


class Manager(Node):

    def __init__(self, o, variables):
        super().__init__(o, variables)
        self.curdir = os.path.dirname(os.path.abspath(__file__))
        self.o.shared["manager_nodes"] = []

    def prepare_template(self):
        tmpl = template_file("provision_first_manager",
                             template=function.file(os.path.join(self.curdir, "scripts", "provision-first-manager.sh")),
                             vars={
                                  "docker_cmd": self.variables.docker_cmd,
                                  "availability": self.variables.availability
                             })

        self.o.shared["provision_first_manager"]=tmpl
        self.o.terrascript.add(tmpl)

        tmpl3 = template_file("provision_manager",
                              template=function.file(os.path.join(self.curdir, "scripts", "provision-manager.sh")),
                              vars={
                                "docker_cmd": self.variables.docker_cmd,
                                "availability": self.variables.availability,
                              })

        self.o.shared["provision_manager"] = tmpl3
        self.o.terrascript.add(tmpl3)

    def node(self, number):
        conn = connection(type="ssh",
                          user=self.variables.provision_user,
                          private_key=function.file(self.variables.provision_ssh_key),
                          timeout=self.variables.connection_timeout)

        prov1 = provisioner("file",
                            content=self.o.shared["provision_first_manager"].rendered,
                            destination="/tmp/provision-first-manager.sh")

        prov3 = provisioner("remote-exec",
                            inline=[
                              "chmod +x /tmp/provision-first-manager.sh",
                              "/tmp/provision-first-manager.sh ${self.ipv4_address_private}",
                            ])

        prov4 = provisioner("remote-exec",
                            when="destroy",
                            inline=[
                              "timeout 25 docker swarm leave --force",
                            ],
                            on_failure="continue")

        prov = [prov4]
        if number == 1:
            prov = [prov1, prov3] + prov

        if not(self.variables.remote_api_ca is None or
           self.variables.remote_api_certificate is None or
           self.variables.remote_api_key is None):
            home_ca = "~/.docker"
            prov.append(provisioner("remote-exec",
                                inline=[
                                  "mkdir -p " + home_ca,
                                ]))
            prov.append(provisioner("file",
                                    content=self.variables.remote_api_ca,
                                    destination=home_ca + "/ca.pem"))
            prov.append(provisioner("file",
                                    content=self.variables.remote_api_certificate,
                                    destination=home_ca + "/server-cert.pem"))
            prov.append(provisioner("file",
                                    content=self.variables.remote_api_key,
                                    destination=home_ca + "/server-key.pem"))
            prov.append(provisioner("file",
                                    content=os.path.join(self.curdir, "scripts", "certs", "default.sh"),
                                    destination=home_ca + "install_certificates.sh"))
            prov.append(provisioner("remote-exec",
                                    inline=[
                                        "chmod +x " + home_ca + "/install_certificates.sh",
                                        home_ca + "/install_certificates.sh",
                                    ]))

        return self.create_droplet(droplet_type="manager", number=number, conn=conn, prov=prov)

    def create_managers(self):
        self.prepare_template()
        for i in range(self.variables.total_instances):
            droplet_manager = self.node(i+1)

            if i == 0:
                swarm_tokens = data("external", "swarm_tokens",
                                    program=["bash", self.curdir + "/scripts/get-swarm-join-tokens.sh"],
                                    query={
                                        "host": droplet_manager.ipv4_address,
                                        "user": self.variables.provision_user,
                                        "private_key": self.variables.provision_ssh_key
                                    })
                self.o.shared["swarm_tokens"] = swarm_tokens
                self.o.terrascript.add(swarm_tokens)

            prov = list()
            prov.append(provisioner("file",
                                    content=self.o.shared["provision_manager"].rendered,
                                    destination="/tmp/provision-manager.sh"))

            prov.append(provisioner("remote-exec",
                                    inline=[
                                      "chmod +x /tmp/provision-manager.sh",
                                      "/tmp/provision-manager.sh " + droplet_manager.ipv4_address_private + " " +
                                      function.lookup(self.o.shared["swarm_tokens"].result, "manager", ""),
                                    ]))
            self.o.terrascript.add(resource("null_resource", "bootstrap",
                                            connection=connection(type="ssh",
                                                                  host=droplet_manager.ipv4_address,
                                                                  user=self.variables.provision_user,
                                                                  private_key=function.file(self.variables.provision_ssh_key),
                                                                  timeout=self.variables.connection_timeout),
                                            triggers={
                                                "cluster_instance_ids": droplet_manager.id
                                            },
                                            provisioner=prov))


class ManagerVariables:
    # Timeout for connection to servers"
    connection_timeout = "2m"

    # Domain name used in droplet hostnames, e.g example.com"
    domain = ""

    # A list of SSH IDs or fingerprints to enable in the format [12345, 123456] that are added to manager nodes"
    ssh_keys = []

    # File path to SSH private key used to access the provisioned nodes.
    # Ensure this key is listed in the manager and work ssh keys list"
    provision_ssh_key = "~/.ssh/id_rsa"

    # User used to log in to the droplets via ssh for issueing Docker commands"
    provision_user = "root"

    # Datacenter region in which the cluster will be created"
    region = "nyc3"

    # Total number of managers in cluster"
    total_instances = 1

    # Droplet image used for the manager nodes"
    image = "ubuntu-18-04-x64"

    # Droplet size of manager nodes"
    size = "s-1vcpu-1gb"

    # Prefix for name of manager nodes"
    name = "manager"

    # Enable DigitalOcean droplet backups"
    backups = "false"

    # User data content for manager nodes"
    user_data = ""

    # Docker command"
    docker_cmd = "sudo docker"

    # List of DigitalOcean tag ids"
    tags = []

    # Availability of the node ('active'|'pause'|'drain')"
    availability = "active"

    remote_api_ca = None

    remote_api_key = None

    remote_api_certificate = None

    # Persistent volume to attach to the Droplets (Array, one volume per droplet)"
    persistent_volumes = None

    # Create the Host entries in the domain specified above
    create_dns = False
