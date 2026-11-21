#!/usr/bin/env python3
"""R66: one-time LOCAL owner-only consistent recovery snapshot helper for R65.

Imported ONLY by R65 after original VC, Beacon and Besu have ALL stopped.
No remote transfers, screenshots, uploads or key display. Single archive
contains original private owner state (including validator signing/slashing
material), kept on same VM in new mode-0700 directory with mode-0600 tar.
Read-only source scan and full member-content integrity verification; output
only nonsecret status, counts, and snapshot root directory (no key material).
The operator must protect/move an offline encrypted copy separately.
"""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import stat
import tarfile

class R66Refused(ValueError):
    pass

MAX_FILES=250_000
MIN_SPARE=64*1024*1024
ROOT_FOLDER_NAME="owner-private"
SNAPSHOT_DIR_NAME="sse-r65-consistent-recovery-local-private"
ARCHIVE_NAME="original-chain31340-state.tar"

def checked_files(owner:Path)->tuple[list[Path],int]:
    """Refuse symlinks, external paths, devices, FIFOs and socket files."""
    if owner.is_symlink() or not owner.is_dir():
        raise R66Refused("original private owner directory unsafe")
    st=owner.stat()
    if stat.S_IMODE(st.st_mode)!=0o700:
        raise R66Refused("original owner directory must remain private mode 0700")
    paths=[]
    total=0
    for root, dirs, files in os.walk(owner,topdown=True,followlinks=False):
        for name in dirs+files:
            p=Path(root)/name
            if len(paths)>=MAX_FILES:
                raise R66Refused("original owner state exceeds bounded file count")
            metadata=p.lstat()
            if not (stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)):
                raise R66Refused("original private owner tree contains unexpected nonregular path")
            if os.path.commonpath((str(owner),str(p.resolve(strict=True))))!=str(owner):
                raise R66Refused("original owner path resolves outside original private root")
            if stat.S_ISREG(metadata.st_mode):
                total+=metadata.st_size
            paths.append(p)
    if total<=0:
        raise R66Refused("original owner data unexpectedly empty")
    return paths,total

def digest_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk=f.read(1024*1024)
            if not chunk:break
            h.update(chunk)
    return h.hexdigest()

def require_stopped_docker(names:tuple[str,str,str])->None:
    """Source helper may never snapshot live signing or database files."""
    import subprocess
    if names!=("sse31340-g2-el-r40","sse31340-g2-bn","sse31340-g2-vc"):
        raise R66Refused("exactly verified original EL, BN and VC required")
    for name in names:
        try:
            result=subprocess.run(
                ["sudo","-n","docker","inspect","--format","{{.State.Running}}",name],
                capture_output=True,text=True,timeout=15,check=False
            )
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise R66Refused("cannot confirm original signer/clients stopped") from exc
        if result.returncode or result.stdout.strip()!="false":
            raise R66Refused("original signer and both databases must be stopped for snapshot")

def safe_tar_entry(item:tarfile.TarInfo)->tarfile.TarInfo:
    if not item.isdir() and not item.isfile():
        raise R66Refused("snapshot refuses symbolic links and special file types")
    if item.name.startswith("/") or ".." in Path(item.name).parts:
        raise R66Refused("snapshot forbids nonrelative or traversing archive paths")
    return item

def snapshot_consistent_original_state(
    owner:Path, original_clients:tuple[str,str,str]
)->dict:
    """Backup original private owner state before any EL/BN replacement.

    Precondition: user already separately approved maintenance + offline
    recoverable backups and R65 already stopped original VC, BN and EL.
    No restoring, deleting, moving or modifying the owner private directory.
    """
    owner=owner.resolve(strict=True)
    require_stopped_docker(original_clients)
    paths,total=checked_files(owner)
    if owner==Path("/") or owner.name!="sse-r35-chain31340-g2-private":
        raise R66Refused("snapshot limited to original audited chain31340 owner tree")
    output=owner.parent/SNAPSHOT_DIR_NAME
    if output.is_symlink() or output.exists():
        raise R66Refused("one-time snapshot already exists; do not overwrite or rerun")
    free=shutil.disk_usage(owner.parent).free
    if free < total*2 + MIN_SPARE:
        raise R66Refused("not enough local disk space for validated consistent recovery snapshot")
    old_umask=os.umask(0o077)
    try:
        output.mkdir(mode=0o700)
        archive=output/ARCHIVE_NAME
        fd=os.open(archive,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,"wb") as file_handle:
            with tarfile.open(fileobj=file_handle,mode="w:") as tf:
                tf.add(owner,arcname=ROOT_FOLDER_NAME,recursive=True,filter=safe_tar_entry)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        if stat.S_IMODE(archive.stat().st_mode)!=0o600:
            raise R66Refused("local owner recovery archive permissions unsafe")
        # Read EVERY stored regular member and compare with the still-stopped
        # original source. This detects missing/short/corrupted snapshot bytes,
        # unlike merely checking tar header listings.
        count=0
        verified_bytes=0
        with tarfile.open(archive,mode="r:") as tf:
            for member in tf:
                safe_tar_entry(member)
                if not member.isfile():
                    continue
                if not member.name.startswith(ROOT_FOLDER_NAME+"/"):
                    raise R66Refused("snapshot archive member root unexpected")
                rel=member.name[len(ROOT_FOLDER_NAME)+1:]
                source=owner/rel
                if not source.is_file() or source.is_symlink():
                    raise R66Refused("snapshot source file changed during archive verification")
                obj=tf.extractfile(member)
                if obj is None:
                    raise R66Refused("snapshot stored file cannot be read")
                h=hashlib.sha256()
                with obj:
                    while True:
                        chunk=obj.read(1024*1024)
                        if not chunk:break
                        h.update(chunk)
                if h.hexdigest()!=digest_file(source) or member.size!=source.stat().st_size:
                    raise R66Refused("consistent owner snapshot does not match source bytes")
                count+=1
                verified_bytes+=member.size
        expected=sum(p.is_file() for p in paths)
        if count!=expected or verified_bytes!=total:
            raise R66Refused("original owner recovery archive incomplete")
        return {
            "consistentStoppedOwnerSnapshotVerified":True,
            "originalOwnerFilesVerified":count,
            "originalOwnerFileBytesVerified":verified_bytes,
            "recoveryArchiveLocalPermissionMode0600":True,
            "recoveryDirectoryLocalPermissionMode0700":True,
            "archiveContainsSensitiveSignerMaterial":True,
            "archiveMustBeEncryptedAndBackedUpOfflineByOwner":True,
            "snapshotArchiveNeverUploadedOrContentsDisplayed":True,
            "originalOwnerDataUnmodifiedBySnapshot":True,
        }
    except (OSError,tarfile.TarError,ValueError) as exc:
        raise R66Refused("local original owner recovery snapshot incomplete; keep original data") from exc
    finally:
        os.umask(old_umask)
