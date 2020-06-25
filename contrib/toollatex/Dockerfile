FROM debian:sid

ARG HOST_USER_UID=1000
ENV HOST_USER_UID=${HOST_USER_UID}
ARG HOST_USER_GID=1000
ENV HOST_USER_GID=${HOST_USER_GID}

ENV CV_WORKDIR="/work"
ENV CV_CODE="/code"
ENV CV_RESOURCES="/_/resources"
ENV CV_OUTPUT="/_/output"
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
        texlive \
        texlive-science \
        texlive-latex-extra \
        texlive-generic-extra \
        texlive-bibtex-extra \
        texlive-xetex \
        texlive-lang-cyrillic \
        latexmk \
        fonts-liberation \
        tex-gyre \
        fonts-texgyre \
        fonts-lato \
        fontconfig \
    && apt-get autoclean \
    && apt-get --purge --yes autoremove \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    \
    # Update fonts cache
    && fc-cache --force --verbose \
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
RUN chmod +x "/entrypoint.sh"

ADD ./europasscv_ru.def /usr/share/texlive/texmf-dist/tex/latex/europasscv/
ENV EUROPASSCV_RUSSIAN_OPT_DECL "\\\\\\DeclareOption{russian}{%\n\
  \\\\AtEndOfPackage{%\n\
    \\\\input{europasscv_ru.def}%\n\
  }%\n\
}"
RUN sed --in-place \
        "/Set language/a ${EUROPASSCV_RUSSIAN_OPT_DECL}" \
        /usr/share/texlive/texmf-dist/tex/latex/europasscv/europasscv.cls \
    && sed --in-place \
        "/europasscv_sv.def/a europasscv_ru.def" \
        /usr/share/texlive/texmf-dist/ls-R \
    && unset EUROPASSCV_RUSSIAN_OPT_DECL

ENTRYPOINT ["/entrypoint.sh"]
