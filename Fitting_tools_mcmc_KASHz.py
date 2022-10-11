#!/usr/bin/env python2
# -*- coding: utf-8 -*-
"""
Created on Wed Aug 16 17:35:45 2017

@author: jscholtz
"""

#importing modules
import numpy as np
import matplotlib.pyplot as plt

from astropy.io import fits as pyfits
from astropy import wcs
from astropy.table import Table, join, vstack
from matplotlib.backends.backend_pdf import PdfPages
import pickle
from scipy.optimize import curve_fit

import emcee
import corner
from astropy.modeling.powerlaws import PowerLaw1D
nan= float('nan')

pi= np.pi
e= np.e

c= 3.*10**8
h= 6.62*10**-34
k= 1.38*10**-23

arrow = u'$\u2193$'

N = 10000
PATH_TO_FeII = '/Users/jansen/My Drive/Astro/General_data/FeII_templates/'


version='KASHz'

def gauss(x, k, mu,sig):

    expo= -((x-mu)**2)/(2*sig*sig)

    y= k* e**expo

    return y

# =============================================================================
#  Function for fitting Halpha with BLR
# =============================================================================
def Halpha_wBLR(x,z,cont, cont_grad, Hal_peak, BLR_peak, NII_peak, Nar_fwhm, BLR_fwhm, BLR_offset, SII_rpk, SII_bpk):
    Hal_wv = 6562.8*(1+z)/1e4
    NII_r = 6583.*(1+z)/1e4
    NII_b = 6548.*(1+z)/1e4

    SII_r = 6731.*(1+z)/1e4
    SII_b = 6716.*(1+z)/1e4

    Nar_sig= Nar_fwhm/3e5*Hal_wv/2.35482
    BLR_sig = BLR_fwhm/3e5*Hal_wv/2.35482

    BLR_wv = Hal_wv + BLR_offset/3e5*Hal_wv

    contm = PowerLaw1D.evaluate(x, cont,Hal_wv, alpha=cont_grad)
    Hal_nar = gauss(x, Hal_peak, Hal_wv, Nar_sig)
    Hal_blr = gauss(x, BLR_peak, BLR_wv, BLR_sig)

    NII_rg = gauss(x, NII_peak, NII_r, Nar_sig)
    NII_bg = gauss(x, NII_peak/3, NII_b, Nar_sig)

    SII_rg = gauss(x, SII_rpk, SII_r, Nar_sig)
    SII_bg = gauss(x, SII_bpk, SII_b, Nar_sig)

    return contm + Hal_nar + Hal_blr + NII_rg + NII_bg + SII_rg + SII_bg


def log_likelihood_Halpha_BLR(theta, x, y, yerr):

    model = Halpha_wBLR(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_Halpha_BLR(theta, priors):
    z, cont, cont_grad ,Hal_peak, BLR_peak, NII_peak, Nar_fwhm, BLR_fwhm, BLR_offset, SII_rpk, SII_bpk  = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['Hal_peak'][1] < np.log10(Hal_peak) < priors['Hal_peak'][2] and priors['Nar_fwhm'][1] < Nar_fwhm <priors['Nar_fwhm'][2] and priors['NII_peak'][1] < np.log10(NII_peak) < priors['NII_peak'][2]\
            and priors['BLR_peak'][1] < np.log10(BLR_peak) < priors['BLR_peak'][2] and priors['BLR_fwhm'][1] < BLR_fwhm <priors['BLR_fwhm'][2] and priors['BLR_offset'][1] < BLR_offset <priors['BLR_offset'][2]\
                and priors['SII_rpk'][1] < np.log10(SII_rpk) < priors['SII_rpk'][2] and priors['SII_bpk'][1] < np.log10(SII_bpk)<priors['SII_bpk'][2]:
                    return 0.0

    return -np.inf
'''
def log_prior_Halpha_BLR(theta, zguess):
    z, cont, cont_grad ,Hal_peak, BLR_peak, NII_peak, Nar_fwhm, BLR_fwhm, BLR_offset, SII_rpk, SII_bpk  = theta

    zcont=0.05
    priors = np.zeros_like(theta)

    priors[0] = uniform.logpdf(z,zguess-zcont,zguess+zcont)
    priors[1] = uniform.logpdf(np.log10(cont), -4,3)
    priors[2] = uniform.logpdf(np.log10(Hal_peak),  -4, 3 )
    priors[3] = uniform.logpdf(np.log10(NII_peak),  -4, 3 )
    priors[4] = uniform.logpdf(Nar_fwhm, 100,1000 )
    priors[5] = norm.logpdf(cont_grad, 0, 0.1)
    priors[6] = uniform.logpdf(np.log10(SII_bpk), -4, 3)
    priors[7] = uniform.logpdf(np.log10(SII_rpk), -4, 3)

    priors[8] = uniform.logpdf(np.log10(BLR_peak),  -4, 3 )
    priors[9] = uniform.logpdf(BLR_fwhm, 2000,9000 )
    priors[10] = norm.logpdf(BLR_offset, 0, 200)

    logprior = np.sum(priors)

    if logprior==np.nan:
        return -np.inf
    else:
        return logprior
'''
def log_probability_Halpha_BLR(theta, x, y, yerr, priors):
    lp = log_prior_Halpha_BLR(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_Halpha_BLR(theta, x, y, yerr)

from scipy.stats import norm, uniform

# =============================================================================
# Function to fit just narrow Halpha
# =============================================================================
def Halpha(x, z, cont,cont_grad,  Hal_peak, NII_peak, Nar_fwhm, SII_rpk, SII_bpk):
    Hal_wv = 6562.8*(1+z)/1e4
    NII_r = 6583.*(1+z)/1e4
    NII_b = 6548.*(1+z)/1e4

    Nar_vel_hal = Nar_fwhm/3e5*Hal_wv/2.35482
    Nar_vel_niir = Nar_fwhm/3e5*NII_r/2.35482
    Nar_vel_niib = Nar_fwhm/3e5*NII_b/2.35482

    SII_r = 6731.*(1+z)/1e4
    SII_b = 6716.*(1+z)/1e4

    Hal_nar = gauss(x, Hal_peak, Hal_wv, Nar_vel_hal)

    NII_nar_r = gauss(x, NII_peak, NII_r, Nar_vel_niir)
    NII_nar_b = gauss(x, NII_peak/3, NII_b, Nar_vel_niib)

    SII_rg = gauss(x, SII_rpk, SII_r, Nar_vel_hal)
    SII_bg = gauss(x, SII_bpk, SII_b, Nar_vel_hal)
    contm = PowerLaw1D.evaluate(x, cont,Hal_wv, alpha=cont_grad)

    return contm+Hal_nar+NII_nar_r+NII_nar_b + SII_rg + SII_bg

def log_likelihood_Halpha(theta, x, y, yerr):

    model = Halpha(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_Halpha(theta, priors):
    z, cont,cont_grad, Hal_peak, NII_peak, Nar_fwhm,  SII_rpk, SII_bpk = theta
    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['Hal_peak'][1] < np.log10(Hal_peak) < priors['Hal_peak'][2] and priors['Nar_fwhm'][1] < Nar_fwhm <priors['Nar_fwhm'][2] and priors['NII_peak'][1] < np.log10(NII_peak) < priors['NII_peak'][2]\
            and priors['SII_rpk'][1] < np.log10(SII_rpk) < priors['SII_rpk'][2] and priors['SII_bpk'][1] < np.log10(SII_bpk)<priors['SII_bpk'][2]:
                return 0.0

    return -np.inf

'''
def log_prior_Halpha(theta, zguess, zcont):
    z, cont,cont_grad, Hal_peak, NII_peak, Nar_fwhm,  SII_rpk, SII_bpk = theta


    priors = np.zeros_like(theta)

    priors[0] = uniform.logpdf(z,zguess-zcont,zguess+zcont)
    priors[1] = uniform.logpdf(np.log10(cont), -4,3)
    priors[2] = uniform.logpdf(np.log10(Hal_peak),  -4, 3 )
    priors[3] = uniform.logpdf(np.log10(NII_peak),  -4, 3 )
    priors[4] = uniform.logpdf(Nar_fwhm, 100,1000 )
    priors[5] = norm.logpdf(cont_grad, 0, 0.1)
    priors[6] = uniform.logpdf(np.log10(SII_bpk), -4, 3)
    priors[7] = uniform.logpdf(np.log10(SII_rpk), -4, 3)

    logprior = np.sum(priors)

    if logprior==np.nan:
        return -np.inf
    else:
        return logprior
'''
def log_probability_Halpha(theta, x, y, yerr, priors):
    lp = log_prior_Halpha(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_Halpha(theta, x, y, yerr)


# =============================================================================
# Function to fit  Halpha with outflow
# =============================================================================
def Halpha_outflow(x, z, cont,cont_grad,  Hal_peak, NII_peak, Nar_fwhm, SII_rpk, SII_bpk, Hal_out_peak, NII_out_peak, outflow_fwhm, outflow_vel):
    Hal_wv = 6562.8*(1+z)/1e4
    NII_r = 6583.*(1+z)/1e4
    NII_b = 6548.*(1+z)/1e4

    Hal_wv_vel = 6562.8*(1+z)/1e4 + outflow_vel/3e5*Hal_wv
    NII_r_vel = 6583.*(1+z)/1e4 + outflow_vel/3e5*Hal_wv
    NII_b_vel = 6548.*(1+z)/1e4 + outflow_vel/3e5*Hal_wv


    Nar_vel_hal = Nar_fwhm/3e5*Hal_wv/2.35482
    Nar_vel_niir = Nar_fwhm/3e5*NII_r/2.35482
    Nar_vel_niib = Nar_fwhm/3e5*NII_b/2.35482

    out_vel_hal = outflow_fwhm/3e5*Hal_wv/2.35482
    out_vel_niir = outflow_fwhm/3e5*NII_r/2.35482
    out_vel_niib = outflow_fwhm/3e5*NII_b/2.35482

    SII_r = 6731.*(1+z)/1e4
    SII_b = 6716.*(1+z)/1e4

    Hal_nar = gauss(x, Hal_peak, Hal_wv, Nar_vel_hal)
    NII_nar_r = gauss(x, NII_peak, NII_r, Nar_vel_niir)
    NII_nar_b = gauss(x, NII_peak/3, NII_b, Nar_vel_niib)

    Hal_out = gauss(x, Hal_out_peak, Hal_wv_vel, out_vel_hal)
    NII_out_r = gauss(x, NII_out_peak, NII_r_vel, out_vel_niir)
    NII_out_b = gauss(x, NII_out_peak/3, NII_b_vel, out_vel_niib)

    outflow = Hal_out+ NII_out_r + NII_out_b

    SII_rg = gauss(x, SII_rpk, SII_r, Nar_vel_hal)
    SII_bg = gauss(x, SII_bpk, SII_b, Nar_vel_hal)
    contm = PowerLaw1D.evaluate(x, cont,Hal_wv, alpha=cont_grad)
    return contm+Hal_nar+NII_nar_r+NII_nar_b + SII_rg + SII_bg + outflow

def log_likelihood_Halpha_outflow(theta, x, y, yerr):

    model = Halpha_outflow(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_Halpha_outflow(theta, priors):
    z, cont,cont_grad, Hal_peak, NII_peak, Nar_fwhm,  SII_rpk, SII_bpk, Hal_out_peak, NII_out_peak, outflow_fwhm, outflow_vel = theta
    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['Hal_peak'][1] < np.log10(Hal_peak) < priors['Hal_peak'][2] and priors['Nar_fwhm'][1] < Nar_fwhm <priors['Nar_fwhm'][2] and priors['NII_peak'][1] < np.log10(NII_peak) < priors['NII_peak'][2]\
            and priors['SII_rpk'][1] < np.log10(SII_rpk) < priors['SII_rpk'][2] and priors['SII_bpk'][1] < np.log10(SII_bpk) <priors['SII_bpk'][2]\
                and priors['Hal_out_peak'][1] < np.log10(Hal_out_peak) < priors['Hal_out_peak'][2] and priors['outflow_fwhm'][1] < outflow_fwhm <priors['outflow_fwhm'][2] \
                    and priors['NII_out_peak'][1] < np.log10(NII_out_peak) < priors['NII_out_peak'][2] and priors['outflow_vel'][1] < outflow_vel <priors['outflow_vel'][2]:
                        return 0.0

    return -np.inf

def log_probability_Halpha_outflow(theta, x, y, yerr, priors):
    lp = log_prior_Halpha_outflow(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_Halpha_outflow(theta, x, y, yerr)


# =============================================================================
#  Primary function to fit Halpha both with or without BLR - data prep and fit
# =============================================================================
def fitting_Halpha(wave, fluxs, error,z, BLR=1,zcont=0.05, progress=True ,priors= {'cont':[0,-3,1],\
                                                                                   'cont_grad':[0,-0.01,0.01], \
                                                                                   'Hal_peak':[0,-3,1],\
                                                                                   'BLR_peak':[0,-3,1],\
                                                                                   'NII_peak':[0,-3,1],\
                                                                                   'Nar_fwhm':[300,100,900],\
                                                                                   'BLR_fwhm':[4000,2000,9000],\
                                                                                   'BLR_offset':[-200,-900,600],\
                                                                                    'SII_rpk':[0,-3,1],\
                                                                                    'SII_bpk':[0,-3,1],\
                                                                                    'Hal_out_peak':[0,-3,1],\
                                                                                    'NII_out_peak':[0,-3,1],\
                                                                                    'outflow_fwhm':[600,300,1500],\
                                                                                    'outflow_vel':[-50, -300,300]}):

    priors['z'] = [z, z-zcont, z+zcont]
    fluxs[np.isnan(fluxs)] = 0
    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>(6562.8-170)*(1+z)/1e4)&(wave<(6562.8+170)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    znew = wave_zoom[peak_loc]/0.6562-1
    if abs(znew-z)<zcont:
        z= znew
    peak = np.ma.max(flux_zoom)

    if BLR==1:
        pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/4, peak/4, priors['Nar_fwhm'][0], priors['BLR_fwhm'][0],priors['BLR_offset'][0],peak/6, peak/6])+ 1e-2 * np.random.randn(32, 11)
        nwalkers, ndim = pos.shape

        sampler = emcee.EnsembleSampler(
            nwalkers, ndim, log_probability_Halpha_BLR, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

        sampler.run_mcmc(pos, N, progress=progress);


        flat_samples = sampler.get_chain(discard=int(0.25*N), thin=15, flat=True)

        labels=('z', 'cont','cont_grad', 'Hal_peak','BLR_peak', 'NII_peak', 'Nar_fwhm', 'BLR_fwhm', 'BLR_offset', 'SIIr_peak', 'SIIb_peak')




        fitted_model = Halpha_wBLR

        res = {'name': 'Halpha_wth_BLR'}
        for i in range(len(labels)):
            res[labels[i]] = flat_samples[:,i]

    if BLR==0:

        pos = np.array([z,np.median(flux[fit_loc]),0.01, peak/2, peak/4,priors['Nar_fwhm'][0],peak/6, peak/6 ])+ 1e-2 * np.random.randn(32, 8)
        nwalkers, ndim = pos.shape

        sampler = emcee.EnsembleSampler(
            nwalkers, ndim, log_probability_Halpha, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

        sampler.run_mcmc(pos, N, progress=progress);

        flat_samples = sampler.get_chain(discard=int(0.25*N), thin=15, flat=True)

        labels=('z', 'cont','cont_grad', 'Hal_peak', 'NII_peak', 'Nar_fwhm', 'SIIr_peak', 'SIIb_peak')

        fitted_model = Halpha

        res = {'name': 'Halpha_wth_BLR'}
        for i in range(len(labels)):
            res[labels[i]] = flat_samples[:,i]

    if BLR==-1:
        pos = np.array([z,np.median(flux[fit_loc]),0.01, peak/2, peak/4, priors['Nar_fwhm'][0],peak/6, peak/6,peak/8, peak/8, priors['outflow_fwhm'][0],priors['outflow_vel'][0] ])+ 1e-2 * np.random.randn(32, 12)
        nwalkers, ndim = pos.shape

        sampler = emcee.EnsembleSampler(
            nwalkers, ndim, log_probability_Halpha_outflow, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

        sampler.run_mcmc(pos, N, progress=progress);

        flat_samples = sampler.get_chain(discard=int(0.25*N), thin=15, flat=True)

        labels=('z', 'cont','cont_grad', 'Hal_peak', 'NII_peak', 'Nar_fwhm', 'SIIr_peak', 'SIIb_peak', 'Hal_out_peak', 'NII_out_peak', 'outflow_fwhm', 'outflow_vel')

        fitted_model = Halpha_outflow

        res = {'name': 'Halpha_wth_out'}
        for i in range(len(labels)):
            res[labels[i]] = flat_samples[:,i]



    return res, fitted_model



# =============================================================================
#    functions to fit [OIII] only with outflow
# =============================================================================
def OIII_outflow(x, z, cont,cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)
    Hbeta = 4861.*(1+z)/1e4


    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482
    Out_fwhm = OIII_out/3e5*OIIIr/2.35482

    out_vel_wv = out_vel/3e5*OIIIr

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)
    OIII_out = gauss(x, OIIIw_peak, OIIIr+out_vel_wv, Out_fwhm) + gauss(x, OIIIw_peak/3, OIIIb+out_vel_wv, Out_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482
    Hbeta_nar = gauss(x, Hbeta_peak, Hbeta, Hbeta_fwhm )
    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + OIII_out + Hbeta_nar



def log_likelihood_OIII_outflow(theta, x, y, yerr):

    model = OIII_outflow(x,*theta)
    sigma2 = yerr*yerr
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_outflow(theta,priors):

    z, cont, cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm, = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['OIIIw_peak'][1] < np.log10(OIIIw_peak) < priors['OIIIw_peak'][2] and priors['OIII_out'][1] < OIII_out <priors['OIII_out'][2]  and priors['out_vel'][1]<out_vel< priors['out_vel'][2] \
                and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]:
                    return 0.0

    return -np.inf

def log_probability_OIII_outflow(theta, x, y, yerr, priors):
    lp = log_prior_OIII_outflow(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_outflow(theta, x, y, yerr)



# =============================================================================
#    functions to fit [OIII] only with outflow with nar Hbeta
# =============================================================================
def OIII_outflow_narHb(x, z, cont,cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbetab_peak, Hbetab_fwhm, Hbetan_peak, Hbetan_fwhm):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)
    Hbeta = 4861.*(1+z)/1e4


    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482
    Out_fwhm = OIII_out/3e5*OIIIr/2.35482

    out_vel_wv = out_vel/3e5*OIIIr

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)
    OIII_out = gauss(x, OIIIw_peak, OIIIr+out_vel_wv, Out_fwhm) + gauss(x, OIIIw_peak/3, OIIIb+out_vel_wv, Out_fwhm)

    Hbetab_fwhm = Hbetab_fwhm/3e5*Hbeta/2.35482
    Hbetab_blr = gauss(x, Hbetab_peak, Hbeta, Hbetab_fwhm )

    Hbetan_fwhm = Hbetan_fwhm/3e5*Hbeta/2.35482
    Hbeta_nar = gauss(x, Hbetan_peak, Hbeta, Hbetan_fwhm )
    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + OIII_out + Hbetab_blr + Hbeta_nar



def log_likelihood_OIII_outflow_narHb(theta, x, y, yerr):

    model = OIII_outflow_narHb(x,*theta)
    sigma2 = yerr*yerr
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_outflow_narHb(theta,priors):
    #zguess = np.loadtxt('zguess.txt')

    z, cont, cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm, Hbetan_peak, Hbetan_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['OIIIw_peak'][1] < np.log10(OIIIw_peak) < priors['OIIIw_peak'][2] and priors['OIII_out'][1] < OIII_out <priors['OIII_out'][2]  and priors['out_vel'][1]<out_vel< priors['out_vel'][2] \
                and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                    and  priors['Hbetan_peak'][1] < np.log10(Hbetan_peak)<priors['Hbetan_peak'][2] and priors['Hbetan_fwhm'][1]<Hbetan_fwhm<priors['Hbetan_fwhm'][2]:
                        return 0.0

    return -np.inf

def log_probability_OIII_outflow_narHb(theta, x, y, yerr, priors):
    lp = log_prior_OIII_outflow_narHb(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_outflow_narHb(theta, x, y, yerr)



# =============================================================================
#  Function to fit [OIII] without outflow with hbeta
# =============================================================================
def OIII(x, z, cont, cont_grad, OIIIn_peak,  OIII_fwhm, Hbeta_peak, Hbeta_fwhm):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)

    Hbeta = 4861.*(1+z)/1e4

    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482

    Hbeta = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)
    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + Hbeta



def log_likelihood_OIII(theta, x, y, yerr):

    model = OIII(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII(theta,priors):

    z, cont, cont_grad, OIIIn_peak, OIII_fwhm, Hbeta_peak, Hbeta_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]:
                return 0.0

    return -np.inf

def log_probability_OIII(theta, x, y, yerr,priors):
    lp = log_prior_OIII(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII(theta, x, y, yerr)


# =============================================================================
#  Function to fit [OIII] without outflow with dual hbeta
# =============================================================================
def OIII_dual_hbeta(x, z, cont, cont_grad, OIIIn_peak,  OIII_fwhm, Hbeta_peak, Hbeta_fwhm, Hbetan_peak, Hbetan_fwhm):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)

    Hbeta = 4861.*(1+z)/1e4

    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482
    Hbetan_fwhm = Hbetan_fwhm/3e5*Hbeta/2.35482

    Hbeta = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)
    Hbeta_nar = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)

    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + Hbeta + Hbeta_nar



def log_likelihood_OIII_dual_hbeta(theta, x, y, yerr):

    model = OIII_dual_hbeta(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_dual_hbeta(theta,priors):

    z, cont, cont_grad, OIIIn_peak, OIII_fwhm, Hbeta_peak, Hbeta_fwhm, Hbetan_peak, Hbetan_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                and priors['Hbetan_peak'][1] < np.log10(Hbetan_peak)< priors['Hbetan_peak'][2] and  priors['Hbetan_fwhm'][1]<Hbetan_fwhm<priors['Hbetan_fwhm'][2]:
                    return 0.0

    return -np.inf

def log_probability_OIII_dual_hbeta(theta, x, y, yerr,priors):
    lp = log_prior_OIII_dual_hbeta(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_dual_hbeta(theta, x, y, yerr)

# =============================================================================
# FeII code
# =============================================================================
from astropy.convolution import Gaussian1DKernel
from astropy.convolution import convolve
from scipy.interpolate import interp1d
#Loading the template

Veron_d = pyfits.getdata(PATH_TO_FeII+ 'Veron-cetty_2004.fits')
Veron_hd = pyfits.getheader(PATH_TO_FeII+'Veron-cetty_2004.fits')
Veron_wv = np.arange(Veron_hd['CRVAL1'], Veron_hd['CRVAL1']+ Veron_hd['NAXIS1'])


Tsuzuki = np.loadtxt(PATH_TO_FeII+'FeII_Tsuzuki_opttemp.txt')
Tsuzuki_d = Tsuzuki[:,1]
Tsuzuki_wv = Tsuzuki[:,0]

BG92 = np.loadtxt(PATH_TO_FeII+'bg92.con')
BG92_d = BG92[:,1]
BG92_wv = BG92[:,0]

with open(PATH_TO_FeII+'Preconvolved_FeII.txt', "rb") as fp:
    Templates= pickle.load(fp)


def FeII_Veron(wave,z, FWHM_feii):

    index = find_nearest(Templates['FWHMs'],FWHM_feii)
    convolved = Templates['Veron_dat'][:,index]

    fce = interp1d(Veron_wv*(1+z)/1e4, convolved , kind='cubic')

    return fce(wave)

def FeII_Tsuzuki(wave,z, FWHM_feii):

    index = find_nearest(Templates['FWHMs'],FWHM_feii)
    convolved = Templates['Tsuzuki_dat'][:,index]

    fce = interp1d(Tsuzuki_wv*(1+z)/1e4, convolved , kind='cubic')

    return fce(wave)

def FeII_BG92(wave,z, FWHM_feii):

    index = find_nearest(Templates['FWHMs'],FWHM_feii)
    convolved = Templates['BG92_dat'][:,index]

    fce = interp1d(BG92_wv*(1+z)/1e4, convolved , kind='cubic')

    return fce(wave)

    '''
def FeII_Veron(wave,z, FWHM_feii):
    gk = Gaussian1DKernel(stddev=FWHM_feii/3e5*5008/2.35)

    convolved = convolve(Veron_d, gk)
    convolved = convolved/max(convolved[(Veron_wv<5400) &(Veron_wv>4900)])

    fce = interp1d(Veron_wv*(1+z)/1e4, convolved , kind='cubic')

    return fce(wave)

def FeII_Tsuzuki(wave,z, FWHM_feii):
    gk = Gaussian1DKernel(stddev=FWHM_feii/3e5*5008/2.35)

    convolved = convolve(Tsuzuki_d, gk)
    convolved = convolved/max(convolved[(Tsuzuki_wv<5400) &(Tsuzuki_wv>4900)])

    fce = interp1d(Tsuzuki_wv*(1+z)/1e4, convolved , kind='cubic')

    return fce(wave)

def FeII_BG92(wave,z, FWHM_feii):
    gk = Gaussian1DKernel(stddev=FWHM_feii/3e5*5008/2.35)

    convolved = convolve(BG92_d, gk)
    convolved = convolved/max(convolved[(BG92_wv<5400) &(BG92_wv>4900)])

    fce = interp1d(BG92_wv*(1+z)/1e4, convolved , kind='cubic')
    return fce(wave)

'''
# =============================================================================
#    functions to fit [OIII] only with outflow
# =============================================================================
def OIII_outflow_Fe(x, z, cont,cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm, FeII_peak, FeII_fwhm, template):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)
    Hbeta = 4861.*(1+z)/1e4


    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482
    Out_fwhm = OIII_out/3e5*OIIIr/2.35482

    out_vel_wv = out_vel/3e5*OIIIr

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)
    OIII_out = gauss(x, OIIIw_peak, OIIIr+out_vel_wv, Out_fwhm) + gauss(x, OIIIw_peak/3, OIIIb+out_vel_wv, Out_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482
    Hbeta_nar = gauss(x, Hbeta_peak, Hbeta, Hbeta_fwhm )

    if template=='BG92':
        FeII_fce = FeII_BG92
    if template=='Tsuzuki':
        FeII_fce = FeII_Tsuzuki
    if template=='Veron':
        FeII_fce = FeII_Veron

    FeII = FeII_peak*FeII_fce(x, z, FeII_fwhm)
    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + OIII_out + Hbeta_nar + FeII



def log_likelihood_OIII_outflow_Fe(theta, x, y, yerr, template):

    model = OIII_outflow_Fe(x,*theta, template)
    sigma2 = yerr*yerr
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_outflow_Fe(theta,priors):
    #zguess = np.loadtxt('zguess.txt')

    z, cont, cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm, FeII_peak, FeII_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['OIIIw_peak'][1] < np.log10(OIIIw_peak) < priors['OIIIw_peak'][2] and priors['OIII_out'][1] < OIII_out <priors['OIII_out'][2]  and priors['out_vel'][1]<out_vel< priors['out_vel'][2] \
                and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                    and priors['Fe_fwhm'][1]<FeII_fwhm<priors['Fe_fwhm'][2] and priors['Fe_peak'][1] < np.log10(FeII_peak)<priors['Fe_peak'][2]:
                        return 0.0

    return -np.inf

def log_probability_OIII_outflow_Fe(theta, x, y, yerr, priors,template):
    lp = log_prior_OIII_outflow_Fe(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_outflow_Fe(theta, x, y, yerr, template)

# =============================================================================
#    functions to fit [OIII] only with outflow with nar Hbeta with Fe
# =============================================================================
def OIII_outflow_Fe_narHb(x, z, cont,cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbetab_peak, Hbetab_fwhm, Hbetan_peak, Hbetan_fwhm, FeII_peak, FeII_fwhm, template):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)
    Hbeta = 4861.*(1+z)/1e4


    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482
    Out_fwhm = OIII_out/3e5*OIIIr/2.35482

    out_vel_wv = out_vel/3e5*OIIIr

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)
    OIII_out = gauss(x, OIIIw_peak, OIIIr+out_vel_wv, Out_fwhm) + gauss(x, OIIIw_peak/3, OIIIb+out_vel_wv, Out_fwhm)


    Hbetab_fwhm = Hbetab_fwhm/3e5*Hbeta/2.35482
    Hbeta_blr = gauss(x, Hbetab_peak, Hbeta, Hbetab_fwhm )

    Hbetan_fwhm = Hbetan_fwhm/3e5*Hbeta/2.35482
    Hbeta_nar = gauss(x, Hbetan_peak, Hbeta, Hbetan_fwhm )
    if template=='BG92':
        FeII_fce = FeII_BG92
    if template=='Tsuzuki':
        FeII_fce = FeII_Tsuzuki
    if template=='Veron':
        FeII_fce = FeII_Veron

    FeII = FeII_peak*FeII_fce(x, z, FeII_fwhm)
    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)

    return contm+ OIII_nar + OIII_out + Hbeta_blr + Hbeta_nar+ FeII



def log_likelihood_OIII_outflow_Fe_narHb(theta, x, y, yerr, template):

    model = OIII_outflow_Fe_narHb(x,*theta, template)
    sigma2 = yerr*yerr
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_outflow_Fe_narHb(theta,priors):
    #zguess = np.loadtxt('zguess.txt')

    z, cont, cont_grad, OIIIn_peak, OIIIw_peak, OIII_fwhm, OIII_out, out_vel, Hbeta_peak, Hbeta_fwhm,Hbetan_peak, Hbetan_fwhm, FeII_peak, FeII_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['OIIIw_peak'][1] < np.log10(OIIIw_peak) < priors['OIIIw_peak'][2] and priors['OIII_out'][1] < OIII_out <priors['OIII_out'][2]  and priors['out_vel'][1]<out_vel< priors['out_vel'][2] \
                and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                    and  priors['Hbetan_peak'][1] < np.log10(Hbetan_peak)<priors['Hbetan_peak'][2] and priors['Hbetan_fwhm'][1]<Hbetan_fwhm<priors['Hbetan_fwhm'][2] \
                        and priors['Fe_fwhm'][1]<FeII_fwhm<priors['Fe_fwhm'][2] and priors['Fe_peak'][1] < np.log10(FeII_peak)<priors['Fe_peak'][2]:
                          return 0.0


    return -np.inf

def log_probability_OIII_outflow_Fe_narHb(theta, x, y, yerr, priors,template):
    lp = log_prior_OIII_outflow_Fe_narHb(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_outflow_Fe_narHb(theta, x, y, yerr, template)


# =============================================================================
#  Function to fit [OIII] without outflow with Fe
# =============================================================================
def OIII_Fe(x, z, cont, cont_grad, OIIIn_peak,  OIII_fwhm, Hbeta_peak, Hbeta_fwhm, FeII_peak, FeII_fwhm, template):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)

    Hbeta = 4861.*(1+z)/1e4

    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482

    Hbeta_nar = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)

    if template=='BG92':
        FeII_fce = FeII_BG92
    if template=='Tsuzuki':
        FeII_fce = FeII_Tsuzuki
    if template=='Veron':
        FeII_fce = FeII_Veron

    FeII = FeII_peak*FeII_fce(x, z, FeII_fwhm)

    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)

    return contm+ OIII_nar + Hbeta_nar + FeII



def log_likelihood_OIII_Fe(theta, x, y, yerr, template):

    model = OIII_Fe(x,*theta, template)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_Fe(theta,priors):

    z, cont, cont_grad, OIIIn_peak, OIII_fwhm, Hbeta_peak, Hbeta_fwhm, FeII_peak, FeII_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] \
            and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2] \
                and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] \
                    and priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                        and priors['Fe_fwhm'][1]<FeII_fwhm<priors['Fe_fwhm'][2] and priors['Fe_peak'][1] < np.log10(FeII_peak)<priors['Fe_peak'][2]:
                          return 0.0

    return -np.inf

def log_probability_OIII_Fe(theta, x, y, yerr,priors, template):
    lp = log_prior_OIII_Fe(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_Fe(theta, x, y, yerr, template)



# =============================================================================
#  Function to fit [OIII] without outflow with dual hbeta and FeII
# =============================================================================
def OIII_dual_hbeta_Fe(x, z, cont, cont_grad, OIIIn_peak,  OIII_fwhm, Hbeta_peak, Hbeta_fwhm, Hbetan_peak, Hbetan_fwhm,FeII_peak, FeII_fwhm, template):
    OIIIr = 5008.*(1+z)/1e4
    OIIIb = OIIIr- (48.*(1+z)/1e4)

    Hbeta = 4861.*(1+z)/1e4

    Nar_fwhm = OIII_fwhm/3e5*OIIIr/2.35482

    OIII_nar = gauss(x, OIIIn_peak, OIIIr, Nar_fwhm) + gauss(x, OIIIn_peak/3, OIIIb, Nar_fwhm)

    Hbeta_fwhm = Hbeta_fwhm/3e5*Hbeta/2.35482
    Hbetan_fwhm = Hbetan_fwhm/3e5*Hbeta/2.35482

    Hbeta = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)
    Hbeta_nar = gauss(x,Hbeta_peak, Hbeta, Hbeta_fwhm)

    if template=='BG92':
        FeII_fce = FeII_BG92
    if template=='Tsuzuki':
        FeII_fce = FeII_Tsuzuki
    if template=='Veron':
        FeII_fce = FeII_Veron

    FeII = FeII_peak*FeII_fce(x, z, FeII_fwhm)

    contm = PowerLaw1D.evaluate(x, cont, OIIIr, alpha=cont_grad)
    return contm+ OIII_nar + Hbeta + Hbeta_nar+ FeII



def log_likelihood_OIII_dual_hbeta_Fe(theta, x, y, yerr, template):

    model = OIII_dual_hbeta_Fe(x,*theta, template)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_OIII_dual_hbeta_Fe(theta,priors):

    z, cont, cont_grad, OIIIn_peak, OIII_fwhm, Hbeta_peak, Hbeta_fwhm, Hbetan_peak, Hbetan_fwhm, FeII_peak, FeII_fwhm = theta

    if priors['z'][1] < z < priors['z'][2] and priors['cont'][1] < np.log10(cont)<priors['cont'][2]  and priors['cont_grad'][1]< cont_grad<priors['cont_grad'][2]  \
        and priors['OIIIn_peak'][1] < np.log10(OIIIn_peak) < priors['OIIIn_peak'][2] and priors['OIII_fwhm'][1] < OIII_fwhm <priors['OIII_fwhm'][2]\
            and priors['Hbeta_peak'][1] < np.log10(Hbeta_peak)< priors['Hbeta_peak'][2] and  priors['Hbeta_fwhm'][1]<Hbeta_fwhm<priors['Hbeta_fwhm'][2]\
                and priors['Hbetan_peak'][1] < np.log10(Hbetan_peak)< priors['Hbetan_peak'][2] and  priors['Hbetan_fwhm'][1]<Hbetan_fwhm<priors['Hbetan_fwhm'][2]\
                    and priors['Fe_fwhm'][1]<FeII_fwhm<priors['Fe_fwhm'][2] and priors['Fe_peak'][1] < np.log10(FeII_peak)<priors['Fe_peak'][2]:
                        return 0.0

    return -np.inf

def log_probability_OIII_dual_hbeta_Fe(theta, x, y, yerr,priors, template):
    lp = log_prior_OIII_dual_hbeta_Fe(theta,priors)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_OIII_dual_hbeta_Fe(theta, x, y, yerr, template)

# =============================================================================
# Primary function to fit [OIII] with and without outflows.
# =============================================================================

def fitting_OIII(wave, fluxs, error,z, outflow=0, template=0, Hbeta_dual=0, progress=True, \
                                                                 priors= {'cont':[0,-3,1],\
                                                                'cont_grad':[0,-0.01,0.01], \
                                                                'OIIIn_peak':[0,-3,1],\
                                                                'OIIIw_peak':[0,-3,1],\
                                                                'OIII_fwhm':[300,100,900],\
                                                                'OIII_out':[700,600,2500],\
                                                                'out_vel':[-200,-900,600],
                                                                'Hbeta_peak':[0,-3,1],\
                                                                'Hbeta_fwhm':[200,120,7000],\
                                                                'Hbetan_peak':[0,-3,1],\
                                                                'Hbetan_fwhm':[300,120,700],\
                                                                'Fe_peak':[0,-3,2],\
                                                                'Fe_fwhm':[3000,2000,6000]}):

    priors['z'] = [z, z-0.05, z+0.05]

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>4700*(1+z)/1e4)&(wave<5100*(1+z)/1e4))[0]

    sel=  np.where((wave<5025*(1+z)/1e4)& (wave>4980*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.argmax(flux_zoom)
    peak = (np.max(flux_zoom))

    selb =  np.where((wave<4880*(1+z)/1e4)& (wave>4820*(1+z)/1e4))[0]
    flux_zoomb = flux[selb]
    wave_zoomb = wave[selb]
    cont = np.median(flux[fit_loc])
    try:
        peak_loc_beta = np.argmax(flux_zoomb)
        peak_beta = (np.max(flux_zoomb))
    except:
        peak_beta = peak/3


    deltaz = 500/3e5*(1+z)
    nwalkers=32
    if outflow==1:
        if template==0:
            if Hbeta_dual == 0:
                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/4, priors[''], 600.,-200, peak_beta, 500])+ 1e-2* np.random.randn(nwalkers,10)
                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/6, 300., 700.,-200, peak_beta, 2000])+ 1e-2* np.random.randn(nwalkers,10)
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/6, priors['OIII_fwhm'][0], priors['OIII_out'][0],priors['out_vel'][0], peak_beta, priors['Hbeta_fwhm'][0]])+ 1e-2* np.random.randn(nwalkers,10)

                '''
                pos[:,0] = np.random.uniform(z-deltaz,z+deltaz,nwalkers)
                pos[:,1] = np.random.uniform(cont*0.8, cont*1.2,nwalkers)
                pos[:,3] = np.random.uniform(peak*0.8, peak*1.2,nwalkers)/2
                pos[:,4] = np.random.uniform(peak*0.8, peak*1.2,nwalkers)/4
                pos[:,5] = np.random.uniform(600,800,nwalkers)
                pos[:,6] = np.random.uniform(1200,1900,nwalkers)
                pos[:,7] = np.random.uniform(-600,-300,nwalkers)
                pos[:,8] = np.random.uniform(peak_beta*0.8, peak_beta*1.3,nwalkers)
                pos[:,9] = np.random.uniform(300,5000,nwalkers)
                '''
                nwalkers, ndim = pos.shape


                sampler = emcee.EnsembleSampler(
                        nwalkers, ndim, log_probability_OIII_outflow, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm')

                fitted_model = OIII_outflow

                res = {'name': 'OIII_outflow'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]
            else:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 300., 900.,-100, peak_beta/2, 4000,peak_beta/2, 600])+ 1e-2* np.random.randn(32,12)
                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4, peak/4, 300., 2000.,-100, peak_beta/2, 4000])+ 1e-2* np.random.randn(32,10)
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/6, priors['OIII_fwhm'][0], priors['OIII_out'][0],priors['out_vel'][0], peak_beta, priors['Hbeta_fwhm'][0],peak_beta, priors['Hbetan_fwhm'][0]])\
                    + 1e-2* np.random.randn(nwalkers,12)
                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_narHb, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels= ('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm')

                fitted_model = OIII_outflow_narHb

                res = {'name': 'OIII_outflow_HBn'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

        else:
            if Hbeta_dual == 0:
                #pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 400., 700.,-300, peak_beta, 600,np.median(flux[fit_loc]), 2000])+ 1e-2* np.random.randn(32,12)
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2, peak/6, priors['OIII_fwhm'][0], priors['OIII_out'][0],priors['out_vel'][0], peak_beta, priors['Hbetan_fwhm'][0],np.median(flux[fit_loc]), priors['Fe_fwhm'][0]])\
                    + 1e-2* np.random.randn(nwalkers,12)

                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_Fe, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm', 'Fe_peak', 'Fe_fwhm')

                fitted_model = OIII_outflow_Fe

                res = {'name': 'OIII_outflow_Fe'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

            else:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 300., 600.,-100, peak_beta/2, 4000,peak_beta/2, 600, np.median(flux[fit_loc]), 2000])+ 1e-2* np.random.randn(32,14)

                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_Fe_narHb, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels= ('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm', 'Fe_peak', 'Fe_fwhm')

                fitted_model = OIII_outflow_Fe_narHb

                res = {'name': 'OIII_outflow_Fe_narHb'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

    if outflow==0:
        if template==0:
            if Hbeta_dual == 0:

                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  120., peak_beta,200])+ 1e-2 * np.random.randn(32, 7)
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  priors['OIII_fwhm'][0], peak_beta, priors['Hbeta_fwhm'][0]]) + 1e-2 * np.random.randn(32, 7)
                #pos[:,6] = np.random.uniform(300,5000,32)

                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4,  2300., peak_beta/2,3700])+ 1e-4 * np.random.randn(32, 7)
                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm')


                fitted_model = OIII

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]


            else:

                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  priors['OIII_fwhm'][0], peak_beta/4, priors['Hbeta_fwhm'][0],peak_beta/4, priors['Hbetan_fwhm'][0]]) \
                    + 1e-2 * np.random.randn(32, 9)

                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_dual_hbeta, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm')


                fitted_model = OIII_dual_hbeta

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

        else:
            if Hbeta_dual == 0:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2,  500., peak_beta,4000, np.median(flux[fit_loc]), 2000])+ 1e-2 * np.random.randn(32, 9)
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  priors['OIII_fwhm'][0], peak_beta, priors['Hbeta_fwhm'][0],np.median(flux[fit_loc]), priors['Fe_fwhm'][0]]) + 1e-2 * np.random.randn(32, 9)

                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_Fe, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm', 'Fe_peak', 'Fe_fwhm')


                fitted_model = OIII_Fe

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]


            else:
                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  priors['OIII_fwhm'][0], peak_beta/2, priors['Hbeta_fwhm'][0],peak_beta/2, priors['Hbetan_fwhm'][0],\
                                np.median(flux[fit_loc]), priors['Fe_fwhm'][0]]) + 1e-2 * np.random.randn(32, 11)

                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_dual_hbeta_Fe, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],priors, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm','Fe_peak', 'Fe_fwhm')


                fitted_model = OIII_dual_hbeta_Fe

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

    return res, fitted_model

from scipy.optimize import curve_fit
def fitting_OIII_curvefit(wave, fluxs, error,z, outflow=0, template=0, Hbeta_dual=0, progress=True):
    import os

    #os.environ["OMP_NUM_THREADS"] = "1"

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>4700*(1+z)/1e4)&(wave<5100*(1+z)/1e4))[0]

    sel=  np.where((wave<5025*(1+z)/1e4)& (wave>4980*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.argmax(flux_zoom)
    peak = (np.max(flux_zoom))
    z = (wave_zoom[peak_loc]/0.5008)-1

    selb =  np.where((wave<4880*(1+z)/1e4)& (wave>4820*(1+z)/1e4))[0]
    flux_zoomb = flux[selb]
    wave_zoomb = wave[selb]
    cont = np.median(flux[fit_loc])
    try:
        peak_loc_beta = np.argmax(flux_zoomb)
        peak_beta = (np.max(flux_zoomb))
    except:
        peak_beta = peak/3
    import multiprocess as mp

    deltaz = 500/3e5*(1+z)
    nwalkers=32
    if outflow==1:
        if template==0:
            if Hbeta_dual == 0:

                pos = np.array([z,cont,0.001, peak/2, peak/4, 500., 1100.,-200, peak_beta, 2000])+ 1e-2* np.random.randn(nwalkers,10)

                pos[:,0] = np.random.uniform(z-deltaz,z+deltaz,nwalkers)
                pos[:,1] = np.random.uniform(cont*0.8, cont*1.2,nwalkers)
                pos[:,3] = np.random.uniform(peak*0.8, peak*1.2,nwalkers)/2
                pos[:,4] = np.random.uniform(peak*0.8, peak*1.2,nwalkers)/4
                pos[:,5] = np.random.uniform(600,800,nwalkers)
                pos[:,6] = np.random.uniform(1200,1900,nwalkers)
                pos[:,7] = np.random.uniform(-600,-300,nwalkers)
                pos[:,8] = np.random.uniform(peak_beta*0.8, peak_beta*1.3,nwalkers)
                pos[:,9] = np.random.uniform(300,5000,nwalkers)

                p = np.array([z,cont,0.001, peak/2, peak/4, 500., 1100.,-200, peak_beta, 2000])

                popt, pcov = curve_fit(OIII_outflow, wave[fit_loc], flux[fit_loc], sigma=error[fit_loc], p0=p, bounds=([z-deltaz,0,-0.1,0, 0 , 200, 800, -900, 0, 200 ] \
                                                                                                                 ,[z+deltaz,1, 0.1,30,30, 800, 2500, 400,30, 7000]))
                print(popt)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm')

                fitted_model = OIII_outflow

                res = {'name': 'OIII_outflow'}
                for i in range(len(labels)):
                    res[labels[i]] = np.random.normal(popt[i], abs(popt[i]*0.2), 5000)
            else:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 300., 900.,-100, peak_beta/2, 4000,peak_beta/2, 600])+ 1e-2* np.random.randn(32,12)
                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4, peak/4, 300., 2000.,-100, peak_beta/2, 4000])+ 1e-2* np.random.randn(32,10)
                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_narHb, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],z, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels= ('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm')

                fitted_model = OIII_outflow_narHb

                res = {'name': 'OIII_outflow_HBn'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

        else:
            if Hbeta_dual == 0:

                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 300., 600.,-100, peak_beta, 600,np.median(flux[fit_loc]), 2000])+ 1e-2* np.random.randn(32,12)

                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4, peak/4, 300., 2000.,-100, peak_beta/2, 4000])+ 1e-2* np.random.randn(32,10)
                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_Fe, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],z, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm', 'Fe_peak', 'Fe_fwhm')

                fitted_model = OIII_outflow_Fe

                res = {'name': 'OIII_outflow_Fe'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

            else:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2, peak/4, 300., 600.,-100, peak_beta/2, 4000,peak_beta/2, 600, np.median(flux[fit_loc]), 2000])+ 1e-2* np.random.randn(32,14)
                nwalkers, ndim = pos.shape
                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_outflow_Fe_narHb, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],z, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)


                labels= ('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIw_peak', 'OIIIn_fwhm', 'OIIIw_fwhm', 'out_vel', 'Hbeta_peak', 'Hbeta_fwhm','Hbetan_peak', 'Hbetan_fwhm', 'Fe_peak', 'Fe_fwhm')

                fitted_model = OIII_outflow_narHb

                res = {'name': 'OIII_outflow_Fe_narHb'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]

    if outflow==0:
        if template==0:
            if Hbeta_dual == 0:

                pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/2,  500., peak_beta,100])+ 1e-4 * np.random.randn(32, 7)
                pos[:,6] = np.random.uniform(300,5000,32)

                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4,  2300., peak_beta/2,3700])+ 1e-4 * np.random.randn(32, 7)
                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],z))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm')


                fitted_model = OIII

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]


            else:
                raise Exception('Sorry dual Hbeta not implemented with no outflow at the moment')

        else:
            if Hbeta_dual == 0:
                pos = np.array([z,np.median(flux[fit_loc])/2,0.001, peak/2,  500., peak_beta,4000, np.median(flux[fit_loc]), 2000])+ 1e-2 * np.random.randn(32, 9)
                #pos = np.array([z,np.median(flux[fit_loc]),0.001, peak/4,  2300., peak_beta/2,3700])+ 1e-4 * np.random.randn(32, 7)
                nwalkers, ndim = pos.shape

                sampler = emcee.EnsembleSampler(
                    nwalkers, ndim, log_probability_OIII_Fe, args=(wave[fit_loc], flux[fit_loc], error[fit_loc],z, template))

                sampler.run_mcmc(pos, N, progress=progress);

                flat_samples = sampler.get_chain(discard=int(0.5*N), thin=15, flat=True)

                labels=('z', 'cont','cont_grad', 'OIIIn_peak', 'OIIIn_fwhm', 'Hbeta_peak', 'Hbeta_fwhm', 'Fe_peak', 'Fe_fwhm')


                fitted_model = OIII_Fe

                res = {'name': 'OIII'}
                for i in range(len(labels)):
                    res[labels[i]] = flat_samples[:,i]


            else:
                raise Exception('Sorry dual Hbeta not implemented with no outflow at the moment')

    return res, fitted_model

def Fitting_OIII_unwrap(lst):

    i,j,flx_spax_m, error, wave, z = lst

    flat_samples_sig, fitted_model_sig = fitting_OIII(wave,flx_spax_m,error,z, outflow=0, progress=False)
    cube_res  = [i,j,prop_calc(flat_samples_sig)]
    return cube_res

def Fitting_OIII_2G_unwrap(lst):

    i,j,flx_spax_m, error, wave, z = lst

    flat_samples_sig, fitted_model_sig = fitting_OIII(wave,flx_spax_m,error,z, outflow=1, progress=False)
    cube_res  = [i,j,prop_calc(flat_samples_sig)]

    return cube_res

import time

def Fitting_Halpha_unwrap(lst):
    i,j,flx_spax_m, error, wave, z = lst
    deltav = 1000
    deltaz = deltav/3e5*(1+z)
    flat_samples_sig, fitted_model_sig = fitting_Halpha(wave,flx_spax_m,error,z, zcont=deltaz, BLR=0, progress=False)
    cube_res  = [i,j,prop_calc(flat_samples_sig)]

    return cube_res


def prop_calc(results):
    labels = list(results.keys())[1:]
    res_plt = []
    res_dict = {'name': results['name']}
    for lbl in labels:

        array = results[lbl]

        p50,p16,p84 = np.percentile(array, (50,16,84))
        p16 = p50-p16
        p84 = p84-p50

        res_plt.append(p50)
        res_dict[lbl] = np.array([p50,p16,p84])

    res_dict['popt'] = res_plt
    return res_dict


# =============================================================================
# Fit single Gaussian
# =============================================================================
def Single_gauss(x, z, cont,cont_grad,  Hal_peak, NII_peak, Nar_fwhm, SII_rpk, SII_bpk):
    Hal_wv = 6562.8*(1+z)/1e4
    NII_r = 6583.*(1+z)/1e4
    NII_b = 6548.*(1+z)/1e4

    Nar_vel_hal = Nar_fwhm/3e5*Hal_wv/2.35482
    Nar_vel_niir = Nar_fwhm/3e5*NII_r/2.35482
    Nar_vel_niib = Nar_fwhm/3e5*NII_b/2.35482

    SII_r = 6731.*(1+z)/1e4
    SII_b = 6716.*(1+z)/1e4

    Hal_nar = gauss(x, Hal_peak, Hal_wv, Nar_vel_hal)

    NII_nar_r = gauss(x, NII_peak, NII_r, Nar_vel_niir)
    NII_nar_b = gauss(x, NII_peak/3, NII_b, Nar_vel_niib)

    SII_rg = gauss(x, SII_rpk, SII_r, Nar_vel_hal)
    SII_bg = gauss(x, SII_bpk, SII_b, Nar_vel_hal)

    return cont+x*cont_grad+Hal_nar+NII_nar_r+NII_nar_b + SII_rg + SII_bg

def log_likelihood_single(theta, x, y, yerr):

    model = Halpha(x,*theta)
    sigma2 = yerr*yerr#yerr ** 2 + model ** 2 #* np.exp(2 * log_f)
    return -0.5 * np.sum((y - model) ** 2 / sigma2) #+ np.log(2*np.pi*sigma2))


def log_prior_single(theta, zguess, zcont):
    z, cont,cont_grad, Hal_peak, NII_peak, Nar_fwhm,  SII_rpk, SII_bpk = theta
    if (zguess-zcont) < z < (zguess+zcont) and -3 < np.log10(cont)<1 and -3<np.log10(Hal_peak)<1 and -3<np.log10(NII_peak)<1 \
        and 150 < Nar_fwhm<900 and -0.01<cont_grad<0.01 and 0<SII_bpk<0.5 and 0<SII_rpk<0.5:
            return 0.0

    return -np.inf

def log_probability_single(theta, x, y, yerr, zguess, zcont=0.05):
    lp = log_prior_Halpha(theta,zguess,zcont)
    if not np.isfinite(lp):
        return -np.inf
    return lp + log_likelihood_Halpha(theta, x, y, yerr)


'''



def fitting_OIII_Hbeta_mul(wave, fluxs, error,z, chir=0, Hbeta=1):#, outflow_lim=150.):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>4800*(1+z)/1e4)&(wave<5100*(1+z)/1e4))[0]

    flux = flux[fit_loc]
    wave = wave[fit_loc]
    error = error[fit_loc]



    sel=  np.where((wave<5050*(1+z)/1e4)& (wave>4980*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    wv = wave[np.where(wave==wave_peak)[0]]

    #plt.plot(wave, flux, drawstyle='steps-mid')



    model = LinearModel() + GaussianModel(prefix='o3rw_')+ GaussianModel(prefix='o3bw_') + GaussianModel(prefix='o3rn_')+ GaussianModel(prefix='o3bn_') + GaussianModel(prefix='Hb_')
    # Starting parameters for the fits
    wv = 5008.*(1+z)/1e4
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
         #a = 0.0, \
		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
		o3rw_amplitude = peak/4,  \
		o3bw_amplitude =  peak/12,   \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		o3rw_center = wv-5.*(1+z)/1e4 ,         \
		o3bw_center = wv - (48.-5)*(1+z)/1e4,   \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		o3rw_sigma = (500.0/2.36/2.9979e5)*5006.84*(1+z)/1e4, \
		o3bw_sigma = (500.0/2.36/2.9979e5)*4958.92*(1+z)/1e4, \
         # pso
         o3rn_amplitude = peak*(3./4),  \
		o3bn_amplitude =  peak*(3./12),   \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		o3rn_center = wv,         \
		o3bn_center = wv - 48.*(1+z)/1e4,   \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		o3rn_sigma = (300.0/2.36/2.9979e5)*5006.84*(1+z)/1e4, \
		o3bn_sigma = (300.0/2.36/2.9979e5)*4958.92*(1+z)/1e4, \
        Hb_amplitude = peak/10,  \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		Hb_center =  4861.2*(1+z)/1e4  ,         \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		Hb_sigma = (300.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,

	)

    # Parameters constraints Narrow line flux > 0.0
    parameters['o3rw_amplitude'].set(min=0.0)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bw_amplitude'].set(expr='o3rw_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rw_sigma'].set(min=(150./2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(up_limit_OIII/2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rw_center'].set(min=5008.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-800.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(800.0/2.9979e5))
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bw_sigma'].set(expr='o3rw_sigma*(4958.92/5006.84)')

    # Parameters constraints Narrow line flux > 0.0
    parameters['o3rn_amplitude'].set(min=0.0)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bn_amplitude'].set(expr='o3rn_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rn_sigma'].set(min=(150.0/2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(up_limit_OIII/2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rn_center'].set(min=5006.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-800.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(800.0/2.9979e5))
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bn_sigma'].set(expr='o3rn_sigma*(4958.92/5006.84)')
    off = 48.*(1+z)/1e4
    parameters['o3bn_center'].set(expr='o3rn_center - '+str(off))
    parameters['o3bw_center'].set(expr='o3rw_center - '+str(off))

    # Parameters constraints Narrow line flux > 0.0
    parameters['Hb_amplitude'].set(min=0.0)

    if Hbeta==0:
        parameters['Hb_amplitude'].set(max= 0.00001)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Hb_sigma'].set(min=(150.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,max=(700.0/2.36/2.9979e5)*4861.2*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Hb_center'].set(min=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4*(-700.0/2.9979e5),max=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4 *(700.0/2.9979e5))


    out = model.fit(flux,params=parameters, errors=error,x=(wave ))
    try:
        chi2 = sum(((out.eval(x=wave)- flux)**2)/(error.data**2))

        BIC = chi2+6*np.log(len(flux))
    except:
        BIC = len(flux)+6*np.log(len(flux))

    if chir==0:
        return out

    else:
        return out,chi2


def fit_continuum(wave, fluxs):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    model = LinearModel()

    # Starting parameters for the fits

    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
        )

    flux[np.isnan(flux)] = 0
    out = model.fit(flux ,params=parameters, x=wave)



    return out


def sub_QSO(wave, fluxs, error,z, fst_out):
    from lmfit.models import LinearModel, GaussianModel, LorentzianModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    sel=  np.where(((wave<(6562.8+60)*(1+z)/1e4))& (wave>(6562.8-60)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]

    peak = np.ma.max(flux_zoom)

    wv = fst_out.params['Haw_center'].value

    model = LinearModel() + GaussianModel(prefix='Ha_')

    # Starting parameters for the fits
    parameters = model.make_params( \
         c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
         #a = 0.0, \
		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
		Ha_amplitude = peak,  \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		Ha_center = wv  ,         \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		Ha_sigma = fst_out.params['Haw_sigma'].value)

    # Parameters constraints Narrow line flux > 0.0
    parameters['Ha_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Ha_sigma'].set(min=fst_out.params['Haw_sigma'].value*0.999999,max=fst_out.params['Haw_sigma'].value*1.000001)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Ha_center'].set(min=wv*0.9999999,max=wv*1.000000000001)

    out = model.fit(flux,params=parameters, errors=error, x=(wave))


    return out



def sub_QSO_Lorentzian(wave, fluxs, error,z, fst_out):
    from lmfit.models import LinearModel, GaussianModel, LorentzianModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    sel=  np.where(((wave<(6562.8+60)*(1+z)/1e4))& (wave>(6562.8-60)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]

    peak = np.ma.max(flux_zoom)

    wv = fst_out.params['Haw_center'].value

    model = LinearModel() + LorentzianModel(prefix='Ha_')

    # Starting parameters for the fits
    parameters = model.make_params( \
         c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
         #a = 0.0, \
		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
		Ha_amplitude = peak,  \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		Ha_center = wv  ,         \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		Ha_sigma = fst_out.params['Haw_sigma'].value)

    # Parameters constraints Narrow line flux > 0.0
    parameters['Ha_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Ha_sigma'].set(min=fst_out.params['Haw_sigma'].value*0.999999,max=fst_out.params['Haw_sigma'].value*1.000001)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Ha_center'].set(min=wv*0.9999999,max=wv*1.000000000001)

    out = model.fit(flux,params=parameters, errors=error, x=(wave))


    return out




def fitting_Halpha_mul_outflow(wave, fluxs, error,z):
    from lmfit.models import GaussianModel, LinearModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]



    fit_loc = np.where((wave>(6562.8-200)*(1+z)/1e4)&(wave<(6562.8+200)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    wv = wave[np.where(wave==wave_peak)[0]]

    z = float(z)
    Hal_cm = 6562.8*(1+z)/1e4


    model = LinearModel()+ GaussianModel(prefix='Haw_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_') + GaussianModel(prefix='Nrw_') + GaussianModel(prefix='Nbw_')


    Hal_cm = 6562.8*(1+z)/1e4
    Nr_cm = 6583.*(1+z)/1e4
    Nb_cm = 6548.*(1+z)/1e4

    sigma_s = 900.
    init_sig = 400.
    wvnet= wv
    # Starting parameters for the fits
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
		Haw_amplitude = peak/3,  \
		#
		Haw_center = wv  ,         \
		#
		Haw_sigma = (sigma_s/2.36/2.9979e5)*Hal_cm, \
         # pso
         Han_amplitude = peak,  \
		#
		Han_center = wv,         \
		#
		Han_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nr_amplitude = peak*(1./6), \
         #
         Nr_center = Nr_cm, \
         #
         Nr_sigma = (init_sig/2.36/2.9979e5)*Nr_cm, \
         #
         Nb_amplitude = peak/18, \
         #
         Nb_center = Nb_cm, \
         #
         Nb_sigma = (init_sig/2.36/2.9979e5)*Nb_cm, \
         #
         Nrw_amplitude = peak*(1./6), \
         #
         Nrw_center = Nr_cm, \
         #
         Nrw_sigma = (init_sig/2.36/2.9979e5)*Nr_cm, \
         #
         Nbw_amplitude = peak/18, \
         #
         Nbw_center = Nb_cm, \
         #
         Nbw_sigma = (init_sig/2.36/2.9979e5)*Nb_cm, \
	)

    # Parameters constraints Broad line flux > 0.0
    parameters['Haw_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 2500 km/s
    #parameters['Haw_sigma'].set(min=(500.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(4000.0/2.36/2.9979e5)*Hal_cm)

    parameters['Haw_sigma'].set(min=(600.0/2.36/2.9979e5)*Hal_cm,max=(1200.0/2.36/2.9979e5)*Hal_cm)
    #parameters['Haw_center'].set(expr='Han_center- (600./3e5*2.114534083642)')

    parameters['Haw_center'].set(min=Hal_cm+ Hal_cm*(-1000.0/2.9979e5),max=Hal_cm+ Hal_cm*(1000.0/2.9979e5))


    # Parameters constraints Narrow line flux > 0.0
    parameters['Han_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 300 km/s
    parameters['Han_sigma'].set(min=((1./3000.0)/2.36)*Hal_cm,max=(1200.0/2.36/2.9979e5)*Hal_cm)
    #
    parameters['Han_center'].set(min=wvnet+ Hal_cm*(-1000.0/2.9979e5),max=wvnet+ Hal_cm*(1000.0/2.9979e5))

    #
    parameters['Nr_amplitude'].set(min=0.0)

    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nb_amplitude'].set(expr='Nr_amplitude/3')
    #
    parameters['Nr_sigma'].set(expr='Han_sigma*(6583/6562)')
    #
    parameters['Nb_sigma'].set(expr='Han_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nr_center'].set(expr='Han_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nb_center'].set(expr='Han_center - '+str(offset_b))
    #parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(2500.0/2.36/2.9979e5)*Hal_cm)

    ####################
    # Broad NII
    parameters['Nrw_amplitude'].set(min=0.0)
    parameters['Nrw_amplitude'].set(max=1.0e-4)
    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nbw_amplitude'].set(expr='Nrw_amplitude/3')
    #
    parameters['Nrw_sigma'].set(expr='Haw_sigma*(6583/6562)')
    #
    parameters['Nbw_sigma'].set(expr='Haw_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nrw_center'].set(expr='Haw_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nbw_center'].set(expr='Haw_center - '+str(offset_b))


    out = model.fit(flux[fit_loc],params=parameters, errors=error[fit_loc], x=(wave[fit_loc]))
    try:
        chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error.data[fit_loc]**2))
    except:
        chi2=1

    print ('Outflow mode: chi2 ', chi2, ' N ', len(flux[fit_loc]))
    print ('OUtflow BIC ', chi2+8*np.log(len(flux[fit_loc]))  )

    return out ,chi2




import math



def Gaussian_BK(x, amplitude, center,sigma,a1,a2):
    from astropy.modeling.powerlaws import BrokenPowerLaw1D

    BK = BrokenPowerLaw1D.evaluate(x,1 ,center,a2,a1)

    GS = gaussian(x, 1, center,sigma)

    fcs = BK*GS
    fcs = fcs/max(fcs)
    y = amplitude*fcs
    return y

def Gaussian_BKc(x, amplitude, center,sigma,a1,a2):
    from astropy.modeling.powerlaws import BrokenPowerLaw1D

    BK = BrokenPowerLaw1D.evaluate(x,1 ,center,a2,a1)

    GS = gaussian(x, 1, center,sigma)

    fcs = np.convolve(BK, GS, 'same')
    fcs = fcs/max(fcs)
    y = amplitude*fcs
    return y

def BKP(x, amplitude, center, a1,a2):
    from astropy.modeling.powerlaws import BrokenPowerLaw1D

    BK = BrokenPowerLaw1D.evaluate(x,1 ,center,a2,a1)


    fcs = BK
    fcs = fcs/max(fcs)
    y = amplitude*fcs
    return y


import lmfit
BkpGModel = lmfit.Model( Gaussian_BK)


def fitting_Halpha_mul_bkp(wave, fluxs, error,z, wvnet=1., decompose=1, offset=0,init_sig=300., broad=1, cont=1, Hal_up=1000.):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel


    #print ('Fitting Broken Power law Gaussian')
    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]



    fit_loc = np.where((wave>(6562.8-600)*(1+z)/1e4)&(wave<(6562.8+600)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    if wvnet ==1.:
        wv = wave[np.where(wave==wave_peak)[0]]

    else:
        wv = wvnet

    Hal_cm = 6562.8*(1+z)/1e4


    model = LinearModel()+ lmfit.Model(Gaussian_BK, prefix='Haw_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_') #+ GaussianModel(prefix='X_')


    # Starting parameters for the fits
    #print wv
    if decompose==1:
        sigma_s = 4000
        c_broad = wv

    else:
        outo = decompose
        sigma_s = outo.params['Haw_sigma'].value/outo.params['Haw_center'].value*3e5
        c_broad = outo.params['Haw_center'].value

    Hal_cm = 6562.8*(1+z)/1e4

    # Starting parameters for the fits
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
		Haw_amplitude = peak/3,  \
		#
		Haw_center = wv  ,         \
		#
		Haw_sigma = (sigma_s/2.9979e5)*Hal_cm, \
         # pso
        Han_amplitude = peak*(2./2),  \
		#
		Han_center = wv,         \
		#
		Han_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nr_amplitude = peak*(1./6), \
         #
         Nr_center = 6583.*(1+z)/1e4, \
         #
         Nr_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nb_amplitude = peak/18, \
         #
         Nb_center = 6548.*(1+z)/1e4, \
         #
         Nb_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         Haw_a1 = + 3, \
         Haw_a2 = - 3, \
	)
    if cont==0:
        parameters['intercept'].set(min=-0.0000000000001)
        parameters['intercept'].set(max= 0.0000000000001)
        parameters['slope'].set(min=-0.0000000000001)
        parameters['slope'].set(max= 0.0000000000001)
        print ('No continuum')
    # Parameters constraints Broad line flux > 0.0
    parameters['Haw_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 2500 km/s


    if decompose == 1:
        parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*Hal_cm)
        parameters['Haw_center'].set(min=Hal_cm+ Hal_cm*(-400.0/2.9979e5),max=Hal_cm+ Hal_cm*(400.0/2.9979e5))

        #parameters['Haw_center'].set(expr='Han_center')

        # Parameters constraints Narrow line flux > 0.0
        parameters['Han_amplitude'].set(min=0.0)

        slp_edge = 200.
        parameters['Haw_a1'].set(min=0.0)
        parameters['Haw_a1'].set(max=slp_edge)

        parameters['Haw_a2'].set(max=0.0)
        parameters['Haw_a2'].set(min= -slp_edge)

        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')

            #print 'No broad'



    elif decompose != 1:
        parameters['Haw_sigma'].set(min= 0.999*outo.params['Haw_sigma'],max=1.0001*outo.params['Haw_sigma'])
        parameters['Haw_center'].set(min= 0.999*outo.params['Haw_center'],max=1.0001*outo.params['Haw_center'])


        parameters['Haw_a1'].set(min= outo.params['Haw_a1'],max=outo.params['Haw_a1']+1)
        parameters['Haw_a2'].set(min= outo.params['Haw_a2']-1,max=outo.params['Haw_a2'])

        #print 'Decomposing based on fixed Halpha broad center: ', c_broad, 'and width ', decompose[0]
        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')
            #print 'No broad'



    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 300 km/s
    parameters['Han_sigma'].set(min=((200.0/2.9979e5)*Hal_cm),max=(Hal_up/2.36/2.9979e5)*Hal_cm)

    #parameters['X_amplitude'].set(min=0)
    #parameters['X_center'].set(min=2.07,max=2.15)
    #parameters['X_sigma'].set(min=0.2,max=(3000.0/2.36/2.9979e5)*Hal_cm)

    parameters['Han_amplitude'].set(min=0.0)

    # Velocity offsets between -800 and 800 km/s for narrow
    if wvnet== 1.:
        parameters['Han_center'].set(min=Hal_cm+ Hal_cm*(-900.0/2.9979e5),max=Hal_cm+ Hal_cm*(900.0/2.9979e5))

    elif wvnet !=1:
        parameters['Han_center'].set(min=wvnet+ Hal_cm*(-600.0/2.9979e5),max=wvnet+ Hal_cm*(600.0/2.9979e5))

    #
    parameters['Nr_amplitude'].set(min=0.0)
    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nb_amplitude'].set(expr='Nr_amplitude/3')
    #
    parameters['Nr_sigma'].set(expr='Han_sigma*(6583/6562)')
    #
    parameters['Nb_sigma'].set(expr='Han_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nr_center'].set(expr='Han_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nb_center'].set(expr='Han_center - '+str(offset_b))
    #parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(2500.0/2.36/2.9979e5)*Hal_cm)


    flux = np.array(flux[fit_loc], dtype='float64')
    error = np.array(error[fit_loc], dtype='float64')
    wave = np.array(wave[fit_loc], dtype='float64')
    out = model.fit(flux,params=parameters, errors=error, x=(wave))

    try:
        chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error.data[fit_loc]**2))

    except:
        try:
            chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error[fit_loc]**2))

        except:
            chi2=1

    Hal_cm = 6562.*(1+z)/1e4
    #print 'Broadline params of the fits ',(out.params['Haw_fwhm'].value/Hal_cm)*2.9979e5, (out.params['Haw_center'].value)
    #print 'BLR mode: chi2 ', chi2, ' N ', len(flux[fit_loc])
    #print 'BLR BIC ', chi2+7*np.log(len(flux[fit_loc]))
    return out ,chi2


def fitting_OIII_Hbeta_qso_mul(wave, fluxs, error,z, chir=0, Hbeta=1, decompose=1, hbw=4861., offn=0, offw=0, o3n=1):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>4700*(1+z)/1e4)&(wave<5200*(1+z)/1e4))[0]

    flux = flux[fit_loc]
    wave = wave[fit_loc]
    error = error[fit_loc]



    sel=  np.where((wave<5050*(1+z)/1e4)& (wave>4980*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    wv = wave[np.where(wave==wave_peak)[0]]

    #plt.plot(wave, flux, drawstyle='steps-mid')



    model = LinearModel() + GaussianModel(prefix='o3rw_')+ GaussianModel(prefix='o3bw_') + GaussianModel(prefix='o3rn_')+ GaussianModel(prefix='o3bn_') + GaussianModel(prefix='Hbn_') + lmfit.Model(Gaussian_BK, prefix='Hbw_')#GaussianModel(prefix='Hbw_')
    # Starting parameters for the fits
    wv = 5008.*(1+z)/1e4

    if decompose==1:
        sigma_s = 800.
        c_broad = wv

    else:
        outo = decompose
        sigma_s = outo.params['Hbw_sigma'].value/outo.params['Hbw_center'].value*3e5
        c_broad = outo.params['Hbw_center'].value

    if 1==1:
        parameters = model.make_params( \
          #  Continuum level @ 5000 Ang; start = mean flux of spectrum
    		c = np.ma.median(flux), \
    		#  Continuum slope; start = 0.0
    		b = -2., \
             #a = 0.0, \
    		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		o3rw_center = wv-10.*(1+z)/1e4 + offw/3e5*wv,         \
    		o3bw_center = wv - (48.+10)*(1+z)/1e4 + offw/3e5*wv,   \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		o3rw_sigma = (1100.0/2.36/2.9979e5)*5006.84*(1+z)/1e4, \
    		o3bw_sigma = (1100.0/2.36/2.9979e5)*4958.92*(1+z)/1e4, \
             # pso
            o3rn_height = peak*(2./4),  \
    		o3bn_height =  peak*(2./12),   \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		o3rn_center = wv+offn/3e5*wv,         \
    		o3bn_center = wv+offn/3e5*wv - 48.*(1+z)/1e4,   \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		o3rn_sigma = (300.0/2.36/2.9979e5)*5006.84*(1+z)/1e4, \
    		o3bn_sigma = (300.0/2.36/2.9979e5)*4958.92*(1+z)/1e4, \
            Hbn_amplitude = peak/10,  \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		Hbn_center =  4861.2*(1+z)/1e4  ,         \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		Hbn_sigma = (300.0/2.36/2.9979e5)*4861.2*(1+z)/1e4, \
            Hbw_a1 = +3., \
            Hbw_a2 = -35., \
            Hbw_amplitude = peak/10,  \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		Hbw_center =  hbw*(1+z)/1e4  ,         \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		Hbw_sigma = (sigma_s/2.9979e5)*4861.2*(1+z)/1e4, \
    	)


    # Parameters constraints Narrow line flux > 0.0
    parameters['o3rw_amplitude'].set(min=0.0)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bw_amplitude'].set(expr='o3rw_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rw_sigma'].set(min=(1000./2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(2000/2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rw_center'].set(min=5008.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-1000.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(800.0/2.9979e5)) #HB89 -700, 800, LBQS -1000, 800,  2QZJ -700,800
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bw_sigma'].set(expr='o3rw_sigma*(4958.92/5006.84)')

    # Parameters constraints Narrow line flux > 0.0
    #parameters['o3rn_amplitude'].set(min=peak*0.1*(np.sqrt(2*np.pi)*0.00278))
    parameters['o3rn_amplitude'].set(min=0.0) # LBQS, HB89 0.0002, 2QZJ=0
    #print('height min on narrow ', peak*0.1)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bn_amplitude'].set(expr='o3rn_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rn_sigma'].set(min=(150.0/2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(1000./2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rn_center'].set(min=5006.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-200.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(500.0/2.9979e5)) # HB89 -500, 500, LBQS -200, 500,  2QZJ -200 500
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bn_sigma'].set(expr='o3rn_sigma*(4958.92/5006.84)')
    off = 48.*(1+z)/1e4
    parameters['o3bn_center'].set(expr='o3rn_center - '+str(off))
    parameters['o3bw_center'].set(expr='o3rw_center - '+str(off))

    if o3n==0:
        parameters['o3rn_amplitude'].set(expr='o3rw_amplitude/100000000000')
        parameters['o3bn_amplitude'].set(expr='o3bw_amplitude/100000000000')
        print('small o3')
    else:
      parameters['o3rn_amplitude'].set(min=0.0002) # LBQS, HB89 0.0002, 2QZJ=0

    # Parameters constraints Narrow line flux > 0.0
    #parameters['Hbn_amplitude'].set(min=0.0)
    parameters['Hbn_amplitude'].set(expr='Hbw_amplitude/100000000')

    parameters['slope'].set(min= -3,max=3)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Hbn_sigma'].set(min=(300.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,max=(700.0/2.36/2.9979e5)*4861.2*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Hbn_center'].set(min=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4*(-700.0/2.9979e5),max=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4 *(700.0/2.9979e5))

    if decompose==1:

        parameters['Hbw_amplitude'].set(min=0.0)
        parameters['Hbw_sigma'].set(min=(2000.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*4861.2*(1+z)/1e4)
        # Velocity offsets between -500 and 500 km/s for narrow
        parameters['Hbw_center'].set(min=hbw*(1+z)/1e4 + hbw*(1+z)/1e4*(-1000.0/2.9979e5),max=hbw*(1+z)/1e4 + hbw*(1+z)/1e4 *(1000.0/2.9979e5))

        slp_edge = 100.
        parameters['Hbw_a1'].set(min=0.0)
        parameters['Hbw_a1'].set(max=slp_edge)

        parameters['Hbw_a2'].set(max=-20)
        parameters['Hbw_a2'].set(min= -slp_edge)
    else:
        parameters['Hbw_sigma'].set(min= 0.999*outo.params['Hbw_sigma'],max=1.0001*outo.params['Hbw_sigma'])
        parameters['Hbw_center'].set(min= 0.999*outo.params['Hbw_center'],max=1.0001*outo.params['Hbw_center'])

        parameters['Hbw_a1'].set(min= outo.params['Hbw_a1'],max=outo.params['Hbw_a1']+1)
        parameters['Hbw_a2'].set(min= outo.params['Hbw_a2']-1,max=outo.params['Hbw_a2'])


    out = model.fit(flux,params=parameters, errors=error,x=(wave ))
    try:
        chi2 = sum(((out.eval(x=wave)- flux)**2)/(error.data**2))

        BIC = chi2+6*np.log(len(flux))
    except:
        BIC = len(flux)+6*np.log(len(flux))

    if chir==0:
        return out

    else:
        chi2 = (out.eval(x=wave)- flux )**2#sum(((out.eval(x=wave)- flux)**2)/(error.data**2))
        return out,chi2


def fitting_OIII_Hbeta_qso_sig(wave, fluxs, error,z, chir=0, Hbeta=1, decompose=1, hbw=4861., offn=0, offw=0, o3n=1):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    fit_loc = np.where((wave>4700*(1+z)/1e4)&(wave<5200*(1+z)/1e4))[0]

    flux = flux[fit_loc]
    wave = wave[fit_loc]
    error = error[fit_loc]



    sel=  np.where((wave<5050*(1+z)/1e4)& (wave>4980*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    wv = wave[np.where(wave==wave_peak)[0]]

    #plt.plot(wave, flux, drawstyle='steps-mid')



    model = LinearModel() + GaussianModel(prefix='o3rw_')+ GaussianModel(prefix='o3bw_') + GaussianModel(prefix='Hbn_') + lmfit.Model(Gaussian_BK, prefix='Hbw_')#GaussianModel(prefix='Hbw_')
    # Starting parameters for the fits
    wv = 5008.*(1+z)/1e4

    if decompose==1:
        sigma_s = 800.
        c_broad = wv

    else:
        outo = decompose
        sigma_s = outo.params['Hbw_sigma'].value/outo.params['Hbw_center'].value*3e5
        c_broad = outo.params['Hbw_center'].value

    if 1==1:
        parameters = model.make_params( \
          #  Continuum level @ 5000 Ang; start = mean flux of spectrum
    		c = np.ma.median(flux), \
    		#  Continuum slope; start = 0.0
    		b = -2., \
             #a = 0.0, \
    		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		o3rw_center = wv-10.*(1+z)/1e4 + offw/3e5*wv,         \
    		o3bw_center = wv - (48.+10)*(1+z)/1e4 + offw/3e5*wv,   \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		o3rw_sigma = (1100.0/2.36/2.9979e5)*5006.84*(1+z)/1e4, \
    		o3bw_sigma = (1100.0/2.36/2.9979e5)*4958.92*(1+z)/1e4, \
             # pso
            o3rw_height = peak*(2./4),  \
    		o3bw_height =  peak*(2./12),   \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger

            Hbn_amplitude = peak/10,  \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		Hbn_center =  4861.2*(1+z)/1e4  ,         \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		Hbn_sigma = (300.0/2.36/2.9979e5)*4861.2*(1+z)/1e4, \
            Hbw_a1 = +3., \
            Hbw_a2 = -35., \
            Hbw_amplitude = peak/10,  \
    		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
    		Hbw_center =  hbw*(1+z)/1e4  ,         \
    		#  [O III] 5007 sigma; start = 300 km/s FWHM
    		Hbw_sigma = (sigma_s/2.9979e5)*4861.2*(1+z)/1e4, \
    	)


    # Parameters constraints Narrow line flux > 0.0
    parameters['o3rw_amplitude'].set(min=0.0)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bw_amplitude'].set(expr='o3rw_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rw_sigma'].set(min=(1000./2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(2000/2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rw_center'].set(min=5008.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-800.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(800.0/2.9979e5)) #LBQS -1000, 800, HB89 -700, 800, 2QZJ -800,800
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bw_sigma'].set(expr='o3rw_sigma*(4958.92/5006.84)')

    # Parameters constraints Narrow line flux > 0.0
    #parameters['o3rn_amplitude'].set(min=peak*0.1*(np.sqrt(2*np.pi)*0.00278))
    parameters['o3rn_amplitude'].set(min=0.0002)
    #print('height min on narrow ', peak*0.1)
    # [O III] 4959 amplitude = 1/3 of [O III] 5007 amplitude
    parameters['o3bn_amplitude'].set(expr='o3rn_amplitude/3.0')
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 1000 km/s
    parameters['o3rn_sigma'].set(min=(150.0/2.36/2.9979e5)*5006.84*(1+z)/1e4,max=(1000./2.36/2.9979e5)*5006.84*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['o3rn_center'].set(min=5006.*(1+z)/1e4 + 5006.84*(1+z)/1e4*(-200.0/2.9979e5),max=5006*(1+z)/1e4+ 5006.84*(1+z)/1e4*(500.0/2.9979e5)) # LBQS -200, 500, HB89 -500, 500, 2QZJ -200 500
    # Constrain narrow line kinematics to match the [O III] line
    parameters['o3bn_sigma'].set(expr='o3rn_sigma*(4958.92/5006.84)')
    off = 48.*(1+z)/1e4
    parameters['o3bn_center'].set(expr='o3rn_center - '+str(off))
    parameters['o3bw_center'].set(expr='o3rw_center - '+str(off))

    if o3n==0:
        parameters['o3rn_amplitude'].set(expr='o3rw_amplitude/100000000000')
        parameters['o3bn_amplitude'].set(expr='o3bw_amplitude/100000000000')
        print('small o3')


    # Parameters constraints Narrow line flux > 0.0
    #parameters['Hbn_amplitude'].set(min=0.0)
    parameters['Hbn_amplitude'].set(expr='Hbw_amplitude/100000000')

    parameters['slope'].set(min= -3,max=3)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Hbn_sigma'].set(min=(300.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,max=(700.0/2.36/2.9979e5)*4861.2*(1+z)/1e4)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Hbn_center'].set(min=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4*(-700.0/2.9979e5),max=4861.2*(1+z)/1e4 + 4861.2*(1+z)/1e4 *(700.0/2.9979e5))

    if decompose==1:

        parameters['Hbw_amplitude'].set(min=0.0)
        parameters['Hbw_sigma'].set(min=(2000.0/2.36/2.9979e5)*4861.2*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*4861.2*(1+z)/1e4)
        # Velocity offsets between -500 and 500 km/s for narrow
        parameters['Hbw_center'].set(min=hbw*(1+z)/1e4 + hbw*(1+z)/1e4*(-1000.0/2.9979e5),max=hbw*(1+z)/1e4 + hbw*(1+z)/1e4 *(1000.0/2.9979e5))

        slp_edge = 100.
        parameters['Hbw_a1'].set(min=0.0)
        parameters['Hbw_a1'].set(max=slp_edge)

        parameters['Hbw_a2'].set(max=-20)
        parameters['Hbw_a2'].set(min= -slp_edge)
    else:
        parameters['Hbw_sigma'].set(min= 0.999*outo.params['Hbw_sigma'],max=1.0001*outo.params['Hbw_sigma'])
        parameters['Hbw_center'].set(min= 0.999*outo.params['Hbw_center'],max=1.0001*outo.params['Hbw_center'])

        parameters['Hbw_a1'].set(min= outo.params['Hbw_a1'],max=outo.params['Hbw_a1']+1)
        parameters['Hbw_a2'].set(min= outo.params['Hbw_a2']-1,max=outo.params['Hbw_a2'])





    out = model.fit(flux,params=parameters, errors=error,x=(wave ))
    try:
        chi2 = sum(((out.eval(x=wave)- flux)**2)/(error.data**2))

        BIC = chi2+6*np.log(len(flux))
    except:
        BIC = len(flux)+6*np.log(len(flux))

    if chir==0:
        return out

    else:
        chi2 = (out.eval(x=wave)- flux )**2#sum(((out.eval(x=wave)- flux)**2)/(error.data**2))
        return out,chi2




def sub_QSO_bkp(wave, fluxs, error,z, fst_out):
    from lmfit.models import LinearModel, GaussianModel, LorentzianModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]

    sel=  np.where(((wave<(6562.8+60)*(1+z)/1e4))& (wave>(6562.8-60)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]

    peak = np.ma.max(flux_zoom)

    wv = fst_out.params['Haw_center'].value

    model = LinearModel() + lmfit.Model(Gaussian_BK, prefix='Ha_')

    # Starting parameters for the fits
    parameters = model.make_params( \
        c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
         #a = 0.0, \
		#  [O III] 5007 amplitude; start = 5 sigma of spectrum
		Ha_amplitude = peak,  \
		#  [O III] 5007 peak; start = zero offset, BLR 5 Ang offset to stagger
		Ha_center = wv  ,         \
		#  [O III] 5007 sigma; start = 300 km/s FWHM
		Ha_sigma = fst_out.params['Haw_sigma'].value,\
        Ha_a1 = fst_out.params['Haw_a1'].value,\
        Ha_a2 = fst_out.params['Haw_a2'].value)

    # Parameters constraints Narrow line flux > 0.0
    parameters['Ha_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of grating of KMOS (R >~ 3000) < max of 2500 km/s
    parameters['Ha_sigma'].set(min=fst_out.params['Haw_sigma'].value*0.999999,max=fst_out.params['Haw_sigma'].value*1.000001)
    # Velocity offsets between -500 and 500 km/s for narrow
    parameters['Ha_center'].set(min=wv*0.9999999,max=wv*1.000000000001)

    parameters['Ha_a1'].set(min= fst_out.params['Haw_a1'],max=fst_out.params['Haw_a1']+1)
    parameters['Ha_a2'].set(min= fst_out.params['Haw_a2']-1,max=fst_out.params['Haw_a2'])


    out = model.fit(flux,params=parameters, errors=error, x=(wave))


    return out




def fitting_Halpha_mul_2QZJ(wave, fluxs, error,z, wvnet=1., decompose=np.array([1]), offset=0,init_sig=300., broad=1, cont=1):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel

    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]



    fit_loc = np.where((wave>(6562.8-600)*(1+z)/1e4)&(wave<(6562.8+600)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    if wvnet ==1.:
        wv = wave[np.where(wave==wave_peak)[0]]

    else:
        wv = wvnet

    Hal_cm = 6562.8*(1+z)/1e4


    model = LinearModel()+ GaussianModel(prefix='Haw_') +  GaussianModel(prefix='Hawn_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_')

    #model = LinearModel()+ GaussianModel(prefix='Haw_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_')

    # Starting parameters for the fits
    #print wv
    if len(decompose)==1:
        sigma_s = 1000
        c_broad = wv


    elif len(decompose)==2:
        sigma_s = decompose[0]
        c_broad = decompose[1]

    Hal_cm = 6562.8*(1+z)/1e4

    # Starting parameters for the fits
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
		Haw_amplitude = peak/2,  \
        Hawn_amplitude = peak/2,  \
		#
		Haw_center = 2.2478  ,         \
        Hawn_center = 2.2391  ,         \
		#
		Haw_sigma = (9700./2.36/2.9979e5)*Hal_cm, \
        Hawn_sigma = (3400./2.36/2.9979e5)*Hal_cm, \
         # pso
        Han_amplitude = peak*(2./2),  \
		#
		Han_center = wv,         \
		#
		Han_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nr_amplitude = peak*(1./6), \
         #
         Nr_center = 6583.*(1+z)/1e4, \
         #
         Nr_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nb_amplitude = peak/18, \
         #
         Nb_center = 6548.*(1+z)/1e4, \
         #
         Nb_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
	)
    if cont==0:
        parameters['intercept'].set(min=-0.0000000000001)
        parameters['intercept'].set(max= 0.0000000000001)
        parameters['slope'].set(min=-0.0000000000001)
        parameters['slope'].set(max= 0.0000000000001)
        print ('No continuum')
    # Parameters constraints Broad line flux > 0.0
    parameters['Haw_amplitude'].set(min=0.0)
    parameters['Hawn_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 2500 km/s


    if len(decompose) == 1:
        parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*Hal_cm)
        parameters['Haw_center'].set(min=Hal_cm+ Hal_cm*(-400.0/2.9979e5),max=Hal_cm+ Hal_cm*(1700.0/2.9979e5))

        parameters['Hawn_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(4000.0/2.36/2.9979e5)*Hal_cm)
        parameters['Hawn_center'].set(min=Hal_cm+ Hal_cm*(-900.0/2.9979e5),max=Hal_cm+ Hal_cm*(900.0/2.9979e5))

        #parameters['Haw_center'].set(expr='Han_center')

        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')
            #print 'No broad'



    elif len(decompose) == 2:
        parameters['Haw_sigma'].set(min=((decompose[0]-20)/2.36/2.9979e5)*Hal_cm,max=((decompose[0]+20)/2.36/2.9979e5)*Hal_cm)
        parameters['Haw_center'].set(min= c_broad+ 6562.8*(-10.0/2.9979e5),max=c_broad+ 6562.8*(10.0/2.9979e5))


        #print 'Decomposing based on fixed Halpha broad center: ', c_broad, 'and width ', decompose[0]
        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')
            #print 'No broad'

    # Parameters constraints Narrow line flux > 0.0
    parameters['Han_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 300 km/s
    parameters['Han_sigma'].set(min=((200.0/2.9979e5)*Hal_cm),max=(up_lim_nar_hal/2.36/2.9979e5)*Hal_cm)


    # Velocity offsets between -800 and 800 km/s for narrow
    if wvnet== 1.:
        parameters['Han_center'].set(min=Hal_cm+ Hal_cm*(-900.0/2.9979e5),max=Hal_cm+ Hal_cm*(900.0/2.9979e5))

    elif wvnet !=1:
        parameters['Han_center'].set(min=wvnet+ Hal_cm*(-600.0/2.9979e5),max=wvnet+ Hal_cm*(600.0/2.9979e5))

    #
    parameters['Nr_amplitude'].set(min=0.0)
    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nb_amplitude'].set(expr='Nr_amplitude/3')
    #
    parameters['Nr_sigma'].set(expr='Han_sigma*(6583/6562)')
    #
    parameters['Nb_sigma'].set(expr='Han_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nr_center'].set(expr='Han_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nb_center'].set(expr='Han_center - '+str(offset_b))
    #parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(2500.0/2.36/2.9979e5)*Hal_cm)


    flux = np.array(flux[fit_loc], dtype='float64')
    error = np.array(error[fit_loc], dtype='float64')
    wave = np.array(wave[fit_loc], dtype='float64')
    out = model.fit(flux,params=parameters, errors=error, x=(wave))

    try:
        chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error.data[fit_loc]**2))

    except:
        try:
            chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error[fit_loc]**2))

        except:
            chi2=1

    Hal_cm = 6562.*(1+z)/1e4
    #print 'Broadline params of the fits ',(out.params['Haw_fwhm'].value/Hal_cm)*2.9979e5, (out.params['Haw_center'].value)
    #print 'BLR mode: chi2 ', chi2, ' N ', len(flux[fit_loc])
    #print 'BLR BIC ', chi2+7*np.log(len(flux[fit_loc]))
    return out ,chi2



def fitting_Halpha_mul_LBQS(wave, fluxs, error,z, wvnet=1., decompose=1, offset=0,init_sig=300., broad=1, cont=1):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel


    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]



    fit_loc = np.where((wave>(6562.8-600)*(1+z)/1e4)&(wave<(6562.8+600)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    if wvnet ==1.:
        wv = wave[np.where(wave==wave_peak)[0]]

    else:
        wv = wvnet

    Hal_cm = 6562.8*(1+z)/1e4


    model = LinearModel()+ lmfit.Model(Gaussian_BK, prefix='Haw_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_') + GaussianModel(prefix='X_')


    # Starting parameters for the fits
    #print wv
    if decompose==1:
        sigma_s = 4000
        c_broad = wv

    else:
        outo = decompose
        sigma_s = outo.params['Haw_sigma'].value/outo.params['Haw_center'].value*3e5
        c_broad = outo.params['Haw_center'].value

    Hal_cm = 6562.8*(1+z)/1e4

    # Starting parameters for the fits
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.0, \
		Haw_amplitude = peak/3,  \
		#
		Haw_center = wv  ,         \
		#
		Haw_sigma = (sigma_s/2.9979e5)*Hal_cm, \
         # pso
        Han_amplitude = peak*(2./2),  \
		#
		Han_center = wv,         \
		#
		Han_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nr_amplitude = peak*(1./6), \
         #
         Nr_center = 6583.*(1+z)/1e4, \
         #
         Nr_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nb_amplitude = peak/18, \
         #
         Nb_center = 6548.*(1+z)/1e4, \
         #
         Nb_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         Haw_a1 = + 3, \
         Haw_a2 = - 3, \

         X_sigma = (6000./2.9979e5)*Hal_cm , \
         X_center = 6350*(1+z)/1e4 , \
	)
    if cont==0:
        parameters['intercept'].set(min=-0.0000000000001)
        parameters['intercept'].set(max= 0.0000000000001)
        parameters['slope'].set(min=-0.0000000000001)
        parameters['slope'].set(max= 0.0000000000001)
        print ('No continuum')
    # Parameters constraints Broad line flux > 0.0
    parameters['Haw_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 2500 km/s


    if decompose == 1:
        parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*Hal_cm)
        parameters['Haw_center'].set(min=Hal_cm+ Hal_cm*(-400.0/2.9979e5),max=Hal_cm+ Hal_cm*(400.0/2.9979e5))

        #parameters['Haw_center'].set(expr='Han_center')

        # Parameters constraints Narrow line flux > 0.0
        parameters['Han_amplitude'].set(min=0.0)

        slp_edge = 200.
        parameters['Haw_a1'].set(min=0.0)
        parameters['Haw_a1'].set(max=slp_edge)

        parameters['Haw_a2'].set(max=0.0)
        parameters['Haw_a2'].set(min= -slp_edge)

        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')

            #print 'No broad'



    elif decompose != 1:
        parameters['Haw_sigma'].set(min= 0.999*outo.params['Haw_sigma'],max=1.0001*outo.params['Haw_sigma'])
        parameters['Haw_center'].set(min= 0.999*outo.params['Haw_center'],max=1.0001*outo.params['Haw_center'])


        parameters['Haw_a1'].set(min= outo.params['Haw_a1'],max=outo.params['Haw_a1']+1)
        parameters['Haw_a2'].set(min= outo.params['Haw_a2']-1,max=outo.params['Haw_a2'])

        parameters['X_sigma'].set(min= 0.999*outo.params['X_sigma'],max=1.0001*outo.params['X_sigma'])
        parameters['X_center'].set(min= 0.999*outo.params['X_center'],max=1.0001*outo.params['X_center'])


        #print 'Decomposing based on fixed Halpha broad center: ', c_broad, 'and width ', decompose[0]
        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')
            #print 'No broad'



    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 300 km/s
    parameters['Han_sigma'].set(min=((200.0/2.9979e5)*Hal_cm),max=(up_lim_nar_hal/2.36/2.9979e5)*Hal_cm)

    #parameters['X_amplitude'].set(min=0)
    #parameters['X_center'].set(min=2.07,max=2.15)
    #parameters['X_sigma'].set(min=0.2,max=(3000.0/2.36/2.9979e5)*Hal_cm)

    parameters['Han_amplitude'].set(min=0.0)

    # Velocity offsets between -800 and 800 km/s for narrow
    if wvnet== 1.:
        parameters['Han_center'].set(min=Hal_cm+ Hal_cm*(-900.0/2.9979e5),max=Hal_cm+ Hal_cm*(900.0/2.9979e5))

    elif wvnet !=1:
        parameters['Han_center'].set(min=wvnet+ Hal_cm*(-600.0/2.9979e5),max=wvnet+ Hal_cm*(600.0/2.9979e5))

    #
    parameters['Nr_amplitude'].set(min=0.0)
    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nb_amplitude'].set(expr='Nr_amplitude/3')
    #
    parameters['Nr_sigma'].set(expr='Han_sigma*(6583/6562)')
    #
    parameters['Nb_sigma'].set(expr='Han_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nr_center'].set(expr='Han_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nb_center'].set(expr='Han_center - '+str(offset_b))
    #parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(2500.0/2.36/2.9979e5)*Hal_cm)
    parameters['X_center'].set(min=6361*(1+z)/1e4+ Hal_cm*(-900.0/2.9979e5),max=6361*(1+z)/1e4+ Hal_cm*(900.0/2.9979e5))
    parameters['X_sigma'].set(min=(4000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(8000.0/2.36/2.9979e5)*Hal_cm)


    flux = np.array(flux[fit_loc], dtype='float64')
    error = np.array(error[fit_loc], dtype='float64')
    wave = np.array(wave[fit_loc], dtype='float64')

    out = model.fit(flux,params=parameters, errors=error, x=(wave))

    try:
        chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error.data[fit_loc]**2))

    except:
        try:
            chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error[fit_loc]**2))

        except:
            chi2=1

    Hal_cm = 6562.*(1+z)/1e4
    #print 'Broadline params of the fits ',(out.params['Haw_fwhm'].value/Hal_cm)*2.9979e5, (out.params['Haw_center'].value)
    #print 'BLR mode: chi2 ', chi2, ' N ', len(flux[fit_loc])
    #print 'BLR BIC ', chi2+7*np.log(len(flux[fit_loc]))
    return out ,chi2



def fitting_Halpha_mul_bkp_2QZJ(wave, fluxs, error,z, wvnet=1., decompose=1, offset=0,init_sig=300., broad=1, cont=1, cont_norm='n'):
    from lmfit.models import GaussianModel, LorentzianModel, LinearModel, QuadraticModel, PowerLawModel


    print ('Fitting Broken Power law Gaussian with fixed slope')
    flux = fluxs.data[np.invert(fluxs.mask)]
    wave = wave[np.invert(fluxs.mask)]



    fit_loc = np.where((wave>(6562.8-600)*(1+z)/1e4)&(wave<(6562.8+600)*(1+z)/1e4))[0]

    sel=  np.where(((wave<(6562.8+20)*(1+z)/1e4))& (wave>(6562.8-20)*(1+z)/1e4))[0]
    flux_zoom = flux[sel]
    wave_zoom = wave[sel]

    peak_loc = np.ma.argmax(flux_zoom)
    peak = np.ma.max(flux_zoom)
    wave_peak = wave_zoom[peak_loc]

    if wvnet ==1.:
        wv = wave[np.where(wave==wave_peak)[0]]

    else:
        wv = wvnet

    Hal_cm = 6562.8*(1+z)/1e4


    model = LinearModel()+ lmfit.Model(Gaussian_BK, prefix='Haw_') + GaussianModel(prefix='Han_') + GaussianModel(prefix='Nr_') + GaussianModel(prefix='Nb_') #+ GaussianModel(prefix='X_')


    # Starting parameters for the fits
    #print wv
    if decompose==1:
        sigma_s = 4000
        c_broad = wv

    else:
        outo = decompose
        sigma_s = outo.params['Haw_sigma'].value/outo.params['Haw_center'].value*3e5
        c_broad = outo.params['Haw_center'].value

    Hal_cm = 6562.8*(1+z)/1e4

    # Starting parameters for the fits
    parameters = model.make_params( \
      #  Continuum level @ 5000 Ang; start = mean flux of spectrum
		c = np.ma.median(flux), \
		#  Continuum slope; start = 0.0
		b = 0.1707, \
		Haw_amplitude = peak/3,  \
		#
		Haw_center = wv  ,         \
		#
		Haw_sigma = (sigma_s/2.9979e5)*Hal_cm, \
         # pso
        Han_amplitude = peak*(2./2),  \
		#
		Han_center = wv,         \
		#
		Han_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nr_amplitude = peak*(1./6), \
         #
         Nr_center = 6583.*(1+z)/1e4, \
         #
         Nr_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         #
         Nb_amplitude = peak/18, \
         #
         Nb_center = 6548.*(1+z)/1e4, \
         #
         Nb_sigma = (init_sig/2.36/2.9979e5)*Hal_cm, \
         Haw_a1 = + 3, \
         Haw_a2 = - 3, \
	)
    if cont==0:
        parameters['intercept'].set(min=-0.0000000000001)
        parameters['intercept'].set(max= 0.0000000000001)
        parameters['slope'].set(min=-0.0000000000001)
        parameters['slope'].set(max= 0.0000000000001)
        print ('No continuum')
    # Parameters constraints Broad line flux > 0.0
    parameters['Haw_amplitude'].set(min=0.0)
    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 2500 km/s

    parameters['slope'].set(min=-0.0000001)
    parameters['slope'].set(max=0.00000001)

    if cont_norm !='n':

        parameters['intercept'].set(min=cont_norm-0.0000001)
        parameters['intercept'].set(max=cont_norm+0.00000001)



    if decompose == 1:
        parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(12000.0/2.36/2.9979e5)*Hal_cm)
        parameters['Haw_center'].set(min=Hal_cm+ Hal_cm*(-400.0/2.9979e5),max=Hal_cm+ Hal_cm*(400.0/2.9979e5))

        #parameters['Haw_center'].set(expr='Han_center')

        # Parameters constraints Narrow line flux > 0.0
        parameters['Han_amplitude'].set(min=0.0)

        slp_edge = 200.
        parameters['Haw_a1'].set(min=0.0)
        parameters['Haw_a1'].set(max=slp_edge)

        parameters['Haw_a2'].set(max=0.0)
        parameters['Haw_a2'].set(min= -slp_edge)

        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')

            #print 'No broad'



    elif decompose != 1:
        parameters['Haw_sigma'].set(min= 0.999*outo.params['Haw_sigma'],max=1.0001*outo.params['Haw_sigma'])
        parameters['Haw_center'].set(min= 0.999*outo.params['Haw_center'],max=1.0001*outo.params['Haw_center'])


        parameters['Haw_a1'].set(min= outo.params['Haw_a1'],max=outo.params['Haw_a1']+1)
        parameters['Haw_a2'].set(min= outo.params['Haw_a2']-1,max=outo.params['Haw_a2'])

        #print 'Decomposing based on fixed Halpha broad center: ', c_broad, 'and width ', decompose[0]
        if broad==0:
            parameters['Haw_amplitude'].set(expr='Han_amplitude/100000000')
            #print 'No broad'



    # Narrow line FWHM > min resolution of YJ grating of KMOS (R >~ 3000) < max of 300 km/s
    parameters['Han_sigma'].set(min=((200.0/2.9979e5)*Hal_cm),max=(up_lim_nar_hal/2.36/2.9979e5)*Hal_cm)

    #parameters['X_amplitude'].set(min=0)
    #parameters['X_center'].set(min=2.07,max=2.15)
    #parameters['X_sigma'].set(min=0.2,max=(3000.0/2.36/2.9979e5)*Hal_cm)

    parameters['Han_amplitude'].set(min=0.0)

    # Velocity offsets between -800 and 800 km/s for narrow
    if wvnet== 1.:
        parameters['Han_center'].set(min=Hal_cm+ Hal_cm*(-900.0/2.9979e5),max=Hal_cm+ Hal_cm*(900.0/2.9979e5))

    elif wvnet !=1:
        parameters['Han_center'].set(min=wvnet+ Hal_cm*(-600.0/2.9979e5),max=wvnet+ Hal_cm*(600.0/2.9979e5))

    #
    parameters['Nr_amplitude'].set(min=0.0)
    #parameters['Nr_amplitude'].set(expr = 'Han_amplitude/1000000000')
    #
    parameters['Nb_amplitude'].set(expr='Nr_amplitude/3')
    #
    parameters['Nr_sigma'].set(expr='Han_sigma*(6583/6562)')
    #
    parameters['Nb_sigma'].set(expr='Han_sigma*(6548/6562)')

    offset_r = (6562.-6583.)*(1+z)/1e4
    #
    parameters['Nr_center'].set(expr='Han_center - '+str(offset_r))

    offset_b = (6562.-6548.)*(1+z)/1e4
    #
    parameters['Nb_center'].set(expr='Han_center - '+str(offset_b))
    #parameters['Haw_sigma'].set(min=(2000.0/2.36/2.9979e5)*6562.8*(1+z)/1e4,max=(2500.0/2.36/2.9979e5)*Hal_cm)


    flux = np.array(flux[fit_loc], dtype='float64')
    error = np.array(error[fit_loc], dtype='float64')
    wave = np.array(wave[fit_loc], dtype='float64')
    out = model.fit(flux,params=parameters, errors=error, x=(wave))

    try:
        chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error.data[fit_loc]**2))

    except:
        try:
            chi2 = sum(((out.eval(x=wave[fit_loc])- flux[fit_loc])**2)/(error[fit_loc]**2))

        except:
            chi2=1

    Hal_cm = 6562.*(1+z)/1e4
    #print 'Broadline params of the fits ',(out.params['Haw_fwhm'].value/Hal_cm)*2.9979e5, (out.params['Haw_center'].value)
    #print 'BLR mode: chi2 ', chi2, ' N ', len(flux[fit_loc])
    #print 'BLR BIC ', chi2+7*np.log(len(flux[fit_loc]))
    return out ,chi2
'''