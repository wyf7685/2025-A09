# ruff: noqa: T201
import py_compile
import shutil
from pathlib import Path


def compile_all(source_dir: Path, target_dir: Path) -> None:
    for source_file in source_dir.rglob("*.py"):
        target_file = target_dir / source_file.relative_to(source_dir).with_suffix(".pyc")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            py_compile.compile(
                file=str(source_file),
                cfile=str(target_file),
                dfile=str(source_file),
                doraise=True,
                optimize=1,
                invalidation_mode=py_compile.PycInvalidationMode.CHECKED_HASH,
                quiet=1,
            )
            print(f"Compiled {source_file} to {target_file}")
        except py_compile.PyCompileError as e:
            print(f"Failed to compile {source_file}: {e.msg}")


def copy_assets(source_dir: Path, target_dir: Path, *asset_extensions: str) -> None:
    for asset_file in source_dir.rglob("*"):
        if asset_file.suffix in asset_extensions:
            target_file = target_dir / asset_file.relative_to(source_dir)
            target_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(asset_file, target_file)
            print(f"Copied {asset_file} to {target_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: python compile_pyc.py <source_dir> <target_dir>")
        sys.exit(1)

    source = Path(sys.argv[1])
    target = Path(sys.argv[2])

    compile_all(source, target)
    copy_assets(source, target, ".md")
