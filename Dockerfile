FROM debian:buster

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install \
    texlive latexmk

ENV LANG en_US.UTF-8

ENV HOME /data
WORKDIR /data

VOLUME ["/data"]
