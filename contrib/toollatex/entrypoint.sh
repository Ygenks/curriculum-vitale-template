#!/usr/bin/env bash

mergerfs -o threads=3,allow_other,use_ino,dropcacheonclose=true,category.create=mfs "${CV_CODE}:/_" "${CV_WORKDIR}"
sudo --user=notroot --group=notroot bash -c "cd ${CV_WORKDIR}; $@"
