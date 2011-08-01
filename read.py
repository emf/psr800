

import sunau

# MONKEY PATCH sunau!  The .au files generated by the GRE PSR-800 scanner are
# not quite compliant.   The metadata is null seperated fields, which confuses
# the _info parser, and the header size is "too large". 
class Au_read:

    def __init__(self, f):
        if type(f) == type(''):
            import __builtin__
            f = __builtin__.open(f, 'rb')
        self.initfp(f)

    def __del__(self):
        if self._file:
            self.close()

    def initfp(self, file):
        self._file = file
        self._soundpos = 0
        magic = int(sunau._read_u32(file))
        if magic != sunau.AUDIO_FILE_MAGIC:
            raise Error, 'bad magic number'
        self._hdr_size = int(sunau._read_u32(file))
        if self._hdr_size < 24:
            raise sunau.Error, 'header size too small'
        #print self._hdr_size
        if self._hdr_size > 512:
            raise sunau.Error, 'header size ridiculously large'
        self._data_size = sunau._read_u32(file)
        if self._data_size != sunau.AUDIO_UNKNOWN_SIZE:
            self._data_size = int(self._data_size)
        self._encoding = int(sunau._read_u32(file))
        if self._encoding not in sunau._simple_encodings:
            raise sunau.Error, 'encoding not (yet) supported'
        if self._encoding in (sunau.AUDIO_FILE_ENCODING_MULAW_8, sunau.AUDIO_FILE_ENCODING_ALAW_8):
            self._sampwidth = 2
            self._framesize = 1
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_LINEAR_8:
            self._framesize = self._sampwidth = 1
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_LINEAR_16:
            self._framesize = self._sampwidth = 2
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_LINEAR_24:
            self._framesize = self._sampwidth = 3
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_LINEAR_32:
            self._framesize = self._sampwidth = 4
        else:
            raise sunau.Error, 'unknown encoding'
        self._framerate = int(sunau._read_u32(file))
        self._nchannels = int(sunau._read_u32(file))
        self._framesize = self._framesize * self._nchannels
        if self._hdr_size > 24:
            self._info = file.read(self._hdr_size - 24)
        else:
            self._info = ''

    def getmetadata(self):
    	from datetime import datetime
        d = {}
        d['datetime'] = datetime( ord(self._info[11]) + 1900, ord(self._info[9]) + 1,  ord(self._info[7]),
                                    ord(self._info[5]), ord(self._info[3]), ord(self._info[1]))
        #d['type'] -- dunno where this is stored, may be a database lookup.
        #d['length'] -- may be computed.
        d['alpha tag'] = self._info[19:self._info.find('\x00',19)]
        d['freq'] = self._info[53:64]
        return d

    def getfp(self):
        return self._file

    def getnchannels(self):
        return self._nchannels

    def getsampwidth(self):
        return self._sampwidth

    def getframerate(self):
        return self._framerate

    def getnframes(self):
        if self._data_size == sunau.AUDIO_UNKNOWN_SIZE:
            return sunau.AUDIO_UNKNOWN_SIZE
        if self._encoding in sunau._simple_encodings:
            return self._data_size / self._framesize
        return 0                # XXX--must do some arithmetic here

    def getcomptype(self):
        if self._encoding == sunau.AUDIO_FILE_ENCODING_MULAW_8:
            return 'ULAW'
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_ALAW_8:
            return 'ALAW'
        else:
            return 'NONE'

    def getcompname(self):
        if self._encoding == sunau.AUDIO_FILE_ENCODING_MULAW_8:
            return 'CCITT G.711 u-law'
        elif self._encoding == sunau.AUDIO_FILE_ENCODING_ALAW_8:
            return 'CCITT G.711 A-law'
        else:
            return 'not compressed'

    def getparams(self):
        return self.getnchannels(), self.getsampwidth(), \
                  self.getframerate(), self.getnframes(), \
                  self.getcomptype(), self.getcompname()

    def getmarkers(self):
        return None

    def getmark(self, id):
        raise sunau.Error, 'no marks'

    def readframes(self, nframes):
        if self._encoding in sunau._simple_encodings:
            if nframes == sunau.AUDIO_UNKNOWN_SIZE:
                data = self._file.read()
            else:
                data = self._file.read(nframes * self._framesize * self._nchannels)
            if self._encoding == sunau.AUDIO_FILE_ENCODING_MULAW_8:
                import audioop
                data = audioop.ulaw2lin(data, self._sampwidth)
            return data
        return None             # XXX--not implemented yet

    def rewind(self):
        self._soundpos = 0
        self._file.seek(self._hdr_size)

    def tell(self):
        return self._soundpos

    def setpos(self, pos):
        if pos < 0 or pos > self.getnframes():
            raise sunau.Error, 'position not in range'
        self._file.seek(pos * self._framesize + self._hdr_size)
        self._soundpos = pos

    def close(self):
        self._file = None

sunau.Au_read = Au_read

def uuidT(epochseconds):
    from uuid import UUID, getnode, RFC_4122
    """Generate a UUID based on given time and hardware address."""
    from random import randrange
    nanoseconds = int(epochseconds * 1e9)
    # 0x01b21dd213814000 is the number of 100-ns intervals between the
    # UUID epoch 1582-10-15 00:00:00 and the Unix epoch 1970-01-01 00:00:00.
    timestamp = int(nanoseconds/100) + 0x01b21dd213814000
    clock = randrange(1<<16) # don't use stable storage
    time_low = timestamp & (0x100000000 - 1)
    time_mid = (timestamp >> 32) & 0xffff
    time_hi_ver = (timestamp >> 48) & 0x0fff
    clock_low = clock & 0xff
    clock_hi_res = (clock >> 8) & 0x3f
    node = getnode()
    uuid = UUID(fields=(time_low, time_mid, time_hi_ver, clock_low, clock_hi_res, node) )
    return uuid

import os
import fnmatch
from time import mktime
from datetime import datetime
import shutil
import sqlite3

inputdir = "."
outputdir = "../tmp/"

conn = sqlite3.connect(outputdir+"recordings.db")
c = conn.cursor()
try:
    c.execute('create table rec (freq text, name text, time text, filename text);')
    c.execute('create index f_idx on rec(freq);')
    c.execute('create index n_idx on rec(name);')
except sqlite3.OperationalError:
    pass

for root, dirs, files in os.walk(inputdir):
    for filename in fnmatch.filter(files, "*.AU"):
        objname = os.path.join(root, filename)
        f = sunau.open(objname, 'r')
        M =  f.getmetadata()
        f.close()
        # generate a new unique filename; a uuid based on the recording's time
        t = int(mktime(M['datetime'].timetuple()))      # time in epochseconds -> rec.time
        newf = str(uuidT(t)) + ".au"                    # new file name -> rec.filename
        print objname, "->", outputdir+newf
        c.execute('insert into rec values(?,?,?,?);', (M['freq'], M['alpha tag'], t, newf) )
        shutil.move(objname, outputdir+newf)
    conn.commit()

