"""Help strings for Swift photometry CLI scripts (argparse descriptions)."""

description = '---Swift photometry---\n\nThis is a python wrapper of basic headas commands for the analysis of UVOT images.\n\n'

infile_help = ('If one argument is provide, simple aperture photometry will be performed. '
              'If two arguments are provided, template subtraction will be performed, with the second '
              'argument being the template reference. The input arguments can be either the Swift ObsID '
              '(ex. 00013174), or a single filter image (ex. sw00013174001uuu_sk.img.gz). '
              'A list of the above objects is also accepted, but not a list containing a combination of them. '
              'Both \'.img\' and \'.gz\' images are accepted.')

sn_reg = ('Region file indicating the coordinates of the SN. The format is the default region file from ds9 '
          '(e.g. fk5;circle(00:00:00.000,+00:00:00.000,3")). The default radius is 3", but the photometry '
          'will also be compared with a 5" aperture. If this argument is not provided, the script will assume '
          'that a file "snbkg.reg" exists.')

bg_reg = ('Region file indicating the area where to measure the background counts. The format is the default '
          'region file from ds9. This has to be an area free from contaminating sources. If this argument '
          'is not provided, the script will assume that a file "sn.reg" exists.')

det_limit = ('Signal-to-noise detection limit. A signal-to-noise above this value will be treated as true '
             'detection, while anything below will be treated as an upper limit.')

ab_mag = 'Change the magnitude system to AB (default is Vega).'

filter = ('Selection of filters to be analysed. Acceptable filters: V, B, U, UVW1, UVM2, UVW2, OPT, UV, ALL. '
          'Default is ALL. Flags for optical only (OPT) and ultraviolet only (UV) are also available. '
          'A custom subset can be provided as a comma-separated list with no spaces (e.g. V,U,UVM2).')

no_combine = ('Prevent merging different extensions of a single file. If set True, this applies to all '
              'files, including the template.')

obj = 'Name of object to save output data.'
