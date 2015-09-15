# -*- coding: utf-8 -*-
"""
Created on Tue Oct  8 17:29:58 2013

@author: cbarbosa

Program to verify results from MCMC runs. 

"""

import os

import numpy as np
import matplotlib.pyplot as plt
from scipy import stats
import matplotlib.cm as cm
import matplotlib.colors as colors
from matplotlib.backends.backend_pdf import PdfPages

from config import *

class Dist():
    """ Simple class to handle the distribution data of MCMC. """
    def __init__(self, data, lims):
        self.data = data
        self.pdf = stats.gaussian_kde(self.data)
        self.median = np.median(self.data)
        self.lims = lims
        self.x = np.linspace(lims[0], lims[1]+1, 1000)
        self.MAPP = self.x[np.argmax(self.pdf(self.x))]        

def hist2D(dist1, dist2):
    """ Plot distribution and confidence contours. """
    X, Y = np.mgrid[dist1.lims[0] : dist1.lims[1] : 20j, 
                    dist2.lims[0] : dist2.lims[1] : 20j]
    extent = [dist1.lims[0], dist1.lims[1], dist2.lims[0], dist2.lims[1]]
    positions = np.vstack([X.ravel(), Y.ravel()])    
    values = np.vstack([dist1.data, dist2.data]) 
    kernel = stats.gaussian_kde(values)
    Z = np.reshape(kernel(positions).T, X.shape)    
    ax.imshow(np.rot90(Z), cmap="gist_heat_r", extent= extent, aspect="auto")
    pers = []
    for per in np.array([32, 5, 0.3]):
        pers.append(stats.scoreatpercentile(kernel(kernel.resample(1000)), 
                                            per))
    plt.contour(Z.T, np.array(pers), colors="k", extent=extent)
    plt.axvline(dist1.MAPP, c="r", ls="--")
    plt.axhline(dist2.MAPP, c="r", ls="--")
    plt.minorticks_on()
    return

def load_results():
    """ Read results from the main table and return strings with values. """
    filename = os.path.join(working_dir, "results.tab")
    names = np.loadtxt(filename, usecols=(0,), dtype=str).tolist()
    data = np.loadtxt(filename, usecols=(69,72,75)).T
    errs1 = np.loadtxt(filename, usecols=(70,73,76)).T
    errs2 = np.loadtxt(filename, usecols=(71,74,77)).T
    for i in range(3):
        errs1[i] = data[i] - errs1[i]
        errs2[i] = errs2[i] - data[i]
    errs1[0] = errs1[0] / data[0] * np.log10(np.e)
    errs2[0] = errs2[0] / data[0] * np.log10(np.e)
    errs1 = errs1.T
    errs2 = errs2.T
    data[0] = np.log10(data[0])
    results = {}
    for i, (a,m,al) in enumerate(data.T):
        age = r"log Age (Gyr)= {0}$^{{+{1}}}_{{-{2}}}$ dex".format(round(a,2),
                                    round(errs2[i,0],2), round(errs1[i,0],2))
        metal = r"[Z/H]={0}$^{{+{1}}}_{{-{2}}}$ dex".format(round(m,2),
                                    round(errs2[i,1],2), round(errs1[i,1],2))
        alpha = r"[$\alpha$/Fe]={0}$^{{+{1}}}_{{-{2}}}$ dex".format(round(al,2),
                                    round(errs2[i,2],2), round(errs1[i,2],2))
        results[names[i]]= (age, metal, alpha)
    return results
              
if __name__ == "__main__":
    working_dir = os.path.join(home, "single2")
    os.chdir(working_dir)
    plt.ioff()
    specs = np.genfromtxt("results.tab", usecols=(0,), dtype=None).tolist()
    dirs = [x.replace(".fits", "_db") for x in specs]
    lims = [[np.log10(1.), np.log10(15.)], [-2.25, 0.67], [-0.3, 0.5]]
    fignums = [4, 7, 8]
    pairs = [[0,1], [0,2], [1,2]]
    plt.ioff()
    pp = PdfPages(os.path.join(working_dir, "mcmc_results.pdf"))
    plt.figure(1, figsize=(9,6.5))
    plt.minorticks_on()
    results = load_results()
    # dirs = ["s1_db"]
    for spec in specs:
        print spec
        folder = spec.replace(".fits", "_db")
        os.chdir(os.path.join(working_dir, folder))
        if working_dir == data_dir:
            name = spec.replace(".fits", '').replace("n3311", "").split("_")
            name = name[1] + name[2]
            name = r"{0}".format(name)
        else:
            name = spec.replace(".fits", "")
        ages_data = np.loadtxt("Chain_0/age_dist.txt")
        ages_data = np.log10(ages_data)
        ages = Dist(ages_data, [np.log10(1),np.log10(15)])
        metal_data = np.loadtxt("Chain_0/metal_dist.txt")
        metal = Dist(metal_data, [-2.25, 0.67])
        alpha_data = np.loadtxt("Chain_0/alpha_dist.txt")
        alpha = Dist(alpha_data, [-0.3, 0.5])
        weights = np.ones_like(ages.data)/len(ages.data)
        dists = [ages, metal, alpha]
        for i, d in enumerate(dists):
            ax = plt.subplot(3,3,(4*i)+1)
            N, bins, patches = plt.hist(d.data, color="w", weights=weights,
                                        ec="w", bins=50, range=tuple(lims[i]))
            fracs = N.astype(float)/N.max()
            norm = colors.normalize(-0.5 * fracs.max(), 1.2 * fracs.max())
            for thisfrac, thispatch in zip(fracs, patches):
                color = cm.gist_heat_r(norm(thisfrac))
                thispatch.set_facecolor(color)
            plt.axvline(d.MAPP, c="r", ls="--")
            plt.tick_params(labelright=True, labelleft=False)
            plt.xlim(d.lims)
            if i < 2:
                plt.setp(ax.get_xticklabels(), visible=False)
            else:
                plt.xlabel(r"[$\mathregular{\alpha}$ / Fe]")
            plt.minorticks_on()
        ax = plt.subplot(3,3,4)
        hist2D(ages, metal)
        plt.setp(ax.get_xticklabels(), visible=False)
        plt.ylabel("[Z/Fe]")
        
        ax = plt.subplot(3,3,7)
        hist2D(ages, alpha) 
        plt.ylabel(r"[$\mathregular{\alpha}$ / Fe]")
        plt.xlabel("log Age (Gyr)")
        ax = plt.subplot(3,3,8)
        plt.xlabel("[Z/Fe]")
        hist2D(metal, alpha)
        plt.annotate(r"Spectrum: {0}".format(name.upper()), xy=(.7,.91),
                     xycoords="figure fraction", ha="center", size=20)
        plt.annotate(r"{0}".format(results[spec][0]), xy=(.7,.84),
                     xycoords="figure fraction", ha="center", size=20)
        plt.annotate(r"{0}".format(results[spec][1]), xy=(.7,.77),
                     xycoords="figure fraction", ha="center", size=20)
        plt.annotate(r"{0}".format(results[spec][2]), xy=(.7,.70),
                     xycoords="figure fraction", ha="center", size=20)
        plt.tight_layout(pad=0.2)        
        pp.savefig()
        plt.savefig(os.path.join(working_dir, "logs/mcmc_{0}.png".format(name)\
                                 ), dpi=100)
        # plt.pause(0.001)
        # plt.show(block=True)
        # raw_input(505)
        plt.clf()
    pp.close()
        
        