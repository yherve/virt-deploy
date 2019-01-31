#!/bin/bash

set -eu

CONTAINER_NAME="$1"
USE_X11="$2"
MOUNTS="$3"

echo "container=$CONTAINER_NAME"
echo "use_x11=$USE_X11"
echo "mount=$MOUNTS"

IMG_NAME=qdeploy_img

SYSMOUNTS="-v /sys/fs/cgroup:/sys/fs/cgroup:rw"

docker build  -q -t $IMG_NAME .

if [[ "$USE_X11" == "true" ]]; then
    X11_SOCKET=/tmp/.X11-unix
    X11_OPTS="-e DISPLAY=$DISPLAY -v $X11_SOCKET:$X11_SOCKET"
    docker run --rm --name $CONTAINER_NAME -d \
           --privileged -e 'container=docker' \
		   $X11_OPTS $SYSMOUNTS $MOUNTS $IMG_NAME

	h=`docker inspect --format='{{ .Config.Hostname }}' $CONTAINER_NAME`
    xhost +local:$h
else
    docker run --rm --name $CONTAINER_NAME -d \
           --privileged -e 'container=docker' \
           $SYSMOUNTS $MOUNTS $IMG_NAME
fi

