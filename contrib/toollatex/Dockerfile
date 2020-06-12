FROM debian:10

ARG HOST_USER_UID=1000
ENV HOST_USER_UID=${HOST_USER_UID}
ARG HOST_USER_GID=1000
ENV HOST_USER_GID=${HOST_USER_GID}

ENV CV_WORKDIR="/work"
ENV CV_CODE="/code"
ENV CV_RESOURCES="/_/resources"
ENV CV_OUTPUT="/output"
ENV DEBIAN_FRONTEND=noninteractive

# Install all TeX and LaTeX dependences
RUN set -ex \
    \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        git \
        sudo \
        mergerfs \
        inotify-tools \
        lmodern \
        make \
        fonts-liberation \
        texlive \
        texlive-science \
        texlive-latex-extra \
        texlive-generic-extra \
        texlive-bibtex-extra \
        texlive-xetex \
        latexmk \
    && apt-get autoclean \
    && apt-get --purge --yes autoremove \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    \
    # After adding linux users into domain there is an issues with
    # huge lastlog (https://linux.die.net/man/8/lastlog) file in docker (see https://github.com/moby/moby/issues/5419).
    # So key --no-log-init is mandatory
    && echo "Creating notroot user and group from host" \
    && groupadd --gid ${HOST_USER_GID} notroot \
    && useradd \
        --no-log-init \
        --create-home \
        --uid ${HOST_USER_UID} \
        --gid ${HOST_USER_GID} \
        notroot \
    && mkdir --parents ${CV_WORKDIR} \
    && chown --recursive notroot:notroot ${CV_WORKDIR} \
    && mkdir --parents ${CV_CODE} \
    && chown --recursive notroot:notroot ${CV_CODE} \
    && mkdir --parents ${CV_RESOURCES} \
    && chown --recursive notroot:notroot "/_" \
    && mkdir --parents ${CV_OUTPUT} \
    && chown --recursive notroot:notroot ${CV_OUTPUT}

VOLUME ${CV_CODE}
VOLUME ${CV_RESOURCES}
VOLUME ${CV_OUTPUT}

WORKDIR "/"
ADD ./entrypoint.sh /
ENTRYPOINT ["/bin/bash", "/entrypoint.sh"]
