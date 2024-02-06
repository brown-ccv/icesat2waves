#!/usr/bin/env python
"""
This file open a ICEsat2 track applied filters and corrections and returns smoothed photon heights on a regular grid in an .nc file.
This is python 3
"""

import copy
import datetime
import h5py
import time
from pathlib import Path

import numpy as np
import xarray as xr
from pprint import pprint
from scipy.ndimage import label
from threadpoolctl import threadpool_info, threadpool_limits
import matplotlib
import typer

import icesat2_tracks.ICEsat2_SI_tools.generalized_FT as gFT
import icesat2_tracks.ICEsat2_SI_tools.iotools as io
import icesat2_tracks.ICEsat2_SI_tools.spectral_estimates as spec
import icesat2_tracks.local_modules.m_general_ph3 as M
import icesat2_tracks.local_modules.m_spectrum_ph3 as spicke_remover
import icesat2_tracks.local_modules.m_tools_ph3 as MT
from icesat2_tracks.config.IceSAT2_startup import mconfig, plt

from icesat2_tracks.clitools import (
    echo,
    validate_batch_key,
    validate_output_dir,
    suppress_stdout,
    update_paths_mconfig,
    report_input_parameters,
    validate_track_name_steps_gt_1,
    makeapp,
)

import tracemalloc


matplotlib.use("Agg")  # prevent plot windows from opening

def linear_gap_fill(F, key_lead, key_int):
    """
    F pd.DataFrame
    key_lead   key in F that determined the independent coordinate
    key_int     key in F that determined the dependent data
    """
    y_g = np.array(F[key_int])

    nans, x2 = np.isnan(y_g), lambda z: z.nonzero()[0]
    y_g[nans] = np.interp(x2(nans), x2(~nans), y_g[~nans])

    return y_g


def run_B02_make_spectra_gFT(
    track_name: str = typer.Option(..., callback=validate_track_name_steps_gt_1),
    batch_key: str = typer.Option(..., callback=validate_batch_key),
    ID_flag: bool = True,
    output_dir: str = typer.Option(None, callback=validate_output_dir),
):
    """
    TODO: add docstring
    """
    with suppress_stdout():
        track_name, batch_key, _ = io.init_from_input(
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

    hemis, batch = batch_key.split("_")

    workdir, plotsdir = update_paths_mconfig(output_dir, mconfig)

    load_path = Path(workdir, batch_key, "B01_regrid")

    save_path = Path(workdir, batch_key, "B02_spectra")
    save_name = f"B02_{track_name}"

    plot_path = Path(plotsdir, hemis, batch_key, track_name, "B_spectra")
    plot_path.mkdir(parents=True, exist_ok=True)
    save_path.mkdir(parents=True, exist_ok=True)

    bad_track_path = Path(workdir, "bad_tracks", batch_key)

    all_beams = mconfig["beams"]["all_beams"]

    N_process = 4

    # open with hdf5
    Gd = h5py.File(Path(load_path) / (track_name + "_B01_binned.h5"), "r")

    # test amount of nans in the data
    nan_fraction = list()
    for k in all_beams:
        heights_c_std = io.get_beam_var_hdf_store(Gd[k], "dist")
        nan_fraction.append(np.sum(np.isnan(heights_c_std)) / heights_c_std.shape[0])

    del heights_c_std

    # test if beam pairs have bad ratio
    bad_ratio_flag = False
    for group in mconfig["beams"]["groups"]:
        Ia = Gd[group[0]]
        Ib = Gd[group[1]]
        ratio = Ia["x"][:].size / Ib["x"][:].size
        if (ratio > 10) | (ratio < 0.1):
            # print("bad data ratio ", ratio, 1 / ratio) # TODO: add logger
            bad_ratio_flag = True

    if (np.array(nan_fraction).mean() > 0.95) | bad_ratio_flag:
        print(
            "nan fraction > 95%, or bad ratio of data, pass this track, add to bad tracks"
        )
        MT.json_save(
            track_name,
            bad_track_path,
            {
                "nan_fraction": np.array(nan_fraction).mean(),
                "date": str(datetime.date.today()),
            },
        )
        print("exit.")
        exit()

    # test LS with an even grid where missing values are set to 0
    print(Gd.keys())
    Gi = Gd[list(Gd.keys())[0]]  # to select a test  beam
    dist = io.get_beam_var_hdf_store(Gd[list(Gd.keys())[0]], "dist")

    # derive spectral limits
    # Longest deserved period:
    T_max = 40  # sec
    k_0 = (2 * np.pi / T_max) ** 2 / 9.81
    x = np.array(dist).squeeze()
    dx = np.round(np.median(np.diff(x)), 1)
    min_datapoint = 2 * np.pi / k_0 / dx

    Lpoints = int(np.round(min_datapoint) * 10)
    Lmeters = Lpoints * dx

    print("L number of gridpoint:", Lpoints)
    print("L length in km:", Lmeters / 1e3)
    print("approx number windows", 2 * dist.iloc[-1] / Lmeters - 1)

    T_min = 6
    lambda_min = 9.81 * T_min**2 / (2 * np.pi)

    oversample = 2
    dlambda = Lmeters * oversample
    kk = np.arange(0, 1 / lambda_min, 1 / dlambda) * 2 * np.pi
    kk = kk[k_0 <= kk]

    print("2 M = ", kk.size * 2)

    print("define global xlims")
    dist_list = np.array([np.nan, np.nan])
    for k in all_beams:
        # print(k) # TODO: add logger
        hkey = "heights_c_weighted_mean"
        x = Gd[k + "/dist"][:]
        # print(x[0], x[-1]) # TODO: add logger
        dist_list = np.vstack([dist_list, [x[0], x[-1]]])

    xlims = np.nanmin(dist_list[:, 0]) - dx, np.nanmin(dist_list[:, 1])

    dist_lim = 2000e3  # maximum distance in the sea ice tha tis analysed:

    if (xlims[1] - xlims[0]) > dist_lim:
        xlims = xlims[0], xlims[0] + dist_lim
        print("-reduced xlims length to ", xlims[0] + dist_lim, "m")

    for k in all_beams:
        dist_i = io.get_beam_var_hdf_store(Gd[k], "dist")
        x_mask = (dist_i > xlims[0]) & (dist_i < xlims[1])
        # print(k, sum(x_mask["dist"]) / (xlims[1] - xlims[0])) # TODO: add logger

    print("-reduced frequency resolution")
    kk = kk[::2]

    print("set xlims: ", xlims)
    print(
        "Loop start:  ",
        tracemalloc.get_traced_memory()[0] / 1e6,
        tracemalloc.get_traced_memory()[1] / 1e6,
    )

    G_gFT = dict()
    G_gFT_x = dict()
    G_rar_fft = dict()
    Pars_optm = dict()

    k = all_beams[0]
    for k in all_beams:
        tracemalloc.start()
        # -------------------------------  use gridded data
        hkey = "heights_c_weighted_mean"
        Gi = io.get_beam_hdf_store(Gd[k])
        x_mask = (Gi["dist"] > xlims[0]) & (Gi["dist"] < xlims[1])
        if sum(x_mask) / (xlims[1] - xlims[0]) < 0.005:
            # print("------------------- not data in beam found; skip") # TODO: add logger
            continue

        Gd_cut = Gi[x_mask]
        x = Gd_cut["dist"]
        del Gi
        # cut data:
        x_mask = (x >= xlims[0]) & (x <= xlims[1])
        x = x[x_mask]

        dd = np.copy(Gd_cut[hkey])

        dd_error = np.copy(Gd_cut["heights_c_std"])
        dd_error[np.isnan(dd_error)] = 100
        # plt.hist(1/dd_weight, bins=40)
        F = M.figure_axis_xy(6, 3)
        plt.subplot(2, 1, 1)

        # compute slope spectra !!
        dd = np.gradient(dd)
        dd, _ = spicke_remover.spicke_remover(dd, spreed=10, verbose=False)
        dd_nans = (np.isnan(dd)) + (Gd_cut["N_photos"] <= 5)

        # using gappy data
        dd_no_nans = dd[~dd_nans]  # windowing is applied here
        x_no_nans = x[~dd_nans]
        dd_error_no_nans = dd_error[~dd_nans]

        plt.plot(
            x_no_nans, dd_no_nans, ".", color="black", markersize=1, label="slope (m/m)"
        )
        plt.legend()
        plt.show()

        with threadpool_limits(limits=N_process, user_api="blas"):
            pprint(threadpool_info())

            S = gFT.wavenumber_spectrogram_gFT(
                np.array(x_no_nans),
                np.array(dd_no_nans),
                Lmeters,
                dx,
                kk,
                data_error=dd_error_no_nans,
                ov=None,
            )
            GG, GG_x, Params = S.cal_spectrogram(
                xlims=xlims, max_nfev=8000, plot_flag=False
            )

        print(
            "after ",
            k,
            tracemalloc.get_traced_memory()[0] / 1e6,
            tracemalloc.get_traced_memory()[1] / 1e6,
        )

        plot_data_model = False
        if plot_data_model:
            for i in np.arange(0, 16, 2):
                c1 = "blue"
                c2 = "red"

                GGi = GG.isel(x=i)

                xi_1 = GG_x.x[i]
                xi_2 = GG_x.x[i + 1]

                F = M.figure_axis_xy(16, 2)
                eta = GG_x.eta

                y_model = GG_x.y_model[:, i]
                plt.plot(
                    eta + xi_1, y_model, "-", c=c1, linewidth=0.8, alpha=1, zorder=12
                )
                y_model = GG_x.y_model[:, i + 1]
                plt.plot(
                    eta + xi_2, y_model, "-", c=c2, linewidth=0.8, alpha=1, zorder=12
                )

                FT = gFT.generalized_Fourier(eta + xi_1, None, GG.k)
                _ = FT.get_H()
                FT.p_hat = np.concatenate([GGi.gFT_cos_coeff, GGi.gFT_sin_coeff])
                plt.plot(
                    eta + xi_1,
                    FT.model(),
                    "-",
                    c="orange",
                    linewidth=0.8,
                    alpha=1,
                    zorder=2,
                )

                FT = gFT.generalized_Fourier(eta + xi_2, None, GG.k)
                _ = FT.get_H()
                FT.p_hat = np.concatenate([GGi.gFT_cos_coeff, GGi.gFT_sin_coeff])
                plt.plot(
                    eta + xi_2,
                    FT.model(),
                    "-",
                    c="orange",
                    linewidth=0.8,
                    alpha=1,
                    zorder=2,
                )

                # original data
                plt.plot(x, dd, "-", c="k", linewidth=2, alpha=0.6, zorder=11)

                F.ax.axvline(xi_1 + eta[0].data, linewidth=4, color=c1, alpha=0.5)
                F.ax.axvline(xi_1 + eta[-1].data, linewidth=4, color=c1, alpha=0.5)
                F.ax.axvline(xi_2 + eta[0].data, linewidth=4, color=c2, alpha=0.5)
                F.ax.axvline(xi_2 + eta[-1].data, linewidth=4, color=c2, alpha=0.5)

                ylims = -np.nanstd(dd) * 2, np.nanstd(dd) * 2
                plt.text(
                    xi_1 + eta[0].data,
                    ylims[-1],
                    "  N="
                    + str(GG.sel(x=xi_1, method="nearest").N_per_stancil.data)
                    + " N/2M= "
                    + str(
                        GG.sel(x=xi_1, method="nearest").N_per_stancil.data
                        / 2
                        / kk.size
                    ),
                )
                plt.text(
                    xi_2 + eta[0].data,
                    ylims[-1],
                    "  N="
                    + str(GG.sel(x=xi_2, method="nearest").N_per_stancil.data)
                    + " N/2M= "
                    + str(
                        GG.sel(x=xi_2, method="nearest").N_per_stancil.data
                        / 2
                        / kk.size
                    ),
                )
                plt.xlim(xi_1 + eta[0].data * 1.2, xi_2 + eta[-1].data * 1.2)

                plt.ylim(ylims[0], ylims[-1])
                plt.show()

        S.parceval(add_attrs=True, weight_data=False)

        # assign beam coordinate
        GG.coords["beam"] = GG_x.coords["beam"] = str(k)
        GG, GG_x = GG.expand_dims(dim="beam", axis=1), GG_x.expand_dims(
            dim="beam", axis=1
        )
        # repack such that all coords are associated with beam
        GG.coords["N_per_stancil"] = (
            ("x", "beam"),
            np.expand_dims(GG["N_per_stancil"], 1),
        )
        GG.coords["spec_adjust"] = (("x", "beam"), np.expand_dims(GG["spec_adjust"], 1))

        # add more coordinates to the Dataset
        x_coord_no_gaps = linear_gap_fill(Gd_cut, "dist", "x")
        y_coord_no_gaps = linear_gap_fill(Gd_cut, "dist", "y")
        mapped_coords = spec.sub_sample_coords(
            Gd_cut["dist"],
            x_coord_no_gaps,
            y_coord_no_gaps,
            S.stancil_iter,
            map_func=None,
        )

        GG.coords["x_coord"] = GG_x.coords["x_coord"] = (
            ("x", "beam"),
            np.expand_dims(mapped_coords[:, 1], 1),
        )
        GG.coords["y_coord"] = GG_x.coords["y_coord"] = (
            ("x", "beam"),
            np.expand_dims(mapped_coords[:, 2], 1),
        )

        # if data starts with nans replace coords with nans again
        if (GG.coords["N_per_stancil"] == 0).squeeze()[0].data:
            nlabel = label((GG.coords["N_per_stancil"] == 0).squeeze())[0]
            nan_mask = nlabel == nlabel[0]
            GG.coords["x_coord"][nan_mask] = np.nan
            GG.coords["y_coord"][nan_mask] = np.nan

        lons_no_gaps = linear_gap_fill(Gd_cut, "dist", "lons")
        lats_no_gaps = linear_gap_fill(Gd_cut, "dist", "lats")
        mapped_coords = spec.sub_sample_coords(
            Gd_cut["dist"], lons_no_gaps, lats_no_gaps, S.stancil_iter, map_func=None
        )

        GG.coords["lon"] = GG_x.coords["lon"] = (
            ("x", "beam"),
            np.expand_dims(mapped_coords[:, 1], 1),
        )
        GG.coords["lat"] = GG_x.coords["lat"] = (
            ("x", "beam"),
            np.expand_dims(mapped_coords[:, 2], 1),
        )

        # calculate number data points
        def get_stancil_nans(stancil):
            x_mask = (stancil[0] < x) & (x <= stancil[-1])
            idata = Gd_cut["N_photos"][x_mask]  # noqa: F821
            return stancil[1], idata.sum()

        photon_list = np.array(
            list(dict(map(get_stancil_nans, copy.copy(S.stancil_iter))).values())
        )
        GG.coords["N_photons"] = (("x", "beam"), np.expand_dims(photon_list, 1))

        # Save to dict
        G_gFT[k] = GG
        G_gFT_x[k] = GG_x
        Pars_optm[k] = Params

        # plot
        plt.subplot(2, 1, 2)
        G_gFT_power = GG.gFT_PSD_data.squeeze()
        plt.plot(
            G_gFT_power.k,
            np.nanmean(G_gFT_power, 1),
            "gray",
            label="mean gFT power data ",
        )
        G_gFT_power = GG.gFT_PSD_model.squeeze()
        plt.plot(GG.k, np.nanmean(S.G, 1), "k", label="mean gFT power model")

        # standard FFT
        print("FFT")
        dd[dd_nans] = 0

        S = spec.wavenumber_spectrogram(x, dd, Lpoints)
        G = S.cal_spectrogram()
        S.mean_spectral_error()  # add x-mean spectral error estimate to xarray
        S.parceval(add_attrs=True)

        # assign beam coordinate
        G.coords["beam"] = str(k)
        G = G.expand_dims(dim="beam", axis=2)
        G.coords["mean_El"] = (("k", "beam"), np.expand_dims(G["mean_El"], 1))
        G.coords["mean_Eu"] = (("k", "beam"), np.expand_dims(G["mean_Eu"], 1))
        G.coords["x"] = G.coords["x"] * dx

        stancil_iter = spec.create_chunk_boundaries(int(Lpoints), dd_nans.size)

        def get_stancil_nans(stancil):
            idata = dd_nans[stancil[0] : stancil[-1]]
            return stancil[1], idata.size - idata.sum()

        N_list = np.array(list(dict(map(get_stancil_nans, stancil_iter)).values()))

        # repack such that all coords are associated with beam
        G.coords["N_per_stancil"] = (("x", "beam"), np.expand_dims(N_list, 1))

        # save to dict  and cut to the same size gFT
        try:
            G_rar_fft[k] = G.sel(x=slice(GG.x[0], GG.x[-1].data))
        except Exception:
            G_rar_fft[k] = G.isel(
                x=(GG.x[0].data < G.x.data) & (G.x.data < GG.x[-1].data)
            )

        # for plotting
        try:
            G_rar_fft_p = G.squeeze()
            plt.plot(
                G_rar_fft_p.k,
                G_rar_fft_p[:, G_rar_fft_p["N_per_stancil"] > 10].mean("x"),
                "darkblue",
                label="mean FFT",
            )
            plt.legend()
            plt.show()
        except Exception:
            print("The command G_rar_fft_p = G.squeeze() failed. Nothing to plot.")
        time.sleep(3)

    del Gd_cut
    Gd.close()

    # save fitting parameters
    MT.save_pandas_table(Pars_optm, save_name + "_params", str(save_path))

    # repack data
    def repack_attributes(DD):
        attr_dim_list = list(DD.keys())
        for k in attr_dim_list:
            for ka in list(DD[k].attrs.keys()):
                I = DD[k]
                I.coords[ka] = ("beam", np.expand_dims(I.attrs[ka], 0))
        return DD

    beams_missing = set(all_beams) - set(G_gFT.keys())

    def make_dummy_beam(GG, beam):
        dummy = GG.copy(deep=True)
        for var in list(dummy.var()):
            dummy[var] = dummy[var] * np.nan
        dummy["beam"] = [beam]
        return dummy

    for beam in beams_missing:
        GG = list(G_gFT.values())[0]
        dummy = make_dummy_beam(GG, beam)
        dummy["N_photons"] = dummy["N_photons"] * 0
        dummy["N_per_stancil"] = dummy["N_per_stancil"] * 0
        G_gFT[beam] = dummy

        GG = list(G_gFT_x.values())[0]
        G_gFT_x[beam] = make_dummy_beam(GG, beam)

        GG = list(G_rar_fft.values())[0].copy(deep=True)
        GG.data = GG.data * np.nan
        GG["beam"] = [beam]
        G_rar_fft[beam] = GG

    G_rar_fft.keys()

    G_gFT = repack_attributes(G_gFT)
    G_gFT_x = repack_attributes(G_gFT_x)
    G_rar_fft = repack_attributes(G_rar_fft)

    # save results
    G_gFT_DS = xr.merge(G_gFT.values())
    G_gFT_DS["Z_hat_imag"] = G_gFT_DS.Z_hat.imag
    G_gFT_DS["Z_hat_real"] = G_gFT_DS.Z_hat.real
    G_gFT_DS = G_gFT_DS.drop_vars("Z_hat")
    G_gFT_DS.attrs["name"] = "gFT_estimates"

    savepathname = str(save_path / save_name)
    G_gFT_DS.to_netcdf(savepathname + "_gFT_k.nc")

    G_gFT_x_DS = xr.merge(G_gFT_x.values())
    G_gFT_x_DS.attrs["name"] = "gFT_estimates_real_space"
    G_gFT_x_DS.to_netcdf(savepathname + "_gFT_x.nc")

    G_fft_DS = xr.merge(G_rar_fft.values())
    G_fft_DS.attrs["name"] = "FFT_power_spectra"
    G_fft_DS.to_netcdf(savepathname + "_FFT.nc")

    echo("saved and done")


step2app = makeapp(run_B02_make_spectra_gFT, name="makespectra")

if __name__ == "__main__":
    step2app()
