import os
from terrascript.digitalocean.r import digitalocean_droplet, digitalocean_volume
from terrascript.digitalocean.d import digitalocean_volume as data_digitalocean_volume
from terrascript.template.d import *
from terrascript import connection, function, provisioner, output


class Worker:

    def __init__(self, o, variables):
        """type o: Terraobject"""
        """type variables: Variables"""
        self.o = o
        self.variables = variables
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

    def node(self, number, volume=None):
        number_str = "{0:02d}".format(number)

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

        if not(volume is None):
            tmpl_attach = template_file("attach_volume_{}_{}".format(self.variables.name, number_str),
                                        template=function.file(os.path.join(self.curdir, "scripts", "attach_volume.sh")),
                                        vars={
                                            "volume_name": "/dev/disk/by-id/scsi-0DO_Volume_sdb",
                                            "mount": "/data"
                                        })
            self.o.terrascript.add(tmpl_attach)
            prov.append(provisioner("file",
                                    content=tmpl_attach.rendered,
                                    destination="/tmp/attach_volume.sh"))

            prov.append(provisioner("remote-exec",
                                    inline=[
                                      "chmod +x /tmp/attach_volume.sh",
                                      "/tmp/attach_volume.sh"]))

        droplet_worker = digitalocean_droplet(self.variables.name + "_" + number_str,
                                              ssh_keys=self.variables.ssh_keys,
                                              image=self.variables.image,
                                              region=self.variables.region,
                                              size=self.variables.size,
                                              private_networking="true",
                                              backups=self.variables.backups,
                                              ipv6="false",
                                              user_data=self.variables.user_data,
                                              tags=self.variables.tags,
                                              count=1,
                                              name="{}-{}.{}.{}".format(self.variables.name, number_str,
                                                                        self.variables.region,
                                                                        self.variables.domain),
                                              connection=conn,
                                              volume_ids=[volume.id] if not(volume is None) else None,
                                              provisioner=prov)

        self.o.shared["worker_nodes"].append(droplet_worker)
        self.o.terrascript.add(droplet_worker)
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_id",
                                      value=droplet_worker.id,
                                      description="The worker node id"))
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_ipv4_public",
                                      value=droplet_worker.ipv4_address,
                                      description="The worker nodes public ipv4 address"))
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_ipv4_private",
                                      value=droplet_worker.ipv4_address_private,
                                      description="The worker nodes private ipv4 address"))

    def create_workers(self):
        self.prepare_template()
        len_volumes = 0 if self.variables.persistent_volumes is None else len(self.variables.persistent_volumes)
        for i in range(0, len_volumes):
            self.node(i+1, volume=self.variables.persistent_volumes[i].create())
        for i in range(len_volumes, self.variables.total_instances):
            self.node(i+1)


class VolumeClaim:
    def __init__(self, o, region, name, size=None):
        self.o = o
        self.region = region
        self.name = name
        self.size = size

    def create(self):
        if self.size is None:
            return self.__existent(self.name)
        else:
            return self.__new(self.name, self.size)

    def __existent(self, name):
        volume = data_digitalocean_volume(name, name=name, region=self.region)
        self.o.terrascript.add(volume)
        return volume

    def __new(self, name, size):
        volume = digitalocean_volume(name,
                                     region=self.region,
                                     name=name,
                                     size=size,
                                     initial_filesystem_type="ext4",
                                     description="Swarm Volume {} of {} gb".format(name, size))
        self.o.terrascript.add(volume)
        return volume


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

    # Persistent volume to attach to First Droplet (Database)"
    persistent_volumes = None
