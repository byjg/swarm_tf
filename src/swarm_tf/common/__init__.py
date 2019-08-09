import os
from terrascript import function, output, provisioner
from terrascript.digitalocean.r import digitalocean_droplet, digitalocean_volume, digitalocean_tag, \
    digitalocean_firewall
from terrascript.digitalocean.d import digitalocean_volume as data_digitalocean_volume
from terrascript.template.d import template_file


class Node:
    def __init__(self, o, variables):
        """type o: Terraobject"""
        """type variables: Variables"""
        self.o = o
        self.variables = variables
        if "__variables" not in o.shared:
            o.shared["__variables"] = []
        o.shared["__variables"] += [{"type": variables.name, "instances": variables.total_instances}]

    def fmt_number(self, number):
        return "{0:02d}".format(number)

    def get_tags_id(self):
        tag_list = []
        for tag in self.variables.tags:
            if "tags:" + tag not in self.o.shared:
                tag_obj = digitalocean_tag(tag, name=tag)
                self.o.terrascript.add(tag_obj)
                self.o.shared["tags:" + tag] = tag_obj
            tag_list += [self.o.shared["tags:" + tag].id]
        return tag_list

    def create_droplet(self, droplet_type, number, conn, prov):
        number_str = self.fmt_number(number)

        volume = None
        if self.variables.persistent_volumes is not None and number <= len(self.variables.persistent_volumes):
            volume = self.variables.persistent_volumes[number-1].create()

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

        droplet = digitalocean_droplet(self.variables.name + "_" + number_str,
                                       ssh_keys=self.variables.ssh_keys,
                                       image=self.variables.image,
                                       region=self.variables.region,
                                       size=self.variables.size,
                                       private_networking="true",
                                       backups=self.variables.backups,
                                       ipv6="false",
                                       user_data=self.variables.user_data,
                                       tags=self.get_tags_id(),
                                       count=1,
                                       name="{}-{}.{}.{}".format(self.variables.name, number_str,
                                                                 self.variables.region,
                                                                 self.variables.domain),
                                       connection=conn,
                                       volume_ids=[volume.id] if not(volume is None) else None,
                                       provisioner=prov)

        self.o.shared[droplet_type + "_nodes"].append(droplet)
        self.o.terrascript.add(droplet)
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_id",
                                      value=droplet.id,
                                      description="The {} node id".format(droplet_type)))
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_ipv4_public",
                                      value=droplet.ipv4_address,
                                      description="The {} nodes public ipv4 address".format(droplet_type)))
        self.o.terrascript.add(output(self.variables.name + "_" + number_str + "_ipv4_private",
                                      value=droplet.ipv4_address_private,
                                      description="The {} nodes private ipv4 address".format(droplet_type)))

        return droplet


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


def get_user_data_script():
    return function.file(os.path.join(os.path.dirname(__file__), "scripts", "install-docker-ce.sh"))


def create_firewall(o, domain, inbound_ports, tag):
    # droplet_ids = []
    # for droplet in o.shared["manager_nodes"] + o.shared["worker_nodes"]:
    #     droplet_ids += [droplet.id]
    inbound_rules = [
        {
            "protocol": "icmp",
            "source_tags": [tag]
        },
        {
            "protocol": "tcp",
            "port_range": "1-65535",
            "source_tags": [tag]
        },
        {
            "protocol": "udp",
            "port_range": "1-65535",
            "source_tags": [tag]
        }
    ]
    for port in inbound_ports:
        rule = {
            "protocol": "tcp",
            "port_range": port,
            "source_addresses": ["0.0.0.0/0", "::/0"]
        }
        inbound_rules += [rule]

    outbound_rules = [
        {
            "protocol": "icmp",
            "destination_addresses": ["0.0.0.0/0", "::/0"],
            "destination_tags": [tag]
        },
        {
            "protocol": "tcp",
            "port_range": "1-65535",
            "destination_addresses": ["0.0.0.0/0", "::/0"],
            "destination_tags": [tag]
        },
        {
            "protocol": "udp",
            "port_range": "1-65535",
            "destination_addresses": ["0.0.0.0/0", "::/0"],
            "destination_tags": [tag]
        }
    ]

    firewall = digitalocean_firewall("firewall",
                                     name="swarm.firewall.for.{}".format(domain),
                                     tags=[tag],
                                     inbound_rule=inbound_rules,
                                     outbound_rule=outbound_rules
                                     )
    o.terrascript.add(firewall)
