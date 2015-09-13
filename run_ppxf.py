# -*- coding: utf-8 -*-
"""
Created on Tue Apr 22 12:10:54 2014

@author: kadu

Program to run pPXF on hydra I data
"""
import os
import pickle

import numpy as np
import pyfits as pf
from scipy import ndimage
from scipy.signal import medfilt
import matplotlib.pyplot as plt

from ppxf import ppxf
import ppxf_util as util
from config import *
from load_templates import stellar_templates, emission_templates, \
                            wavelength_array
 
def run_ppxf(spectra, velscale):
    """ Run pPXF in a list of spectra"""
    ##########################################################################
    # Load templates for both stars and gas
    star_templates, logLam2, delta, miles= stellar_templates(velscale)
    gas_templates,logLam_gas, delta_gas, gas_files=emission_templates(velscale)
    ##########################################################################
    # Join templates and set components for fit
    templates = np.column_stack((star_templates, gas_templates))
    components = np.hstack((np.zeros(len(star_templates[0])),
                            np.ones(len(gas_templates[0]))))
    # Single component
    # templates = star_templates.copy()
    # components = np.zeros_like(templates)
    # templates_names = miles
    # components = np.zeros(len(templates))
    templates_names = np.hstack((miles, gas_files))
    ##########################################################################
    # Adapt guesses for the case there are more than one component
    comps = np.unique(components)
    if len(comps) == 1:
        components=0
        moments = [4]
    else:
        moments = [4,2]
    for i, spec in enumerate(spectra):
        print "pPXF run of spectrum {0} ({1} of {2})".format(spec, i+1,
              len(spectra))
        outfile = spec.replace(".fits", ".pkl")
        ######################################################################
        # Read one galaxy spectrum and define the wavelength range
        specfile = os.path.join(data_dir, spec)
        hdu = pf.open(specfile)
        spec_lin = hdu[0].data
        h1 = pf.getheader(specfile)
        lamRange1 = h1['CRVAL1'] + np.array([0.,h1['CDELT1']*(h1['NAXIS1']-1)])
        ######################################################################
        # Degrade observed spectra to match template resolution
        FWHM_dif = np.sqrt(FWHM_tem**2 - FWHM_spec**2)
        sigma = FWHM_dif/2.355/delta # Sigma difference in pixels
        spec_lin = ndimage.gaussian_filter1d(spec_lin,sigma)
        ######################################################################
        # Rebin to log scale
        galaxy, logLam1, velscale = util.log_rebin(lamRange1, spec_lin, 
                                                   velscale=velscale)
        ######################################################################
        # First guess for the noise
        noise = np.ones_like(galaxy) * np.std(galaxy - medfilt(galaxy, 5))
        ######################################################################
        # Calculate difference of velocity between spectrum and templates
        # due to different initial wavelength
        dv = (logLam2[0]-logLam1[0])*c
        ######################################################################
        # Set first guess from setup files
        start, goodPixels = read_setup_file(spec, logLam1, mask_emline=False)
        ######################################################################
        # Expand start variable to include multiple components
        if len(comps) > 1:
            start = np.tile(start, len(comps)).reshape(len(comps),2)
            start[1,1] = 30.
        ######################################################################
        # First pPXF interaction
        pp0 = ppxf(templates, galaxy, noise, velscale, start,
                   goodpixels=goodPixels, plot=False, moments=moments,
                   degree=12, mdegree=-1, vsyst=dv, component=components)
        rms0 = galaxy[goodPixels] - pp0.bestfit[goodPixels]
        noise0 = 1.4826 * np.median(np.abs(rms0 - np.median(rms0)))
        noise0 = np.zeros_like(galaxy) + noise0
        # Second pPXF interaction, realistic noise estimation
        pp = ppxf(templates, galaxy, noise0, velscale, start,
                  goodpixels=goodPixels, plot=False, moments=moments,
                  degree=12, mdegree=-1, vsyst=dv, component=components)
        raw_input(pp.sol)
        pp.template_files = templates_names
        pp.star = 0
        ######################################################################
        # Save to output file to keep session
        with open(spec.replace(".fits", ".pkl"), "w") as f:
            pickle.dump(pp, f)
        ######################################################################
    return

def read_setup_file(gal, logw, mask_emline=True):
    """ Read setup file to set first guess and regions to be avoided. """
    w = np.exp(logw)
    filename = os.path.join(data_dir, gal + ".setup")
    with open(filename) as f:
        f.readline()
        start = f.readline().split()
    start = np.array(start, dtype=float)
    ranges = np.loadtxt(filename, skiprows=5)
    ##########################################################################
    # Mask all the marked regions in the setup file
    if mask_emline:
        for i, (w1, w2) in enumerate(ranges.reshape((len(ranges)/2, 2))):
            if i == 0:
                good = np.where(np.logical_and(w > w1, w < w2))[0]
            else:
                good = np.hstack((good, np.where(np.logical_and(w > w1,
                                                                w < w2))[0]))
        good = np.array(good)
        good.sort()

    ##########################################################################
    # Mask only regions in the beginning and in the end of the spectra plus
    # the residuals in the emission line at 5577 Angstroms
    else:
        ranges = [[np.min(ranges), 5577. - 15], [5577. + 15, np.max(ranges)]]
        for i, (w1, w2) in enumerate(ranges):
            if w1 >= w2:
                continue
            if i == 0:
                good = np.where(np.logical_and(w > w1, w < w2))[0]
            else:
                good = np.hstack((good, np.where(np.logical_and(w > w1,
                                                                w < w2))[0]))
        good = np.array(good)
        good.sort()
        return start, good

def make_table(spectra, outfile):
    """ Make table with results. """
    head = ("{0:<30}{1:<14}{2:<14}{3:<14}{4:<14}{5:<14}{6:<14}{7:<14}"
             "{8:<14}{9:<14}{10:<14}\n".format("# FILE", "V", "dV", "S", 
              "dS", "h3", "dh3", "h4", "dh4", "chi/DOF", "S/N (/ pixel)"))
    results = []
    for spec in spectra:
        pkl = spec.replace(".fits", ".pkl") 
        if not os.path.exists(pkl):
            continue
        with open(pkl) as f:
            pp = pickle.load(f)
        rms = pp.galaxy - pp.bestfit
        noise = 1.4826 * np.median(np.abs(rms - np.median(rms)))
        signal = np.sum(pp.galaxy[pp.goodpixels]) / len(pp.goodpixels)
        sn = signal / noise
        comment = "#" if pp.error[1] == 0.0 else ""
        comment = ""
        line = [spec, pp.sol[0], pp.error[0],
                pp.sol[1], pp.error[1], pp.sol[2], pp.error[2], pp.sol[3],
                pp.error[3], pp.chi2, sn]
        results.append(line)
    results = np.array(results)
    with open(outfile, "w") as f:
        f.write(head)
        np.savetxt(f, results, fmt="%.30s")
    return

def em_analysis(spectra):
    for spec in spectra:
        with open(spec.replace(".fits", ".pkl")) as f:
            pp = pickle.load(f)
        print spec, pp.sol[1],
        weights = pp.weights.copy()
        weights[:-3] = 0.
        em = pp.matrix.dot(weights) / pp.noise
        print em.max()
        plt.ion()
        plt.plot(em, "-k")
        plt.pause(0.001)
        plt.show()
        raw_input()
        plt.clf()

class pPXF():
    """ Class to read pPXF pkl files """
    def __init__(self, spec, velscale, pklfile=None):
        """ Load the pkl file from previous ppxf fit and define some atributes.
        """
        if pklfile == None:
            pklfile = spec.replace(".fits", ".pkl")
        with open(pklfile) as f:
            pp = pickle.load(f)
        self.__dict__ = pp.__dict__.copy()
        self.spec = spec
        if not os.path.exists(os.path.join(os.getcwd(), spec)):
            self.spec = os.path.join(data_dir, spec)
        self.velscale = velscale
        self.w = wavelength_array(self.spec)
        self.flux = pf.getdata(self.spec)
        self.flux_log, self.logw, velscale = util.log_rebin(
                        [self.w[0], self.w[-1]], self.flux, velscale=velscale)
        self.w_log = np.exp(self.logw)
        self.header = pf.getheader(self.spec)
        self.lam = self.header['CRVAL1'] + np.array([0.,
                              self.header['CDELT1']*(self.header['NAXIS1']-1)])
        ######################################################################
        # Read templates
        self.templates, self.logLam2, self.delta = stellar_templates(velscale,
                                                                  norm=False)
        ######################################################################
        # Convolve our spectra to match MILES resolution
        FWHM_dif = np.sqrt(FWHM_tem**2 - FWHM_spec**2)
        sigma = FWHM_dif/2.355/self.delta # Sigma difference in pixels
        ######################################################################
        spec_lin = ndimage.gaussian_filter1d(self.flux,sigma)
        # Rebin to logarithm scale
        galaxy, self.logLam1, velscale = util.log_rebin(self.lam, spec_lin,
                                                   velscale=velscale)
        self.dv = (self.logLam2[0]-self.logLam1[0])*c
        # if self.sky != None:
        #     sky = self.weights[-1] * self.sky.T[0]
        #     self.bestfit -= sky
        #     self.galaxy -= sky
        #     skyspec = os.path.join(sky_data_dir, spec.replace("fin1", "sky1"))
        #     sky_lin = pf.getdata(skyspec)


        return

    def calc_sn(self, w1=5200., w2=5500.):
        idx = np.logical_and(self.w >=w1, self.w <=w2)
        self.res = self.galaxy[idx] - self.bestfit[idx]
        # Using robust method to calculate noise using median deviation
        self.noise = 1.4826 * np.median(np.abs(self.res - np.median(self.res)))
        self.signal = np.sum(self.galaxy[idx]) / len(self.galaxy[idx])
        self.sn = self.signal / self.noise
        return

    def mc_errors(self, nsim=200):
        """ Calculate the errors using MC simulations"""
        errs = np.zeros((nsim, len(self.error)))
        for i in range(nsim):
            y = self.bestfit + np.random.normal(0, self.noise,
                                                len(self.galaxy))

            noise = np.ones_like(self.galaxy) * self.noise
            sim = ppxf(self.bestfit_unbroad, y, noise, velscale,
                       [0, self.sol[1]],
                       goodpixels=self.goodpixels, plot=False, moments=4,
                       degree=-1, mdegree=-1,
                       vsyst=self.vsyst, lam=self.lam, quiet=True, bias=0.)
            errs[i] = sim.sol
        median = np.ma.median(errs, axis=0)
        error = 1.4826 * np.ma.median(np.ma.abs(errs - median), axis=0)
        # Here I am using always the maximum error between the simulated
        # and the values given by pPXF.
        self.error = np.maximum(error, self.error)
        return

def speclist():
    """ Defines a sorted list of all spectra in FORS2 dataset.

    Spectra are sorted by mask and number, with HCC 007 spectra in the end. """
    masks = ["cen1", "cen2", "inn1", "inn2", "out1", "out2"]
    spectra, spectra2 = [], []
    for mask in masks:
        for i in range(60):
            n = "fin1_n3311{0}_s{1}.fits".format(mask, i)
            na = "fin1_n3311{0}_s{1}a.fits".format(mask, i)
            nb = "fin1_n3311{0}_s{1}b.fits".format(mask, i)
            s =  "s_n3311{0}_s{1}.fits".format(mask, i)
            for name in [n, na, nb]:
                if os.path.exists(os.path.join(data_dir, name)):
                    spectra.append(name)
            if os.path.exists(os.path.join(data_dir, s)):
                spectra2.append(s)
        spectra.extend(spectra2)
    return spectra



if __name__ == '__main__':
    ##########################################################################
    # Change to data directory according to setup.py program
    wdir = home + "/single2"
    os.chdir(wdir)
    spectra = speclist()
    ##########################################################################
    # Go to the main routine of fitting
    # velscale is defined in the setup.py file, it is used to rebin data
    # specs = [x for x in spectra if x.startswith("s")]
    run_ppxf(spectra, velscale)
    ##########################################################################
    # Make_table produces a table with summary of results and errors
    #spectra = [x for x in os.listdir(".") if x.endswith(".fits")]
    make_table(spectra, "ppxf_results.dat")
    ##########################################################################
    # Observe the results for the emission lines
    # em_analysis(spectra)
    ##########################################################################