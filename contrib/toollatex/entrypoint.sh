#!/usr/bin/env bash

mergerfs -o threads=0,xattr=passthrough,async_read=false,symlinkify=false,posix_acl=true,use_ino,cache.files=off,dropcacheonclose=true,allow_other,category.create=mfs "${CV_CODE}:/_" "${CV_WORKDIR}"
cd "${CV_WORKDIR}" || exit 1;
sudo --user=notroot --group=notroot "$@"
