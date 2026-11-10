"""Bounded, read-only inventory of untrusted Skills ZIP files."""
from pathlib import Path
from pathlib import PurePosixPath
import hashlib
import stat
import zipfile

class SkillArchiveError(ValueError):
    pass

def inventory(path, *, max_files=10000, max_total_bytes=100_000_000, max_member_bytes=2_000_000):
    skills = []
    seen = set()
    total = 0
    with zipfile.ZipFile(Path(path)) as archive:
        infos = archive.infolist()
        if len(infos) > max_files:
            raise SkillArchiveError("too many members")
        for item in infos:
            name = item.filename
            parts = name.split("/")
            if (not name or name.startswith("/") or "\\" in name or "\x00" in name
                or any(p in ("", ".", "..") for p in parts[:-1])
                or parts[-1] in (".", "..") or ":" in parts[0]):
                raise SkillArchiveError("unsafe path")
            key = str(PurePosixPath(name)).casefold()
            if key in seen:
                raise SkillArchiveError("duplicate path")
            seen.add(key)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or (mode and stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise SkillArchiveError("unsupported file type")
            total += item.file_size
            if total > max_total_bytes:
                raise SkillArchiveError("archive too large")
            if item.is_dir() or parts[-1] != "SKILL.md":
                continue
            if item.file_size > max_member_bytes:
                raise SkillArchiveError("skill too large")
            with archive.open(item) as stream:
                data = stream.read(max_member_bytes + 1)
            if len(data) > max_member_bytes:
                raise SkillArchiveError("skill too large")
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SkillArchiveError("invalid UTF-8") from exc
            skills.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"skill_count": len(skills), "skills": sorted(skills, key=lambda x: x["path"])}
