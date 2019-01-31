FROM jrei/systemd-debian
RUN apt-get update
RUN apt-get install -y qemu-kvm libvirt-clients libvirt-daemon-system  cgroup-tools virtinst
RUN apt-get install -y virt-manager spice-client-gtk
RUN apt-get install -y vim nmap net-tools tcpdump openssh-client dnsutils bind9-host
# RUN apt-get install -y spice-html5 websockify x11-apps

RUN systemctl enable libvirtd; systemctl enable virtlockd

RUN echo "listen_tls = 0" >> /etc/libvirt/libvirtd.conf;    \
echo 'listen_tcp = 1' >> /etc/libvirt/libvirtd.conf;        \
echo 'tls_port = "16514"' >> /etc/libvirt/libvirtd.conf;    \
echo 'tcp_port = "16509"' >> /etc/libvirt/libvirtd.conf;    \
echo 'auth_tcp = "none"' >> /etc/libvirt/libvirtd.conf;     \
echo 'libvirtd_opts="-l"' >> /etc/default/libvirtd

RUN echo 'vnc_listen = "0.0.0.0"' >> /etc/libvirt/qemu.conf

ADD libvirt-post.service /usr/lib/systemd/system/libvirt-post.service
ADD libvirt-post.sh /libvirt-post.sh
RUN chmod a+x /libvirt-post.sh
RUN systemctl enable libvirt-post
