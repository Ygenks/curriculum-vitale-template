IMAGE=cv-image
CONTAINER=cv-container

.PHONY: all image build_image run attach

all: image

build_image:
	docker build -t ${IMAGE} .

image: build_image
	docker container rm -f ${CONTAINER}; true
	docker container create --name ${CONTAINER} \
	--privileged \
	-t -i ${IMAGE}

start:
	docker container start ${CONTAINER}

attach:
	docker exec -it ${CONTAINER} /bin/bash
