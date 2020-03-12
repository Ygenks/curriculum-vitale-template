FROM debian:buster

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install \
    locales \
    texlive latexmk


# Set the locale
RUN sed -i -e 's/# en_US.UTF-8 UTF-8/en_US.UTF-8 UTF-8/' /etc/locale.gen && \
    locale-gen
ENV LANG en_US.UTF-8
ENV LANGUAGE en_US:en
ENV LC_ALL en_US.UTF-8

ENV HOME /data
WORKDIR /data

ADD . /data

VOLUME ["/data"]
