from __future__ import annotations

import asyncio
import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

from backend.config import DATA_DIR, PROJECT_ROOT, SESSIONS_DIR

TDATA_DIR = DATA_DIR / "tdata"
TDATA_DIR.mkdir(parents=True, exist_ok=True)

_KEY_DATA_FILES = ("key_datas", "key_data0", "key_data1")
_TWO_FA_KEYS = ("twoFA", "two_fa", "twofa", "password", "2fa")
_SESSION_STRING_KEYS = ("session_string", "sessionString", "string_session")


@dataclass
class AccountPackage:
    name: str
    root: Path
    tdata_dir: Path | None = None
    session_file: Path | None = None
    json_file: Path | None = None
    session_string: str = ""
    two_fa: str = ""
    json_data: dict = field(default_factory=dict)


@dataclass
class ImportItem:
    name: str
    method: str
    session_file: str = ""
    error: str = ""


def _is_tdata_dir(path: Path) -> bool:
    return path.is_dir() and any((path / name).exists() for name in _KEY_DATA_FILES)


def _read_json(path: Path | None) -> dict:
    if not path or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _first_session_file(folder: Path) -> Path | None:
    files = sorted(
        p for p in folder.glob("*.session") if p.is_file() and p.stat().st_size > 0
    )
    return files[0] if files else None


def _first_json_file(folder: Path, stem: str | None = None) -> Path | None:
    if stem:
        named = folder / f"{stem}.json"
        if named.is_file():
            return named
    files = sorted(p for p in folder.glob("*.json") if p.is_file())
    return files[0] if files else None


def _read_two_fa(folder: Path, json_data: dict) -> str:
    for key in _TWO_FA_KEYS:
        value = str(json_data.get(key) or "").strip()
        if value:
            return value
    for name in ("2fa.txt", "2FA.txt", "password.txt"):
        path = folder / name
        if not path.is_file():
            continue
        try:
            line = path.read_text(encoding="utf-8-sig", errors="ignore").strip().splitlines()
        except OSError:
            continue
        if line and line[0].strip():
            return line[0].strip()
    return ""


def _read_session_string(folder: Path, json_data: dict) -> str:
    for key in _SESSION_STRING_KEYS:
        value = str(json_data.get(key) or "").strip()
        if value:
            return value
    for path in sorted(folder.glob("*.txt")):
        if path.name.lower() in {"2fa.txt", "2fa.txt", "password.txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig", errors="ignore").strip()
        except OSError:
            continue
        line = next((part.strip() for part in text.splitlines() if part.strip()), "")
        if len(line) >= 40 and not any(ch.isspace() for ch in line):
            return line
    return ""


def _package_from_dir(folder: Path) -> AccountPackage | None:
    tdata_dir: Path | None = None
    search_dirs = [folder]
    if _is_tdata_dir(folder):
        tdata_dir = folder
        if folder.name.lower() == "tdata":
            search_dirs.append(folder.parent)
    elif _is_tdata_dir(folder / "tdata"):
        tdata_dir = folder / "tdata"

    session_file = None
    json_file = None
    for directory in search_dirs:
        session_file = session_file or _first_session_file(directory)
        json_file = json_file or _first_json_file(
            directory, session_file.stem if session_file else folder.name
        )

    json_data = _read_json(json_file)
    two_fa = _read_two_fa(folder, json_data)
    if tdata_dir and tdata_dir != folder:
        two_fa = two_fa or _read_two_fa(tdata_dir.parent, json_data)
    session_string = _read_session_string(folder, json_data)
    if not session_string:
        for directory in search_dirs:
            session_string = _read_session_string(directory, json_data)
            if session_string:
                break

    if not session_file and not session_string and tdata_dir is None:
        return None

    phone = str(json_data.get("phone") or json_data.get("phoneNumber") or "").lstrip("+")
    if folder.name.lower() == "tdata" and folder.parent.name:
        name = phone or folder.parent.name
    else:
        name = phone or (session_file.stem if session_file else folder.name)
    return AccountPackage(
        name=name,
        root=folder,
        tdata_dir=tdata_dir,
        session_file=session_file,
        json_file=json_file,
        session_string=session_string,
        two_fa=two_fa,
        json_data=json_data,
    )


def discover_account_packages(root: Path) -> list[AccountPackage]:
    root = root.expanduser()
    if not root.exists():
        raise ValueError(f"目录不存在: {root}")
    if not root.is_dir():
        raise ValueError(f"不是文件夹: {root}")

    children: list[AccountPackage] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.lower() == "tdata":
            continue
        package = _package_from_dir(child)
        if package:
            children.append(package)
    if children:
        return children

    package = _package_from_dir(root)
    if package:
        return [package]
    raise ValueError("未找到可导入的账号（需要 .session / .json / 直登号 tdata）")


def _patch_opentele() -> None:
    import importlib.util
    import sys
    import types

    if "opentele.tl.telethon" in sys.modules:
        return

    spec = importlib.util.find_spec("opentele")
    if spec is None or not spec.origin:
        raise ValueError("未安装 opentele，请运行: pip install opentele")
    pkg_dir = Path(spec.origin).parent

    # 避免执行 opentele/__init__.py（它会先加载 tl，导致补丁来不及打上）
    if "opentele" in sys.modules and "opentele.td" not in sys.modules:
        for key in list(sys.modules):
            if key == "opentele" or key.startswith("opentele."):
                del sys.modules[key]

    if "opentele" not in sys.modules:
        pkg = types.ModuleType("opentele")
        pkg.__path__ = [str(pkg_dir)]
        pkg.__package__ = "opentele"
        pkg.__file__ = spec.origin
        pkg.__spec__ = spec
        if spec.submodule_search_locations is None:
            spec.submodule_search_locations = [str(pkg_dir)]
        sys.modules["opentele"] = pkg

    def load_submodule(fullname: str, filename: str):
        if fullname in sys.modules:
            return sys.modules[fullname]
        file_path = pkg_dir / filename
        sub_spec = importlib.util.spec_from_file_location(fullname, file_path)
        if sub_spec is None or sub_spec.loader is None:
            raise ValueError(f"无法加载 {fullname}")
        module = importlib.util.module_from_spec(sub_spec)
        sys.modules[fullname] = module
        sub_spec.loader.exec_module(module)
        return module

    load_submodule("opentele.debug", "debug.py")
    utils = load_submodule("opentele.utils", "utils.py")
    if getattr(utils.extend_class, "_paperwing_patched", False):
        return

    skip = {
        "__abstractmethods__",
        "__module__",
        "_abc_impl",
        "__doc__",
        "__firstlineno__",
        "__static_attributes__",
        "__type_params__",
        "__annotate__",
        "__annotate_func__",
        "__qualname__",
        "__dict__",
        "__weakref__",
    }

    def patched_new(cls, decorated_cls, isOverride: bool = False):
        new_attributes = dict(decorated_cls.__dict__)
        for name in list(new_attributes):
            if name in skip:
                new_attributes.pop(name, None)

        base = decorated_cls.__bases__[0]
        cross_delete = {}
        if not isOverride:
            for attribute_name, attribute_value in new_attributes.items():
                result = utils.extend_class.getattr(base, attribute_name)
                if result is None:
                    continue
                if id(result["value"]) == id(attribute_value):
                    cross_delete[attribute_name] = attribute_value
                    continue
                if not utils.override.isOverride(attribute_value):
                    if attribute_name.startswith("__") and attribute_name.endswith("__"):
                        cross_delete[attribute_name] = attribute_value
                        continue
                    raise RuntimeError(f"opentele extend_class 冲突: {attribute_name}")
            for name in cross_delete:
                new_attributes.pop(name, None)

        for attribute_name, attribute_value in new_attributes.items():
            result = utils.extend_class.getattr(base, attribute_name)
            if result is not None:
                setattr(
                    base,
                    f"__{decorated_cls.__name__}__{attribute_name}",
                    result["value"],
                )
                setattr(
                    decorated_cls,
                    f"__{decorated_cls.__name__}__{attribute_name}",
                    result["value"],
                )
            setattr(base, attribute_name, attribute_value)
        return decorated_cls

    utils.extend_class.__new__ = patched_new  # type: ignore[method-assign]
    utils.extend_class._paperwing_patched = True  # type: ignore[attr-defined]


def _tdata_search_roots() -> list[Path]:
    roots = [TDATA_DIR]
    # 仅开发态：安装包/PyInstaller 冻结后只认当前 DATA_DIR，避免扫到安装目录旁的空 data
    if getattr(sys, "frozen", False):
        return roots
    extra = PROJECT_ROOT / "data" / "tdata"
    try:
        if extra.resolve() != TDATA_DIR.resolve():
            roots.append(extra)
    except OSError:
        roots.append(extra)
    return roots


def find_account_package(account_id: str) -> AccountPackage | None:
    for root in _tdata_search_roots():
        folder = root / account_id
        if folder.is_dir():
            package = _package_from_dir(folder)
            if package:
                return package
    return None


def restore_packaged_session(account_id: str, dest: Path) -> bool:
    package = find_account_package(account_id)
    if not package or not package.session_file or not package.session_file.exists():
        return False
    if package.session_file.resolve() == dest.resolve():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(package.session_file, dest)
    attach_package_meta(package, dest.stem)
    return True


def _opentele_runtime():
    _patch_opentele()
    from opentele.td import TDesktop
    from opentele.tl import telethon as ot_tl

    return TDesktop, ot_tl.API, ot_tl.UseCurrentSession, ot_tl.CreateNewSession


def _desktop_api_from_meta(meta: dict):
    from backend.storage.session_json import session_device_kwargs

    _TDesktop, API, _use_current, _create_new = _opentele_runtime()
    device = session_device_kwargs(meta)
    return API.TelegramDesktop(
        device_model=device.get("device_model"),
        system_version=device.get("system_version"),
        app_version=device.get("app_version"),
        lang_code=device.get("lang_code"),
        system_lang_code=device.get("system_lang_code"),
        lang_pack=str(meta.get("lang_pack") or "tdesktop"),
    )


def _load_tdesktop(tdata_dir: Path, passcode: str = "", api=None):
    TDesktop, API, _use_current, _create_new = _opentele_runtime()
    api = api or API.TelegramDesktop
    candidates: list[str] = [""]
    if passcode:
        candidates.append(passcode)
    tried: set[str] = set()
    last_error: Exception | None = None
    for code in candidates:
        if code in tried:
            continue
        tried.add(code)
        try:
            tdesk = TDesktop(str(tdata_dir), api=api, passcode=code)
        except Exception as exc:
            last_error = exc
            continue
        if tdesk.isLoaded():
            return tdesk
        last_error = ValueError("tdata 未能加载账号")
    detail = f"：{last_error}" if last_error else ""
    raise ValueError(
        "无法加载 tdata，请确认目录含 key_datas，且未被 Portable 客户端打开过" + detail
    )


def _write_session_from_string(session_string: str, dest_base: Path) -> Path:
    from telethon.sessions import SQLiteSession, StringSession

    src = StringSession(session_string)
    if src.auth_key is None:
        raise ValueError("session_string 无效")

    session_file = dest_base.with_suffix(".session") if dest_base.suffix != ".session" else dest_base
    sqlite_base = session_file.with_suffix("")
    if session_file.exists():
        session_file.unlink()
    journal = Path(str(session_file) + "-journal")
    if journal.exists():
        journal.unlink()

    dst = SQLiteSession(str(sqlite_base))
    dst.set_dc(src.dc_id, src.server_address, src.port)
    dst.auth_key = src.auth_key
    dst.save()
    dst.close()
    if not session_file.exists():
        raise ValueError("写入 session 文件失败")
    return session_file


def attach_package_meta(package: AccountPackage, account_id: str) -> None:
    dest = SESSIONS_DIR / f"{account_id}.json"
    data = _read_json(dest)
    if not data and package.json_file and package.json_file.exists():
        shutil.copy2(package.json_file, dest)
        data = _read_json(dest)
    elif package.json_data and not data:
        data = dict(package.json_data)
    if package.two_fa and not any(str(data.get(key) or "").strip() for key in _TWO_FA_KEYS):
        data["twoFA"] = package.two_fa
        data["password"] = package.two_fa
    if package.name and not str(data.get("phone") or "").strip():
        data["phone"] = package.name
    if data:
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_sidecar_json(package: AccountPackage, session_file: Path) -> None:
    dest = session_file.with_suffix(".json")
    data = dict(package.json_data) if package.json_data else _read_json(dest)
    if package.json_file and package.json_file.exists() and not data:
        shutil.copy2(package.json_file, dest)
        return
    if package.two_fa and not any(str(data.get(key) or "").strip() for key in _TWO_FA_KEYS):
        data["twoFA"] = package.two_fa
        data["password"] = package.two_fa
    if package.name and not str(data.get("phone") or "").strip():
        data["phone"] = package.name
    if data:
        dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _staging_dir() -> Path:
    path = SESSIONS_DIR / "_tdata_staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _to_telethon_safe(tdesk, *, dest_base: Path, flag, api, password, kwargs, timeout: float):
    try:
        return await asyncio.wait_for(
            tdesk.ToTelethon(
                session=str(dest_base),
                flag=flag,
                api=api,
                password=password or None,
                **kwargs,
            ),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        raise ValueError("tdata 转换超时") from exc
    except Exception:
        raise
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        raise ValueError(f"{type(exc).__name__}: {exc}") from None


def _unlink_session_files(session_file: Path) -> None:
    for path in (session_file, Path(str(session_file) + "-journal")):
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass


async def _convert_tdata_package(
    package: AccountPackage,
    session_name: str,
    *,
    create_new: bool = False,
    proxy=None,
) -> Path:
    if package.tdata_dir is None:
        raise ValueError("没有可转换的 tdata 目录")

    _TDesktop, _API, UseCurrentSession, CreateNewSession = _opentele_runtime()
    api = _desktop_api_from_meta(package.json_data)
    tdesk = _load_tdesktop(package.tdata_dir, package.two_fa, api=api)
    dest_base = _staging_dir() / session_name
    session_file = Path(f"{dest_base}.session")
    _unlink_session_files(session_file)
    flag = CreateNewSession if create_new else UseCurrentSession
    kwargs: dict = {
        "timeout": 20,
        "connection_retries": 3,
        "request_retries": 3,
        "retry_delay": 1,
        "use_ipv6": False,
    }
    if proxy:
        kwargs["proxy"] = proxy
    client = await _to_telethon_safe(
        tdesk,
        dest_base=dest_base,
        flag=flag,
        api=api,
        password=package.two_fa,
        kwargs=kwargs,
        timeout=120 if create_new else 45,
    )
    try:
        await client.disconnect()
    except Exception:
        pass
    try:
        client.session.close()
    except Exception:
        pass
    if not session_file.exists():
        raise ValueError("tdata 转换后未生成 session")
    _write_sidecar_json(package, session_file)
    return session_file


async def convert_tdata_for_account(
    account_id: str,
    dest: Path,
    *,
    create_new: bool = False,
    proxy=None,
):
    package = find_account_package(account_id)
    if not package or package.tdata_dir is None:
        raise ValueError("没有对应的 tdata 目录")

    _TDesktop, _API, UseCurrentSession, CreateNewSession = _opentele_runtime()
    api = _desktop_api_from_meta(package.json_data)
    tdesk = _load_tdesktop(package.tdata_dir, package.two_fa, api=api)
    dest_base = dest.with_suffix("")
    _unlink_session_files(dest)
    flag = CreateNewSession if create_new else UseCurrentSession
    kwargs: dict = {
        "timeout": 20,
        "connection_retries": 3,
        "request_retries": 3,
        "retry_delay": 1,
        "use_ipv6": False,
    }
    if proxy:
        kwargs["proxy"] = proxy
    try:
        client = await _to_telethon_safe(
            tdesk,
            dest_base=dest_base,
            flag=flag,
            api=api,
            password=package.two_fa,
            kwargs=kwargs,
            timeout=120 if create_new else 45,
        )
    except Exception:
        restore_packaged_session(account_id, dest)
        raise
    attach_package_meta(package, dest.stem)
    if create_new:
        return client
    try:
        await client.disconnect()
    except Exception:
        pass
    try:
        client.session.close()
    except Exception:
        pass
    if not dest.exists():
        raise ValueError("tdata 转换后未生成 session")
    return None


async def materialize_package(package: AccountPackage, session_name: str | None = None) -> tuple[Path, str]:
    name = (session_name or "").strip() or package.name
    if package.session_file and package.session_file.exists():
        return package.session_file, "session"
    if package.session_string:
        session_file = _write_session_from_string(package.session_string, _staging_dir() / name)
        _write_sidecar_json(package, session_file)
        return session_file, "session_string"
    if package.tdata_dir:
        session_file = await _convert_tdata_package(package, name)
        return session_file, "tdata"
    raise ValueError("账号包缺少 session / session_string / tdata")


async def convert_tdata_to_session(tdata_path: Path, session_name: str | None = None) -> Path:
    packages = discover_account_packages(tdata_path)
    if len(packages) != 1:
        raise ValueError(f"该路径包含 {len(packages)} 个账号，请使用批量导入")
    session_file, _method = await materialize_package(packages[0], session_name)
    return session_file


async def import_tdata_path(tdata_path: Path, session_name: str | None = None) -> tuple[list[ImportItem], list[ImportItem]]:
    packages = discover_account_packages(tdata_path)
    imported: list[ImportItem] = []
    errors: list[ImportItem] = []
    single_name = session_name if len(packages) == 1 else None
    for package in packages:
        try:
            session_file, method = await materialize_package(package, single_name)
            imported.append(
                ImportItem(
                    name=package.name,
                    method=method,
                    session_file=str(session_file),
                )
            )
        except Exception as exc:
            errors.append(ImportItem(name=package.name, method="", error=str(exc)))
    return imported, errors
