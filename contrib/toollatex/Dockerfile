FROM debian:10

ARG HOST_USER_UID=1000
ARG HOST_USER_GID=1000

ENV CV_WORKDIR "/code"
ENV CV_OUTPUT "/output"
ENV DEBIAN_FRONTEND noninteractive

# Install all TeX and LaTeX dependences
RUN set -ex \
    \
    && apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        git \
        inotify-tools \
        lmodern \
        make \
        fonts-liberation \
        texlive \
        texlive-science \
        texlive-latex-extra \
        texlive-generic-extra \
        texlive-bibtex-extra \
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
    \
    && mkdir --parents ${CV_WORKDIR} \
    && chown --recursive notroot:notroot ${CV_WORKDIR}

# Export the output data
WORKDIR ${CV_WORKDIR}
VOLUME [${CV_WORKDIR}]
VOLUME [${CV_OUTPUT}]
