# Swarm Terraform using Python

This is a python package that wraps the terraform necessary to create a Swarm Cluster at Digital Ocean.
You do not need to know the terraform configuration language (a.k.a HCL), just Python.

However, you'll rely the creation of the resources to Terraform. The best of the two worlds :)

# What this script create?

- Full Docker Swarm cluster
- Manager Node with auto-join
- Worker Node with auto-join
- Create or use an existing volume and attach it automatically to the node
- Custom Digital Ocean tags
- Create a Firewall for the Cluster
- Use existing DNS at Digital Ocean and add address record for each node.
- (@todo soon) Create NFS Server that can be used inside the docker swarm cluster

# Get Started

1 - Add to your project the Swarm_TF:

```bash
pip install swarm_tf=0.2.2
```

2 - Create your Cluster:

```python
import sys
from terraobject import Terraobject
from swarm_tf.workers import WorkerVariables
from swarm_tf.workers import Worker
from swarm_tf.managers import ManagerVariables
from terrascript import provider, function, output
from terrascript.digitalocean.d import digitalocean_ssh_key as data_digitalocean_ssh_key
from swarm_tf.managers import Manager
from swarm_tf.common import VolumeClaim, get_user_data_script, create_firewall
from terrascript.digitalocean.r import *

# Setup
do_token = "DIGITAL OCEAN TOKEN"

# Common
domain = "swarm.example.com"
region = "nyc3"
ssh_key = "~/.ssh/id_rsa"
user_data = get_user_data_script()

o = Terraobject()

o.terrascript.add(provider("digitalocean", token=do_token))

# ---------------------------------------------
# Get Existing Object at Digital Ocean
# ---------------------------------------------
sshkey = data_digitalocean_ssh_key("mysshkey", name="id_rsa")
o.terrascript.add(sshkey)
o.shared['sshkey'] = sshkey


# ---------------------------------------------
# Creating Swarm Manager
# ---------------------------------------------
managerVar = ManagerVariables()
managerVar.image = "ubuntu-18-04-x64"
managerVar.size = "s-1vcpu-1gb"
managerVar.name = "manager"
managerVar.region = region
managerVar.domain = domain
managerVar.total_instances = 1
managerVar.user_data = user_data
managerVar.tags = ["cluster", "manager"]
managerVar.remote_api_ca = None
managerVar.remote_api_key = None
managerVar.remote_api_certificate = None
managerVar.ssh_keys = [sshkey.id]
managerVar.provision_ssh_key = ssh_key
managerVar.provision_user = "root"
managerVar.connection_timeout = "2m"
managerVar.create_dns = True

manager = Manager(o, managerVar)
manager.create_managers()

# ---------------------------------------------
# Creating Worker Nodes
# ---------------------------------------------
workerVar = WorkerVariables()
workerVar.image = "ubuntu-18-04-x64"
workerVar.size = "s-1vcpu-1gb"
workerVar.name = "worker"
workerVar.region = region
workerVar.domain = domain
workerVar.total_instances = 2
workerVar.user_data = user_data
workerVar.tags = ["cluster", "worker"]
workerVar.manager_private_ip = o.shared["manager_nodes"][0].ipv4_address_private
workerVar.join_token = function.lookup(o.shared["swarm_tokens"].result, "worker", "")
workerVar.ssh_keys = [sshkey.id]
workerVar.provision_ssh_key = ssh_key
workerVar.provision_user = "root"
workerVar.persistent_volumes = None
workerVar.connection_timeout = "2m"
workerVar.create_dns = True

worker = Worker(o, workerVar)
worker.create_workers()

# ---------------------------------------------
# Creating Persistent Nodes
# ---------------------------------------------
workerVar.name = "persistent"
workerVar.persistent_volumes = [VolumeClaim(o, region, "volume-nyc3-01")]
workerVar.total_instances = 1
persistent_worker = Worker(o, workerVar)
persistent_worker.create_workers()

# ---------------------------------------------
# Creating Firewall
# ---------------------------------------------
create_firewall(o, domain=domain, inbound_ports=[22, 80, 443, 9000], tag="cluster")


# ---------------------------------------------
# Outputs
# ---------------------------------------------
o.terrascript.add(output("manager_ips",
                         value=[value.ipv4_address for value in o.shared["manager_nodes"]],
                         description="The manager nodes public ipv4 addresses"))

o.terrascript.add(output("manager_ips_private",
                         value=[value.ipv4_address_private for value in o.shared["manager_nodes"]],
                         description="The manager nodes private ipv4 addresses"))

o.terrascript.add(output("worker_ips",
                         value=[value.ipv4_address for value in o.shared["worker_nodes"]],
                         description="The worker nodes public ipv4 addresses"))

o.terrascript.add(output("worker_ips_private",
                         value=[value.ipv4_address_private for value in o.shared["worker_nodes"]],
                         description="The worker nodes private ipv4 addresses"))

o.terrascript.add(output("manager_token",
                         value=function.lookup(o.shared["swarm_tokens"].result, "manager", ""),
                         description="The Docker Swarm manager join token",
                         sensitive=True))

o.terrascript.add(output("worker_token",
                         value=function.lookup(o.shared["swarm_tokens"].result, "worker", ""),
                         description="The Docker Swarm worker join token",
                         sensitive=True))

o.terrascript.add(output("worker_ids",
                         value=[value.id for value in o.shared["worker_nodes"]]))

o.terrascript.add(output("manager_ids",
                         value=[value.id for value in o.shared["manager_nodes"]]))

if len(sys.argv) == 2 and sys.argv[1] == "label":
    for obj in o.shared["__variables"]:
        for i in range(1, obj["instances"]+1):
            print("docker node update --label-add type={0} {0}_{1:02d}".format(obj["type"], i))
else:
    print(o.terrascript.dump())
```

# Volumes

It is possible to use the `VolumeClaim` class to attach an existent or create a new volume to a droplet. This volume
will be mounted in the host folder `/data`. So you can deploy your stack or service an map to this volume. 

# Terraform Plan & Apply

Instead to run terraform directly you can use the `terrascript` wrapper that will run the python, save the terraform json and then 
execute the terraform action you want. 

For example, to run the terraform plan you can use this:  

```bash
terrascript plan -out my.tfplan
```

and for apply you can use:

```bash
terrascript apply "my.tfplan"
```

Note: Your main script need to named as `main.py` and need to be in the folder your running the `terrascript`

# Deploying Services and Stacks

You can only execute the Deploy on the machine. We provided a script to connect to the Manager, so this way you can
deploy your stacks and services from you local machine. Execute these commands:

```bash
connect_to_manager -c
export DOCKER_HOST=tcp://localhost:2377
```

To disconnect just execute:

```bash
connect_to_manager -d
unset DOCKER_HOST
```


# References:

**swarm_tf** uses the `python_terrascript` code. Refer to the project link to get more information about it:
- https://github.com/mjuenema/python-terrascript/


