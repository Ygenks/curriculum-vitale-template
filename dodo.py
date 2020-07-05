import os
import errno
import json
import shutil
import pathlib
from typing import Union, Dict, List, Callable, Iterable, Iterator, Any

import docker
from git import Repo
from termcolor import colored


PROJECT_PREFIX = "CV"
VERSION_ENV_VARIABLE = "CV_VERSION"
REPO_MAIN_DIR = pathlib.Path(os.path.dirname(os.path.realpath(__file__)))

RESOURCES_DIR = REPO_MAIN_DIR / "resources"
BUILD_DIR_ROOT = REPO_MAIN_DIR / "build"

RESUME_SRC_DIR = REPO_MAIN_DIR / "resumé"
RESUME_OUTPUT_DIR = BUILD_DIR_ROOT / "resumé"


REPO = Repo(REPO_MAIN_DIR)
assert not REPO.bare

DOCKER_CLIENT = docker.APIClient(base_url="unix://var/run/docker.sock")
DOIT_CONFIG = {"default_tasks": ["build_all_images"]}

# Don't modify this variables manually
IMAGE_BUILD_TASKS = []
IMAGE_CLEAN_TASKS = []


def get_current_branch():
    try:
        return os.environ["CI_COMMIT_REF_NAME"]
    except KeyError:
        return REPO.head.ref.name


def get_version():
    head_commit_datetime = REPO.head.commit.authored_datetime
    head_commit_hash = REPO.head.commit.hexsha

    return "{0}-{1}-{2}".format(
        get_current_branch(),
        head_commit_datetime.strftime("%Y-%m-%d"),
        head_commit_hash[:7]
    )


def create_dir_if_not_exists(path_to_dir: str) -> bool:
    try:
        os.makedirs(path_to_dir)
        return True
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise

        return False


def is_dir_modified(relative_path_to_dir: str) -> bool:
    path = os.path.normpath(relative_path_to_dir)
    is_files_modified = len(REPO.index.diff(None, path)) != 0
    is_new_files_added = any(untracked_file.startswith(path)
                             for untracked_file in REPO.untracked_files)

    return is_files_modified or is_new_files_added


def get_all_tasks() -> List[Callable]:
    result = []
    for name, value in globals().items():
        if name.startswith("task_"):
            result.append(value)

    return result


def delete_using_rglob(path: pathlib.Path, pattern: str) -> None:
    for path in REPO_MAIN_DIR.rglob(pattern):
        print(path)
        if path.is_dir():
            path.rmdir()
        else:
            path.unlink()


def get_task_name(task_obj: Union[Callable, str]) -> str:
    if callable(task_obj):
        task_obj = task_obj.__name__

    return task_obj.replace("task_", "")


def get_cli_handy_string(text: str) -> str:
    return text.replace("_", "-")


def get_cli_handy_task_name(task_func: Union[Callable, str]) -> str:
    return get_cli_handy_string(get_task_name(task_func))


def construct_full_image_name(image_name: str) -> str:
    return f"{PROJECT_PREFIX.lower()}-{image_name}"


def construct_tagged_full_image_name(image_name: str) -> str:
    return f"{construct_full_image_name(image_name)}:{get_version()}"


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
        forcerm=True,
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


def print_text(generator: Iterator[bytes]) -> None:
    line = bytearray()
    for obj in generator:
        line.extend(obj)
        if chr(line[-1]) == "\n":
            print(line.decode(), end="")
            line = bytearray()

    # Print characters without \n symbol
    if line:
        print(line.decode(), end="\n")


def run_command_in_container(
        full_image_name: str,
        command: Union[List[str], str],
        volumes: List[str] = None,
        host_config: Dict = None
) -> bool:
    container_info = DOCKER_CLIENT.create_container(
        full_image_name,
        command,
        user=os.getuid() if "privileged" in host_config else None,
        tty=True,
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

        generator = DOCKER_CLIENT.logs(container_id,
                                       stream=True, follow=True,
                                       stdout=True, stderr=True)
        print_text(generator)

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
        full_image_name = construct_tagged_full_image_name(image_name)
        output_iter = start_docker_image_building(
            full_image_name,
            path_to_build_context,
            path_to_dockerfile,
            build_args={VERSION_ENV_VARIABLE: get_version(), **build_args}
        )
        return analyze_and_print_image_building_status(output_iter)

    return build_image


def clean_image(img_name: str) -> None:
    full_img_name = construct_full_image_name(img_name)

    containers = DOCKER_CLIENT.containers(
        all=True,
        filters={"name": full_img_name}
    )
    for container in containers:
        DOCKER_CLIENT.remove_container(container.id, force=True)
        print(f"{container.id} container removed")

    images = DOCKER_CLIENT.images(name=full_img_name, all=True)
    images_except_lasp = sorted(images, key=lambda el: el["Created"])[:-1]
    for image in images_except_lasp:
        DOCKER_CLIENT.remove_image(image["Id"], force=True)
        print(f"{img_name} - {image['Id']} image removed")


def create_image_build_task(
    task_name: str,
    image_name: str,
    image_builder_args: Dict[str, Any]
) -> Callable:
    def task():
        return {
            "basename": task_name,
            "actions": [
                create_image_builder(image_name, **image_builder_args)
            ],
            "verbosity": 2
        }

    task.__doc__ = f"Build <{image_name}> Docker image"

    return task


def create_image_clean_task(task_name: str, image_name: str):
    def task():
        return {
            "basename": task_name,
            "actions": [lambda: clean_image(image_name)],
            "verbosity": 2
        }

    task.__doc__ = ("Remove useless containers and images"
                    f" of <{image_name}> Docker image")

    return task


def create_tasks_for_docker_image_management(
    img_name: str,
    image_builder_args: Dict[str, Any]
):
    task_name_major_part = get_cli_handy_string(img_name)

    image_build_task = create_image_build_task(
        task_name_major_part,
        img_name,
        image_builder_args
    )
    globals()[f"task_{task_name_major_part}"] = image_build_task
    IMAGE_BUILD_TASKS.append(image_build_task)

    clean_task_name = f"clean-{task_name_major_part}"
    image_clean_task = create_image_clean_task(clean_task_name, img_name)
    globals()[f"task_{clean_task_name}"] = image_clean_task
    IMAGE_CLEAN_TASKS.append(image_clean_task)


def task_resume():
    """Build resume as pdf file"""
    def create_output_dir():
        create_dir_if_not_exists(RESUME_OUTPUT_DIR)

    def build_resume():
        return run_command_in_container(
            construct_tagged_full_image_name("toollatex"),
            command=[
                "latexmk",
                "-f",
                "-pdfxe",
                "-xelatex",
                "-shell-escape",
                "-output-directory=output",
                "-jobname=main"
            ],
            volumes=["/code", "/_/resources", "/_/output"],
            host_config=DOCKER_CLIENT.create_host_config(
                privileged=True,
                binds={
                    RESUME_SRC_DIR: {"bind": "/code", "mode": "ro"},
                    RESOURCES_DIR: {"bind": "/_/resources", "mode": "ro"},
                    RESUME_OUTPUT_DIR: {"bind": "/_/output", "mode": "rw"}
                }
            )
        )

    def clean():
        if RESUME_OUTPUT_DIR.exists():
            print(RESUME_OUTPUT_DIR)
            shutil.rmtree(RESUME_OUTPUT_DIR, ignore_errors=True)

    return {
        "actions": [create_output_dir, build_resume],
        "targets": [f"{RESUME_OUTPUT_DIR}/main.pdf"],
        "task_dep": ["toollatex"],
        "clean": [clean],
        "verbosity": 2
    }


def task_cleanup():
    """Remove useless temporary files"""
    def clean():
        for task in get_all_tasks():
            if task is task_cleanup:
                continue

            attrs = task()
            if "clean" in attrs:
                assert callable(attrs["clean"][0])
                attrs["clean"][0]()

        if BUILD_DIR_ROOT.exists():
            print(BUILD_DIR_ROOT)
            BUILD_DIR_ROOT.rmdir()

        delete_using_rglob(BUILD_DIR_ROOT, "*.pyc")
        delete_using_rglob(BUILD_DIR_ROOT, "__pycache__")
        delete_using_rglob(BUILD_DIR_ROOT, "*~")

    return {
        "actions": [clean],
        "verbosity": 2
    }


def task_get_version():
    """Print project version"""
    def print_version():
        print(get_version())

    return {
        "basename": get_cli_handy_task_name(task_get_version),
        "actions": [print_version],
        "verbosity": 2
    }


def task_build_all_images():
    """Build all required Docker images"""
    return {
        "basename": get_cli_handy_task_name(task_build_all_images),
        "actions": [lambda: print("All images have just been built")],
        "task_dep": [task()["basename"] for task in IMAGE_BUILD_TASKS],
        "verbosity": 2
    }


def task_clean_images():
    """Removing useless containers and images"""
    return {

        "basename": get_cli_handy_task_name(task_clean_images),
        "actions": [lambda: print("All useless containers and images"
                                  " have just been removed")],
        "task_dep": [task()["basename"] for task in IMAGE_CLEAN_TASKS],
        "verbosity": 2
    }


create_tasks_for_docker_image_management(
    "toollatex",
    {"path_to_build_context": "./contrib/toollatex"}
)
