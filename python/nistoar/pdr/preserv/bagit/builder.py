"""
Tools for building a NIST Preservation bags
"""
from __future__ import print_function, absolute_import
import os, errno, logging, re, json, pkg_resources, textwrap, datetime
import pynoid as noid
from shutil import copy as filecopy, rmtree
from copy import deepcopy
from collections import Mapping, Sequence, OrderedDict
from urllib import quote as urlencode

from .. import (SIPDirectoryError, SIPDirectoryNotFound, 
                ConfigurationException, StateException, PODError)
from .exceptions import BagProfileError, BagWriteError
from .. import PreservationSystem, read_nerd, read_pod, write_json
from ...utils import build_mime_type_map, checksum_of, measure_dir_size
from ....nerdm.exceptions import (NERDError, NERDTypeError)
from ....nerdm.convert import PODds2Res
from ....id import PDRMinter
from ... import def_jq_libdir, def_etc_dir
from ...config import load_from_file, merge_config
from .bag import NISTBag
from .exceptions import BadBagRequest
from .validate.nist import NISTAIPValidator

from multibag import open_headbag

NORM=15  # Log Level for recording normal activity
logging.addLevelName(NORM, "NORMAL")
log = logging.getLogger(__name__)

DEF_BAGLOG_FORMAT = "%(asctime)s %(levelname)s: %(message)s"

DEF_MBAG_VERSION = "0.2"

POD_FILENAME = "pod.json"
NERDMD_FILENAME = "nerdm.json"
FILEMD_FILENAME = NERDMD_FILENAME
RESMD_FILENAME  = NERDMD_FILENAME
COLLMD_FILENAME = NERDMD_FILENAME

ANNOT_FILENAME = "annot.json"
FILEANNOT_FILENAME = ANNOT_FILENAME
RESANNOT_FILENAME  = ANNOT_FILENAME
COLLANNOT_FILENAME = ANNOT_FILENAME

NERD_PRE = "nrd"
NERDPUB_PRE = "nrdp"
NERDM_SCH_ID_BASE = "https://data.nist.gov/od/dm/nerdm-schema/"
NERDMPUB_SCH_ID_BASE = "https://data.nist.gov/od/dm/nerdm-schema/pub/"
NERDM_SCH_VER = "v0.2"
NERDMPUB_SCH_VER = NERDM_SCH_VER
NERDM_SCH_ID = NERDM_SCH_ID_BASE + NERDM_SCH_VER + "#"
NERDMPUB_SCH_ID = NERDMPUB_SCH_ID_BASE + NERDMPUB_SCH_VER + "#"
NERD_DEF = NERDM_SCH_ID + "/definitions/"
NERDPUB_DEF = NERDMPUB_SCH_ID + "/definitions/"
DATAFILE_TYPE = NERDPUB_PRE + ":DataFile"
DOWNLOADABLEFILE_TYPE = NERDPUB_PRE + ":DownloadableFile"
SUBCOLL_TYPE = NERDPUB_PRE + ":Subcollection"
NERDM_CONTEXT = "https://data.nist.gov/od/dm/nerdm-pub-context.jsonld"
DISTSERV = "https://data.nist.gov/od/ds/"
DEF_MERGE_CONV = "midas0"

class BagBuilder(PreservationSystem):
    """
    A class for building up and populating a BagIt bag compliant with the 
    NIST Profile.

    This class can take a configuration dictionary on construction; the 
    following properties are supported:
    :prop log_filename str ("preserv.log"):  the name to give to the logfile 
                              to embed into the output bag
    :prop bag_log_format str:  a format string used to format the embedded
                              log file.
    :prop id_minter dict ({}):  a set of properties to pass to an IDMinter
                              object upon creation (if a minter is not 
                              provided).
    :prop jq_lib       str:  the full path to the JQ transform library 
                              directory; if not set, the directory is 
                              searched for in a few typical places.
    :prop merge_etc    str:  the full path to directory containing the NERDm
                              merger annotated schemas;  if not set, the 
                              directory is searched for in a few typical places.
    :prop merge_convention str ("dev"): the merge convention name to 
                                 use to merge annotation data into the primary
                                 NERDm metadata.
    :prop validate_id bool (True):  If True, an identifier provided to the 
                              constructor will be checked for transcription
                              error.
    :prop copy_on_link_failure bool (True):  If True, then when moving datafiles 
                              to output bag via a hardlink, then the file 
                              will get copied if the linking fails.  
    :prop file_md_extract dict (None):  a set of parameters to pass to the 
                              configured file metadata extractor.
    :prop json_indent int (4):  The amount of indent to use when exporting JSON
                              data
    :prop ensure_nerdm_type_on_add bool (True):  if True, make sure that the 
                         resource metadata has a recognized value for "_schema".
    """

    def __init__(self, parentdir, bagname, config=None, id=None, minter=None,
                 logger=None):
        """
        create the Builder to build a bag with a given name

        :param parentdir str:  the directory that will contain the bag's root 
                                 directory
        :param bagname str:    the name to give to the bag
        :param config dict:    a dictionary of configuration data (see class
                                 documentation for supported parameters). 
        :param id      str:    the ARK identifier to assign to this record.  If 
                                 None, one will be minted automatically when it
                                 is needed.  
        :param minter IDMinter: an IDMinter to use to mint a new identifier to 
                                 assign to this dataset.  
        :param logger Logger:  a Logger object to send messages to.  This will 
                                 used to send messages to a preservation log
                                 inside the bag.  
        """
        if not os.path.exists(parentdir):
            raise StateException("Bag Workspace dir does not exist: " +
                                 parentdir, sys=self)
            
        self._name = bagname
        self._pdir = parentdir
        self._bagdir = os.path.join(self._pdir, self._name)
        self._mbagver = DEF_MBAG_VERSION
        self._bag = None

        if not logger:
            logger = log
        self.log = logger
        self.log.setLevel(NORM)
        
        if not config:
            config = {}
        self.cfg = self._merge_def_config(config)
        
        self._id = self._fix_id(id)
        self._ediid = None
        self._logname = self.cfg.get('log_filename', 'preserv.log')
        self._loghdlr = None
        self._mimetypes = None
        self._mbtagdir = None
        self._distbase = self.cfg.get('distrib_service_baseurl', DISTSERV)
        if not self._distbase.endswith('/'):
            self._distbase += '/'

        if not minter:
            cfg = self.cfg.get('id_minter', {})
            minter = PDRMinter(self._pdir, cfg)
            if not os.path.exists(minter.registry.store):
                self.log.warning("Creating new ID minter for bag, "+self._name)
        self._minter = minter
        
        jqlib = self.cfg.get('jq_lib', def_jq_libdir)
        self.pod2nrd = PODds2Res(jqlib)

# Not sure why this was added originally, but it causes problems to create
# the bag directory and log in the constructor, and breaks assumptions of
# ensure_bagdir().
# 
#        if os.path.exists(self.bagdir):
#            self.ensure_bagdir() # this initializes some data like self._bag

    def rename_bag(self, name):
        """
        rename the bag to the given name.  Note that finalize_bag() will need
        to be (re-)called after calling this method.
        """
        if name == self._name:
            return

        newdir = os.path.join(self._pdir, name)
        if os.path.exists(self._bagdir):
            os.rename(self._bagdir, newdir)

        self._name = name
        self._bagdir = newdir

        if self._bag:
            self._bag = NISTBag(self._bagdir)

    def _merge_def_config(self, config):
        if not def_etc_dir:
            self.log.warning("BagBuilder: Can't load default config: " +
                             "can't find etc directory")
            return config
        defconffile = os.path.join(def_etc_dir, "nist_bagger_conf.yml")
        if not os.path.exists(defconffile):
            self.log.warning("BagBuilder: default config file not found: " +
                             defconffile)
            return config

        defconf = load_from_file(defconffile)
        return merge_config(config, defconf)

    def _fix_id(self, id):
        if id is None:
            return None
        if re.search(r"^/?\d+", id):
            id = "ark:/" + id.lstrip('/')
        elif re.search(r"^A[Rr][Kk]:", id):
            id = "ark" + id[3:]

        if not re.match(r"^ark:/\d+/\w", id):
            raise ValueError("Invalid ARK identifier provided: "+id)
        if self.cfg.get('validate_id', True) and not noid.validate(id):
            raise ValueError("Invalid ARK identifier provided (bad check char): "
                             +id)
            
        return id

    def _mint_id(self, ediid):
        seedkey = self.cfg.get('id_minter', {}).get('ediid_data_key', 'ediid')
        return self._minter.mint({ seedkey: ediid })

    @property
    def bagname(self):
        return self._name

    @property
    def bagdir(self):
        return self._bagdir

    @property
    def multibag_version(self):
        """
        the version of the NIST BagIt Profile that this builder is set to 
        build to.  
        """
        return self._mbagver

    @property
    def logname(self):
        return self._logname

    @property
    def id(self):
        return self._id

    @property
    def ediid(self):
        return self._ediid

    @ediid.setter
    def ediid(self, val):
        if val:
            self.record("Setting ediid: " + val)
        elif self._ediid:
            self.record("Unsetting ediid")
        self._ediid = val
        self._upd_ediid(val)
        self._upd_downloadurl(val)

    def _upd_ediid(self, ediid):
        # this updates the ediid metadatum in the resource nerdm.json
        mdfile = self.nerdm_file_for("")
        if os.path.exists(mdfile):
            mdata = read_nerd(mdfile)
            if mdata.get('ediid') != ediid:
                if ediid:
                    mdata['ediid'] = ediid
                elif 'ediid' in mdata:
                    del mdata['ediid']
                self._write_json(mdata, mdfile)

    def _upd_downloadurl(self, ediid):
        mdtree = os.path.join(self.bagdir, 'metadata')
        dftype = ":".join([NERDPUB_PRE, "DataFile"])
        if os.path.exists(mdtree):
            for dir, subdirs, files in os.walk(mdtree):
                if FILEMD_FILENAME in files:
                    mdfile = os.path.join(dir, FILEMD_FILENAME)
                    mdata = read_nerd(mdfile)
                    if dftype in mdata.get("@type", []) and  \
                       mdata.get('filepath') and             \
                       mdata.get("downloadURL", self._distbase)    \
                            .startswith(self._distbase):
                        if ediid:
                            mdata["downloadURL"] = \
                               self._download_url(self.ediid, mdata['filepath'])
                                    
                        else:
                            del mdata["downloadURL"]
                        self._write_json(mdata, mdfile)

    def _download_url(self, ediid, destpath):
        path = "/".join(destpath.split(os.sep))
        return self._distbase + ediid + '/' + urlencode(path)

    def ensure_bagdir(self):
        """
        ensure that the working bag directory exists with the proper name
        an that we can write to it.  
        """
        didit = False
        if not os.path.exists(self.bagdir):
            try:
                os.mkdir(self.bagdir)
                didit = True
            except OSError, e:
                raise BagWriteError("Unable to create bag directory: "+
                                    self.bagdir+": "+str(e), cause=e, sys=self)

        if not os.access(self.bagdir, os.R_OK|os.W_OK|os.X_OK):
            raise BagWriteError("Insufficient permissions on bag directory: " +
                                self.bagdir, sys=self)

        if not self._loghdlr:
            self._set_logfile()
        if didit:
            self.record("Created bag with name, %s", self.bagname)
        self._bag = NISTBag(self.bagdir)
        if os.path.exists(self._bag.nerd_file_for("")):
            # load the resource-level metadata that's already there
            md = self._bag.nerd_metadata_for("")
            self._id = md.get('@id')
            self._ediid = md.get('ediid')
        

    def _set_logfile(self):
        if self._loghdlr:
            self._unset_logfile()
        filepath = os.path.join(self.bagdir, self.logname)
        self._loghdlr = logging.FileHandler(filepath)
        # self._loghdlr.setLevel(NORM)
        fmt = self.cfg.get('bag_log_format', DEF_BAGLOG_FORMAT)
        self._loghdlr.setFormatter(logging.Formatter(fmt))
        self.log.addHandler(self._loghdlr)

    def _unset_logfile(self):
        if hasattr(self, '_loghdlr') and self._loghdlr:
            self.log.removeHandler(self._loghdlr)
            self._loghdlr.close()
            self._loghdlr = None

    def ensure_bag_structure(self):
        """
        make sure that the working bag contains the basic directory structure--
        namely, has data and metadata directories.  
        """
        self.ensure_bagdir()

        dirs = [ "data", "metadata" ]
        self._extend_file_list(dirs, 'extra_tag_dirs')

        for dir in dirs:
            dir = os.path.join(self.bagdir, dir)
            if not os.path.exists(dir):
                os.mkdir(dir)

    def ensure_ansc_collmd(self, destpath):
        """
        ensure that the directories to contain a subcollection with a given 
        path and its metadata exist.

        :param destpath str:   the desired path for the file relative to the 
                               root of the dataset.
        """
        destpath = os.path.normpath(destpath)
        if os.path.isabs(destpath):
            raise ValueError("collection path cannot be absolute: "+destpath)
        if destpath.startswith(".."+os.sep):
            raise ValueError("collection path cannot contain ..: "+destpath)

        collpath = os.path.dirname(destpath)
        self._ensure_metadata_dirs(collpath)

        while collpath != "":
            if not os.path.exists(self.nerdm_file_for(collpath)):
                self.init_collmd_for(collpath, write=True, examine=False)
            collpath = os.path.dirname(collpath)

    def _ensure_metadata_dirs(self, destpath):

        self.ensure_bag_structure()
        path = os.path.join(self.bagdir, "metadata", destpath)
        try:
            if not os.path.exists(path):
                os.makedirs(path)
        except Exception, ex:
            pdir = os.path.join(os.path.basename(self.bagdir),
                                "metadata", destpath)
            raise BagWriteError("Failed to create directory tree ({0}): {1}"
                                .format(str(ex), pdir), cause=ex, sys=self)

    def ensure_metadata_dirs(self, destpath):
        destpath = os.path.normpath(destpath)
        if os.path.isabs(destpath):
            raise ValueError("data path cannot be absolute: "+destpath)
        if destpath.startswith(".."+os.sep):
            raise ValueError("data path cannot contain ..: "+destpath)

        self._ensure_metadata_dirs(destpath)
        

    def ensure_datafile_dirs(self, destpath):
        """
        ensure that the directories to contain a data file with a given 
        path and its metadata exist.

        :param destpath str:   the desired path for the file relative to the 
                               root of the dataset.
        """
        destpath = os.path.normpath(destpath)
        if os.path.isabs(destpath) or destpath.startswith(".."+os.sep):
            raise ValueError("ensure_datafile_dirs: destpath cannot be an "
                             "absolute path")

        ddir = os.path.join(self.bagdir, "data")
        if not os.path.exists(ddir):
            self.ensure_bag_structure()

        pdir = os.path.dirname(destpath)
        if pdir:
            path = os.path.join(ddir, pdir)
            try:
                if not os.path.exists(path):
                    os.makedirs(path)
            except Exception, ex:
                pdir = os.path.join(os.path.basename(self.bagdir), "data", pdir)
                raise BagWriteError("Failed to create directory tree ({0}): {1}"
                                     .format(str(ex), pdir), cause=ex, sys=self)

        self.ensure_metadata_dirs(destpath)
        
    def _extend_file_list(self, filelist, param):
        extras = self.cfg.get(param)
        if extras:
            if isinstance(extras, (str, unicode)):
                extras = [ extras ]
            if hasattr(extras, '__iter__'):
                bad = [f for f in extras if not isinstance(f, (str, unicode))]
                if bad:
                    self.log.warning("Ignoring entries in config param, "+param+
                                     ", with non-string type: " + str(bad))
                    extras = [f for f in extras if isinstance(f, (str, unicode))]
                filelist.extend(extras)
            else:
                self.log.warning("Ignoring config param, 'extra_tag_dirs': " +
                                 "wrong value type: " + str(extras))

    def add_data_file(self, destpath, srcpath=None, hardlink=False, initmd=True):
        """
        add a data file to the bag.  This creates directories representing it in 
        both the data and metadata directories.  If a srcpath is provided, the 
        file will actually be copied into the data directory.  If the file is 
        provided and initmd is True, the metadata for the file will be 
        initialized and placed in the metadata directory.  

        :param destpath str:   the desired path for the file relative to the 
                               root of the dataset.
        :param scrpath str:    the path to an existing file to copy into the 
                               bag's data directory.
        :param hardlink bool:  If True, attempt to create a hard link to the 
                               file instead of copying it.  For this to be 
                               successful, the bag directory and the srcpath
                               must be on the same filesystem.  A hard copy 
                               will be attempted if linking fails if the 
                               configuration option 'copy_on_link_failure' is
                               not false.
        :param initmd bool:    If True and a file is provided, the file will 
                               be examined and extraction of metadata will be 
                               attempted.  Resulting metadata will be written 
                               into the metadata directory. 
        """
        self.ensure_datafile_dirs(destpath)
        outfile = os.path.join(self.bagdir, 'data', destpath)

        msg = "Adding file, " + destpath
        if initmd:
            msg += ", and intializing metadata"
        self.record(msg)

        if srcpath:
            if hardlink:
                try:
                    os.link(srcpath, outfile)
                    self.record("Added data file at "+destpath)
                except OSError, ex:
                    msg = "Unable to create link for data file ("+ destpath + \
                          "): "+ str(ex)
                    if self.cfg.get('copy_on_link_failure', True):
                        hardlink = False
                        self.log.warning(msg)
                    else:
                        self.log.exception(msg, exc_info=True)
                        raise BagWriteError(msg, sys=self)
            if not hardlink:
                try:
                    filecopy(srcpath, outfile)
                    self.record("Added data file at "+destpath)
                except Exception, ex:
                    msg = "Unable to copy data file (" + srcpath + \
                          ") into bag (" + outfile + "): " + str(ex)
                    self.log.exception(msg, exc_info=True)
                    raise BagWriteError(msg, cause=ex, sys=self)
    
        if initmd:
            self.init_filemd_for(destpath, write=True, examine=srcpath)

    def ensure_colls_for(self, destpath):
        """
        ensure that all enclosing collections for the component at destpath
        have had their metadata initialized.  
        """
        destpath = os.path.dirname(destpath)
        metadir = os.path.join(self.bagdir, "metadata")
        while destpath != "":
            mdfile = self.nerdm_file_for(destpath)
            if not os.path.exists(mdfile):
                self.init_collmd_for(destpath, write=True)

            destpath = os.path.dirname(destpath)
            
    def add_metadata_for_file(self, destpath, mdata, disttype=None):
        """
        write metadata for the component at the given destination path to the 
        proper location under the metadata directory.

        This implementation will provide default values for key values that 
        are missing.

        :param destpath str:  the path to the data file that metadata is being
                              provided for
        :param mdata   dict:  a Mapping object containing the metadata to 
                              associate with the file.  This will be merged 
                              with default data.  
        :param disttype str:  the default file distribution type to assign to 
                              the file (with the default default being 
                              "DataFile"); if examine is True, the type may 
                              change based on inspection of the file.  
        """
        if not isinstance(mdata, Mapping):
            raise NERDTypeError("dict", type(mdata), "NERDm Component")

        if not disttype:
            # get the disttype by consulting the metadata itself
            if '@type' in mdata:
                pfx = re.compile(r'^[^:]*:')
                ftypes = [p for p in [pfx.sub('', t) for t in mdata['@type']]
                            if p in self._file_types]
                if len(ftypes) > 0:
                    disttype = ftypes[0]
        if not disttype:
            # if a recognized file distribution type is not set in the metadata,
            # default to DataFile
            disttype = "DataFile"

        md = self._create_init_filemd_for(destpath, disttype=disttype)
        md.update(mdata)

# We now have other types of files (e.g. ChecksumFile); do not ensure
# DataFile type
#
#        try:
#            if not isinstance(md['@type'], list):
#                raise NERDTypeError('list', str(mdata['@type']), '@type')
#
#            if DATAFILE_TYPE not in md['@type']:
#                md['@type'].append(DATAFILE_TYPE)
#                    
#        except TypeError, ex:
#            raise NERDTypeError(msg="Unknown DataFile property type error",
#                                cause=ex)

        try:
            self.ensure_metadata_dirs(destpath)
            self.record("Adding file metadata for %s", destpath)
            self._write_json(md, self.nerdm_file_for(destpath))
        except Exception, ex:
            self.log.exception("Trouble adding metadata: %s", str(ex))
            raise

    def add_metadata_for_coll(self, destpath, mdata):
        """
        write metadata for the component at the given destination path to the 
        proper location under the metadata directory.
        """
        if not isinstance(mdata, Mapping):
            raise NERDTypeError("dict", type(mdata), "NERDm Component")
        
        md = self._create_init_collmd_for(destpath)
        md.update(mdata)
        
        try:
            if not isinstance(md['@type'], list):
                raise NERDTypeError('list', str(md['@type']), '@type')

            if SUBCOLL_TYPE not in md['@type']:
                md['@type'].append(SUBCOLL_TYPE)
                    
        except TypeError, ex:
            raise NERDTypeError(msg="Unknown DataFile property type error",
                                cause=ex)

        try:
            self.ensure_metadata_dirs(destpath)
            self.record("Adding collection metadata for %s", destpath)
            self._write_json(md, self.nerdm_file_for(destpath))
        except Exception, ex:
            self.log.exception("Trouble adding metadata: "+str(ex))
            raise

    def pod_file(self):
        """
        return the path to the output POD dataset metadata file
        """
        return os.path.join(self.bagdir, "metadata", POD_FILENAME)

    def nerdm_file_for(self, destpath):
        """
        return the path to NERDm metadata file that corresponds to a data file
        or subcollection with the given collection path.

        :param destpath str:  the path to the data file relative to the 
                              dataset's root.  An empty value indicates the 
                              NERDm resource-level file.  
        """
        return os.path.join(self.bagdir, "metadata", destpath, FILEMD_FILENAME)

    def annot_file_for(self, destpath):
        """
        return the path to NERDm metadata file that corresponds to a data file
        or subcollection with the given collection path.

        :param destpath str:  the path to the data file relative to the 
                              dataset's root. (Caution: not the bag's root.)
        """
        return os.path.join(self.bagdir, "metadata", destpath,
                            FILEANNOT_FILENAME)

    def update_annot_for(self, destpath, mdata):
        """
        merge (via update) the given metadata into the annotation data for a 
        given destination path in the bag.  The properties in the input data
        will override that found in the annotation file (using dict.update()).

        :param destpath str:  the path to the data file relative to the 
                              dataset's root. (Caution: not the bag's root.)
                              An empty string refers to the resource-level 
                              metadata.  
        :param mdata dict:    the metadata to merge in.  
        """
        if not mdata:
            return
        self.ensure_metadata_dirs(destpath)
        annotf = self.annot_file_for(destpath)
        if self.bagdir and os.path.exists(annotf):
            amdata = read_nerd(annotf)
        else:
            amdata = {}
        amdata.update(mdata)
        write_json(amdata, annotf)
            

    def init_filemd_for(self, destpath, write=False, examine=None,
                        disttype="DataFile"):
        """
        create some initial file metadata for a file at a given path.

        :param destpath str:  the path to the data file relative to the 
                              dataset's root.
        :param write   bool:  if True, write the metadata into its proper 
                              location in the bag.  This will overwrite 
                              any existing (non-annotation) metadata.  
        :param examine str or bool:  if a str, it is taken to be the path 
                              to a copy of the source data file to examine 
                              to surmise and extract additional metadata.
                              If it otherwise evaluates to True, the copy 
                              previously copied to the output bag will be 
                              examined.
        :param disttype str:  the default file distribution type to assign to 
                              the file (with the default default being 
                              "DataFile"); if examine is True, the type may 
                              change based on inspection of the file.  
        """
        self.record("Initializing metadata for file %s", destpath)
        mdata = self._create_init_filemd_for(destpath, disttype=disttype)
        if examine:
            if isinstance(examine, (str, unicode)):
                datafile = examine
            else:
                datafile = os.path.join(self.bagdir, "data", destpath)
                
            self._add_mediatype(datafile, mdata, {})
            if os.path.exists(datafile):
                self._add_extracted_metadata(datafile, mdata,
                                             self.cfg.get('file_md_extract'))
            else:
                log.warning("Unable to examine data file: doesn't exist (yet): "+
                            destpath)
        if write:
            self.add_metadata_for_file(destpath, mdata)
            self.ensure_ansc_collmd(destpath)

        return mdata

    def init_collmd_for(self, destpath, write=False, examine=False):
        """
        create some initial subcollection metadata for a folder at a given path.

        :param destpath str:  the path to the folder relative to the 
                              dataset's root.
        :param write   bool:  if True, write the metadata into its proper 
                              location in the bag.  This will overwrite 
                              any existing (non-annotation) metadata.  
        :param examine bool:  if True, examine all files below the collection
                              to extract additional metadata.
        """
        self.record("Initializing metadata for subcollection %s", destpath)
        mdata = self._create_init_collmd_for(destpath)
        if examine:
            colldir = os.path.join(self.bagdir, "data", destpath)

            # FIX
            # if os.path.exist(datafile):
            #    self._add_extracted_metadata(datafile, mdata,
            #                                 self.cfg.get('file_md_extract'))
            # else:
            #     log.warning("Unable to examine data file: doesn't exist yet: " +
            #                 destpath)
        if write:
            if destpath:
                self.add_metadata_for_coll(destpath, mdata)
            else:
                self.log.error("Cannot put subcollection metadata in the root "+
                               "collection; will skip writing")

        return mdata

    def _write_json(self, jsdata, destfile):
        indent = self.cfg.get('json_indent', 4)
        write_json(jsdata, destfile, indent)

    def _add_extracted_metadata(self, dfile, mdata, config):
        self._add_osfile_metadata(dfile, mdata, config)
        self._add_checksum(dfile, mdata, config)

    def _add_osfile_metadata(self, dfile, mdata, config):
        mdata['size'] = os.stat(dfile).st_size
    def _add_checksum(self, dfile, mdata, config):
        mdata['checksum'] = {
            'algorithm': { '@type': "Thing", 'tag': 'sha256' },
            'hash': checksum_of(dfile)
        }
    def _add_mediatype(self, dfile, mdata, config):
        if not self._mimetypes:
            mtfile = pkg_resources.resource_filename('nistoar.pdr',
                                                     'data/mime.types')
            self._mimetypes = build_mime_type_map([mtfile])
        mdata['mediaType'] = self._mimetypes.get(os.path.splitext(dfile)[1][1:],
                                                 'application/octet-stream')

    _file_types = {
        "DataFile": [
            [ ":".join([NERDPUB_PRE, "DataFile"]),
              ":".join([NERDPUB_PRE, "DownloadableFile"]),
              "dcat:Distribution" ],
            [ NERDPUB_DEF + "DataFile" ]
        ],
        "ChecksumFile": [
            [ ":".join([NERDPUB_PRE, "ChecksumFile"]),
              ":".join([NERDPUB_PRE, "DownloadableFile"]),
              "dcat:Distribution" ],
            [ NERDPUB_DEF + "ChecksumFile" ]
        ]
    }
    _checksum_alg_names = { "sha256": "SHA-256" }

    def _create_init_filemd_for(self, destpath, disttype="DataFile"):
        if disttype not in self._file_types:
            raise ValueError("Unsupported file distribution type: "+disttype)
        out = {
            "_schema": NERD_DEF + "Component",
            "@context": NERDM_CONTEXT,
            "@id": "cmps/" + urlencode(destpath),
            "@type": deepcopy(self._file_types[disttype][0]),
            "filepath": destpath,
        }
        if self.ediid:
            out['downloadURL'] = self._download_url(self.ediid, destpath)

        if disttype == 'ChecksumFile':
            fname = os.path.splitext(destpath)
            if fname[1] and fname[1][1:] in self._checksum_alg_names:
                out['algorithm'] = { "@type": "Thing", "tag": fname[1][1:] }
                out['describes'] = "cmps/" + fname[0]
                out['description'] = "checksum value for " + \
                                     os.path.basename(fname[0])
                out['description'] = self._checksum_alg_names[fname[1][1:]] + \
                                     ' ' + out['description']

        out["_extensionSchemas"] =  deepcopy(self._file_types[disttype][1])

        return out

    def _create_init_collmd_for(self, destpath):
        out = {
            "_schema": NERD_DEF + "Component",
            "@context": NERDM_CONTEXT,
            "@id": "cmps/" + urlencode(destpath),
            "@type": [ ":".join([NERDPUB_PRE, "Subcollection"]) ],
            "filepath": destpath,
            "_extensionSchemas": [ NERDPUB_DEF + "Subcollection" ]
        }
        return out
    
    def finalize_bag(self, finalcfg=None):
        """
        Assume that all needed data and minimal metadata have been added to the
        bag and fill out the remaining bag components to complete the bag.

        When finalcfg (dict) is provided, its properties will be used to control 
        behavior of the bag finalization.  If not provided, the configuration 
        property 'finalize' provided at construction will control finalization.
        The following finalize sub-properties will be recognized:
          :param 'ensure_component_metadata' bool (True):   if True, this will ensure 
                    that all data files and subcollections have been examined 
                    and had metadata extracted.  
          :param 'trim_folders' bool (False):  if True, remove all empty data directories

        :return list:  a list of errors encountered while trying to complete
                       the bag.  An empty list indicates that the bag is complete
                       and ready to preserved.  
        """
        if finalcfg is None:
            finalcfg = self.cfg.get('finalize', {})

        # Start by trimming the empty data folders
        trim = finalcfg.get('trim_folders', False)
        if trim:
            self.trim_data_folders()

        # Make sure all remaining components have metadata
        if finalcfg.get('ensure_component_metadata', True):
            self.ensure_comp_metadata(examine=True)
        self.ensure_merged_annotations()

        # Now trim empty metadata folders
        if trim:
            self.trim_metadata_folders()

        self.ensure_bagit_ver()
        self.write_data_manifest(finalcfg.get('confirm_checksums', False))
        self.write_mbag_files()
        # write_ore_file
        # write_pidmapping_file
        self.write_about_file()
        # write_premis_file
        self.ensure_baginfo()

        # this file was used to assist when this bag is an update on an
        # earlier version.  We no longer need it, so get rid of it.
        deprecinfof = os.path.join(self.bagdir,"multibag","deprecated-info.txt")
        if os.path.exists(deprecinfof):
            os.remove(deprecinfof)

        self.log.error("Implementation of Bag finalization is not complete!")
        self.log.info("Bag does not include PREMIS and ORE files")

    def write_about_file(self):
        """
        Write out the about.txt file.  This requires that the resource-level
        metdadata has been written out; if it hasn't, a BagProfileError is 
        raised.  
        """
        if not self._bag:
            self.ensure_bagdir()
        nerdresf = self._bag.nerd_file_for("")
        podf = self._bag.pod_file()
        if not os.path.exists(podf):
            raise BagProfileError("Missing POD metadata file; is this bag complete?")
        if not os.path.exists(nerdresf):
            raise BagProfileError("Missing POD metadata file; is this bag complete?")
        try:
            mf = nerdresf
            nerdm = self._bag.nerd_metadata_for("")
            mf = podf
            podm = self._bag.read_pod(mf)
        except OSError, ex:
            raise BagItException("failed to read data from file, " +
                                 mf + ": " + str(ex), cause=ex)

        try:
            ec = 'utf-8'
            with open(os.path.join(self.bagdir, "about.txt"), 'w') as fd:
                print("This data package contain NIST Public Data\n", file=fd)

                # title
                print(textwrap.fill(podm['title'].encode(ec), 79), file=fd)

                # authors, if available
                if 'authors' in nerdm:
                    auths = []
                    affils = []
                    for auth in nerdm['authors']:
                        if auth.get('fn'):
                            aus = auth['fn']
                        else:
                            aus = " ".join([ auth.get('givenName',''),
                                            auth.get('middleName', ''),
                                            auth.get('familyName', '') ]).strip()
                        if aus and auth.get('affiliation'):
                            try:
                                whichaffil = affils.index(auth['affiliation'])+1
                            except ValueError:
                                affils.append(auth['affiliation'])
                                whichaffil = len(affils)

                            # using = as a non-breakable space here, see sub()
                            # below.
                            aus += "=[{0}]".format(whichaffil)

                        auths.append(aus)

                    if len(auths) > 0:
                        if len(auths) == 1:
                            aus = auths[0]
                        elif len(auths) == 2:
                            aus = auths[0] + " and " + auths[1]
                        else:
                            aus = " ".join(auths[:-1]) + ", and " + auths[-1]
                        print( re.sub(r'=', ' ', textwrap.fill(aus.encode(ec))),
                               file=fd )

                        i=1
                        for affil in affils:
                           print(textwrap.fill("[{0}] {1}".format(i, affil)
                                                          .encode(ec)), file=fd)

                # identifier(s)
                if nerdm.get('doi'):
                    print("Identifier: doi:{0} ({1})".format(nerdm['doi'],
                                                             nerdm['@id']),
                          file=fd)
                else:
                    print("Identifier: {0}".format(nerdm['@id']), file=fd)
                fd.write('\n')

                # contact
                if 'contactPoint' in nerdm:
                    cp = nerdm['contactPoint']
                    if cp.get('fn') and cp.get('hasEmail'):
                        aus = re.sub('^mailto:\s*', '', cp['hasEmail'])
                        print("Contact: {0} ({1})".format(cp['fn'], aus)
                                                  .encode(ec), file=fd)
                    else:
                        print("Contact: {0}".format(cp.get('fn') or
                                                    cp.get('hasEmail')),
                              file=fd)
                    if 'postalAddress' in cp:
                        for line in cp['postalAddress']:
                            print("         {0}".format(line.strip()).encode(ec),
                                  file=fd)
                    if 'phoneNumber' in cp:
                        print("         Phone: {0}".format(
                                          cp['phoneNumber'].strip()).encode(ec),
                              file=fd)
                    fd.write("\n")

                # description
                if podm.get('description'):
                    print( textwrap.fill(podm['description'].encode(ec)),
                           file=fd )
                    fd.write("\n")

                # landing page
                if nerdm.get('doi'):
                    print("More information:\nhttps://doi.org/" +
                          nerdm.get('doi'), file=fd)
                elif nerdm.get('landingPage'):
                    print("More information:\n" +
                          nerdm.get('landingPage').encode(ec),
                          file=fd)
                
        except OSError, ex:
            raise BagWriteError("Problem writing about.txt file: " + str(ex),
                                cause=ex)

    def ensure_bagit_ver(self):
        """
        ensure that the bag's bagit.txt file exists
        """
        if not os.path.exists(os.path.join(self.bagdir, "bagit.txt")):
            self.write_bagit_ver()

    def write_bagit_ver(self):
        """
        write the bagit.txt file
        """
        self.ensure_bagdir()
        ver = self.cfg.get('bagit_version', "0.97")
        enc = self.cfg.get('bagit_encoding', "UTF-8")

        try: 
            with open(os.path.join(self.bagdir, 'bagit.txt'), 'w') as fd:
                print("BagIt-Version: "+ver, file=fd)
                print("Tag-File-Character-Encoding: "+enc, file=fd)
        except OSError, ex:
            raise BagWriteError("Error writing bagit.txt: "+str(ex), cause=ex)

    def write_mbag_files(self, overwrite=False):
        """
        write out tag files for the MultiBag BagIt profile.  
        """
        self.ensure_bagit_ver()

        # Use the head bag interface provided by the external multibag package
        # Note that previously saved data (i.e. cached from previously
        # published version) will be retained.
        hbag = open_headbag(self.bagdir)

        # append the bag we're building to the member bag list and save
        url = self.cfg.get('bag-download-url')
        if url:
            if not url.endswith('/'):
                url += '/'
            url += self.bagname
        hbag.add_member_bag(self.bagname, url)
        hbag.save_member_bags()

        # update the file lookup with the contents of this new bag
        for dir, sdirs, files in os.walk(self._bag.data_dir):
            dir = dir[len(self.bagdir)+1:]
            for f in files:
                f = os.path.join(dir, f)
                f = "/".join(f.split(os.sep))
                hbag.add_file_lookup(f, self.bagname)
        for dir, sdirs, files in os.walk(self._bag.metadata_dir):
            dir = dir[len(self.bagdir)+1:]
            for f in files:
                f = os.path.join(dir, f)
                f = "/".join(f.split(os.sep))
                hbag.add_file_lookup(f, self.bagname)
        for f in "preserv.log ore.txt premis.xml".split():
            if hbag.exists(f):
                hbag.add_file_lookup(f, self.bagname)
        hbag.save_file_lookup()
        
    def ensure_baginfo(self, overwrite=False):
        """
        ensure that a complete bag-info.txt file is written out to the bag.
        Any data that has already been written out will remain, and any missing
        default information will be added.
        """
        if not self._bag:
            self.ensure_bagdir()

        initdata = self.cfg.get('init_bag_info', OrderedDict())

        # add items based on bag's contents
        nerdm = self._bag.nerd_metadata_for("")
        initdata['Bagging-Date'] = datetime.date.today().isoformat()
        initdata['Bag-Group-Identifier'] = nerdm.get('ediid') or self.ediid
        initdata['Internal-Sender-Identifier'] = self.bagname

        desc = [p for p in nerdm.get('description', []) if len(p.strip()) > 0]
        if desc:
            initdata['External-Description'] = desc
        else:
            initdata['External-Description'] = \
"This collection contains data for the NIST data resource entitled, {0}". \
format(nerdm['title'])

        initdata['External-Identifier'] = [self.id]
        if nerdm.get('doi'):
            initdata['External-Identifier'].append("doi:"+nerdm['doi'])

        # Calculate the payload Oxum
        oxum = self._measure_oxum(self._bag._datadir)
        initdata['Payload-Oxum'] = "{0}.{1}".format(oxum[0], oxum[1])

        # update the multibag version, deprecation
        self.update_head_version(initdata, nerdm.get("version", "1"))

        # write everything except Bag-Size
        self.write_baginfo_data(initdata, overwrite=overwrite)

        # calculate and write the size of the bag 
        oxum = self._measure_oxum(self.bagdir)
        size = self._format_bytes(oxum[0])
        oxum[0] += len("Bag-Size: {0} ".format(size))
        oxum[0] += len("Bag-Oxum: {0}.{1} ".format(oxum[0], oxum[1]))
        size = self._format_bytes(oxum[0])
        szdata = OrderedDict([
            ('Bag-Oxum', "{0}.{1}".format(*oxum)),
            ('Bag-Size', size),
        ])
        self.write_baginfo_data(szdata, overwrite=False)

    def update_head_version(self, baginfo, version):
        """
        update the given bag info metadata with values for 
        'Multibag-Head-Version' and possibly 'Multibag-Head-Deprecates'
        """
        baginfo['Multibag-Head-Version'] = version

        # if there is a multibag/deprecated-info.txt, extract the
        # 'Multibag-Head-Deprecates' values
        #
        multibagdir = baginfo.get('Multibag-Tag-Directory', 'multibag')
        if isinstance(multibagdir, list):
            multibagdir = (len(multibagdir) >0 and multibagdir[-1]) or 'multibag'
        depinfof = os.path.join(self._bag.dir,multibagdir, "deprecated-info.txt")
        
        if os.path.exists(depinfof):
            # indicates that this is an update to a previous version of the
            # dataset.  Add deprecation information.
            
            depinfo = self._bag.get_baginfo(depinfof)

            if 'Multibag-Head-Deprecates' not in baginfo:
                baginfo['Multibag-Head-Deprecates'] = []

            # add the previous head version
            baginfo['Multibag-Head-Deprecates'].extend(
                depinfo.get('Multibag-Head-Version', ["1"]) )

            # add in all the previous deprecated versions
            for val in depinfo.get('Multibag-Head-Deprecates', []):
                if val not in baginfo['Multibag-Head-Deprecates']:
                    baginfo['Multibag-Head-Deprecates'].append( val )
                
    def _measure_oxum(self, rootdir):
        return measure_dir_size(rootdir)

    def _format_bytes(self, nbytes):
        prefs = ["", "k", "M", "G", "T"]
        ordr = 0
        while nbytes >= 1000.0 and ordr < 4:
            nbytes /= 1000.0
            ordr += 1
        pref = prefs[ordr]
        ordr = 0
        while nbytes >= 10.0:
            nbytes /= 10.0
            ordr += 1
        nbytes = str(round(nbytes, 3) * 10**ordr)
        if '.' in nbytes:
            nbytes = re.sub(r"0+$", "", nbytes)
        if nbytes.endswith('.'):
            nbytes = nbytes[:-1]    
        return "{0} {1}B".format(nbytes, pref)

    def write_baginfo_data(self, data, altfile=None, overwrite=False):
        """
        write out specific data to the bag-info.txt file.  Normally, this will
        append the provided data to the file.  Name-value pairs that already 
        exist in the file will not be overwritten.

        :param data dict:  a dictionary (preferably, an OrderedDict) containing
                           the data to add.  
        :param overwrite bool:  if True, any previously written data will be 
                           cleared before writing the new data.  
        """
        if not isinstance(data, Mapping):
            raise TypeError("write_baginfo_data(): Not a dictionary-like " +
                            "object: "+type(data))

        def upd_info(currdata, newdata):
            out = OrderedDict()
            for name, vals in newdata.items():
                out[name] = []
                if isinstance(vals, (str, unicode)) or \
                   not isinstance(vals, Sequence):
                    vals = [vals]
                if name in currdata:
                    for val in vals:
                        if val not in currdata[name]:
                            out[name].append(val)
                else:
                    out[name] = vals
            return out

        if not self._bag:
            self.ensure_bagdir()
        if not overwrite:
            data = upd_info(self._bag.get_baginfo(altfile), data)
        self._write_baginfo_data(data, altfile, overwrite)

    def _write_baginfo_data(self, data, infofile=None, overwrite=False):
        mode = 'w'
        if not overwrite:
            mode = 'a'

        if not infofile:
            infofile = os.path.join(self.bagdir, "bag-info.txt")
        with open(infofile, mode) as fd:
            for name, vals in data.items():
                if isinstance(vals, (str, unicode)) or \
                   not isinstance(vals, Sequence):
                    vals = [vals]
                for val in vals:
                    out = "{0}: {1}".format(name, val.encode('utf-8'))
                    if len(out) > 79:
                        out = textwrap.fill(out, 79, subsequent_indent=' ')
                    print(out, file=fd)

    def trim_data_folders(self, rmmeta=False):
        """
        look through the data directory for empty subdirectories and remove 
        them.  This will also eliminate the corresponding metadata folders 
        unless (1) they contain metadata files, AND (2) rmmeta is False.

        :param rmmeta bool:  If False, only purge a corresponding metadata 
                             directory if it contains no metadata.  If True,
                             any metadata for components that do not exist
                             under data nor in the fetch.txt will be removed. 
        """
        # ascend the data directory from leaves to root, looking for empty
        # directories
        droot = os.path.join(self.bagdir, "data")
        mroot = os.path.join(self.bagdir, "metadata")
        for ddir, subdirs, files in os.walk(droot, topdown=False):
            if ddir == droot:
                # don't delete the root "data" directory
                continue
            subdirs = [d for d in subdirs
                         if os.path.exists(os.path.join(ddir, d))]
            if len(files) == 0 and len(subdirs) == 0:
                # the data directory is empty
                try:
                    os.rmdir(ddir)

                    # check the contents of the corresponding metadata dir
                    mdir = os.path.join(mroot, ddir[len(droot)+1:])
                    if os.path.exists(mdir):
                        if os.path.isdir(mdir):
                            # is there anything in the metadata directory?
                            mcont = [os.path.join(mdir, d)
                                     for d in os.listdir(mdir)]

                            # rm metadata directory if it's empty or rmmeta=True
                            if len(mcont) == 0 or rmmeta:
                                rmtree(mdir)

                        else:
                            self.log.error("NIST bag profile error: not a " +
                                           "directory: " +
                                  os.path.join("metadata", ddir[len(droot)+1:]))
                except OSError, ex:
                    self.log.exception("Failed to remove empty data dir: " +
                                       ddir + ": " + str(ex))
                    
    def trim_metadata_folders(self):
        """
        look for empty directories in the metadata tree and remove them.  
        """
        mroot = os.path.join(self.bagdir, "metadata")
        for mdir, subdirs, files in os.walk(mroot, topdown=False):
            subdirs = [d for d in subdirs
                         if os.path.exists(os.path.join(mdir, d))]
            if len(files) == 0 and len(subdirs) == 0:
                # the metadata directory is empty
                try:
                    os.rmdir(mdir)
                except OSError, ex:
                    self.log.exception("Failed to remove empty metadata dir: " +
                                       mdir + ": " + str(ex))


    def ensure_comp_metadata(self, examine=True):
        """
        iterate through all the data files found under the data directory
        and ensure there is metadata describing them.  

        :param examine bool:  if true, actually examine the files to extract
                              additional metadata (e.g. size, checksum, type, 
                              etc.)
        """
        if not self._bag:
            self.ensure_bagdir()
        for dfile in self._bag.iter_data_files():
            mdfile = self._bag.nerd_file_for(dfile)
            if examine or not os.path.exists(mdfile):
                # we'll merge the new examination with the previous:
                # except 'checksum', previous data will over-ride new 
                if os.path.exists(mdfile):
                    oldmd = self._bag.nerd_metadata_for(dfile)
                else:
                    oldmd = OrderedDict()

                # generate metadata
                md = self.init_filemd_for(dfile, write=False, examine=examine)

                # merge it with the previous metadata
                cksm = md.get('checksum')
                sz = md.get('size')
                md.update(oldmd)
                override = {}
                if cksm:
                    override['checksum'] = cksm
                if sz:
                    override['size'] = sz
                md.update(override)

                # write it out
                self.add_metadata_for_file(dfile, md)
                self.ensure_ansc_collmd(dfile)


    def __del__(self):
        self._unset_logfile()

    def validate(self, config=None):
        """
        Determine if the bag is complete and compliant with the NIST BagIt
        profile.

        :param config dict:  a configuration to pass to the validator; see 
                             nistoar.pdr.preserv.bagit.validate for details.
                             If not provided, the configuration for this 
                             builder will be checked for the 'validator' 
                             property to use as the configuration.
                             
        :return ValidationResults:  a 
                             nistoar.pdr.preserv.bagit.validate.ValidationResults
                             instance containing the lists of errors, warnings, 
                             or recommendations resulting. 
        """
        if not self._bag:
            raise BagItException("Bag directory for id=" + self._name +
                                 "has not been created.")
        if config is None:
            self.cfg.get('validator', {})
        vld8r = NISTAIPValidator(config)
        return vld8r.validate(self._bag)

    def record(self, msg, *args, **kwargs):
        """
        record a message indicating a relevent change made to this bag to 
        go into this bag's log file.  
        """
        self.log.log(NORM, msg, *args, **kwargs)

    def add_res_nerd(self, mdata, savefilemd=True):
        """
        write out the resource-level NERDm data into the bag.  

        :param mdata      dict:  the JSON object containing the NERDm Resource 
                                   metadata
        :param savefilemd bool:  if True (default), any DataFile or 
                                   Subcollection metadata will be split off and 
                                   saved in the appropriate locations for 
                                   file metadata.
        """
        self.ensure_bag_structure()
        mdata = deepcopy(mdata)

        self.record("Adding resourse-level metadata")
        
        # validate type
        if mdata.get("_schema") != NERDM_SCH_ID:
            if self.cfg.get('ensure_nerdm_type_on_add', True):
                raise NERDError("Not a NERDm Resource Record; wrong schema id: "+
                                str(mdata.get("_schema")))
            else:
                self.log.warning("provided NERDm data does not look like a "+
                                 "Resource record")
        
        if "components" in mdata:
            components = mdata['components']
            if not isinstance(components, list):
                raise NERDTypeError("list", str(type(mdata['components'])),
                                    'components')
            for i in range(len(components)-1, -1, -1):
                tps = components[i].get('@type',[])
                if DOWNLOADABLEFILE_TYPE in tps or DATAFILE_TYPE in tps:
                    if savefilemd and 'filepath' not in components[i]:
                        msg = "DataFile missing 'filepath' property"
                        if '@id' in components[i]:
                            msg += " ({0})".format(components[i]['@id'])
                        self.warning(msg)
                    else:
                        if savefilemd:
                            self.add_metadata_for_file(components[i]['filepath'],
                                                       components[i])
                        components.pop(i)
                            
                elif SUBCOLL_TYPE in components[i].get('@type',[]):
                    if savefilemd and 'filepath' not in components[i]:
                        msg = "Subcollection missing 'filepath' property"
                        if '@id' in components[i]:
                            msg += " ({0})".format(components[i]['@id'])
                        self.warning(msg)
                    else:
                        if savefilemd:
                            self.add_metadata_for_coll(components[i]['filepath'],
                                                       components[i])
                        components.pop(i)

        if 'inventory' in mdata:
            # we'll recalculate the inventory at the end; for now, get rid of it.
            del mdata['inventory']
        if 'dataHierarchy' in mdata:
            # we'll recalculate the dataHierarchy at the end; for now, get rid
            # of it.
            del mdata['dataHierarchy']
        if 'ediid' in mdata:
            # this will trigger updates to DataFile components
            self.ediid = mdata['ediid']

        self._write_json(mdata, self.nerdm_file_for(""))
                                             

    def add_ds_pod(self, pod, convert=True, savefilemd=True):
        """
        write out the dataset-level POD data into the bag.

        :param pod str or dict:  the POD Dataset metadata; if a str, the value
                             is the full pathname to a file containing the JSON
                             data; if it is a dictionary, it is the parsed JSON 
                             metadata.
        :param convert bool: if True, in addition to writing the POD file, it 
                             will be converted to NERDm data and written out 
                             as well.
        :param savefilemd bool:  if True (default) and convert=True, any DataFile
                             or Subcollection metadata will be split off and 
                             saved in the appropriate locations for file 
                             metadata.

        :return dict:  the NERDm-converted metadata or None if convert=False
        """
        if not isinstance(pod, (str, unicode, Mapping)):
            raise NERDTypeError("dict", type(pod), "POD Dataset")
        self.ensure_bag_structure()

        if self.log.isEnabledFor(logging.INFO):
            msg = "Adding POD data"
            if convert:
                msg += " and converting to NERDm"
            self.log.info(msg)

        outfile = os.path.join(self.bagdir, "metadata", POD_FILENAME)
        pdata = None
        if not isinstance(pod, Mapping):
            if convert:
                pdata = read_pod(pod)
            filecopy(pod, outfile)
        else:
            pdata = pod
            self._write_json(pdata, outfile)

        nerd = None
        if convert:
            if not self._id:
                self._id = self._mint_id(pdata.get('identifier'))
                self.record("Assigning new identifier: " + self.id)
                
            nerd = self.pod2nrd.convert_data(pdata, self.id)
            self.add_res_nerd(nerd, savefilemd)
        return nerd

    def add_annotation_for(self, destpath, mdata):
        """
        add the given data as annotations to the metadata for the file or 
        collection with the given path.  This metadata represents updates to 
        the base level metadata.  This metadata will be merged in with the 
        base level to create the final NERDm metadata (when finalize_bag() is 
        called).  

        :param destpath str:   the desired path for the file relative to the 
                               root of the dataset.  An empty string means that
                               the annotation should be associated with the 
                               resource-level metadata.
        :param mdata Mapping:  a dictionary with the annotating metadata.
        """
        if not isinstance(mdata, Mapping):
            raise NERDTypeError("dict", type(mdata), "Annotation data")
        self.ensure_metadata_dirs(destpath)
        self._write_json(mdata, self.annot_file_for(destpath))
    
    def remove_component(self, destpath, trimcolls=False):
        """
        remove a data file or subcollection and all its associated metadata 
        from the bag.  

        Note that it is not an error to attempt to remove a component that 
        does not actually exist in the bag; rather, a warning is written to 
        the log.  

        :param destpath  str:  the root-collection-relative path to the data
                               file
        :parm trimcolls bool:  If True, remove any ancestor subcollections that
                               become empty as a result of the removal.
        :return bool:  True if anything was found and removed.  
        """
        removed = False
        if not destpath:
            raise ValueError("Empty destpath argument (not allowed to remove "
                             "root collection)")
        self.ensure_bag_structure()
        
        # First look for metadata
        target = os.path.join(self.bagdir, "metadata", destpath)
        if os.path.isdir(target):
            removed = True
            rmtree(target)
        elif os.path.exists(target):
            raise BadBagRequest("Request path does not look like a data "+
                                "component (it's a file in the metadata tree): "+
                                destpath, bagname=self.bagname, sys=self)

        # remove the data file if it exists
        target = os.path.join(self.bagdir, "data", destpath)
        if os.path.isfile(target):
            removed = True
            os.remove(target)
        elif os.path.isdir(target):
            removed = True
            rmtree(target)

        if destpath and trimcolls:
            destpath = os.path.dirname(destpath)

            # is this collection empty?
            if destpath and len(self._bag.subcoll_children(destpath)) == 0:
                if self.remove_component(destpath):
                    removed = True

        if not removed:
            self.log.warning("Data component requested for removal does not exist in bag: %s",
                             destpath)

        return removed

    def write_data_manifest(self, confirm=False):
        """
        Write the manifest-<algorithm>.txt file based on the data files that 
        are currently in the data directory.  Each datafile must have a 
        corresponding metadata file that contains the correct checksum.  

        :param confirm bool:  if False (default), the checksum found in the
                              data file's metadata will be assumed to be 
                              correct and added to the manifest file.  If 
                              True, the checksum will be calculated to ensure
                              the value in the metadata file is correct.
        """
        # the checksum should not be part of annotations (?).
        # self.ensure_merged_annotations()
        manfile = os.path.join(self.bagdir, "manifest-sha256.txt")
        try:
          with open(manfile, 'w') as fd:
            for datapath in self._bag.iter_data_files():
                md = self._bag.nerd_metadata_for(datapath, merge_annots=False)
                checksum = md.get('checksum')
                if not checksum or 'hash' not in checksum:
                    raise BagProfileError("Missing checksum for datafile: "+
                                          datapath)
                algo = checksum.get('algorithm', {}).get('tag')
                if algo != 'sha256':
                    raise BagProfileError("Unexpected checksum algorithm found: "+
                                          str(algo))
                checksum = checksum['hash']
                if confirm:
                    if checksum_of(self._bag._full_dpath(datapath)) != checksum:
                        raise BagProfileError("Checksum failure for "+datapath)

                self._record_checksum(fd, checksum,os.path.join('data', datapath))

        except Exception, e:
            if os.path.exists(manfile):
                os.remove(manfile)
            raise

    def _record_checksum(self, fd, checksum, filepath):
        fd.write(checksum)
        fd.write(' ')
        fd.write(filepath)
        fd.write('\n')        
                       
    def ensure_merged_annotations(self):
        """
        ensure that the annotations have been merged primary NERDm metadata.
        """
        # this implementation assumes that merging can be applied multiple
        # times and give the same result.  (It would be better to determine
        # if the annotation's already been applied and not repeat it, for
        # performance reasons.)

        mergeconv = self.cfg.get('merge_convention', DEF_MERGE_CONV)

        # update the resource-level metadata
        if os.path.exists(self.annot_file_for("")):
            self.record("Updating resource-level metadata to merge "+
                        "annotations...")
            nerd = self._bag.nerd_metadata_for("", mergeconv)
            self.add_res_nerd(nerd, False)

        # update the file metadata
        for dfile in self._bag.iter_data_components():
            if os.path.exists(self.annot_file_for(dfile)):
                nerd = self._bag.nerd_metadata_for(dfile, mergeconv)
                self.add_metadata_for_file(dfile, nerd)
        

        
        

