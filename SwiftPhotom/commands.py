"""Run HEASoft shell commands (uvotimsum, uvotmaghist, fcopy, fappend)."""
import subprocess
import sys


def run(_command):
    """Execute a shell command and return stdout; exit on stderr.

    Parameters
    ----------
    _command : str
        Shell command to run (e.g. ``uvotimsum infile outfile ...``).

    Returns
    -------
    bytes
        Standard output of the command.

    Raises
    ------
    SystemExit
        If the command writes to stderr.
    """
    pid = subprocess.Popen(_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = pid.communicate()
    if error:
        print('ERROR while running ' + _command)
        print(error)
        sys.exit()
    return output


def uvotimsum(_in, _out, _exclude='none', ignoreframetime=False):
    """Sum UVOT sky images into a single output file.

    Parameters
    ----------
    _in : str
        Input FITS file (optionally with extension specifier).
    _out : str
        Output FITS file path.
    _exclude : str, optional
        Comma-separated extension indices to exclude, or ``'none'``.
    ignoreframetime : bool, optional
        If True, combine extensions with different FRAMTIME (uvotimsum
        ignoreframetime=yes). Photometry on the sum may be less accurate.
    """
    ign = 'yes' if ignoreframetime else 'no'
    comm = 'uvotimsum %s %s exclude=%s ignoreframetime=%s' % (_in, _out, _exclude, ign)
    run(comm)

def uvotmaghist(_in, _reg, _bgreg, _out, _gif):
    """Run uvotmaghist for aperture photometry with curve-of-growth correction.

    Parameters
    ----------
    _in : str
        Input image or stacked product FITS file.
    _reg : str
        DS9 region file for the source aperture.
    _bgreg : str
        DS9 region file for the background.
    _out : str
        Output photometry FITS file.
    _gif : str
        Output plot file path (e.g. GIF).
    """
    comm = ('uvotmaghist %s srcreg=%s bkgreg=%s outfile=%s plotfile=%s '
            'coinfile=caldb zerofile=caldb exclude=none chatter=0 clobber=yes '
            'logtime=no psffile=caldb apercorr=curveofgrowth' % (_in, _reg, _bgreg, _out, _gif))
    run(comm)


def fappend(_in, _out):
    """Append one FITS file to another using HEASoft fappend.

    Parameters
    ----------
    _in : str
        FITS file to append.
    _out : str
        Target FITS file (will have _in appended).
    """
    comm = 'fappend ' + _in + ' ' + _out
    run(comm)


def fcopy(_in, _out):
    """Copy a FITS file using HEASoft fcopy.

    Parameters
    ----------
    _in : str
        Source FITS file path.
    _out : str
        Destination FITS file path.
    """
    comm = 'fcopy ' + _in + ' ' + _out
    run(comm)
