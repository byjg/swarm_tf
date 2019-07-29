#!/usr/bin/env bash

mkdir -p ${mount}
mount -o discard,defaults ${volume_name} ${mount}
echo ${volume_name} ${mount} ext4 defaults,nofail,discard 0 0 | sudo tee -a /etc/fstab
