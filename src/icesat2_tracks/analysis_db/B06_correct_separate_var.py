"""
This file open a ICEsat2 track applied filters and corections and returns smoothed photon heights on a regular grid in an .nc file.
This is python 3
"""

import os, sys


import h5py
from pathlib import Path
import icesat2_tracks.ICEsat2_SI_tools.iotools as io
import icesat2_tracks.local_modules.m_tools_ph3 as MT
from icesat2_tracks.local_modules import m_general_ph3 as M
import time
import copy
import icesat2_tracks.ICEsat2_SI_tools.generalized_FT as gFT
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
import typer

from icesat2_tracks.config.IceSAT2_startup import (
    mconfig,
    color_schemes,
    font_for_pres,
    font_for_print,
    lstrings,
    fig_sizes,
)

from icesat2_tracks.clitools import (
    echo,
    validate_batch_key,
    validate_output_dir,
    suppress_stdout,
    update_paths_mconfig,
    report_input_parameters,
    validate_track_name_steps_gt_1,
    makeapp    
)


def run_B06_correct_separate_var(
    track_name: str = typer.Option(..., callback=validate_track_name_steps_gt_1),
    batch_key: str = typer.Option(..., callback=validate_batch_key),
    ID_flag: bool = True,
    output_dir: str = typer.Option(None, callback=validate_output_dir),
    verbose: bool = False,
):

    with suppress_stdout(verbose):
        kargs = {
            "track_name": track_name,
            "batch_key": batch_key,
            "ID_flag": ID_flag,
            "output_dir": output_dir,
        }

    report_input_parameters(**kargs)
    
    workdir, plotsdir = update_paths_mconfig(output_dir, mconfig)

    kargs = {
        "ID": ID,
        "track_names": track_names,
        "hemis": hemis,
        "batch": batch,
        "mconfig": workdir,
        "heading": "** Revised input parameters:",
    }
    report_input_parameters(**kargs)

    xr.set_options(display_style="text")
    track_name, batch_key, test_flag = io.init_from_input(
        [
            None,
            track_name,
            batch_key,
            ID_flag,
        ]  # init_from_input expects sys.argv with 4 elements
    )

    kargs = {
        "track_name": track_name,
        "batch_key": batch_key,
        "ID_flag": ID_flag,
        "output_dir": output_dir,
    }
    report_input_parameters(**kargs)
    
    workdir, plotsdir = update_paths_mconfig(output_dir, mconfig)
    with suppress_stdout():
        ID, track_names, hemis, batch = io.init_data(
            str(track_name), str(batch_key), str(ID_flag), str(workdir)
        )  # TODO: clean up application of str() to all arguments

    kargs = {
        "ID": ID,
        "track_names": track_names,
        "hemis": hemis,
        "batch": batch,
        "mconfig": workdir,
        "heading": "** Revised input parameters:",
    }

    report_input_parameters(**kargs)

    hemis, batch = batch_key.split("_")

    all_beams = mconfig["beams"]["all_beams"]
    high_beams = mconfig["beams"]["high_beams"]
    low_beams = mconfig["beams"]["low_beams"]

    load_path_work = Path(workdir, batch_key)

    B3_hdf5 = h5py.File(
        Path(load_path_work, "B01_regrid", track_name, "_B01_binned.h5"), "r"
    )

    load_path_angle = Path(load_path_work, batch_key, "B04_angle")

    B3 = dict()
    for b in all_beams:
        B3[b] = io.get_beam_hdf_store(B3_hdf5[b])

    B3_hdf5.close()

    load_file = Path(load_path_work, "B02_spectra", "B02_", track_name)  # + '.nc'

    Gk = xr.open_dataset(load_file + "_gFT_k.nc")
    Gx = xr.open_dataset(load_file + "_gFT_x.nc")
    Gfft = xr.open_dataset(load_file + "_FFT.nc")

    plot_path = Path(plotsdir, hemis, batch_key, track_name, "B06_correction")
    plot_path.mkdirs(parents=True, exist_ok=True)

    save_path = Path(workdir, batch_key, "B06_corrected_separated")
    save_path.mkdirs(parents=True, exist_ok=True)

    color_schemes.colormaps2(31, gamma=1)
    col_dict = color_schemes.rels

    def dict_weighted_mean(Gdict, weight_key):
        """
        returns the weighted meean of a dict of xarray, data_arrays
        weight_key must be in the xr.DataArrays
        """

        akey = list(Gdict.keys())[0]
        GSUM = Gdict[akey].copy()
        GSUM.data = np.zeros(GSUM.shape)
        N_per_stancil = GSUM.N_per_stancil * 0
        N_photons = np.zeros(GSUM.N_per_stancil.size)

        counter = 0
        for _, I in Gdict.items():
            I = I.squeeze()
            echo(len(I.x))
            if len(I.x) != 0:
                GSUM += I.where(~np.isnan(I), 0) * I[weight_key]
                N_per_stancil += I[weight_key]
            if "N_photons" in GSUM.coords:
                N_photons += I["N_photons"]
            counter += 1

        GSUM = GSUM / N_per_stancil

        if "N_photons" in GSUM.coords:
            GSUM.coords["N_photons"] = (("x", "beam"), np.expand_dims(N_photons, 1))

        GSUM["beam"] = ["weighted_mean"]
        GSUM.name = "power_spec"

        return GSUM

    G_gFT_wmean = (
        Gk.where(~np.isnan(Gk["gFT_PSD_data"]), 0) * Gk["N_per_stancil"]
    ).sum("beam") / Gk["N_per_stancil"].sum("beam")
    G_gFT_wmean["N_photons"] = Gk["N_photons"].sum("beam")

    G_fft_wmean = (Gfft.where(~np.isnan(Gfft), 0) * Gfft["N_per_stancil"]).sum(
        "beam"
    ) / Gfft["N_per_stancil"].sum("beam")
    G_fft_wmean["N_per_stancil"] = Gfft["N_per_stancil"].sum("beam")

    # plot
    # derive spectral errors:
    Lpoints = Gk.Lpoints.mean("beam").data
    N_per_stancil = Gk.N_per_stancil.mean("beam").data  # [0:-2]

    G_error_model = dict()
    G_error_data = dict()

    for bb in Gk.beam.data:
        I = Gk.sel(beam=bb)
        b_bat_error = np.concatenate(
            [I.model_error_k_cos.data, I.model_error_k_sin.data]
        )
        Z_error = gFT.complex_represenation(b_bat_error, Gk.k.size, Lpoints)
        PSD_error_data, PSD_error_model = gFT.Z_to_power_gFT(
            Z_error, np.diff(Gk.k)[0], N_per_stancil, Lpoints
        )

        G_error_model[bb] = xr.DataArray(
            data=PSD_error_model,
            coords=I.drop("N_per_stancil").coords,
            name="gFT_PSD_data_error",
        ).expand_dims("beam")
        G_error_data[bb] = xr.DataArray(
            data=PSD_error_data,
            coords=I.drop("N_per_stancil").coords,
            name="gFT_PSD_data_error",
        ).expand_dims("beam")

    gFT_PSD_data_error_mean = xr.concat(G_error_model.values(), dim="beam")
    gFT_PSD_data_error_mean = xr.concat(G_error_data.values(), dim="beam")

    gFT_PSD_data_error_mean = (
        gFT_PSD_data_error_mean.where(~np.isnan(gFT_PSD_data_error_mean), 0)
        * Gk["N_per_stancil"]
    ).sum("beam") / Gk["N_per_stancil"].sum("beam")
    gFT_PSD_data_error_mean = (
        gFT_PSD_data_error_mean.where(~np.isnan(gFT_PSD_data_error_mean), 0)
        * Gk["N_per_stancil"]
    ).sum("beam") / Gk["N_per_stancil"].sum("beam")

    G_gFT_wmean["gFT_PSD_data_err"] = gFT_PSD_data_error_mean
    G_gFT_wmean["gFT_PSD_data_err"] = gFT_PSD_data_error_mean

    Gk["gFT_PSD_data_err"] = xr.concat(G_error_model.values(), dim="beam")
    Gk["gFT_PSD_data_err"] = xr.concat(G_error_data.values(), dim="beam")

    #

    G_gFT_smth = (
        G_gFT_wmean["gFT_PSD_data"].rolling(k=30, center=True, min_periods=1).mean()
    )
    G_gFT_smth["N_photons"] = G_gFT_wmean.N_photons
    G_gFT_smth["N_per_stancil_fraction"] = Gk["N_per_stancil"].T.mean(
        "beam"
    ) / Gk.Lpoints.mean("beam")

    k = G_gFT_smth.k

    F = M.figure_axis_xy()

    plt.loglog(k, G_gFT_smth / k)

    plt.title("displacement power Spectra", loc="left")

    def define_noise_wavenumber_tresh_simple(
        data_xr, k_peak, k_end_lim=None, plot_flag=False
    ):
        """
        returns noise wavenumber on the high end of a spectral peak. This method fits a straight line in loglog speace using robust regression.
        The noise level is defined as the wavenumber at which the residual error of a linear fit to the data is minimal.

        inputs:
        data_xr xarray.Dataarray with the power spectra with k as dimension
        k_peak  wavenumber above which the searh should start
        dk      the intervall over which the regrssion is repeated

        returns:
        k_end   the wavenumber at which the spectrum flattens
        m       slope of the fitted line
        b       intersect of the fitted line
        """

        if k_end_lim is None:
            k_end_lim = data_xr.k[-1]

        k_lead_peak_margin = k_peak * 1.05
        try:
            data_log = (
                np.log(data_xr)
                .isel(k=(data_xr.k > k_lead_peak_margin))
                .rolling(k=10, center=True, min_periods=1)
                .mean()
            )

        except:
            data_log = (
                np.log(data_xr)
                .isel(k=(data_xr.k > k_lead_peak_margin / 2))
                .rolling(k=10, center=True, min_periods=1)
                .mean()
            )

        k_log = np.log(data_log.k)
        try:
            d_grad = (
                data_log.differentiate("k")
                .rolling(k=40, center=True, min_periods=4)
                .mean()
            )
        except:
            d_grad = (
                data_log.differentiate("k")
                .rolling(k=20, center=True, min_periods=2)
                .mean()
            )
        ll = label(d_grad >= -5)

        if ll[0][0] != 0:
            echo("no decay, set to peak")
            return k_peak

        if sum(ll[0]) == 0:
            k_end = d_grad.k[-1]
        else:
            k_end = d_grad.k[(ll[0] == 1)][0].data

        if plot_flag:
            plt.plot(np.log(data_xr.k), np.log(data_xr))
            plt.plot(k_log, data_log)
            plt.plot([np.log(k_end), np.log(k_end)], [-6, -5])
        return k_end

    # new version
    def get_correct_breakpoint(pw_results):
        br_points = list()
        for i in pw_results.keys():
            [br_points.append(i) if "breakpoint" in i else None]
        br_points_df = pw_results[br_points]
        br_points_sorted = br_points_df.sort_values()

        alphas_sorted = [
            i.replace("breakpoint", "alpha") for i in br_points_df.sort_values().index
        ]
        alphas_sorted.append("alpha" + str(len(alphas_sorted) + 1))

        betas_sorted = [
            i.replace("breakpoint", "beta") for i in br_points_df.sort_values().index
        ]

        # betas_sorted
        alphas_v2 = list()
        alpha_i = pw_results["alpha1"]
        for i in [0] + list(pw_results[betas_sorted]):
            alpha_i += i
            alphas_v2.append(alpha_i)

        alphas_v2_sorted = pd.Series(index=alphas_sorted, data=alphas_v2)
        br_points_sorted["breakpoint" + str(br_points_sorted.size + 1)] = "end"

        echo("all alphas")
        echo(alphas_v2_sorted)
        slope_mask = alphas_v2_sorted < 0

        if sum(slope_mask) == 0:
            echo("no negative slope found, set to lowest")
            breakpoint = "start"
        else:
            # take steepest slope
            alpah_v2_sub = alphas_v2_sorted[slope_mask]
            echo(alpah_v2_sub)
            echo(alpah_v2_sub.argmin())
            break_point_name = alpah_v2_sub.index[alpah_v2_sub.argmin()].replace(
                "alpha", "breakpoint"
            )

            # take first slope
            breakpoint = br_points_sorted[break_point_name]

        return breakpoint

    def get_breakingpoints(xx, dd):
        import piecewise_regression

        x2, y2 = xx, dd
        convergence_flag = True
        n_breakpoints = 3
        while convergence_flag:
            pw_fit = piecewise_regression.Fit(x2, y2, n_breakpoints=n_breakpoints)
            echo("n_breakpoints", n_breakpoints, pw_fit.get_results()["converged"])
            convergence_flag = not pw_fit.get_results()["converged"]
            n_breakpoints += 1
            if n_breakpoints >= 4:
                convergence_flag = False

        pw_results = pw_fit.get_results()

        if pw_results["converged"]:
            pw_results_df = pd.DataFrame(pw_results["estimates"]).loc["estimate"]

            breakpoint = get_correct_breakpoint(pw_results_df)

            return pw_fit, breakpoint

        else:
            return pw_fit, False

    def define_noise_wavenumber_piecewise(data_xr, plot_flag=False):
        data_log = data_xr
        data_log = np.log(data_xr)

        k = data_log.k.data
        k_log = np.log(k)

        pw_fit, breakpoint_log = get_breakingpoints(k_log, data_log.data)

        if breakpoint_log is "start":
            echo("no decay, set to lowerst wavenumber")
            breakpoint_log = k_log[0]
        if (breakpoint_log is "end") | (breakpoint_log is False):
            echo("higest wavenumner")
            breakpoint_log = k_log[-1]

        breakpoint_pos = abs(k_log - breakpoint_log).argmin()
        breakpoint_k = k[breakpoint_pos]

        if plot_flag:
            pw_fit.plot()
            plt.plot(k_log, data_log)

        return breakpoint_k, pw_fit

    k_lim_list = list()
    k_end_previous = np.nan
    x = G_gFT_smth.x.data[0]
    k = G_gFT_smth.k.data

    for x in G_gFT_smth.x.data:
        echo(x)
        # use displacement power spectrum
        k_end, pw_fit = define_noise_wavenumber_piecewise(
            G_gFT_smth.sel(x=x) / k, plot_flag=False
        )

        k_save = k_end_previous if k_end == k[0] else k_end
        k_end_previous = k_save
        k_lim_list.append(k_save)
        echo("--------------------------")

    font_for_pres()
    G_gFT_smth.coords["k_lim"] = ("x", k_lim_list)
    G_gFT_smth.k_lim.plot()
    k_lim_smth = G_gFT_smth.k_lim.rolling(x=3, center=True, min_periods=1).mean()
    k_lim_smth.plot(c="r")

    plt.title("k_c filter", loc="left")
    F.save_light(path=plot_path, name=str(track_name) + "_B06_atten_ov")

    G_gFT_smth["k_lim"] = k_lim_smth
    G_gFT_wmean.coords["k_lim"] = k_lim_smth

    font_for_print()

    fn = copy.copy(lstrings)
    F = M.figure_axis_xy(
        fig_sizes["two_column"][0],
        fig_sizes["two_column"][0] * 0.9,
        container=True,
        view_scale=1,
    )

    plt.suptitle(
        "Cut-off Frequency for Displacement Spectral\n" + io.ID_to_str(track_name),
        y=0.97,
    )
    gs = GridSpec(8, 3, wspace=0.1, hspace=1.5)

    k_lims = G_gFT_wmean.k_lim
    xlims = G_gFT_wmean.k[0], G_gFT_wmean.k[-1]
    #
    k = high_beams[0]
    for pos, k, pflag in zip(
        [gs[0:2, 0], gs[0:2, 1], gs[0:2, 2]], high_beams, [True, False, False]
    ):
        ax0 = F.fig.add_subplot(pos)
        Gplot = (
            Gk.sel(beam=k)
            .isel(x=slice(0, -1))
            .gFT_PSD_data.squeeze()
            .rolling(k=20, x=2, min_periods=1, center=True)
            .mean()
        )
        Gplot = Gplot.where(Gplot["N_per_stancil"] / Gplot["Lpoints"] >= 0.1)
        alpha_range = iter(np.linspace(1, 0, Gplot.x.data.size))
        for x in Gplot.x.data:
            ialpha = next(alpha_range)
            plt.loglog(
                Gplot.k,
                Gplot.sel(x=x) / Gplot.k,
                linewidth=0.5,
                color=color_schemes.rels[k],
                alpha=ialpha,
            )
            ax0.axvline(
                k_lims.sel(x=x), linewidth=0.4, color="black", zorder=0, alpha=ialpha
            )

        plt.title(next(fn) + k, color=col_dict[k], loc="left")
        plt.xlim(xlims)
        #
        if pflag:
            ax0.tick_params(labelbottom=False, bottom=True)
            plt.ylabel("Power (m$^2$/k')")
            plt.legend()
        else:
            ax0.tick_params(labelbottom=False, bottom=True, labelleft=False)

    for pos, k, pflag in zip(
        [gs[2:4, 0], gs[2:4, 1], gs[2:4, 2]], low_beams, [True, False, False]
    ):
        ax0 = F.fig.add_subplot(pos)
        Gplot = (
            Gk.sel(beam=k)
            .isel(x=slice(0, -1))
            .gFT_PSD_data.squeeze()
            .rolling(k=20, x=2, min_periods=1, center=True)
            .mean()
        )

        Gplot = Gplot.where(Gplot["N_per_stancil"] / Gplot["Lpoints"] >= 0.1)

        alpha_range = iter(np.linspace(1, 0, Gplot.x.data.size))
        for x in Gplot.x.data:
            ialpha = next(alpha_range)
            plt.loglog(
                Gplot.k,
                Gplot.sel(x=x) / Gplot.k,
                linewidth=0.5,
                color=color_schemes.rels[k],
                alpha=ialpha,
            )
            ax0.axvline(
                k_lims.sel(x=x), linewidth=0.4, color="black", zorder=0, alpha=ialpha
            )

        plt.title(next(fn) + k, color=col_dict[k], loc="left")
        plt.xlim(xlims)
        plt.xlabel("observed wavenumber k' ")

        if pflag:
            ax0.tick_params(bottom=True)
            plt.ylabel("Power (m$^2$/k')")
            plt.legend()
        else:
            ax0.tick_params(bottom=True, labelleft=False)

    F.save_light(path=plot_path, name=str(track_name) + "_B06_atten_ov_simple")
    F.save_pup(path=plot_path, name=str(track_name) + "_B06_atten_ov_simple")

    pos = gs[5:, 0:2]
    ax0 = F.fig.add_subplot(pos)

    lat_str = (
        str(np.round(Gx.isel(x=0).lat.mean().data, 2))
        + " to "
        + str(np.round(Gx.isel(x=-1).lat.mean().data, 2))
    )
    plt.title(next(fn) + "Mean Displacement Spectra\n(lat=" + lat_str + ")", loc="left")

    dd = 10 * np.log((G_gFT_smth / G_gFT_smth.k).isel(x=slice(0, -1)))
    dd = dd.where(~np.isinf(dd), np.nan)

    ## filter out segments with less then 10% of data points
    dd = dd.where(G_gFT_smth["N_per_stancil_fraction"] >= 0.1)

    dd_lims = np.round(dd.quantile(0.01).data * 0.95, 0), np.round(
        dd.quantile(0.95).data * 1.05, 0
    )
    plt.pcolor(
        dd.x / 1e3,
        dd.k,
        dd,
        vmin=dd_lims[0],
        vmax=dd_lims[-1],
        cmap=color_schemes.white_base_blgror,
    )
    cb = plt.colorbar(orientation="vertical")

    cb.set_label("Power (m$^2$/k)")
    plt.plot(
        G_gFT_smth.isel(x=slice(0, -1)).x / 1e3,
        G_gFT_smth.isel(x=slice(0, -1)).k_lim,
        color=color_schemes.black,
        linewidth=1,
    )
    plt.ylabel("wavenumber k")
    plt.xlabel("X (km)")

    pos = gs[6:, -1]
    ax9 = F.fig.add_subplot(pos)

    plt.title("Data Coverage (%)", loc="left")
    plt.plot(
        G_gFT_smth.x / 1e3,
        G_gFT_smth["N_per_stancil_fraction"] * 100,
        linewidth=0.8,
        color="black",
    )
    ax9.spines["left"].set_visible(False)
    ax9.spines["right"].set_visible(True)
    ax9.tick_params(labelright=True, right=True, labelleft=False, left=False)
    ax9.axhline(10, linewidth=0.8, linestyle="--", color="black")
    plt.xlabel("X (km)")

    F.save_light(path=plot_path, name=str(track_name) + "_B06_atten_ov")
    F.save_pup(path=plot_path, name=str(track_name) + "_B06_atten_ov")

    # reconstruct slope displacement data
    def fit_offset(x, data, model, nan_mask, deg):
        p_offset = np.polyfit(x[~nan_mask], data[~nan_mask] - model[~nan_mask], deg)
        p_offset[-1] = 0
        poly_offset = np.polyval(p_offset, x)
        return poly_offset

    def tanh_fitler(x, x_cutoff, sigma_g=0.01):
        """
        zdgfsg
        """

        decay = 0.5 - np.tanh((x - x_cutoff) / sigma_g) / 2
        return decay

    def reconstruct_displacement(Gx_1, Gk_1, T3, k_thresh):
        """
        reconstructs photon displacement heights for each stancil given the model parameters in Gk_1
        A low-pass frequeny filter can be applied using k-thresh

        inputs:
        Gk_1    model data per stencil from _gFT_k file with sin and cos coefficients
        Gx_1    real data per stencil from _gFT_x file with mean photon heights and coordindate systems
        T3
        k_thresh (None) threshold for low-pass filter

        returns:
        height_model  reconstucted displements heights of the stancil
        poly_offset   fitted staight line to the residual between observations and model to account for low-pass variability
        nan_mask      mask where is observed data in
        """

        dist_stencil = Gx_1.eta + Gx_1.x
        dist_stencil_lims = dist_stencil[0].data, dist_stencil[-1].data

        gFT_cos_coeff_sel = np.copy(Gk_1.gFT_cos_coeff)
        gFT_sin_coeff_sel = np.copy(Gk_1.gFT_sin_coeff)

        gFT_cos_coeff_sel = gFT_cos_coeff_sel * tanh_fitler(
            Gk_1.k, k_thresh, sigma_g=0.003
        )
        gFT_sin_coeff_sel = gFT_sin_coeff_sel * tanh_fitler(
            Gk_1.k, k_thresh, sigma_g=0.003
        )

        FT_int = gFT.generalized_Fourier(Gx_1.eta + Gx_1.x, None, Gk_1.k)
        _ = FT_int.get_H()
        FT_int.p_hat = np.concatenate(
            [-gFT_sin_coeff_sel / Gk_1.k, gFT_cos_coeff_sel / Gk_1.k]
        )

        dx = Gx.eta.diff("eta").mean().data
        height_model = FT_int.model() / dx
        dist_nanmask = np.isnan(Gx_1.y_data)
        height_data = np.interp(
            dist_stencil, T3_sel["dist"], T3_sel["heights_c_weighted_mean"]
        )
        return height_model, np.nan, dist_nanmask

    # cutting Table data
    G_height_model = dict()
    k = "gt2l"
    for bb in Gx.beam.data:
        G_height_model_temp = dict()
        for i in np.arange(Gx.x.size):
            Gx_1 = Gx.isel(x=i).sel(beam=bb)
            Gk_1 = Gk.isel(x=i).sel(beam=bb)
            k_thresh = G_gFT_smth.k_lim.isel(x=0).data

            dist_stencil = Gx_1.eta + Gx_1.x
            dist_stencil_lims = dist_stencil[0].data, dist_stencil[-1].data
            dist_stencil_lims_plot = dist_stencil_lims
            dist_stencil_lims_plot = Gx_1.eta[0] * 1 + Gx_1.x, Gx_1.eta[-1] * 1 + Gx_1.x

            T3_sel = B3[k].loc[
                (
                    (B3[k]["dist"] >= dist_stencil_lims[0])
                    & (B3[k]["dist"] <= dist_stencil_lims[1])
                )
            ]

            if T3_sel.shape[0] != 0:
                height_model, poly_offset, dist_nanmask = reconstruct_displacement(
                    Gx_1, Gk_1, T3_sel, k_thresh=k_thresh
                )
                poly_offset = poly_offset * 0
                G_height_model_temp[str(i) + bb] = xr.DataArray(
                    height_model,
                    coords=Gx_1.coords,
                    dims=Gx_1.dims,
                    name="height_model",
                )
            else:
                G_height_model_temp[str(i) + bb] = xr.DataArray(
                    Gx_1.y_model.data,
                    coords=Gx_1.coords,
                    dims=Gx_1.dims,
                    name="height_model",
                )

        G_height_model[bb] = xr.concat(G_height_model_temp.values(), dim="x").T

    Gx["height_model"] = xr.concat(G_height_model.values(), dim="beam").transpose(
        "eta", "beam", "x"
    )

    Gx_v2, B2_v2, B3_v2 = dict(), dict(), dict()
    for bb in Gx.beam.data:
        echo(bb)
        Gx_k = Gx.sel(beam=bb)
        Gh = Gx["height_model"].sel(beam=bb).T
        Gh_err = Gx_k["model_error_x"].T
        Gnans = np.isnan(Gx_k.y_model)

        concented_heights = Gh.data.reshape(Gh.data.size)
        concented_err = Gh_err.data.reshape(Gh.data.size)
        concented_nans = Gnans.data.reshape(Gnans.data.size)
        concented_x = (Gh.x + Gh.eta).data.reshape(Gh.data.size)

        dx = Gh.eta.diff("eta")[0].data
        continous_x_grid = np.arange(concented_x.min(), concented_x.max(), dx)
        continous_height_model = np.interp(
            continous_x_grid, concented_x, concented_heights
        )
        concented_err = np.interp(continous_x_grid, concented_x, concented_err)
        continous_nans = np.interp(continous_x_grid, concented_x, concented_nans) == 1

        T3 = B3[bb]
        T3 = T3.sort_values("x")
        T3 = T3.sort_values("dist")

        T3["heights_c_model"] = np.interp(
            T3["dist"], continous_x_grid, continous_height_model
        )
        T3["heights_c_model_err"] = np.interp(
            T3["dist"], continous_x_grid, concented_err
        )
        T3["heights_c_residual"] = T3["heights_c_weighted_mean"] - T3["heights_c_model"]

        B3_v2[bb] = T3
        Gx_v2[bb] = Gx_k

    try:
        G_angle = xr.open_dataset(
            load_path_angle + "/B05_" + track_name + "_angle_pdf.nc"
        )

        font_for_pres()

        Ga_abs = (
            G_angle.weighted_angle_PDF_smth.isel(angle=G_angle.angle > 0).data
            + G_angle.weighted_angle_PDF_smth.isel(angle=G_angle.angle < 0).data[
                :, ::-1
            ]
        ) / 2
        Ga_abs = xr.DataArray(
            data=Ga_abs.T,
            dims=G_angle.dims,
            coords=G_angle.isel(angle=G_angle.angle > 0).coords,
        )

        Ga_abs_front = Ga_abs.isel(x=slice(0, 3))
        Ga_best = (Ga_abs_front * Ga_abs_front.N_data).sum(
            "x"
        ) / Ga_abs_front.N_data.sum("x")

        theta = Ga_best.angle[Ga_best.argmax()].data
        theta_flag = True

        font_for_print()
        F = M.figure_axis_xy(3, 5, view_scale=0.7)

        plt.subplot(2, 1, 1)
        plt.pcolor(Ga_abs)
        plt.xlabel("abs angle")
        plt.ylabel("x")

        ax = plt.subplot(2, 1, 2)
        Ga_best.plot()
        plt.title("angle front " + str(theta * 180 / np.pi), loc="left")
        ax.axvline(theta, color="red")
        F.save_light(path=plot_path, name="B06_angle_def")
    except:
        echo("no angle data found, skip angle corretion")
        theta = 0
        theta_flag = False

    # %%
    lam_p = 2 * np.pi / Gk.k
    lam = lam_p * np.cos(theta)

    if theta_flag:
        k_corrected = 2 * np.pi / lam
        x_corrected = Gk.x * np.cos(theta)
    else:
        k_corrected = 2 * np.pi / lam * np.nan
        x_corrected = Gk.x * np.cos(theta) * np.nan

    # spectral save
    G5 = G_gFT_wmean.expand_dims(dim="beam", axis=1)
    G5.coords["beam"] = ["weighted_mean"]
    G5 = G5.assign_coords(N_photons=G5.N_photons)
    G5["N_photons"] = G5["N_photons"].expand_dims("beam")
    G5["N_per_stancil_fraction"] = G5["N_per_stancil_fraction"].expand_dims("beam")

    Gk_v2 = xr.merge([Gk, G5])

    Gk_v2 = Gk_v2.assign_coords(x_corrected=("x", x_corrected.data)).assign_coords(
        k_corrected=("k", k_corrected.data)
    )

    Gk_v2.attrs["best_guess_incident_angle"] = theta

    # save collected spectral data
    Gk_v2.to_netcdf(save_path + "/B06_" + track_name + "_gFT_k_corrected.nc")

    # save real space data
    Gx.to_netcdf(save_path + "/B06_" + track_name + "_gFT_x_corrected.nc")

    def save_table(data, tablename, save_path):
        try:
            io.save_pandas_table(data, tablename, save_path)
        except Exception as e:
            tabletoremove = save_path + tablename + ".h5"
            echo(e, f"Failed to save table. Removing {tabletoremove} and re-trying..")
            os.remove(tabletoremove)
            io.save_pandas_table(data, tablename, save_path)

    B06_ID_name = "B06_" + track_name
    table_names = [
        B06_ID_name + suffix for suffix in ["_B06_corrected_resid", "_binned_resid"]
    ]
    data = [B2_v2, B3_v2]
    for tablename, data in zip(table_names, data):
        save_table(data, tablename, save_path)

    MT.json_save(
        "B06_success",
        plot_path + "../",
        {"time": time.asctime(time.localtime(time.time()))},
    )
    echo("done. saved target at " + plot_path + "../B06_success")

step7app = makeapp(run_B06_correct_separate_var, name="threads-prior")

if __name__ == "__main__":
    step7app()
