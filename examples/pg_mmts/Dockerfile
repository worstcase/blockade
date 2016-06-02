# vim:set ft=dockerfile:
FROM debian:jessie

# explicitly set user/group IDs
RUN groupadd -r postgres --gid=999 && useradd -r -g postgres --uid=999 postgres

# make the "en_US.UTF-8" locale so postgres will be utf-8 enabled by default
RUN apt-get update && apt-get install -y locales && rm -rf /var/lib/apt/lists/* \
	&& localedef -i en_US -c -f UTF-8 -A /usr/share/locale/locale.alias en_US.UTF-8
ENV LANG en_US.utf8

# use git to fetch sources
RUN apt-get update \
    && apt-get install -y git \
	&& rm -rf /var/lib/apt/lists/*

# postgres build deps
RUN apt-get update && apt-get install -y \
	make \
	gcc \
	libreadline-dev \
	bison \
	flex \
	zlib1g-dev \ 
	&& rm -rf /var/lib/apt/lists/*

RUN mkdir /pg
RUN chown postgres:postgres /pg

USER postgres
WORKDIR /pg
ENV CFLAGS -O0
RUN git clone https://github.com/postgrespro/postgres_cluster.git --depth 1
WORKDIR /pg/postgres_cluster
RUN ./configure  --enable-cassert --enable-debug --prefix=/usr/local/
RUN make -j 4

USER root
RUN make install
RUN cd /pg/postgres_cluster/contrib/pg_tsdtm && make install
RUN cd /pg/postgres_cluster/contrib/raftable && make install
RUN cd /pg/postgres_cluster/contrib/mmts && make install
RUN cd /pg/postgres_cluster/contrib/postgres_fdw && make install
RUN mkdir -p /var/lib/postgresql/data && chown -R postgres /var/lib/postgresql/data
RUN mkdir -p /run/postgresql && chown -R postgres /run/postgresql

USER postgres
ENV PATH /usr/local/bin:$PATH
ENV PGDATA /var/lib/postgresql/data
VOLUME /var/lib/postgresql/data

COPY docker-entrypoint.sh  /

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5432
CMD ["postgres"]



