#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on 04/03/15 14:18

@author: Carlos Eduardo Barbosa

Calculating the differences in the stellar populations for 1% errors in sky
subtraction
"""
import os

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import gridspec

from config import *

def window_rms(a, window_size):
  a2 = np.power(a,2)
  window = np.ones(window_size)/float(window_size)
  return np.sqrt(np.convolve(a2, window, 'same'))

def rolling_window(a, window):
    shape = a.shape[:-1] + (a.shape[-1] - window + 1, window)
    strides = a.strides + (a.strides[-1],)
    return np.lib.stride_tricks.as_strided(a, shape=shape, strides=strides)

def mad(a, axis=0):
   return 1.4826 * np.median(np.abs(a - np.median(a, axis=axis)), axis=axis)

def mask_slits(table, cols):
    data = np.loadtxt(table, dtype=str, usecols=cols).T
    mask = ["inn1_s22", "inn1_s25", "inn1_s27", "out1_s19", "out1_s20",
            "out1_s21", "out1_s22","out1_s23", "out1_s24", "out1_s25",
            "out1_s26", "inn2_s39", "cen1_s14", "cen2_s15"]
    mask = np.array(["fin1_n3311{0}.fits".format(x) for x in mask])
    data = data[~np.in1d(data[:,0], mask)]
    return data

def match_data(s1, s2, d1):
    idx = np.array([s1.index(x) for x in s2])
    return d1[idx]

if __name__ == "__main__":
    cols = (0, 3, 39, 41, 47, 49, 51, 53, 55)
    data = mask_slits(os.path.join(home, "single2", "results.tab"),
                      cols=cols)
    datap = mask_slits(os.path.join(home, "p5pc", "results.tab"),
                      cols=cols)
    datam = mask_slits(os.path.join(home, "m5pc", "results.tab"),
                      cols=cols)
    ##########################################################################
    # Get intersection of data
    sref = list(set(data[0]) & set(datap[0]) & set(datam[0]))
    sref.sort()
    ##########################################################################
    # Filter data
    data = match_data(data[0].tolist(), sref, data[1:].T.astype(float)).T
    datam = match_data(datam[0].tolist(), sref, datam[1:].T.astype(float)).T
    datap = match_data(datap[0].tolist(), sref, datap[1:].T.astype(float)).T
    ##########################################################################
    data[0] = np.log10(data[0]/re)
    fig = plt.figure(1, figsize=(5,10))
    gs = gridspec.GridSpec(7,1)
    gs.update(left=0.15, right=0.975, bottom = 0.05, top=0.985, hspace = 0.09,
               wspace=0.05)
    pars = [r"H$\beta$ (\AA)", r"Fe5015 (\AA)", r"Mg $b$ (\AA)",
            r"Fe5270 (\AA)", r"Fe5335 (\AA)", r"Fe5406 (\AA)", r"Fe5709 (\AA)"]
    rms_r, rms_sb = [], []
    for i,j in enumerate((1,2,3,4,5,6,7)):
        ########################################
        # Differences as function of the radius
        ########################################
        idx1 = np.argwhere(np.isfinite(datap[j])).T
        idx2 = np.argwhere(np.isfinite(datam[j])).T
        idx3 =  np.argwhere(np.isfinite(data[j])).T
        idx = np.intersect1d(idx1, np.intersect1d(idx2, idx3))
        diffp = datap[j][idx] - data[j][idx]
        diffm = datam[j][idx] - data[j][idx]
        diff = np.hstack((diffp, diffm))
        rdiff = np.hstack((data[0][idx], data[0][idx]))
        ind = rdiff.argsort()
        diff = diff[ind]
        rdiff = rdiff[ind]
        r = np.min(rolling_window(rdiff, 50), axis=1)
        diff_window = rolling_window(diff, 50)
        median = np.median(diff_window, axis=1)
        rms = np.zeros_like(median)
        for k in range(len(median)):
            rms[k] = 1.4826 * np.median(np.abs(diff_window[k] - np.median(diff_window[k])))
        r = np.hstack((r, rdiff[-1]))
        rms = np.hstack((rms, rms[-1]))
        if i==0:
            rms_r.append(rdiff)
        rms_r.append(rms)
        ax = plt.subplot(gs[i])
        ax.minorticks_on()
        ax.plot(data[0][idx], diffp, "ob", mec="none", alpha=1,
                label=r"+1\%")
        ax.plot(data[0][idx], diffm, "or", mec="none", alpha=1,
                label=r"-1\%")
        ax.axhline(y=0, ls="--", c="k")
        ax.fill_between(r, rms, -rms, edgecolor="none", color="y",
                        linewidth=0, alpha=0.5)
        if i != 6:
            ax.xaxis.set_ticklabels([])
        else:
            plt.xlabel(r"$\log R / R_e$")
        plt.ylabel(r"$\delta$ {0}".format(pars[i]), size=10)
        if i == 0:
            plt.legend(loc=0, ncol=2, prop={'size':10})
        ax.set_ylim(-2*rms.max(), 2 * rms.max())
        np.savetxt(os.path.join(tables_dir, "rms_1pc_lick_{0}.txt".format(i)),
                   np.column_stack((r, rms)))
    # plt.pause(0.001)
    plt.savefig(os.path.join(figures_dir, "sky_pm_1pc_lick.png"))
    plt.show(block=False)


