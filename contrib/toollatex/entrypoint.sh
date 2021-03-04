#!/usr/bin/env bash

mergerfs -o threads=16,xattr=passthrough,async_read=false,symlinkify=true,posix_acl=true,use_ino,cache.files=off,dropcacheonclose=true,allow_other,category.create=mfs "${CV_CODE}:/_" "${CV_WORKDIR}"
cd "${CV_WORKDIR}" || exit 1;
sudo --user notroot \
	 --group $(cat /etc/group | grep ":${HOST_USER_GID}:" | head -1 | cut --delimiter=":" --fields=1) \
	 "$@"
