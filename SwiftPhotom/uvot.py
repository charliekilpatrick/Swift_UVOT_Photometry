"""UVOT-specific logic: filter handling, aspect correction, product creation, photometry extraction."""
import os
import json
import astropy.io.fits as pf
import SwiftPhotom.errors
import SwiftPhotom.commands as sc
import numpy as np
import matplotlib.pyplot as plt

ZP = {'V': [17.88, 0.01], 'B': [18.98, 0.02], 'U': [19.36, 0.02], 'UVW1': [18.95, 0.03],
      'UVM2': [18.54, 0.03], 'UVW2': [19.11, 0.03]}
Vega = {'V': -0.01, 'B': -0.13, 'U': 1.02, 'UVW1': 1.51, 'UVM2': 1.69, 'UVW2': 1.73}

mjdref = 51910.0  # JD reference used by Swift


def sort_filters(_filt_list):
    """Parse filter selection into a list of UVOT filter names.

    Parameters
    ----------
    _filt_list : str
        One of ``'ALL'``, ``'OPT'``, ``'UV'``, or a comma-separated list of
        filter names (e.g. ``'V,U,UVM2'``). Case-insensitive.

    Returns
    -------
    list of str
        Canonical filter names, e.g. ``['V', 'B', 'U', 'UVW1', 'UVM2', 'UVW2']``.

    Raises
    ------
    SwiftPhotom.errors.FilterError
        If no valid filter is found (e.g. all tokens invalid).
    """
    
    full_filter_list=['V','B','U','UVW1','UVM2','UVW2']
    if _filt_list=='ALL':
        return full_filter_list
    elif _filt_list=='OPT':
        return ['V','B','U']
    elif _filt_list=='UV':
        return ['UVW1','UVM2','UVW2']
    else:
        out_filter_list=[]
        for _f in _filt_list.split(','):
            if _f.upper() not in full_filter_list:
                print('WARNING - Filter %s not recognized. Skipped.\n' % _f)
                continue
            out_filter_list.append(_f.upper())
        
        if len(out_filter_list)==0:
            raise SwiftPhotom.errors.FilterError
        
        return out_filter_list

def load_obsid(_obsid_string):
    """Find sky frames for a given Swift ObsID under the current working directory.

    Searches recursively for files matching ``sw<obsID>*_sk.img`` or ``*_sk.img.gz``.
    Skips paths containing ``products``.

    Parameters
    ----------
    _obsid_string : str
        Observation ID (e.g. ``'00013174'`` or ``'13174'``); zero-padded to 8 digits.

    Returns
    -------
    list of str
        Paths to matching sky frame files.
    """
    # In the file path the ObsID has 8 digits, with leading zeros
    obsid=_obsid_string.zfill(8)

    out_file_list=[]

    for root, dirs, files in os.walk("."):
        for file in files:
            if file.startswith('sw'+obsid) and (file.endswith('_sk.img.gz') or file.endswith('_sk.img')):
                sky_frame = os.path.join(root,file)
                #skipping files in the products folder
                if 'products' not in os.path.normpath(sky_frame).split(os.sep):
                    out_file_list.append(sky_frame)
    
    return out_file_list


def interpret_infile(_infile):
    """Interpret CLI input into object and template file lists.

    Each element of _infile can be: a path to a single sky image, a path to a
    list file (one path per line), or an ObsID string. Expands ObsIDs and list
    files into full file paths.

    Parameters
    ----------
    _infile : list of str
        One or two elements: [object_spec], or [object_spec, template_spec].

    Returns
    -------
    list of list of str
        [object_file_list, template_file_list]. Flattened file paths per role.

    Raises
    ------
    SwiftPhotom.errors.ListError
        If a list file contains no valid paths or ObsIDs.
    SwiftPhotom.errors.FileNotFound
        If an ObsID is given but no matching sky frames are found.
    """
    file_list = [[], []]
    
    for i in range(len(_infile)):
        if os.path.isfile(_infile[i]):
            file_exist=1
        else:
            file_exist=0
        
        if file_exist:
            #single file is provided
            if _infile[i].endswith('_sk.img.gz') or _infile[i].endswith('_sk.img'):
                file_list[i].append(_infile[i])
            else:
                with open(_infile[i]) as inp:
                    for line in inp:
                        ff=line.strip('\n')
                        if os.path.isfile(ff):
                            file_list[i].append(ff)
                        else:
                            list_from_obsid = load_obsid(ff)
                            if len(list_from_obsid) == 0:
                                print(ff+' not found. Skipped.')
                            else:
                                file_list[i] = file_list[i] + list_from_obsid
                
                if len(file_list[i])==0:
                    raise SwiftPhotom.errors.ListError(_infile[i])

        #If no file exists, maybe an ObsID was provided.
        else:
            file_list[i] = load_obsid(_infile[i])
            
            #If we reached this point there is a problem with
            if len(file_list[i])==0:
                raise SwiftPhotom.errors.FileNotFound

    return file_list

def get_aperture_size(_reg):
    """Read the aperture radius in arcsec from a DS9 circle region file.

    Parameters
    ----------
    _reg : str
        Path to a DS9 region file containing a circle (e.g. ``fk5;circle(...,3")``).

    Returns
    -------
    str
        Aperture size as string (e.g. ``'3'`` or ``'5'``), without the arcsec suffix.
    """
    with open(_reg) as inp:
        for line in inp:
            if line[0]=='#':continue
            size=line.strip('\n').split(',')[-1][:-2]
    
    size = size.rstrip('0')
    
    #Very brutal way to check if the size is an int
    if size[-1]=='.':
        size = size[:-1]
    
    return size

def _warn_bad_aspect(_infile, bad_inds):
    """Print one warning per extension that is not aspect-corrected (ASPCORR != 'DIRECT').

    Parameters
    ----------
    _infile : str
        Path to the FITS file.
    bad_inds : list of int
        Extension indices to warn about.
    """
    hdu = pf.open(_infile)
    for i in bad_inds:
        ext = hdu[i].header.get('EXTNAME', str(i))
        print('WARNING - Extension '+str(i)+ ' '+str(ext)+ ' of '+_infile+' has not been aspect corrected. Skipping in analysis.')
    hdu.close()
    del hdu


def check_aspect_correction(_infile):
    """Identify aspect-corrected extensions and print warnings for the rest.

    Parameters
    ----------
    _infile : str
        Path to the FITS file.

    Returns
    -------
    good : list of int
        Extension indices with ASPCORR == 'DIRECT'.
    bad : list of int
        Extension indices without aspect correction (warnings printed).
    """
    good, bad = get_aspect_corrected_extension_indices(_infile)
    if bad:
        _warn_bad_aspect(_infile, bad)
    return good, bad


def get_aspect_corrected_extension_indices(_infile):
    """Return extension indices split by aspect correction status.

    Only extensions with ASPCORR == 'DIRECT' are considered good for analysis;
    others are excluded to avoid bad astrometry.

    Parameters
    ----------
    _infile : str
        Path to the FITS file.

    Returns
    -------
    good : list of int
        Extension indices where ASPCORR == 'DIRECT'.
    bad : list of int
        Extension indices where ASPCORR != 'DIRECT' or missing.
    """
    hdu = pf.open(_infile)
    good = []
    bad = []
    for i in range(len(hdu)):
        if hdu[i].name == 'PRIMARY':
            continue
        try:
            if hdu[i].header.get('ASPCORR', '').strip().upper() == 'DIRECT':
                good.append(i)
            else:
                bad.append(i)
        except (KeyError, TypeError):
            bad.append(i)
    hdu.close()
    del hdu
    return good, bad


def sort_file_list(_flist):
    """Group file paths by UVOT filter using the FILTER keyword in each FITS primary header.

    Parameters
    ----------
    _flist : list of str
        Paths to UVOT sky or product FITS files.

    Returns
    -------
    dict
        Mapping of filter name to list of file paths (e.g. ``{'U': [path1, path2]}``).
    """
    out_file_list = {}
    for file in _flist:
        filter=pf.getheader(file)['FILTER']
        if filter not in out_file_list:
            out_file_list[filter]=[]
        out_file_list[filter].append(file)

    return out_file_list

def combine(_list, _outfile):
    """Concatenate multiple FITS files into one using fcopy for the first and fappend for the rest.

    Parameters
    ----------
    _list : list of str
        Ordered list of input FITS file paths.
    _outfile : str
        Output FITS file path (overwritten if present).
    """
    for i, img in enumerate(_list):
        if i==0:
            sc.fcopy(img,_outfile)
        else:
            sc.fappend(img,_outfile)

def create_product(_flist, _filter, template=0, no_combine=0, allow_different_frametime=False):
    """Build a single product FITS file per filter from a list of sky images.

    For each file, only aspect-corrected (ASPCORR=DIRECT) extensions are used.
    By default, multi-extension files are merged with uvotimsum; if FRAMTIMEs
    differ, extensions are left unmerged unless allow_different_frametime is True.
    With no_combine=True, each extension is written separately. All resulting
    images are then concatenated into one product file in reduction/<filter>/.

    Parameters
    ----------
    _flist : list of str
        Paths to UVOT sky FITS files for this filter.
    _filter : str
        Filter name (e.g. 'U', 'UVW2') for directory and filename.
    template : int, optional
        If non-zero, output is named as template product (e.g. templ_<filter>.img).
    no_combine : int, optional
        If non-zero, do not merge extensions with uvotimsum; append each extension.
    allow_different_frametime : bool, optional
        If True, merge extensions even when FRAMTIME differs (ignoreframetime=yes).

    Returns
    -------
    str
        Path to the product FITS file (e.g. reduction/U/<object>_U.img).
    """
    out_dir = os.path.join('reduction', _filter, 'mid-products')
    if not os.path.isdir(out_dir):
        os.mkdir(out_dir)
    
    fig_dir=os.path.join('reduction',_filter,'figures')
    if not os.path.isdir(fig_dir):
        os.mkdir(fig_dir)

    prod_list=[]
    for file in _flist:
        good_inds, bad_inds = get_aspect_corrected_extension_indices(file)
        if bad_inds:
            _warn_bad_aspect(file, bad_inds)
        if not good_inds:
            print('WARNING - Skipping '+file+' (no aspect-corrected extensions).')
            continue
        
        hdu=pf.open(file)
        
        if no_combine:
            for i in good_inds:
                prod_list.append(file+'['+str(i)+']')
            hdu.close()
            del hdu
            continue
        
        obsID=hdu[0].header['OBS_ID']
        out_file=os.path.join(out_dir,obsID+'_'+_filter+'.fits')
        if os.path.isfile(out_file):
            os.remove(out_file)
        
        framtime=[]
        for i in good_inds:
            framtime.append(hdu[i].header['FRAMTIME'])
        
        same_frametime = len(set(framtime)) == 1
        exclude_list = ','.join(str(i) for i in bad_inds) if bad_inds else 'none'

        if same_frametime and not bad_inds:
            sc.uvotimsum(file, out_file, _exclude='none')
            prod_list.append(out_file)
        elif same_frametime and bad_inds:
            sc.uvotimsum(file, out_file, _exclude=exclude_list)
            prod_list.append(out_file)
        elif allow_different_frametime:
            if bad_inds:
                sc.uvotimsum(file, out_file, _exclude=exclude_list, ignoreframetime=True)
            else:
                sc.uvotimsum(file, out_file, _exclude='none', ignoreframetime=True)
            prod_list.append(out_file)
        else:
            print('WARNING - extensions of '+file+' have different FRAMTIMEs. Left unmerged.')
            for i in good_inds:
                prod_list.append(file+'['+str(i)+']')
        hdu.close()
        del hdu

    if not template:
        objname = pf.getheader(file)['OBJECT']
        objname = objname.replace('(','')
        objname = objname.replace(')','')
        objname = objname.replace(',','_')
        objname = objname.replace(' ','_')

        prod_out_file= os.path.join('reduction',_filter,objname+'_'+_filter+'.img')
    else:
        prod_out_file= os.path.join('reduction',_filter,'templ_'+_filter+'.img')
    if os.path.isfile(prod_out_file):
        os.remove(prod_out_file)

    combine(prod_list,prod_out_file)

    return prod_out_file

def run_uvotmaghist(_prod_file, _sn_reg, _bg_reg, _filter):
    """Run uvotmaghist on a product file and write photometry FITS and plot.

    Parameters
    ----------
    _prod_file : str
        Path to the stacked or combined product FITS file.
    _sn_reg : str
        DS9 source region file path.
    _bg_reg : str
        DS9 background region file path.
    _filter : str
        Filter name (for figure subdirectory).

    Returns
    -------
    str
        Path to the output photometry FITS file (e.g. ..._phot.fits).
    """
    fig_dir = os.path.join('reduction', _filter, 'figures')
    photo_out=_prod_file[:-4]+'_phot.fits'
    gif_out=os.path.join(fig_dir,_prod_file.split('/')[-1][:-4]+'_phot.gif')
    if os.path.isfile(photo_out):
        os.remove(photo_out)
    if os.path.isfile(gif_out):
        os.remove(gif_out)
    sc.uvotmaghist(_prod_file,_sn_reg,_bg_reg, photo_out,gif_out)

    return photo_out

def extract_photometry(_phot_file, _ab, _det_limit, _ap_size, _templ_file=None):
    """Extract magnitudes from uvotmaghist output and optionally subtract template.

    Uses both the user aperture and the 5 arcsec aperture; applies aperture and
    coincidence-loss corrections. Detections above _det_limit S/N get magnitude
    and error; below that, 3-sigma upper limit is reported. Writes count-rate and
    magnitude figures to reduction/<filter>/figures/.

    Parameters
    ----------
    _phot_file : str
        Path to the uvotmaghist output FITS file.
    _ab : int or bool
        If true, use AB magnitudes; otherwise Vega.
    _det_limit : float
        Signal-to-noise threshold for detection vs. upper limit.
    _ap_size : str
        User aperture size in arcsec (e.g. '3').
    _templ_file : str, optional
        Path to template photometry FITS; if given, template subtraction is applied.

    Returns
    -------
    dict
        Keys ``'<ap>_arcsec'`` and ``'5_arcsec'``, each a list of dicts with
        'filter', 'mjd', 'mag', 'mag_err', 'upper_limit', 'mag_limit', etc.
    """
    if _templ_file is not None:
        template=1

    if _ab==1:
        Vega_corr={'V':0,'B':0,'U':0,'UVW1':0,'UVM2':0,'UVW2':0}
        mag_sys = 'AB'
    else:
        Vega_corr=Vega
        mag_sys = 'Vega'

    user_ap = _ap_size+'_arcsec'

    col={user_ap:'b','5_arcsec':'r'}
    mag={user_ap:[],'5_arcsec':[]}

    BCR_temp={}
    BCRe_temp={}

    for i, file in enumerate([_templ_file, _phot_file]):
        if file is None:
            #In case there is no template, nothing will be subtracted.
            BCR_temp={user_ap:0.,'5_arcsec':0.}
            BCRe_temp={user_ap:0.,'5_arcsec':0.}
            template=0
            continue
    
        hdu=pf.open(file)
        dd=hdu[1].data
        filter=dd['FILTER'][0]
        hdu.close()

        #The long-term detector sensitivity correction factor.
        SC=dd['SENSCORR_FACTOR']

        #This is the count rate for the user defined aperture
        S3BCR=dd['COI_SRC_RATE']*SC
        
        #adding 3% error on count rate of the source in quadrature to poission error
        if template and i==1:
            S3BCRe=np.sqrt((dd['COI_SRC_RATE_ERR'])**2+(S3BCR*0.03)**2)
        else:
            S3BCRe=dd['COI_SRC_RATE_ERR']
        
        #These is the count rate for 5arcsec
        S5CR=dd['RAW_STD_RATE']*dd['COI_STD_FACTOR']
        S5CRe=dd['RAW_STD_RATE_ERR']*dd['COI_STD_FACTOR']
        S5BCR=((dd['RAW_STD_RATE'] *dd['COI_STD_FACTOR'] * SC) - (dd['COI_BKG_RATE'] * SC * dd['STD_AREA']))
        if template and i==1:
            S5BCRe=np.sqrt((S5CRe)**2+(S5CR*0.03)**2+(dd['COI_BKG_RATE_ERR']*dd['STD_AREA'])**2)
        else:
            S5BCRe=np.sqrt((S5CRe)**2+(dd['COI_BKG_RATE_ERR']*dd['STD_AREA'])**2)
        
        
        
        fig_dir=os.path.join('reduction',filter,'figures')
        fig=plt.figure()
        ax=fig.add_subplot(111)
        
        if template:
            fig_mag=plt.figure()
            ax_mag=fig_mag.add_subplot(111)
        
        fig_sub=plt.figure()
        ax_sub=fig_sub.add_subplot(111)

        for BCR,BCRe,label in [[S3BCR,S3BCRe,user_ap] , [S5BCR,S5BCRe,'5_arcsec']]:
        



            if i==0:
                epochs=range(len(BCR))
                ax.errorbar(epochs,BCR,yerr=BCRe,marker='o', color=col[label],label=label)
            
                #weighed avarage the template fluxes
                BCR_temp[label]=np.sum(BCR/BCRe**2)/np.sum(1./BCRe**2)
                BCRe_temp[label]=np.sqrt(1./np.sum(1./BCRe**2))
                
                xx=[0,len(BCR)-1]
                ax.plot(xx,[BCR_temp[label]]*2,color=col[label],lw=2)
                ax.fill_between(xx, [BCR_temp[label]+BCRe_temp[label]]*2,  [BCR_temp[label]-BCRe_temp[label]]*2, color=col[label],lw=2, alpha=0.2)
            
                ax.set_xlabel('Epoch')
            
                print('Galaxy count rates in '+label.split('_')[0]+'" aperture: %.3f +- %.3f' %(BCR_temp[label],BCRe_temp[label]))

            else:
                all_point=[]
                mjd=mjdref+(dd['TSTART']+dd['TSTOP'])/2./86400.
                ax.errorbar(mjd,BCR,yerr=BCRe,marker='o', color=col[label],label=label)
                
                ax.set_xlabel('MJD')
                
                
                #subtract galaxy, propogate error
                BCGR=(BCR-BCR_temp[label])
                BCGRe=np.sqrt((BCRe)**2+(BCRe_temp[label])**2)

                if label==user_ap:
                    # apply aperture correction
                    BCGAR=BCGR*dd['AP_FACTOR']
                    BCGARe=BCGRe*dd['AP_FACTOR_ERR']
                    BCAR=BCR*dd['AP_FACTOR']
                    BCARe=BCRe*dd['AP_FACTOR_ERR']
                else:
                    BCGAR=BCGR
                    BCGARe=BCGRe
                    BCAR=BCR
                    BCARe=BCRe
                
                if template:
                    #Not subtracted magnitudes
                    or_mag=-2.5*np.log10(BCAR)+ZP[filter][0]-Vega_corr[filter]
                    or_mage=np.sqrt(((2.5/np.log(10.))*((BCRe/BCAR)))**2+ZP[filter][1]**2)
                
                    mag_host=-2.5*np.log10(BCR_temp[label])+ZP[filter][0]-Vega_corr[filter]
                    mag_hoste=np.sqrt(((2.5/np.log(10.))*((BCRe_temp[label]/BCR_temp[label])))**2+ZP[filter][1]**2)
                
                    ax_mag.errorbar(mjd,or_mag,yerr=or_mage,marker='o', color=col[label],label=label)

                    ax_mag.plot([min(mjd),max(mjd)],[mag_host]*2,color=col[label],lw=2)
                    ax_mag.fill_between([min(mjd),max(mjd)], [mag_host+mag_hoste]*2,  [mag_host-mag_hoste]*2, color=col[label],lw=2, alpha=0.2)

                
            



                # determine significance/3 sigma upper limit
                BCGARs=BCGAR/BCGARe
                BCGAMl=(-2.5*np.log10(3.*BCGARe))+ZP[filter][0]-Vega_corr[filter]

                #convert rate,err to magnitudes"
                for j,CR in enumerate(BCGARs):
                    mag[label].append({
                    'filter':filter,
                    'aperture_correction':float(dd['AP_FACTOR'][j]),
                    'coincidence_loss_correction':float(dd['COI_STD_FACTOR'][j]),
                    'mag_sys':mag_sys,
                    'mag_limit':float(BCGAMl[j]),
                    'template_subtracted':bool(template),
                    'mjd':float(mjd[j])
                    })
                    
                    #detection
                    if BCGARs[j]>=_det_limit:
                        BCGAM=-2.5*np.log10(BCGAR[j])+ZP[filter][0]-Vega_corr[filter]
                        BCGAMe=np.sqrt(((2.5/np.log(10.))*((BCGARe[j]/BCGAR[j])))**2+ZP[filter][1]**2)
                    
                        mag[label][-1]['upper_limit']=False
                        print('%.2f\t%.3f\t%.3f' % (mjd[j],BCGAM,BCGAMe))
                    #non detection
                    else:
                        BCGAM=BCGAMl[j]
                        BCGAMe=0.2
                        
                        mag[label][-1]['upper_limit']=True
                        print('%.2f\t> %.3f (%.2f)' % (mjd[j],BCGAM,np.fabs(BCGARs[j])))
                    
                    mag[label][-1]['mag'] = float(BCGAM)
                    mag[label][-1]['mag_err'] = float(BCGAMe)
                    all_point.append([mjd[j],BCGAM])
 
                detections = [[ep['mjd'], ep['mag'], ep['mag_err']] for ep in mag[label] if not ep['upper_limit']]
                non_detections = [[ep['mjd'], ep['mag'], ep['mag_err']] for ep in mag[label] if ep['upper_limit']]
                
                if len(detections)>0:
                    xx,yy,ee=zip(*sorted(detections))
                    ax_sub.errorbar(xx,yy,yerr=ee,marker='o', color=col[label],label=label,ls='')

                
                if len(non_detections)>0:
                    xx,yy,ee=zip(*sorted(non_detections))
                    ax_sub.errorbar(xx,yy, yerr=[np.abs(np.array(ee)),[0]*len(ee)], uplims=True, marker='o', color=col[label],label=label,ls='')
                
                #since I'm plotting detections and non detections separately
                #this is done only to have a line connecting all epochs
                xx,yy=zip(*sorted(all_point))
                ax_sub.plot(xx,yy, color=col[label])

                if label==user_ap:
                    print('\n'+_ap_size+'" aperture done!\n')
                else:
                    print('\n5" aperture done!\n')
        
        if i==1:
        
            ax_sub.set_title(file.split('/')[-1])
            ax_sub.set_xlabel('MJD')
            ax_sub.set_ylabel('Mag')
            ax_sub.invert_yaxis()
            ax_sub.legend()
            
            
            out_fig=os.path.join(fig_dir,file.split('/')[-1][:-5]+'_mag_final.png')
            if os.path.isfile(out_fig):
                os.remove(out_fig)

            fig_sub.savefig(out_fig)
            plt.close(fig_sub)
            del fig_sub
            del ax_sub
            
            
            if template:
                ax_mag.set_title(file.split('/')[-1])
                ax_mag.set_xlabel('MJD')
                ax_mag.set_ylabel('Mag')
                ax_mag.invert_yaxis()
                ax_mag.legend()


                out_fig=os.path.join(fig_dir,file.split('/')[-1][:-5]+'_mag.png')
                if os.path.isfile(out_fig):
                    os.remove(out_fig)

                fig_mag.savefig(out_fig)
                plt.close(fig_mag)
                del fig_mag
                del ax_mag

        ax.set_title(file.split('/')[-1])
        ax.set_ylabel('Coincident-corrected count rates')
        ax.legend()
        
        

        out_fig=os.path.join(fig_dir,file.split('/')[-1][:-5]+'_counts.png')
        if os.path.isfile(out_fig):
            os.remove(out_fig)

        fig.savefig(out_fig)
        plt.close(fig)
        del fig
        del ax
        


    return mag

def output_mags(_mag, _ap_size, obj=None):
    """Write extracted photometry to JSON files and optionally a .phot file.

    Parameters
    ----------
    _mag : dict
        Output from extract_photometry (keys like '3_arcsec', '5_arcsec').
    _ap_size : str
        User aperture size string (e.g. '3').
    obj : str, optional
        If set, also write `<obj>_Swift.phot` with 5 arcsec mags.
    """
    user_ap = _ap_size + '_arcsec'

    with open(os.path.join('reduction', _ap_size + '_arcsec_photometry.json'), 'w') as out:
        out.write(json.dumps(_mag[user_ap], indent = 4))
    
    with open(os.path.join('reduction','5_arcsec_photometry.json'),'w') as out:
        out.write(json.dumps(_mag['5_arcsec'], indent = 4))

    print('5-arcsec output photometry:\n')
    print('#'*80+'\n\n')
    _mag['5_arcsec'] = sorted(_mag['5_arcsec'], key=lambda x: x['mjd'])
    mjds = []
    newdata = []
    for val in _mag['5_arcsec']:
        if val['mjd'] not in mjds:
            mjds.append(val['mjd'])
            newdata.append(val)
    _mag['5_arcsec'] = newdata

    if obj:
        outfile = open(obj+'_Swift.phot','w')

    for photom in _mag['5_arcsec']:
        mjd = photom['mjd']
        filt = photom['filter'].rjust(5)
        if photom['upper_limit']:
            mag = photom['mag_limit']
            magerr = 0.0
        else:
            mag = photom['mag']
            magerr = photom['mag_err']

        mjd = '%.5f'%mjd
        mag = '%.4f'%mag
        magerr = '%.4f'%magerr

        print(mjd,filt,mag,magerr)
        if obj:
            outfile.write(f'{mjd} {filt} {mag} {magerr} \n')

