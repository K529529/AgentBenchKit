"""Build a pinned Qoder CN inference image without changing the official testbed."""

import argparse
import hashlib
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

CLI_VERSION = "1.1.65"
SDK_VERSION = "1.0.15"
CLI_URL = (
    "https://static.qoder.com.cn/qoder-cli-cn/releases/1.1.65/qoderclicn-linux-x64-baseline.tar.gz"
)
CLI_ARCHIVE_SHA256 = "7b28022b3eac5dfd66e4cad78767f91c985ae071a149329042bc21890a4a4876"


def build(image: str, tag: str, uv_binary: Path, cli_archive: Path, wheel: Path) -> None:
    if "@sha256:" not in image or len(image.rsplit(":", 1)[-1]) != 64:
        raise ValueError("provide an immutable official base image digest")
    if hashlib.sha256(cli_archive.read_bytes()).hexdigest() != CLI_ARCHIVE_SHA256:
        raise ValueError("official Qoder CN archive checksum mismatch")
    if uv_binary.read_bytes()[:4] != b"\x7fELF" or wheel.suffix != ".whl":
        raise ValueError("provide Linux uv and a built ABK wheel")
    with tempfile.TemporaryDirectory(prefix="abk-qoder-image-") as folder:
        context = Path(folder)
        shutil.copy2(uv_binary, context / "uv")
        shutil.copy2(wheel, context / wheel.name)
        with tarfile.open(cli_archive) as archive:
            members = [
                m for m in archive.getmembers() if m.isfile() and Path(m.name).name == "qoderclicn"
            ]
            if len(members) != 1:
                raise ValueError("official archive executable is ambiguous")
            stream = archive.extractfile(members[0])
            assert stream is not None
            with stream, (context / "qoderclicn").open("wb") as out:
                shutil.copyfileobj(stream, out)
        (context / "Dockerfile").write_text(
            f'FROM {image}\nLABEL agentbenchkit.benchmark.base="{image}"\n'
            "COPY uv /usr/local/bin/uv\nCOPY qoderclicn /usr/local/bin/qoderclicn\n"
            f"COPY {wheel.name} /tmp/{wheel.name}\n"
            "RUN chmod 755 /usr/local/bin/uv /usr/local/bin/qoderclicn && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv python install 3.12.10 && "
            "UV_PYTHON_INSTALL_DIR=/opt/abk-python uv venv --python 3.12.10 /opt/abk && "
            f"uv pip install --python /opt/abk/bin/python /tmp/{wheel.name} "
            f"qodercn-agent-sdk=={SDK_VERSION}\n"
            f'RUN test "$(qoderclicn --version)" = "{CLI_VERSION}"\n'
            f'LABEL agentbenchkit.qoder.cli="{CLI_VERSION}" '
            f'agentbenchkit.qoder.sdk="{SDK_VERSION}" '
            f'agentbenchkit.driver.wheel.sha256="{hashlib.sha256(wheel.read_bytes()).hexdigest()}"\n',
            encoding="utf-8",
        )
        subprocess.run(["docker", "build", "--tag", tag, str(context)], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--uv-binary", required=True, type=Path)
    parser.add_argument("--cli-archive", required=True, type=Path)
    parser.add_argument("--wheel", required=True, type=Path)
    args = parser.parse_args()
    build(args.image, args.tag, args.uv_binary, args.cli_archive, args.wheel)
