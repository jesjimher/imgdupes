#!/usr/bin/python3
# -*- coding: utf-8 -*-
import argparse
import hashlib
import os
import pickle
import shutil
import subprocess as sub
import sys
import tempfile
import time
import zlib
from collections import defaultdict
from io import BytesIO
from multiprocessing import Pool
from subprocess import DEVNULL, check_call

import gi
import texttable as tt
from jpegtran import JPEGImage
from PIL import Image

gi.require_version("GExiv2", "0.10")
from gi.repository.GExiv2 import Metadata

VERSION = "2.1"

JPEG_CACHE_FILE = "/.signatures"


# Calculates hash of the specified object x. x is a tuple with the format
# (JPEGImage object,rotation,hash_method)
# This is the function that will be executed in the process pool
def phash(x):
    img = x[0]
    rot = x[1]
    method = x[2]

    # Rotate the image if necessary before calculating hash
    if rot == 0:
        data = img.as_blob()
    else:
        data = img.rotate(rot).as_blob()
    try:
        im = Image.open(BytesIO(data))
    except IOError:
        sys.stderr.write(
            "    *** Error reading image data, it will be ignored\n"
        )
        return ["ERR"]

    datstr = im.tobytes()
    # CRC should be faster than MD5 (al least in theory,
    # actually it's about the same since the process is I/O bound)
    if method == "CRC":
        h = zlib.crc32(datstr)
    else:
        # If unknown, use MD5
        h = hashlib.md5(datstr).digest()

    return h


# Calculates all possible hashes for a single file
# (normal, and all possible rotations)
# Just image data, ignore headers
# Uses a process pool to benefit from multiple cores
def hashcalc(path, pool, method="MD5", havejpeginfo=False):
    rotations = [0, 90, 180, 270]

    # Check file integrity using jpeginfo if available
    if havejpeginfo:
        try:
            check_call(
                ["jpeginfo", "-c", path], stdout=DEVNULL, stderr=DEVNULL
            )
        except:
            sys.stderr.write("     Corrupt JPEG, skipping\n")
            return ["ERR"]

    try:
        img = JPEGImage(path)
    except IOError:
        sys.stderr.write(
            "    *** Error opening file %s, file will be ignored\n" % path
        )
        return ["ERR"]
    else:
        lista = [(img, rot, method) for rot in rotations]

    try:
        results = pool.map(phash, lista)
    except:
        sys.stderr.write(
            "    *** Error reading image data, it will be ignored\n"
        )
        return ["ERR"]
    del lista
    del img
    return results


# Writes the specified dict to disk
def writecache(d, clean, fsigs):
    if not clean:
        cache = open(fsigs, "wb")
        pickle.dump(d, cache)
        cache.close()


# Deletes any temporary files
def rmtemps(dirlist):
    for d in dirlist:
        shutil.rmtree(d)


# Print a tag comparison detail, showing differences between provided files
def metadata_comp_table(files):
    # Extract tags for each file
    tags = {}
    for f in files:
        exif = Metadata()
        exif.open_path(f)
        tags[f] = {(x, exif[x]) for x in exif.get_tags()}
    # Compute common tags intersecting all sets
    commontags = tags[files[0]]
    for f in tags:
        commontags = commontags.intersection(tags[f])
    # Delete common tags for each entry
    for f in tags:
        tags[f] = tags[f] - commontags
    # Print results
    head = ["Tag"] + [os.path.basename(x) for x in files]
    tab = []
    alluniquetags = set()
    for f in tags:
        alluniquetags |= {x[0] for x in tags[f]}
    for t in alluniquetags:
        aux = [t]
        for f in files:
            if t in [x[0] for x in tags[f]]:
                aux.append(dict(tags[f])[t][:200])
            else:
                aux.append("-")
        tab.append(aux)
    t = tt.Texttable()
    t.header(head)
    t.add_rows(tab, header=False)
    t.set_deco(t.HEADER)
    t.set_chars(["-", "|", "+", "-"])
    maxw = len(max(alluniquetags, key=len)) if alluniquetags else 5
    arrw = [maxw] + [25] * len(files)
    t.set_cols_width(arrw)
    print()
    print(t.draw())
    print("\n(Unique fields only. Common EXIF tags have been omitted)")
    print()


# Summarize most relevant image metadata in one line
def metadata_summary(path):
    exif = Metadata()
    exif.open_path(path)
    taglist = exif.get_tags()

    # Date
    date = []
    if "Exif.Photo.DateTimeOriginal" in taglist:
        date.append(exif["Exif.Photo.DateTimeOriginal"])
    if "Xmp.exif.DateTimeOriginal" in taglist:
        date.append(exif["Xmp.exif.DateTimeOriginal"])
    # date.append(time.ctime(os.path.getmtime(path)))
    if len(date) > 0:
        date = time.strftime(
            "%d/%m/%Y %H:%M:%S", time.strptime(date[0], "%Y:%m:%d %H:%M:%S")
        )
    else:
        date = ""

    # Orientation
    ori = exif.get("Exif.Image.Orientation", "?")

    # Tags
    tags = []
    if "Iptc.Application2.Keywords" in taglist:
        tags.append(exif["Iptc.Application2.Keywords"])
    if "Xmp.dc.subject" in taglist:
        tags += exif["Xmp.dc.subject"].split(",")
    if "Xmp.digiKam.TagsList" in taglist:
        tags += exif["Xmp.digiKam.TagsList"].split(",")
    if "Xmp.MicrosoftPhoto.LastKeywordXMP" in taglist:
        tags += exif["Xmp.MicrosoftPhoto.LastKeywordXMP"].split(",")
    tags = [x.strip() for x in tags]
    tags = list(set(tags))
    tags.sort()

    # Title
    aux = []
    title = ""
    if "Iptc.Application2.Caption" in taglist:
        aux.append(exif["Iptc.Application2.Caption"])
    if "Xmp.dc.title" in taglist:
        aux.append(exif["Xmp.dc.title"])
    if "Iptc.Application2.Headline" in taglist:
        aux.append(exif["Iptc.Application2.Headline"])
    if len(aux) > 0:
        title = aux[0]

    # Software
    aux = []
    soft = ""
    if "Exif.Image.Software" in taglist:
        aux.append(exif["Exif.Image.Software"])
    if "Iptc.Application2.Program" in taglist:
        aux.append(exif["Iptc.Application2.Program"])
    if len(aux) > 0:
        soft = list(set(aux))[0]

    # Shorten title and soft
    if len(title) > 13:
        title = title[:10] + "..."
    if len(soft) > 15:
        soft = soft[:12] + "..."

    dinfo = {
        "date": date,
        "orientation": ori,
        "tags": tags,
        "title": title,
        "software": soft,
    }

    return dinfo

def parse_cmdline():
    # The first, and only mandatory argument needs to be a directory
    parser = argparse.ArgumentParser(
        description="Checks for duplicated images in a directory tree. Compares just image data, metadata is ignored, so physically different files may be reported as duplicates if they have different metadata (tags, titles, JPEG rotation, EXIF info...)."
    )
    parser.add_argument("directory", help="Base directory to check. When filtering against library folder, this is the directory from which files will be deleted.")
    parser.add_argument(
        "--library",
        help="Optional. If library directory exists, files from directory that also exist in library, will be deleted from directory.",
        required=False,
    )
    parser.add_argument(
        "-1",
        "--sameline",
        help="List each set of matches in a single line",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-d",
        "--delete",
        help="Prompt user for files to preserve, deleting all others",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-a",
        "--auto",
        help="If -d or --delete flag is enabled, always select the 'auto' action to select the file to preserve.",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-c",
        "--clean",
        help="Don't write to disk signatures cache",
        action="store_true",
        required=False,
    )
    parser.add_argument(
        "-m",
        "--method",
        help="Hash method to use. Default is MD5, but CRC might be faster on slower CPUs where process is not I/O bound",
        default="MD5",
        choices=["MD5", "CRC"],
        required=False,
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + VERSION
    )
    return parser.parse_args()


def is_jpeginfo_installed():
    havejpeginfo = True
    try:
        check_call(["jpeginfo", "--version"], stdout=DEVNULL, stderr=DEVNULL)
        sys.stderr.write(
            "jpeginfo found in system, will be used to check JPEG file integrity\n"
        )
    except (sub.CalledProcessError, FileNotFoundError):
        sys.stderr.write(
            "jpeginfo not found in system, please install it for smarter JPEG file integrity detection\n"
        )
        havejpeginfo = False
    return havejpeginfo


def load_hashes(fsigs):
    # Reload hash data from previous run, if it exists

    jpegs = {}
    # This flag indicates if there is anything to update in the cache
    modif = False

    if os.path.isfile(fsigs):
        cache = open(fsigs, "rb")
        try:
            sys.stderr.write("Signatures cache detected, loading...\n")
            jpegs = pickle.load(file=cache)
            cache.close()
            # Clean up non-existing entries
            sys.stderr.write("Updating cache, removing deleted files from cache...\n")
            jpegs = dict(
                [x for x in iter(jpegs.items()) if os.path.exists(x[0])]
            )
        except (
            pickle.UnpicklingError,
            KeyError,
            EOFError,
            ImportError,
            IndexError,
        ):
            # Si el fichero no es válido,
            # ignorarlo y marcar que hay que escribir cambios
            jpegs = {}
            modif = True
            cache.close()
    return jpegs, modif


def calculate_hashes(rootDir, jpegs, modif, havejpeginfo, fsigs, clean, hash_method):
    # Create process pool for parallel hash calculation
    pool = Pool()
    # Allowed extensions (case insensitive)
    extensions = ("jpg", "jpeg")
    count = 0
    for dirName, subdirList, fileList in os.walk(rootDir):
        sys.stderr.write("Exploring %s\n" % dirName)
        for fname in fileList:
            # Update signatures cache every 100 files
            if modif and ((count % 100) == 0):
                writecache(jpegs, clean, fsigs)
                modif = False
            if fname.lower().endswith(extensions):
                filepath = os.path.join(dirName, fname)
                # Si el fichero no está en la caché,
                # o está pero con tamaño diferente, añadirlo
                if (filepath not in jpegs) or (
                    (filepath in jpegs)
                    and (jpegs[filepath]["size"] != os.path.getsize(filepath))
                ):
                    sys.stderr.write("   Calculating hash of %s\n" % filepath)
                    jpegs[filepath] = {
                        "name": fname,
                        "dir": dirName,
                        "hash": hashcalc(
                            filepath, pool, hash_method, havejpeginfo
                        ),
                        "size": os.path.getsize(filepath),
                    }
                    modif = True
                    count += 1
    pool.close()
    return jpegs, modif, count


def get_hashes(rootDir, havejpeginfo, hash_method, clean):
    fsigs = rootDir + JPEG_CACHE_FILE
    jpegs, modif = load_hashes(fsigs)
    jpegs, modif, count = calculate_hashes(rootDir, jpegs, modif, havejpeginfo, fsigs, clean, hash_method)
    # Write hash cache to disk
    if modif:
        writecache(jpegs, clean, fsigs)
    return jpegs, modif, count


def get_terminal_width():
    # Get terminal width in order to set column sizes, width must be at least 134
    colsize = int(os.popen("stty size", "r").read().split()[1])
    assert 133 < colsize, "Terminial width must be at least 134"
    return colsize


def remove_duplicates(args):
    if args.auto and not args.delete:
        sys.stderr.write(
            "'-a' or '--auto' only makes sense when deleting files with '-d' or '--delete'\n"
        )
        exit(1)

    # Check if jpeginfo is installed
    havejpeginfo = is_jpeginfo_installed()

    pwd = os.getcwd()
    try:
        os.chdir(args.directory)
    except:
        sys.stderr.write("Directory %s doesn't exist\n" % args.directory)
        exit(1)

    colsize = get_terminal_width()

    rootDir = "."
    jpegs, modif, count = get_hashes(rootDir, havejpeginfo, args.method, args.clean)
    fsigs = rootDir + JPEG_CACHE_FILE
    # Check for duplicates

    # Create a new dict indexed by hash
    hashes = defaultdict(list)
    
    # Group files with the same hash together
    for f in jpegs:
        for h in jpegs[f]["hash"]:
            # Skip entries whose hash couldn't be generated, so they're not reported as duplicates
            if "ERR" != h:
                hashes[h].append(jpegs[f])

    # Discard hashes without duplicates
    dupes = {}
    for h in hashes:
        if len(hashes[h]) > 1:
            dupes[h] = hashes[h]

    # Discard duplicated sets (probably a lot if --rotations is activated)
    nodupes = []
    for elem in list(dupes.values()):
        if not elem in nodupes:
            nodupes.append(elem)
    # Cleanup. Not strictly necessary,
    # but if there're a lot of files these can get quite big
    del hashes, dupes

    seperator = " " if args.sameline else "\n"

    nset = 1
    tmpdirs = []
    for dupset in nodupes:
        # Add path field (for convenience) and sort by file path
        for d in dupset:
            d.update({"path": os.path.join(d["dir"], d["name"])})
        dupset.sort(key=lambda k: k["path"])
        print()
        if args.delete:
            # Calculate best guess for auto mode
            dupaux = [d["path"] for d in dupset]
            # Sort by path length
            # (probably not needed as dupset is already sorted,
            # but just in case)
            dupaux.sort(key=len)
            # Best guess is the entry with most tags,
            # or the one with shorter path if tags are equal
            # (due to previous sort)
            bestguess = dupaux.index(
                max(dupaux, key=lambda k: len(metadata_summary(k)["tags"]))
            )

            optselected = False
            while not optselected:
                # Prompt for which duplicated file to keep, delete the others
                t = tt.Texttable()
                t.set_cols_align(["c", "r", "l", "l", "l", "l", "l", "l"])
                t.set_chars(["-", "|", "+", "-"])
                t.set_deco(t.HEADER)
                
                t.set_cols_width(
                    [1, 1, 50, 20, 11, 10, 10, colsize - 103 - 30]
                )

                rws = [
                    [
                        "",
                        "#",
                        "file",
                        "date",
                        "orientation",
                        "title",
                        "software",
                        "tags",
                    ]
                ]
                for i in range(len(dupset)):
                    aux = dupset[i]
                    md = metadata_summary(aux["path"])
                    rws.append(
                        [
                            "*" if i == bestguess else " ",
                            i + 1,
                            dupset[i]["path"],
                            md["date"],
                            md["orientation"],
                            md["title"],
                            md["software"],
                            ", ".join(md["tags"]),
                        ]
                    )
                t.add_rows(rws)
                print(("\n" + t.draw()))
                if args.auto:
                    answer = "auto"
                else:
                    answer = input(
                        "\nSet %d of %d, preserve files [%d - %d, all, auto, show, detail, help, quit] (default: auto): "
                        % (nset, len(nodupes), 1, len(dupset))
                    )
                if answer in ["detail", "d"]:
                    # Show detailed differences in EXIF tags
                    filelist = [
                        os.path.join(x["dir"], x["name"]) for x in dupset
                    ]
                    metadata_comp_table(filelist)
                elif answer in ["help", "h"]:
                    print()
                    print("[0-9]:    Keep the selected file, delete the rest")
                    print("(a)ll:    Keep all files, don't delete anything")
                    print(
                        "auto:     Keep picture with most tags, or shorter path. If equal, don't delete anything"
                    )
                    print(
                        "(s)how:   Copy duplicated files to a temporary directory and open in a file manager window (desktop default)"
                    )
                    print(
                        "(d)etail: Show a detailed table with metadata differences between files"
                    )
                    print("(h)elp:   Show this screen")
                    print("(q)uit:   Exit program")
                    print()
                elif answer in ["quit", "q"]:
                    # If asked, write changes, delete temps and quit
                    if modif:
                        writecache(jpegs, args.clean, fsigs)
                    rmtemps(tmpdirs)
                    exit(0)
                elif answer in ["show", "s"]:
                    # Create a temporary directory,
                    # copy duplicated files and open a file manager
                    tmpdir = tempfile.mkdtemp()
                    tmpdirs.append(tmpdir)
                    for i in range(len(dupset)):
                        p = dupset[i]["path"]
                        ntemp = "%d_%s" % (i, dupset[i]["name"])
                        shutil.copyfile(p, os.path.join(tmpdir, ntemp))
                    sub.Popen(["xdg-open", tmpdir], stdout=None, stderr=None)
                elif answer in ["all", "a"]:
                    # Don't delete anything
                    sys.stderr.write(
                        "Skipping deletion, all duplicates remain\n"
                    )
                    optselected = True
                elif answer in ["auto", ""]:
                    answer = bestguess
                else:
                    # If it's no option, assume it's a number
                    # and convert it to an array index
                    answer = int(answer) - 1
                # If we have a valid number as an answer,
                # delete all but the selected file
                try:
                    answer = int(answer)
                    for i in range(len(dupset)):
                        if i != answer:
                            p = dupset[i]["path"]
                            os.remove(p)
                            del jpegs[p]
                            modif = True
                    sys.stderr.write(
                        "Kept %s, deleted others\n" % (dupset[answer]["name"])
                    )
                    optselected = True
                except ValueError:
                    pass
            nset += 1
        else:
            # Just print the duplicates
            print(seperator.join([f["path"] for f in dupset]))


    # Final update of the cache in order to remove signatures of deleted files
    if modif:
        writecache(jpegs, args.clean, fsigs)

    # Delete temps
    rmtemps(tmpdirs)

    # Restore directory
    os.chdir(pwd)


def filter_folder(tofilter, library, delete, hash_method="MD5", clean=False):
    """ Scan the tofilter folder and remove any jpegs from there that exist in the library folder as well, ignoring metadata.
        Nothing will be deleted from the library folder.
    """
    
    havejpeginfo = is_jpeginfo_installed()
    
    # calculate hashes or load from file for tofilter dir
    # calculate hashes or load from file for library dir


    jpegs_tofilter, _ , tofilter_count = get_hashes(tofilter, havejpeginfo, hash_method, clean)  # jpegs, modif, count
    jpegs_library, _ , library_count = get_hashes(library, havejpeginfo, hash_method, clean)    # jpegs, modif, count
    hashes_library = [h for jpeg in jpegs_library.values() for h in jpeg['hash']]

    if not delete:
        sys.stderr.write("No files will be deleted, only printed instead. Run with --delelte to delete")
    sys.stderr.write("Files to be deleted:")

    delete_count = 0
    # for each hash in tofilter dir, if it exist in library, delete the corresponding file from tofilter dir
    for fpath, jpeg in jpegs_tofilter.items():
        for h in jpeg['hash']:
            if h in hashes_library:
                delete_count += 1
                print(jpeg['name'])
                if delete:
                    os.remove(fpath)
                break

    # print summary
    sys.stderr.write(f"nr hashes calculated- tofilter: {tofilter_count},  library: {library_count}")
    sys.stderr.write(f"Nr files deleted {delete_count}")


def main():
    args = parse_cmdline()
    if args.library is not None:
        filter_folder(args.directory, args.library, args.delete, args.method, args.clean)
    else:
        remove_duplicates(args)


# Execute main if called as a script
if __name__ == "__main__":
    main()
