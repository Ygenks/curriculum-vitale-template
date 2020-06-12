import os
import errno
import json
import string
import random
import shutil
import pathlib
from typing import Dict, List, Callable, Iterable

import docker
from doit.action import CmdAction
from git import Repo
from termcolor import colored


PROJECT_PREFIX = "CV"
VERSION_ENV_VARIABLE = "CV_VERSION"
REPO_MAIN_DIR = os.path.dirname(os.path.realpath(__file__))

BUILD_DIR_ROOT = f"{REPO_MAIN_DIR}/build"
RESUME_OUTPUT_DIR = f"{BUILD_DIR_ROOT}/resumé"
RESUME_SRC_DIR = f"{REPO_MAIN_DIR}/resumé"



REPO = Repo(REPO_MAIN_DIR)
assert not REPO.bare


def get_current_branch():
    try:
        return os.environ["CI_COMMIT_REF_NAME"]
    except KeyError:
        return REPO.head.ref.name


CURRENT_BRANCH = get_current_branch()


def get_version():
    head_commit_datetime = REPO.head.commit.authored_datetime
    head_commit_hash = REPO.head.commit.hexsha

    return "{0}-{1}-{2}".format(
        CURRENT_BRANCH,
        head_commit_datetime.strftime("%Y-%m-%d"),
        head_commit_hash[:7]
    )


VERSION = get_version()


def task_get_version():
    def print_version():
        print(VERSION)

    return {
        "actions": [print_version],
        "verbosity": 2
    }


DOCKER_CLIENT = docker.APIClient(base_url="unix://var/run/docker.sock")
DOIT_CONFIG = {"default_tasks": ["build_all_images"]}

# Don't modify this variable manually
IMAGE_BUILDERS = []


class NotTaskObject(Exception):
    pass


def docker_image_builder(image_builder: Callable) -> Callable:
    """Decorator for tasks for building docker images."""
    IMAGE_BUILDERS.append(image_builder)

    return image_builder


def get_task_name(task_obj: Callable) -> str:
    if hasattr(task_obj, "create_doit_tasks"):
        return task_obj.__name__

    task_name_prefix = "task_"
    if task_obj.__name__.startswith(task_name_prefix):
        return task_obj.__name__[len(task_name_prefix):]

    raise NotTaskObject()


def get_names_of_image_builders() -> List[str]:
    names_of_image_builders = []
    for image_builder in IMAGE_BUILDERS:
        task_name = get_task_name(image_builder)
        names_of_image_builders.append(task_name)

    return names_of_image_builders


def create_dir_if_not_exists(path_to_dir: str) -> bool:
    try:
        os.makedirs(path_to_dir)
        return True
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

        return False


def construct_full_image_name(image_name: str) -> str:
    return "{}-{}:{}".format(PROJECT_PREFIX.lower(), image_name, VERSION)


def start_docker_image_building(
        full_image_name: str,
        path_to_context: str,
        path_to_dockerfile_in_context: str,
        build_args: Dict[str, str] = {}
) -> Iterable[str]:
    info_txt = "Start building {} image".format(full_image_name)
    print(colored(info_txt, "blue", "on_white", attrs=["bold"]))

    return DOCKER_CLIENT.build(
        path="{}/{}/".format(REPO_MAIN_DIR, path_to_context),
        dockerfile=path_to_dockerfile_in_context,
        rm=True,
        buildargs={
            "HOST_USER_UID": str(os.getuid()),
            "HOST_USER_GID": str(os.getgid()),
            **build_args
        },
        tag=full_image_name
    )


def convert_bytes_to_human_readable(B: int) -> str:
    """Return the given bytes as a human friendly KB, MB, GB, or TB string."""
    B = float(B)
    KB = float(1024)
    MB = float(KB ** 2)  # 1,048,576
    GB = float(KB ** 3)  # 1,073,741,824
    TB = float(KB ** 4)  # 1,099,511,627,776

    if B < KB:
        return "{0} {1}".format(B, "Bytes" if 0 == B > 1 else "Byte")
    elif KB <= B < MB:
        return "{0:.2f} KB".format(B / KB)
    elif MB <= B < GB:
        return "{0:.2f} MB".format(B / MB)
    elif GB <= B < TB:
        return "{0:.2f} GB".format(B / GB)
    elif TB <= B:
        return "{0:.2f} TB".format(B / TB)


def generate_password(
        size: int = 8,
        chars: str = string.ascii_letters + string.digits
) -> str:
    """
    Returns a string of random characters, useful in generating temporary
    passwords for automated password resets.

    size: default=8; override to provide smaller/larger passwords
    chars: default=A-Za-z0-9; override to provide more/less diversity
    """
    return "".join(random.choice(chars) for i in range(size))


def construct_loading_progress_string(cur_bytes: int, total_bytes: int) -> str:
    return "{}/{}".format(
        convert_bytes_to_human_readable(cur_bytes),
        convert_bytes_to_human_readable(total_bytes)
    )


def analyze_and_print_image_building_status(
        output_iter: Iterable[str]
) -> bool:
    """Read and analyze JSON serialized info about status line by line.
    Returns:
        True - if all is good
        False - if error occurs during image building
    """
    for line in output_iter:
        data = json.loads(line)
        if "stream" in data:
            print(data["stream"], end="")
        elif "status" in data:
            layer_status = data["status"]

            if "id" in data:
                layer_id = data["id"]
                if ("progressDetail" in data
                        and "current" in data["progressDetail"]):
                    bytes_loaded = data["progressDetail"]["current"]
                    if "total" not in data["progressDetail"]:
                        print("======", data["progressDetail"])

                    total_bytes = data["progressDetail"]["total"]
                    progress = construct_loading_progress_string(
                        bytes_loaded,
                        total_bytes
                    )

                    print(f"{layer_id}: {layer_status} {progress}")
                else:
                    print(f"{layer_id}: {layer_status}")
            else:
                print(layer_status)
        elif "error" in data:
            print(data["error"])
            return False
        else:
            print(data)

    return True


def run_command_in_container(
        full_image_name: str,
        command: str,
        volumes: List[str] = None,
        host_config: Dict = None
) -> bool:
    container_info = DOCKER_CLIENT.create_container(
        full_image_name,
        command,
        tty=True,
        user=os.getuid(),
        stdin_open=True,
        volumes=volumes,
        host_config=host_config
    )
    container_id = container_info["Id"]

    exit_info = {"StatusCode": -1}
    # Using try..finally statement because process running in the
    # container not interractive, therefore all we can do is send
    # interruption to script (Ctrl-C), which will break connection
    # with docker daemon, which will stop container
    try:
        DOCKER_CLIENT.start(container_id)

        output_iter = DOCKER_CLIENT.attach(container_id, stream=True)
        for line in output_iter:
            print(line.decode(), end="")

        exit_info = DOCKER_CLIENT.wait(container_id)
    finally:
        DOCKER_CLIENT.remove_container(container_id, v=True, force=True)

    return exit_info["StatusCode"] == 0


def create_image_builder(
        image_name: str,
        path_to_build_context: str,
        path_to_dockerfile: str = "./Dockerfile",
        build_args: Dict[str, str] = {}
) -> Callable:
    def build_image():
        full_image_name = construct_full_image_name(image_name)
        output_iter = start_docker_image_building(
            full_image_name,
            path_to_build_context,
            path_to_dockerfile,
            build_args={VERSION_ENV_VARIABLE: VERSION, **build_args}
        )
        return analyze_and_print_image_building_status(output_iter)

    return build_image


def is_dir_modified(relative_path_to_dir: str) -> bool:
    path = os.path.normpath(relative_path_to_dir)
    is_files_modified = len(REPO.index.diff(None, path)) != 0
    is_new_files_added = any(untracked_file.startswith(path)
                             for untracked_file in REPO.untracked_files)

    return is_files_modified or is_new_files_added


@docker_image_builder
def task_toollatex():
    return {
        "actions": [create_image_builder("toollatex", "./contrib/toollatex")],
        "verbosity": 2
    }


def task_build_all_images():
    return {
        "actions": ["true"],
        "task_dep": get_names_of_image_builders()
    }


def task_resume():
    """Task for building resume in pdf file."""
    def create_output_dir():
        create_dir_if_not_exists(RESUME_OUTPUT_DIR)

    def build_resume():
        full_image_name = construct_full_image_name("toollatex")
        command = (
            "pdflatex"
            " -halt-on-error"
            " -output-directory /output"
            " main.tex"
        )

        return run_command_in_container(
            full_image_name,
            command,
            volumes=["/code", "/output"],
            host_config=DOCKER_CLIENT.create_host_config(
                binds={
                    RESUME_SRC_DIR: {"bind": "/code", "mode": "ro"},
                    RESUME_OUTPUT_DIR: {"bind": "/output", "mode": "rw"}
                }
            )
        )

    return {
        "actions": [create_output_dir, build_resume],
        "targets": [f"{RESUME_OUTPUT_DIR}/main.pdf"],
        "task_dep": [get_task_name(task_toollatex)],
        "verbosity": 2
    }


def task_clean_resume():
    """Task for cleaning result of build_resume task."""
    def delete_resume_dir():
        shutil.rmtree(RESUME_OUTPUT_DIR, ignore_errors=True)

    return {
        "actions": [delete_resume_dir]
    }
