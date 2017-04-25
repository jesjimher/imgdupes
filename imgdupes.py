#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys
import subprocess as sub
import pickle
import argparse
from PIL import Image
import zlib
import hashlib
import tempfile
import shutil
import gi
gi.require_version('GExiv2', '0.10')
from gi.repository.GExiv2 import Metadata
import time
import texttable as tt
from jpegtran import JPEGImage
from StringIO import StringIO
from multiprocessing import Pool
from pprint import pprint

VERSION="1.2"

# Calculates hash of the specified object x. x is a tuple with the format (JPEGImage object,rotation,hash_method)
# This is the function that will be executed in the process pool
def phash(x):
    img=x[0]
    rot=x[1]
    method=x[2]

    # Rotate the image if necessary before calculating hash
    if rot==0:
        data=img.as_blob()
    else:
        data=img.rotate(rot).as_blob()
    try:
        im=Image.open(StringIO(data))
    except IOError:
        sys.stderr.write("    *** Error opening file %s, file will be ignored\n" % path)
        return ["ERR"]

    datstr=im.tobytes()
    # CRC should be faster than MD5 (al least in theory, actually it's about the same since the process is I/O bound)
    if method=="CRC":
        h=zlib.crc32(datstr)
    else:
        # If unknown, use MD5
        h=hashlib.md5(datstr).digest()

    return h

# Calculates all possible hashes for a single file (normal, and all possible rotations)
# Just image data, ignore headers
# Uses a process pool to benefit from multiple cores
def hashcalc(path,pool,method="MD5"):
    rots=[0,90,180,270]
    try:
        img=JPEGImage(path)
        lista=[]
        for rot in rots:
            lista.append((img,rot,method))
    except IOError:
        sys.stderr.write("    *** Error opening file %s, file will be ignored\n" % path)
        return ["ERR"]
    results=pool.map(phash,lista)

    return results

# Writes the specified dict to disk
def writecache(d):
    if not args.clean:
        cache=open(fsigs,'wb')
        pickle.dump(d,cache)
        cache.close()

# Deletes any temporary files
def rmtemps(dirlist):
    for d in dirlist:
        shutil.rmtree(d)

# Print a tag comparison detail, showing differences between provided files
def metadata_comp_table(files):
    # Extract tags for each file
    tags={}
    for f in files:
        exif=Metadata()
        exif.open_path(f)
        tags[f]={(x,exif[x]) for x in exif.get_tags()}
    # Compute common tags intersecting all sets
    commontags=tags[files[0]]
    for f in tags:
        commontags=commontags.intersection(tags[f])
    # Delete common tags for each entry
    for f in tags:
        tags[f]=tags[f]-commontags
    # Print results
    head=["Tag"]+[os.path.basename(x) for x in files]
    tab=[]
    alluniquetags=set()
    for f in tags:
        alluniquetags|=({x[0] for x in tags[f]})
    for t in alluniquetags:
        aux=[t]
        for f in files:
            if t in [x[0] for x in tags[f]]:
                aux.append(dict(tags[f])[t][:200])
            else:
                aux.append("-")
        tab.append(aux)
    t=tt.Texttable()
    t.header(head)
    t.add_rows(tab,header=False)
    t.set_deco(t.HEADER)
    t.set_chars(['-','|','+','-'])
    maxw=len(max(alluniquetags,key=len)) if alluniquetags else 5
    arrw=[maxw]+[25]*len(files)
    t.set_cols_width(arrw)
    print
    print t.draw()
    print "\n(Unique fields only. Common EXIF tags have been omitted)"
    print



# Summarize most relevant image metadata in one line
def metadata_summary(path):
    exif=Metadata()
    exif.open_path(path)
    taglist=exif.get_tags()

    # Date
    date=[]
    if 'Exif.Photo.DateTimeOriginal' in taglist:
        date.append(exif['Exif.Photo.DateTimeOriginal'])
    if 'Xmp.exif.DateTimeOriginal' in taglist:
        date.append(exif['Xmp.exif.DateTimeOriginal'])
    #date.append(time.ctime(os.path.getmtime(path)))
    if len(date)>0:
        date=time.strftime("%d/%m/%Y %H:%M:%S",time.strptime(date[0],"%Y:%m:%d %H:%M:%S"))
    else:
        date=""

    # Orientation
    ori=exif.get('Exif.Image.Orientation',"?")

    # Tags
    tags=[]
    if 'Iptc.Application2.Keywords' in taglist:
        tags.append(exif['Iptc.Application2.Keywords'])
    if 'Xmp.dc.subject' in taglist:
        tags+=exif['Xmp.dc.subject'].split(",")
    if 'Xmp.digiKam.TagsList' in taglist:
        tags+=exif['Xmp.digiKam.TagsList'].split(",")
    if 'Xmp.MicrosoftPhoto.LastKeywordXMP' in taglist:
        tags+=exif['Xmp.MicrosoftPhoto.LastKeywordXMP'].split(",")
    tags=[x.strip() for x in tags]
    tags=list(set(tags))
    tags.sort()

    # Title
    aux=[]
    title=""
    if 'Iptc.Application2.Caption' in taglist:
        aux.append(exif['Iptc.Application2.Caption'])
    if 'Xmp.dc.title' in taglist:
        aux.append(exif['Xmp.dc.title'])
    if 'Iptc.Application2.Headline' in taglist:
        aux.append(exif['Iptc.Application2.Headline'])
    if len(aux)>0:
        title=aux[0]

    # Software
    aux=[]
    soft=""
    if 'Exif.Image.Software' in taglist:
        aux.append(exif['Exif.Image.Software'])
    if 'Iptc.Application2.Program' in taglist:
        aux.append(exif['Iptc.Application2.Program'])
    if len(aux)>0:
        soft=list(set(aux))[0]

    # Shorten title and soft
    if len(title)>13:
        title=title[:10]+"..."
    if len(soft)>15:
        soft=soft[:12]+"..."

    dinfo={"date":date,"orientation":ori,"tags":tags,"title":title,"software":soft}

    return dinfo

# The first, and only argument needs to be a directory
parser=argparse.ArgumentParser(description="Checks for duplicated images in a directory tree. Compares just image data, metadata is ignored, so physically different files may be reported as duplicates if they have different metadata (tags, titles, JPEG rotation, EXIF info...).")
parser.add_argument('directory',help="Base directory to check")
parser.add_argument('-1','--sameline',help="List each set of matches in a single line",action='store_true',required=False)
parser.add_argument('-d','--delete',help="Prompt user for files to preserve, deleting all others",action='store_true',required=False)
parser.add_argument('-c','--clean',help="Don't write to disk signatures cache",action='store_true',required=False)
parser.add_argument('-m','--method',help="Hash method to use. Default is MD5, but CRC might be faster on slower CPUs where process is not I/O bound",default="MD5",choices=["MD5","CRC"],required=False)
parser.add_argument('--version', action='version', version='%(prog)s ' + VERSION)
args=parser.parse_args()

pwd=os.getcwd()

try:
    os.chdir(args.directory)
except:
    sys.stderr.write( "Directory %s doesn't exist\n" % args.directory)
    exit(1)

# Extensiones admitidas (case insensitive)
extensiones=('jpg','jpeg')

# Diccionario con información sobre los ficheros
jpegs={}
# Flag para saber si hay que volver a escribir la caché por cambios
modif=False

# Recuperar información de los ficheros generada previamente, si existe
rootDir='.'
fsigs='.signatures'
if os.path.isfile(fsigs):
    cache=open(fsigs,'rb')
    try:
        sys.stderr.write("Signatures cache detected, loading...\n")
        jpegs=pickle.load(cache)
        cache.close()
	# Clean up non-existing entries
        sys.stderr.write("Cleaning up deleted files from cache...\n")
	jpegs=dict(filter(lambda x:os.path.exists(x[0]),jpegs.iteritems()))
    except (pickle.UnpicklingError,KeyError,EOFError,ImportError,IndexError):
        # Si el fichero no es válido, ignorarlo y marcar que hay que escribir cambios
        jpegs={}
        modif=True
        cache.close()

# Create process pool for parallel hash calculation
pool=Pool()

count=1
for dirName, subdirList, fileList in os.walk(rootDir):
    sys.stderr.write('Exploring %s\n' % dirName)
    for fname in fileList:
        # Update signatures cache every 100 files
        if modif and ((count % 100)==0):
            writecache(jpegs)
            modif=False
        if fname.lower().endswith(extensiones):
            ruta=os.path.join(dirName,fname)
            # Si el fichero no está en la caché, o está pero con tamaño diferente, añadirlo
            if (ruta not in jpegs) or ((ruta in jpegs) and (jpegs[ruta]['size']!=os.path.getsize(ruta))):
                sys.stderr.write("   Calculating hash of %s...\n" % ruta)
                jpegs[ruta]={
                        'name':fname,
                        'dir':dirName,
                        'hash':hashcalc(ruta,pool,args.method),
                        'size':os.path.getsize(ruta)
                        }
                modif=True
                count+=1

# Write hash cache to disk
if modif: writecache(jpegs)

# Check for duplicates

# Create a new dict indexed by hash
# Initialize dict with an empty list for every possible hash
hashes={}
for f in jpegs:
    for h in jpegs[f]['hash']:
        hashes[h]=[]
# Group files with the same hash together
for f in jpegs:
    for h in jpegs[f]['hash']:
        hashes[h].append(jpegs[f])
# Discard hashes without duplicates
dupes={}
for h in hashes:
    if len(hashes[h])>1:
        dupes[h]=hashes[h]
# Delete entries whose hash couldn't be generated, so they're not reported as duplicates
if 'ERR' in dupes: del dupes['ERR']
# Discard duplicated sets (probably a lot if --rotations is activated)
nodupes=[]
for elem in dupes.values():
    if not elem in nodupes:
        nodupes.append(elem)
# Cleanup. Not strictly necessary, but if there're a lot of files these can get quite big
del hashes,dupes

nset=1
tmpdirs=[]
for dupset in nodupes:
    # Add path field (for convenience) and sort by file path
    for d in dupset:
        d.update({"path":os.path.join(d["dir"],d["name"])})
    dupset.sort(key=lambda k:k['path'])
    print
    if args.delete:
        # Calculate best guess for auto mode
        dupaux=[d['path'] for d in dupset]
        # Sort by path length (probably not needed as dupset is already sorted, but just in case)
        dupaux.sort(key=len)
        # Best guess is the entry with most tags, or the one with shorter path if tags are equal (due to previous sort)
        bestguess=dupaux.index(max(dupaux,key=lambda k:len(metadata_summary(k)["tags"])))

        optselected=False
        while not optselected:
            # Prompt for which duplicated file to keep, delete the others
            t=tt.Texttable()
            t.set_cols_align(["c","r","l","l","l","l","l","l"])
            t.set_chars(['-','|','+','-'])
            t.set_deco(t.HEADER)
            # Get terminal width in order to set column sizes.
            colsize=int(os.popen('stty size', 'r').read().split()[1])
            t.set_cols_width([1,1,50,20,11,10,10,colsize-103-30])

            rws=[["","#","file","date","orientation","title","software","tags"]]
            for i in range(len(dupset)):
                aux=dupset[i]
                md=metadata_summary(aux["path"])
                rws.append(["*" if i==bestguess else " ",i+1,dupset[i]["path"],md["date"],md["orientation"],md["title"],md["software"],", ".join(md["tags"])])
            t.add_rows(rws)
            print("\n"+t.draw())
            answer=raw_input("\nSet %d of %d, preserve files [%d - %d, all, auto, show, detail, help, quit] (default: auto): " % (nset,len(nodupes),1,len(dupset)))
            if answer in ["detail","d"]:
                # Show detailed differences in EXIF tags
                filelist=[os.path.join(x['dir'],x['name']) for x in dupset]
                metadata_comp_table(filelist)
            elif answer in ["help","h"]:
                print
                print "[0-9]:    Keep the selected file, delete the rest"
                print "(a)ll:    Keep all files, don't delete anything"
                print "auto:     Keep picture with most tags, or shorter path. If equal, don't delete anything"
                print "(s)how:   Copy duplicated files to a temporary directory and open in a file manager window (desktop default)"
                print "(d)etail: Show a detailed table with metadata differences between files"
                print "(h)elp:   Show this screen"
                print "(q)uit:   Exit program"
                print
            elif answer in ["quit","q"]:
                # If asked, write changes, delete temps and quit
                if modif: writecache(jpegs)
                rmtemps(tmpdirs)
                exit(0)
            elif answer in ["show","s"]:
                # Create a temporary directory, copy duplicated files and open a file manager
                tmpdir=tempfile.mkdtemp()
                tmpdirs.append(tmpdir)
                for i in range(len(dupset)):
                    p=dupset[i]['path']
                    ntemp="%d_%s" % (i,dupset[i]['name'])
                    shutil.copyfile(p,os.path.join(tmpdir,ntemp))
                sub.Popen(["xdg-open",tmpdir],stdout=None,stderr=None)
            elif answer in ["all","a"]:
                # Don't delete anything
                sys.stderr.write("Skipping deletion, all duplicates remain\n")
                optselected=True
            elif answer in ["auto",""]:
                answer=bestguess
            else:
                # If it's no option, assume it's a number and convert it to an array index
                answer=int(answer)-1
            # If we have a valid number as an answer, delete all but the selected file
            try:
                answer=int(answer)
                for i in range(len(dupset)):
                    if i!=answer:
                        p=dupset[i]['path']
                        os.remove(p)
                        del jpegs[p]
                        modif=True
                sys.stderr.write("Kept %s, deleted others\n" % (dupset[answer]["name"]))
                optselected=True
            except ValueError:
                pass
        nset+=1
    else:
        # Just show duplicates
        for f in dupset:
            print f['path'],
            if not args.sameline:
                print "\n",

# Final update of the cache in order to remove signatures of deleted files
if modif: writecache(jpegs)

# Delete temps
rmtemps(tmpdirs)

# Restore directory
os.chdir(pwd)
