FROM clearlinux:latest
RUN swupd bundle-add package-builder python-extras
COPY entrypoint.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
