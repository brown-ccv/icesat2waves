import logging
import os
import re
import string

from scipy import signal

from matplotlib.colors import LinearSegmentedColormap
from matplotlib import dates
import datetime as DT

from . import m_tools_ph3 as MT
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.ticker as ticker
from sklearn import linear_model

_logger = logging.getLogger(__name__)

class Color:
    def __init__(self):

        self.red = (203 / 255, 32 / 255, 39 / 255)
        self.green = (15 / 255, 150 / 255, 72 / 255)
        self.orange = (247 / 255, 191 / 255, 88 / 255)
        self.grey1 = (167 / 255, 180 / 255, 183 / 255)
        self.grey = self.grey1
        self.grey2 = (123 / 255, 121 / 255, 125 / 255)
        self.grey3 = (72 / 255, 70 / 255, 77 / 255)

        self.blue1 = (18 / 255, 78 / 255, 153 / 255)
        self.blue = self.blue1
        self.blue2 = (85 / 255, 133 / 255, 196 / 255)
        self.blue3 = (129 / 255, 140 / 255, 192 / 255)
        self.blue4 = (7 / 255, 137 / 255, 198 / 255)
        self.black = (0, 0, 0)
        self.white = (1, 1, 1)

    def alpha(self, color, a):
        return (color[0], color[1], color[2], a)

    def colormaps(self, n, gamma=None):
        gamma = 1 if gamma is None else gamma
        self.whitebluered = LinearSegmentedColormap.from_list(
            "my_colormap",
            (self.white, self.blue2, self.blue1, self.red),
            N=n,
            gamma=gamma,
        )
        self.whiteblue = LinearSegmentedColormap.from_list(
            "my_colormap", (self.white, self.blue2, self.blue1), N=n, gamma=gamma
        )

    def show(self):
        for key in self.__dict__.keys():
            _logger.debug(key)


class FigureAxisXY:
    """define standart  XY Plot with reduced grafics"""

    def __init__(
        self,
        x_size=None,
        y_size=None,
        view_scale=0.5,
        size_tuple=None,
        fig_scale=1,
        container=False,
        dpi=180,
    ):

        if size_tuple is not None:
            xsize, ysize = size_tuple[0], size_tuple[1]
        else:
            xsize = x_size if x_size is not None else 8
            ysize = y_size if y_size is not None else 5


        self.label_letters = iter(f"{i}) " for i in string.ascii_lowercase)

        if container:
            self.fig = plt.figure(
                edgecolor="None",
                dpi=dpi * view_scale,
                figsize=(xsize * fig_scale, ysize * fig_scale),
                facecolor="w",
            )
        else:
            self.fig, self.ax = plt.subplots(
                num=None,
                figsize=(xsize * fig_scale, ysize * fig_scale),
                dpi=dpi * view_scale,
                facecolor="w",
                edgecolor="None",
            )

    def make_clear_weak(self):
        self.ax.spines["right"].set_color("none")
        self.ax.yaxis.tick_left()
        self.ax.spines["top"].set_color("none")
        self.ax.xaxis.tick_bottom()

    def make_clear(self):
        self.make_clear_weak()

    def make_clear_strong(self):
        self.ax.spines["right"].set_color("none")
        self.ax.spines["left"].set_color("none")
        self.ax.yaxis.tick_left()
        self.ax.spines["top"].set_color("none")
        self.ax.spines["bottom"].set_color("none")
        self.ax.xaxis.tick_bottom()

    def tight(self):
        self.fig.tight_layout()

    def label(self, x="x", y="y", t=None):
        self.ax.set_xlabel(x)
        self.ax.set_ylabel(y)
        self.ax.set_title(t, y=1.04)

    def save(self, name=None, path=None, verbose=True):
        savepath = (
            path
            if path
            else os.path.join(os.path.dirname(os.path.realpath("__file__")), "plot/")
        )
        if not os.path.exists(savepath):
            os.makedirs(savepath)
        name = name if name is not None else DT.date.today().strftime("%Y%m%d_%I%M%p")
        extension = ".pdf"
        full_name = (os.path.join(savepath, name)) + extension
        self.fig.savefig(full_name, bbox_inches="tight", format="pdf", dpi=180)
        _logger.info("save at: %s", name)

    def save_pup(self, name=None, path=None):
        name = re.sub("\.", "_", name)
        savepath = (
            path
            if path
            else os.path.join(os.path.dirname(os.path.realpath("__file__")), "plot/")
        )
        if not os.path.exists(savepath):
            os.makedirs(savepath)
        name = name if name is not None else DT.date.today().strftime("%Y%m%d_%I%M%p")
        extension = ".pdf"
        full_name = (os.path.join(savepath, name)) + extension
        self.fig.savefig(full_name, bbox_inches="tight", format="pdf", dpi=300)
        _logger.info("save at: %s", full_name)

    def save_light(self, name=None, path=None):

        savepath = (
            path
            if path is not None
            else os.path.join(os.path.dirname(os.path.realpath("__file__")), "plot/")
        )
        if not os.path.exists(savepath):
            os.makedirs(savepath)

        name = name if name is not None else DT.date.today().strftime("%Y%m%d_%I%M%p")
        extension = ".png"
        full_name = (os.path.join(savepath, name)) + extension
        self.fig.savefig(full_name, bbox_inches="tight", format="png", dpi=180)
        _logger.info("save with: %s", name)


class SubplotRoutines(FigureAxisXY):
    def __init__(self, ax):
        self.ax = ax


class PlotSprecta:
    def __init__(self, fs, Xdata, sample_unit="df", data_unit= "X"):

        self.fs = fs
        self.Xdata = Xdata
        self.sample_unit = sample_unit
        self.data_unit = data_unit

    def linear(self, Color="b", fig_scale=2, fax="f"):
        self.F = FigureAxisXY(fig_scale=fig_scale)
        if fax == "f":
            xax = self.fs
            xlabelstr = f"f ({self.sample_unit})"
        elif fax == "w":
            xax = 2 * np.pi * self.fs
            xlabelstr = f"w (rad {self.sample_unit})"

        self.line = plt.plot(xax[1:], (self.Xdata[1:]), Color=Color)

        plt.ylabel(f"|X|^2/f ({self.data_unit}^2/{self.sample_unit})")
        plt.xlabel(xlabelstr)
        plt.xlim(xax[1], xax[-1])

        self.F.make_clear()
        plt.grid()
        return self.F

    def power_linear(self, Color="b", fax="f"):
        self.F = FigureAxisXY(fig_scale=2)
        if fax == "f":
            xax = self.fs
            xlabelstr = "f  (" + self.sample_unit + ")"
        elif fax == "w":
            xax = 2 * np.pi * self.fs
            xlabelstr = "w  (rad " + self.sample_unit + ")"

        self.line = plt.plot(xax[1:], 10 * np.log10(self.Xdata[1:]), Color=Color)

        plt.ylabel(f"Power db({self.data_unit}^2/{self.sample_unit})")
        plt.xlabel(xlabelstr)
        plt.xlim(xax[1], xax[-1])
        self.F.make_clear()
        plt.grid()

    def loglog(self, Color="b", fax="f"):
        self.F = FigureAxisXY(fig_scale=2)
        if fax == "f":
            xax = self.fs
            xlabelstr = f"f ({self.sample_unit})"
        elif fax == "w":
            xax = 2 * np.pi * self.fs
            xlabelstr = f"w (rad {self.sample_unit})"

        self.line = plt.loglog(xax[1:], (self.Xdata[1:]), Color=Color)

        plt.ylabel(f"|X|^2/f ({self.data_unit}^2/{self.sample_unit})")
        plt.xlabel(xlabelstr)
        plt.xlim(xax[1], xax[-1])

        self.F.make_clear()
        plt.grid()

    def power(self, Color="b", fig_scale=2, fax="f"):
        self.F = FigureAxisXY(fig_scale=fig_scale)
        if fax == "f":
            xax = self.fs
            xlabelstr = f"f  ({self.sample_unit})"
        elif fax == "w":
            xax = 2 * np.pi * self.fs
            xlabelstr = f"w  (rad {self.sample_unit})"

        self.line = plt.semilogx(xax[1:], 10 * np.log10(self.Xdata[1:]), Color=Color)

        plt.ylabel(f"Power db({self.data_unit }^2/ {self.sample_unit} )")
        plt.xlabel(xlabelstr)
        plt.xlim(xax[1], xax[-1])
        self.F.make_clear()
        plt.grid()


class PlotPeriodogram:
    def __init__(
        self,
        time,
        fs,
        data,
        clevs=None,
        sample_unit="df",
        data_unit="X",
        ylim=None,
        time_unit="dt",
        cmap=plt.cm.ocean_r,
    ):
        self.fs = fs[1:]
        self.time = time
        self.data = data[:, 1:]
        self.clevs = clevs
        self.sample_unit = sample_unit

        self.data_unit = data_unit
        self.time_unit = time_unit

        self.cmap = cmap
        self.ylim = ylim if ylim is not None else [fs[0], fs[-1]]

    def loglog(self):
        self.F = FigureAxisXY(fig_scale=2)

        plt.loglog(self.fs[1:], (self.Xdata[1:]))

        plt.ylabel(f"|X|^2/f ({self.data_unit}^2/{self.sample_unit})")
        plt.xlabel(f"f  ({self.sample_unit})")
        plt.xlim(self.fs[1], self.fs[-1])

        self.F.make_clear()
        plt.grid()

    def linear(self):
        self.F = FigureAxisXY(10, 4, fig_scale=2)
        dd = 10 * np.log10(self.data[:-2, :]).T
        self.clevs = self.clevs if self.clevs is not None else clevels(dd)
        self.F.ax.set_yscale("log", nonposy="clip")
        tt = self.time.astype(DT.datetime)
        self.cs = plt.contourf(tt[:-2], self.fs[:], dd, self.clevs, cmap=self.cmap)
        _logger.debug("%s", self.clevs)
        plt.ylabel(f"Power db({self.data_unit}^2/{self.sample_unit})")
        plt.xlabel(f"f  ({self.sample_unit})")
        self.cbar = plt.colorbar(self.cs, pad=0.01)
        self.cbar.ax.aspect = 100
        self.cbar.outline.set_linewidth(0)
        self.cbar.set_label(f"({self.data_unit})")

        ax = plt.gca()
        ax.set_ylim(self.ylim[0], self.ylim[1])

        ax.xaxis_date()
        Month = dates.MonthLocator()
        Day = dates.DayLocator(interval=5)
        dfmt = dates.DateFormatter("%y-%b")

        ax.xaxis.set_major_locator(Month)
        ax.xaxis.set_major_formatter(dfmt)
        ax.xaxis.set_minor_locator(Day)

        # Set both ticks to be outside
        ax.tick_params(which="both", direction="out")
        ax.tick_params("both", length=6, width=1, which="major")
        ax.tick_params("both", length=3, width=1, which="minor")

        # Make grid white
        ax.grid()
        gridlines = ax.get_xgridlines() + ax.get_ygridlines()

        for line in gridlines:
            line.set_color("white")

    def power(self, anomalie=False):
        self.F = FigureAxisXY(10, 4, fig_scale=2)
        dd = 10 * np.log10(self.data[:-1, :])

        if anomalie:
            dd_tmp = dd.mean(axis=0).repeat(self.time.size - 1)
            dd = dd - dd_tmp.reshape(self.fs.size, self.time.size - 1).T
            dd = dd

        self.clevs = self.clevs if self.clevs is not None else clevels(dd)
        self.F.ax.set_yscale("log", nonposy="clip")
        tt = self.time.astype(DT.datetime)

        _logger.debug("%s %s", tt[:-1].shape, self.fs[:].shape,dd.T.shape)
        self.cs = plt.contourf(tt[:-1], self.fs[:], dd.T, self.clevs, cmap=self.cmap)
        self.x = np.arange(0, tt[:-1].size)
        _logger.debug("%s", self.clevs)
        plt.xlabel("Time")
        plt.ylabel(f"f  ({self.sample_unit})")
        self.cbar = plt.colorbar(self.cs, pad=0.01)
        self.cbar.ax.aspect = 100
        self.cbar.outline.set_linewidth(0)
        self.cbar.set_label(f"Power db({self.data_unit}^2/f )")

        ax = plt.gca()
        # Set y-lim
        ax.set_ylim(self.ylim[0], self.ylim[1])

        # format X-Axis
        ax.xaxis_date()
        Month = dates.MonthLocator()
        Day = dates.DayLocator(interval=5)
        dfmt = dates.DateFormatter("%y-%b")

        ax.xaxis.set_major_locator(Month)
        ax.xaxis.set_major_formatter(dfmt)
        ax.xaxis.set_minor_locator(Day)

        # Set both ticks to be outside
        ax.tick_params(which="both", direction="out")
        ax.tick_params("both", length=6, width=1, which="major")
        ax.tick_params("both", length=3, width=1, which="minor")

        # Make grid white
        ax.grid()
        gridlines = ax.get_xgridlines() + ax.get_ygridlines()

        for line in gridlines:
            line.set_color("white")
            line.set_linestyle("--")

    def imshow(
        self,
        shading=None,
        downscale_fac=None,
        anomalie=False,
        downscale_type=None,
        fig_size=None,
        ax=None,
        cbar=True,
    ):
        nopower = True
        self.power_imshow(
            shading,
            downscale_fac,
            anomalie,
            downscale_type,
            fig_size,
            nopower,
            ax=ax,
            cbar=cbar,
        )
        if cbar:
            self.cbar.set_label("Power (" + self.data_unit + "^2/f )")

    def power_imshow(
        self,
        shading=None,
        downscale_fac=None,
        anomalie=False,
        downscale_type=None,
        fig_size=[10, 4],
        nopower=False,
        ax=None,
        cbar=True,
    ):

        shading = "gouraud" if shading else "flat"
        if ax:
            assert type(ax) is tuple, "put ax as tuple ax=(ax,F)"
            self.F = ax[1]
            ax_local = ax[0]
        else:
            self.F = FigureAxisXY(fig_size[0], fig_size[1], fig_scale=2)
            ax_local = self.F.ax

        if nopower:
            dd = self.data
        else:
            dd = 10 * np.log10(self.data[:-1, :])

        if anomalie:
            dd_tmp = dd.mean(axis=0).repeat(self.time.size - 1)
            dd = dd - dd_tmp.reshape(self.fs.size, self.time.size - 1).T

        self.clevs = self.clevs if self.clevs is not None else clevels(dd)

        norm = colors.BoundaryNorm(boundaries=self.clevs, ncolors=256)

        tt = self.time

        ax_local.set_yscale("log", nonposy="clip")

        if downscale_fac:
            if downscale_type == "inter":
                fn = [
                    np.mean(self.fs[yr : yr + downscale_fac])
                    for yr in np.arange(0, self.fs.size, downscale_fac)
                ]
            else:

                ddn = np.empty((self.time.size - 1))
                fsn_p = gen_log_space(
                    self.fs.size, int(np.round(self.fs.size / downscale_fac))
                )
                fsn_p_run = np.append(fsn_p, fsn_p[-1])
                dd = dd.T

                for fr in np.arange(0, fsn_p.size, 1):
                    ddn = np.vstack(
                        (ddn, np.mean(dd[fsn_p_run[fr] : fsn_p_run[fr + 1], :], axis=0))
                    )

                ddn = np.delete(ddn, 0, 0)

                dd2 = ddn
                fn = self.fs[fsn_p]

                if not nopower:
                    tt = tt[:-1]

        else:
            if not nopower:
                tt = tt[:-1]

            dd2 = dd.T
            fn = self.fs

        if isinstance(tt[0], np.datetime64):
            _logger.debug('time axis is numpy.datetime64, converted to number for plotting')
            ttt = dates.date2num(tt.astype(DT.datetime))

        elif isinstance(tt[0], np.timedelta64):
            _logger.debug('time axis is numpy.timedelta64, converted to number for plotting')
            ttt = tt
        else:
            _logger.debug('time axis is not converted')
            ttt = tt

        MT.stats_format(dd2)
        self.cs = plt.pcolormesh(
            ttt, fn, dd2, cmap=self.cmap, norm=norm, shading=shading
        )
        plt.ylabel(("f  (" + self.sample_unit + ")"))
        if cbar:
            self.cbar = plt.colorbar(self.cs, pad=0.01)
            self.cbar.ax.aspect = 100
            self.cbar.outline.set_linewidth(0)
            self.cbar.set_label("Power db(" + self.data_unit + "^2/f ")

        ax = ax_local
        if isinstance(tt[0], np.datetime64):
            plt.xlabel("Time")
            # Set y-lim
            ax.set_ylim(self.ylim[0], self.ylim[1])
            ax.set_xlim(ttt[0], ttt[-1])

            # format X-Axis
            Month = dates.MonthLocator()
            Day = dates.DayLocator(interval=5)
            dfmt = dates.DateFormatter("%b/%y")

            ax.xaxis.set_major_locator(Month)
            ax.xaxis.set_major_formatter(dfmt)
            ax.xaxis.set_minor_locator(Day)
        elif isinstance(tt[0], np.float64):
            plt.xlabel("Time")
            # Set y-lim
            ax.set_ylim(self.ylim[0], self.ylim[1])
            ax.set_xlim(ttt[0], ttt[-1])

            # format X-Axis
            Month = dates.MonthLocator()
            Day = dates.DayLocator(interval=5)
            dfmt = dates.DateFormatter("%b/%y")

            ax.xaxis.set_major_locator(Month)
            ax.xaxis.set_major_formatter(dfmt)
            ax.xaxis.set_minor_locator(Day)
        else:
            plt.xlabel(f"Time ({self.time_unit})")
            ax.set_ylim(self.ylim[0], self.ylim[1])
            ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
            ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

        # Set both ticks to be outside
        ax.tick_params(which="both", direction="out")
        ax.tick_params("both", length=6, width=1, which="major")
        ax.tick_params("both", length=3, width=1, which="minor")

        # Make grid white
        ax.grid()
        self.ax = ax
        gridlines = ax.get_xgridlines() + ax.get_ygridlines()

        for line in gridlines:
            line.set_color("white")

        self.x = ttt

    def linear_imshow(
        self,
        shading=None,
        downscale_fac=None,
        anomalie=False,
        downscale_type=None,
        fig_size=[10, 4],
        nopower=False,
        ax=None,
    ):

        shading = "gouraud" if shading else "flat"
        if ax:
            assert type(ax) is tuple, "put ax as tuple ax=(ax,F)"
            self.F = ax[1]
            ax_local = ax[0]
        else:
            self.F = FigureAxisXY(fig_size[0], fig_size[1], fig_scale=2)
            ax_local = self.F.ax

        if nopower:
            dd = self.data
        else:
            dd = 10 * np.log10(self.data[:-1, :])

        if anomalie:
            dd_tmp = dd.mean(axis=0).repeat(self.time.size - 1)
            dd = dd - dd_tmp.reshape(self.fs.size, self.time.size - 1).T

        self.clevs = self.clevs if self.clevs is not None else clevels(dd)

        norm = colors.BoundaryNorm(boundaries=self.clevs, ncolors=256)

        tt = self.time

        self.F.ax.set_yscale("log", nonposy="clip")

        if downscale_fac is not None:
            if downscale_type == "inter":
                fn = []
                for yr in np.arange(0, self.fs.size, downscale_fac):
                    fn.append(np.mean(self.fs[yr : yr + downscale_fac]))
            else:

                ddn = np.empty((self.time.size - 1))
                fsn_p = gen_log_space(
                    self.fs.size, int(np.round(self.fs.size / downscale_fac))
                )
                fsn_p_run = np.append(fsn_p, fsn_p[-1])
                dd = dd.T

                for fr in np.arange(0, fsn_p.size, 1):
                    ddn = np.vstack(
                        (ddn, np.mean(dd[fsn_p_run[fr] : fsn_p_run[fr + 1], :], axis=0))
                    )

                ddn = np.delete(ddn, 0, 0)

                dd2 = ddn
                fn = self.fs[fsn_p]

                if nopower:
                    tt = tt
                else:
                    tt = tt[:-1]

        else:
            if not nopower:
                tt = tt[:-1]

            dd2 = dd.T
            fn = self.fs

        if isinstance(tt[0], np.datetime64):
            _logger.debug('numpy.datetime64')
            ttt = dates.date2num(tt.astype(DT.datetime))

        elif isinstance(tt[0], np.timedelta64):
            _logger.debug('numpy.timedelta64')
            ttt = tt
        else:
            _logger.debug('something else')
            ttt = tt

        self.cs = plt.pcolormesh(
            ttt, fn, dd2, cmap=self.cmap, norm=norm, shading=shading
        )

        plt.ylabel(("f  (" + self.sample_unit + ")"))
        self.cbar = plt.colorbar(self.cs, pad=0.01)
        self.cbar.ax.aspect = 100
        self.cbar.outline.set_linewidth(0)
        self.cbar.set_label("Power db(" + self.data_unit + "^2/f ")

        ax = plt.gca()
        if isinstance(tt[0], np.datetime64):
            plt.xlabel("Time")
            # Set y-lim
            ax.set_ylim(self.ylim[0], self.ylim[1])
            ax.set_xlim(ttt[0], ttt[-1])

            # format X-Axis
            Month = dates.MonthLocator()
            Day = dates.DayLocator(interval=5)
            dfmt = dates.DateFormatter("%b/%y")

            ax.xaxis.set_major_locator(Month)
            ax.xaxis.set_major_formatter(dfmt)
            ax.xaxis.set_minor_locator(Day)
        else:
            plt.xlabel("Time (" + self.time_unit + ")")
            ax.set_ylim(self.ylim[0], self.ylim[1])
            ax.xaxis.set_major_locator(ticker.MultipleLocator(5))
            ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))

        # Set both ticks to be outside
        ax.tick_params(which="both", direction="out")
        ax.tick_params("both", length=6, width=1, which="major")
        ax.tick_params("both", length=3, width=1, which="minor")

        # Make grid white
        ax.grid()
        self.ax = ax
        gridlines = ax.get_xgridlines() + ax.get_ygridlines()

        for line in gridlines:
            line.set_color("white")

        self.x = np.arange(0, ttt.size + 1)

    def set_xaxis_to_days(self, **kwargs):
        set_timeaxis_days(self.ax, **kwargs)


class PlotPolarspectra:
    def __init__(
        self, f, thetas, data, unit="X", data_type="fraction", lims=None, verbose=False
    ):

        self.f = f
        self.data = data
        self.thetas = thetas

        self.unit = unit

        # decided on freq limit
        lims = [self.f.min(), self.f.max()] if lims is None else lims
        self.lims = 1.0 / lims[1], 1.0 / lims[0]

        freq_sel_bool = cut_nparray(self.f, lims[0], lims[1])

        self.min = np.nanmin(data[freq_sel_bool, :])
        self.max = np.nanmax(data[freq_sel_bool, :])
        if verbose:
            _logger.debug(str(self.min), str(self.max))

        self.ylabels = np.arange(10, 100, 20)
        self.data_type = data_type
        if data_type == "fraction":
            self.clevs = np.linspace(0.01, self.max * 0.5, 21)
        elif data_type == "energy":
            self.ctrs_min = self.min + self.min * 0.05
            self.clevs = np.linspace(self.min + self.min * 0.05, self.max * 0.60, 21)

    def linear(self, radial_axis="period", circles=None, ax=None, fontsize=10):

        if ax is None:
            ax = plt.subplot(111, polar=True)
            self.title = plt.suptitle(
                "  Polar Spectrum", y=0.95, x=0.5, horizontalalignment="center"
            )


        # left turned postive
        ax.set_theta_direction(-1)
        ax.set_theta_zero_location("N")

        ax.set_yticks(self.ylabels)
        ax.set_yticklabels(f" {y} s" for y in self.ylabels)

        ## Set titles and colorbar
        grid = ax.grid(color="k", alpha=0.5, linestyle="--", linewidth=0.5)

        if self.data_type == "fraction":
            cm = plt.cm.RdYlBu_r
            colorax = ax.contourf(
                self.thetas, 1 / self.f, self.data, self.clevs, cmap=cm, zorder=1
            )
        elif self.data_type == "energy":
            cm = plt.cm.Paired
            cm.set_under = "w"
            cm.set_bad = "w"
            colorax = ax.contourf(
                self.thetas, 1 / self.f, self.data, self.clevs, cmap=cm, zorder=1
            )

        if circles is not None:
            theta = np.linspace(0, 2 * np.pi, 360)
            r1 = theta * 0 + circles[0]
            r2 = theta * 0 + circles[1]
            plt.plot(theta, r1, c="red", alpha=0.6, linewidth=1, zorder=10)
            plt.plot(theta, r2, c="red", alpha=0.6, linewidth=1, zorder=10)

        cbar = plt.colorbar(colorax, fraction=0.046, pad=0.06, orientation="horizontal")
        if self.data_type == "fraction":
            cbar.set_label("Fraction of Energy", rotation=0)
        elif self.data_type == "energy":
            cbar.set_label(f"Energy Density ({self.unit})", rotation=0)
        cbar.ax.get_yaxis().labelpad = 30
        cbar.outline.set_visible(False)

        degrange = range(0, 360, 30)

        lines, labels = plt.thetagrids(degrange, labels=None)

        for line in lines:
            line.set_linewidth(5)

        ax.set_ylim(self.lims)
        ax.spines["polar"].set_color("none")
        ax.set_rlabel_position(87)
        self.ax = ax


def plot_scatter_2d(intersect_chain, slope_chain, xname="intersect", yname="slope"):

    col.colormaps(20)
    xbins = np.linspace(
        intersect_chain.quantile(0.025), intersect_chain.quantile(0.975), 30
    )
    xlim = (xbins[0], xbins[-1])
    ybins = np.linspace(slope_chain.quantile(0.025), slope_chain.quantile(0.975), 30)
    ylim = (ybins[0], ybins[-1])

    S1 = plt.subplot2grid((3, 3), (0, 0), facecolor="white", colspan=1, rowspan=2)

    H = plt.hist(slope_chain, ybins, orientation="horizontal")
    plt.gca().invert_xaxis()
    plt.ylabel(yname)
    S2 = plt.subplot2grid((3, 3), (0, 1), facecolor="white", colspan=2, rowspan=2)
    H = plt.hist2d(
        list(intersect_chain),
        list(slope_chain),
        bins=(xbins, ybins),
        norm=colors.LogNorm(),
        cmap=col.white_base_bluegreen,
    )

    S2 = plt.subplot2grid((3, 3), (2, 1), facecolor="white", colspan=2, rowspan=1)
    H = plt.hist(intersect_chain, xbins)
    plt.xlabel(xname)


def set_timeaxis_days(ax, int1=1, int2=2, bymonthday=range(1, 32)):
    # int1 interval of the major (labeld) days
    # int2 intercal of the minor (only ticks) days

    Month = dates.MonthLocator()
    Month_dfmt = dates.DateFormatter("%b/%y")
    Day = dates.DayLocator(interval=int2, bymonthday=bymonthday)
    Day_dfmt = dates.DateFormatter("%d")
    Day2 = dates.DayLocator(interval=int1, bymonthday=bymonthday)
    Day2_dfmt = dates.DateFormatter("")

    ax.xaxis.set_major_locator(Day)
    ax.xaxis.set_major_formatter(Day_dfmt)
    ax.xaxis.set_minor_locator(Day2)
    ax.xaxis.set_minor_formatter(Day2_dfmt)


def log_power(data):
    return 10 * np.log10(data)


def echo_dt(a, as_string=False):
    string = (
        str(a.astype("timedelta64[s]"))
        + "/"
        + str(a.astype("timedelta64[m]"))
        + "/"
        + str(a.astype("timedelta64[h]"))
        + "/"
        + str(a.astype("timedelta64[D]"))
    )
    if as_string:
        return string
    else:
        _logger.debug(string)


def easy_dtstr(a):
    if a.astype("timedelta64[s]") < np.timedelta64(60, "s"):
        return str(a.astype("timedelta64[s]"))
    elif a.astype("timedelta64[m]") < np.timedelta64(60, "m"):
        return str(a.astype("timedelta64[m]"))
    elif a.astype("timedelta64[h]") < np.timedelta64(24, "h"):
        return str(a.astype("timedelta64[h]"))
    elif a.astype("timedelta64[D]") < np.timedelta64(365, "D"):
        return str(a.astype("timedelta64[D]"))
    elif a.astype("timedelta64[M]") < np.timedelta64(24, "M"):
        return str(a.astype("timedelta64[M]"))
    else:
        return str(a.astype("timedelta64[Y]"))


def clevels(data, dstep=21, symmetric=False):
    mmax = np.ceil(np.nanmax(data))
    mmin = np.floor(np.nanmin(data))

    if symmetric:
        tmax = np.max([mmax, -mmin])
        clim = np.linspace(-tmax, tmax, dstep)
    else:
        clim = np.linspace(mmin, mmax, dstep)

    return clim


def save_anyfig(fig, name=None, path=None):

    savepath = (
        path
        if path is not None
        else os.path.join(os.path.dirname(os.path.realpath("__file__")), "plot/")
    )
    if not os.path.exists(savepath):
        os.makedirs(savepath)
    name = name if name is not None else datetime.date.today().strftime("%Y%m%d_%I%M%p")

    extension = ".png"
    full_name = (os.path.join(savepath, name)) + extension
    fig.savefig(full_name, bbox_inches="tight", format="png", dpi=180)
    _logger.debug('save at: %s',full_name)


def read_cdo(file):
    cdo = Cdo()
    G = cdo.readCdf(file).variables
    _logger.debug(G.keys())
    return G


def build_timestamp(time, unit, start, verbose=True):
    timestamp = np.datetime64(start) + time[:].astype("m8[" + unit + "]")
    if verbose:
        _logger.debug(timestamp)
    return timestamp


def build_timestamp_v2(time, unit, start, verbose=True):
    timestamp = np.datetime64(start) + time[:].astype("datetime64[s]")
    if verbose:
        _logger.debug(timestamp)
    return timestamp


def cut_nparray(var, low, high, verbose=False):
    if low < high:
        if low < var[0]:
            if verbose:
                _logger.debug("out of lower limit!")
        if high > var[-1]:
            if verbose:
                _logger.debug('out of upper limit!')
                _logger.debug("%s > %s", high, var[-1])
        return (var >= low) & (var <= high)

    elif high < low:
        if high < var[0]:
            _logger.debug("limits flipped, out of lower limit!")
        if low > var[-1]:
            _logger.debug("limits flipped, out of lower limit!")

        return (var >= high) & (var <= low)

    elif high == low:
        if verbose:
            _logger.debug("find nearest")
        a = var - low
        return np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))

    else:
        _logger.debug("error")
        return


def boxmean(data, lon, lat, xlim, ylim):
    xs = lon.shape
    ys = lat.shape

    xp = data.shape.index(xs[0])
    yp = data.shape.index(ys[0])
    if xlim[0] <= xlim[1]:
        xbool = (lon >= xlim[0]) & (lon <= xlim[1])
    else:
        xbool = (lon >= xlim[1]) & (lon <= xlim[0])

    if ylim[0] <= ylim[1]:
        ybool = (lat >= ylim[0]) & (lat <= ylim[1])
    else:
        ybool = (lat >= ylim[1]) & (lat <= ylim[0])

    match (xp, yp):
        case (0, 1):
            datan = data[xbool, :, :][:, ybool, :].mean()
        case (0, 2):
            datan = data[xbool, :, :][:, :, ybool]
        case (1, 0):
            datan = data[:, xbool, :][ybool, :, :]
        case (1, 2):
            datan = data[:, xbool, :][:, :, ybool]
        case (2, 0):
            datan = data[:, :, xbool][ybool, :, :]
        case (2, 1):
            datan = data[:, :, xbool][:, ybool, :]
        case _:
            _logger.debug('arrays have not the same shape')


    _logger.debug("new shape %s", datan.shape)

    return np.nanmean(np.nanmean(datan, axis=xp), axis=yp).squeeze()


def detrend(data, od=None, x=None, plot=False, verbose=False):
    # data  data that should be detrended
    # od order of polynomial
    # x  optional xaxis, otherwise equal distance is assument
    # plot True for plot
    od = 0 if od is None else od

    if od == 0:
        d_detrend = data - np.nanmean(data)
        d_org = []
        dline = []

    elif od > 0:
        if verbose:
            _logger.debug("assume data is equal dist. You can define option x= if not.")

        d_org = data - np.nanmean(data)
        x = np.arange(0, d_org.size, 1) if x is None else x

        idx = np.isfinite(x) & np.isfinite(d_org)
        px = np.polyfit(x[idx], d_org[idx], od)
        dline = np.polyval(px, x)
        d_detrend = d_org - dline

    if plot:
        F = FigureAxisXY(15, 5)
        if od > 0:
            plt.plot(d_org, Color="black")
            plt.plot(dline, Color="black")
        plt.plot(d_detrend, Color="r")
        F.make_clear()
        plt.grid()
        plt.legend(["org", "line", "normalized"])

    stats = dict()
    stats["org"] = d_org
    stats["std"] = np.nanstd(d_detrend)
    if od > 0:
        stats["line"] = dline
        stats["polynom order"] = od
        stats["polyvals"] = px
    if verbose:
        _logger.debug(stats)
    return d_detrend / np.nanstd(d_detrend), stats


def normalize(data):
    return detrend(data)[0]


def nannormalize(data):
    return (data - np.nanmean(data)) / np.nanstd(data)


def runningvar(var, m, tailcopy=False):
    m = int(m)
    s = var.shape
    if s[0] <= 2 * m:
        _logger.debug("0 Dimension is smaller then averaging length")
        return
    rr = np.asarray(var) * np.nan
    var_range = np.arange(m, int(s[0]) - m - 1, 1)

    for i in var_range[np.isfinite(var[m : int(s[0]) - m - 1])]:
        rr[int(i)] = np.nanvar(var[i - m : i + m])

    if tailcopy:
        rr[0:m] = rr[m + 1]
        rr[-m - 1 : -1] = rr[-m - 2]
    return rr


def runningstd(var, m, tailcopy=False):
    return np.sqrt(runningvar(var, m, tailcopy=tailcopy))


def runningmean_wrap_around(var, m):
    m = int(m)
    s = var.shape
    if s[0] <= 2 * m:
        _logger.debug("0 Dimension is smaller then averaging length")
        return

    rr = np.asarray(var) * np.nan
    var_range = np.arange(var.size)

    for i in var_range:
        rr[int(i)] = np.nanmean(var.take(range(i - m, i + m), mode="wrap"))

    return rr


def runningmean(var, m, tailcopy=False):
    m = int(m)
    s = var.shape
    if s[0] <= 2 * m:
        _logger.debug("0 Dimension is smaller then averaging length")
        return
    rr = np.asarray(var) * np.nan
    var_range = np.arange(m, int(s[0]) - m - 1, 1)

    for i in var_range[np.isfinite(var[m : int(s[0]) - m - 1])]:
        rr[int(i)] = np.nanmean(var[i - m : i + m])

    if tailcopy:
        rr[0:m] = rr[m + 1]
        rr[-m - 1 : -1] = rr[-m - 2]

    return rr


def find_max_ts(
    data_org,
    threshold=None,
    jump=None,
    smooth=True,
    spreed=None,
    plot=False,
    nocopy=False,
    verbose=True,
):
    """
    This function finds local minima in a 1-dimensional array by asking where the gradient of the data changes sign

    input:
        data_org    data array, like a time series or so. (even or uneven distributed?)

        threshold   (None) Only concider data above a threshold
        jump        (None) minimal distance in data points two minima are allowed to be appart .
        smooth      (True) if True smoothing the time series using a running mean
            spreed      (None) the with of the running mean. If None its set to 2 data point.

        plot        (False) if True it plots somethinhe (not implemented jet)
        nocopy      if True, the time series is not coyed and altered in this function (be cause python is updatedingh links)

        verbose     prints statements if True

    returns:
        jump is None:       tuple with  (index, data, data[index])
                index           index points of maxima,
                data            the modified 1d data array
                data[index]     values of the maxima points

        jump is not None:   tuple with  (index_reduced, data, data[index], index)
                index_reduced   index points of maxima according to jump condition
                data            the modified 1d data array
                data[index]     values of the maxima points
                index           all indexes without the jump condition

    """
    if nocopy:
        data = data_org
    else:
        data = np.copy(data_org)
    spreed = 2 if spreed is None else spreed

    if smooth:
        data = runningmean(data, spreed)

    if threshold is not None and threshold > np.nanmin(data):
        data[np.isnan(data)] = 0
        data[data < threshold] = 0
    else:
        data[np.isnan(data)] = 0

    index = np.where(np.diff(np.sign(np.gradient(data))) == -2)[0] + 1

    if index.size == 0:
        index = np.where(data == data.max())[0]

    index2 = list()
    for i in index:

        adjustment = data[i - 1 : i + 2].argmax() - 1
        if adjustment != 0:
            index2.append(i + data[i - 1 : i + 2].argmax() - 1)
        else:
            index2.append(i)

    index = index2

    if jump is None:
        if verbose:
            _logger.debug("index, data, edit ts (index)")
        return index, data, data[index]
    else:
        c = np.diff(index)
        b = []
        i = 0
        while i < index.size - 1:
            if c[i] < jump:
                if i >= index.size - 2:
                    nc = 1
                elif sum(c[i:] >= jump) == 0:
                    nc = c[i:].size
                else:
                    nc = np.nonzero(c[i:] >= jump)[0][0]
                b = np.append(b, np.round(np.mean(index[i : i + nc + 1]))).astype(int)
                i = i + nc + 1
            else:
                b = np.append(b, index[i]).astype(int)
                i = i + 1
        if verbose:
            _logger.debug("index, edited ts, edit ts (index), org_index")

        return b, data, data[b], index


def spickes_to_nan(ts, nloop=None, spreed=1):
    nloop = 0 if nloop is None else nloop
    i = 0
    while i <= nloop:
        ts.max()
        pa = np.where(ts == np.nanmax(ts))[0][0]
        ts[pa - spreed : pa + spreed] = np.NaN
        i = i + 1
    return ts


def spickes_to_mean(ts, nloop=None, spreed=1, gaussian=True):
    nloop = 0 if nloop is None else nloop
    i = 0
    tsmean = ts.mean()
    b = 2 * spreed
    gaus = signal.gaussian(b, std=b / 10)
    while i <= nloop:
        tsabs = np.abs(ts)
        tmax = np.nanmax(tsabs)
        pa = np.where(tsabs == tmax)[0][0]

        if gaussian:
            tsm = np.mean([ts[pa - spreed], ts[pa + spreed]])
            le = int(pa - spreed)
            ue = int(pa + spreed)

            ts[le:ue] = ts[le:ue] - gaus * (tmax - tsm)
        else:
            if pa + spreed > len(ts):
                le = int(pa - spreed)
                ts[le:-1] = np.linspace(ts[le], ts[-1], len(ts[le:-1]))
            else:
                le = int(pa - spreed)
                ue = int(pa + spreed)
                ts[le:ue] = np.linspace(ts[le], ts[ue], len(ts[le:ue]))

        i = i + 1
    return ts


## Composites


class CompositeData:
    def __init__(self, var, index_weight=None):
        self.composites = var
        self.comp_mean = np.nanmean(var, axis=0)
        self.comp_std = np.nanstd(var, axis=0)
        if var.shape[0] != 1:
            self.comp_norm = self.comp_mean / self.comp_std
        self.comp_sum = np.nansum(var, axis=0)
        if index_weight is not None:
            self.weight(index_weight)

    def weight(self, index_weight):
        length = self.comp_mean.size
        weight_mat = (
            np.repeat(index_weight, length).reshape((self.composites.shape))
            / index_weight.mean()
        )
        self.comp_weighted_mean = np.nanmean(self.composites * weight_mat, axis=0)
        self.comp_weighted_norm = self.comp_weighted_mean / np.nanstd(
            self.comp_weighted_mean, axis=0
        )

    def bootstrap(
        self,
        ci=[2.5, 50, 97.5],
        reps=1000,
    ):
        # bootstrap MC integration
        reps = 1000
        xb = np.random.choice(x, (n, reps), replace=True)
        yb = 1 / np.arange(1, n + 1)[:, None] * np.cumsum(xb, axis=0)
        upper, lower = np.percentile(yb, [2.5, 97.5], axis=1)


class CompIter:
    def __init__(self, span, dt=None, unit="h"):
        self.span = list(span)
        for s in self.span:
            assert type(s) is int, "span is not an integrer!"

        self.length = self.span[1] -self.span[0]
        self.loop_iter = np.arange(0, self.length, 1)
        self.index_iter = np.arange(self.span[0], self.span[1], 1)
        if dt:
            self.dt = dt
            self.time_iter = self.index_iter * dt
            time_str = []
            time_iter_axis = []
            for p in self.loop_iter:
                time_str = np.append(
                    time_str, str(self.time_iter[p].astype("timedelta64[" + unit + "]"))
                )

            self.time_iter_string = time_str


class Composite:
    def __init__(self, index, time=None, weigthing=False, span=None):
        """Initial Class for bulding composite based on:
            index       position in the time vector 'time'
            time        np.array of datetime64 times
        optional:
            weighting   amplitude of the indexes for weighted composties (default=false)
            span        lead lag composite in units of timesteps in time (default=None)
        """
        self.index = index
        self.iter_operate = None
        span = 0 if span is None else span
        self.span = [0, span] if type(span) == int else span

        self.weigthing = weigthing if weigthing is not False else None
        self.comp = dict()
        if time is None:
            _logger.debug(
                "timeaxis is not defined. Make sure that both timeseries have the same timestamp"
            )
            self.time_index = None
        else:
            self.time_index = time
            self.dtstamp = MT.dt_form_timestamp(self.time_index)

    def build_iter(self, dt=None, dt_unit=None):
        self.iter = CompIter(self.span, dt=dt, unit=dt_unit)
        self.iter_operate = (
            self.iter if self.iter_operate is None else self.iter_operate
        )

    def corse_iter(self, dt, unit=None):
        """build intereration aaxis and timestamps for corser resoltions"""

        assert unit == self.iter.unit, (
            "span units do not match! old unit=" + self.iter.unit + ", new unit=" + unit
        )

        span = []
        dt_format = (
            np.timedelta64(self.iter.dt, self.iter.unit)
            .astype("timedelta64[" + unit + "]")
            .astype("float")
        )
        span_new = np.array(self.span) * dt_format / dt
        _logger.debug('old span= %s',self.span)
        _logger.debug('new span= %s',span_new )

        for s in span_new:
            span.append(int(np.floor(s)))

        _logger.debug(span)
        self.iter2 = CompIter(span, dt, unit=unit)

    def iter_info(self):
        self.iter_operate.__dict__

        _logger.debug("available iters")
        if self.iter is not None:
            _logger.debug("self.iter")
            self.iter.__dict__
        if self.iter2 is not None:
            _logger.debug("self.iter2")
            self.iter2.__dict__

    def info(self):
        _logger.debug("index %s", self.index)
        _logger.debug("span %s", self.span)
        _logger.debug("weight %s", self.weigthing)
        _logger.debug("comp %s", self.comp.keys())

    def transform_index_time(self, time_index, time_composite):
        """find nearest time index of compostite time compared to index times"""
        index_composite = []
        for i in self.index:
            t_diff = time_index[i] - time_composite
            nindex = np.unravel_index(np.abs(t_diff).argmin(), t_diff.shape)
            index_composite = np.append(index_composite, nindex)
        return index_composite.astype(int)

    def compose_ts(self, ts, name, time=None):
        if time is not None:
            if self.time_index is None:
                _logger.debug("timeaxis of index TS is not defined!")
                return
            else:
                iindex = self.transform_index_time(self.time_index, time)
        else:
            iindex = self.index

        span = self.iter_operate.span
        _logger.debug(iindex)
        if self.span != [0, 0]:
            comp = np.empty((-span[0] + span[1]))
            self.length = comp.size

            for i in iindex:
                if i + span[0] < 0:
                    _logger.debug('i: %s span: %s %s', i, span[0], span[1])
                    _logger.debug('left postion: %s', i+span[0])
                    raise ValueError("composite span exceeds ts limits")

                    return -1
                elif i + span[1] > ts.size:
                    return -1
                    _logger.debug(i, span[0], span[1])
                    _logger.debug('i: %s span: %s %s', i, span[0], span[1])
                    _logger.debug('right postion: %s',i+span[1])
                    raise ValueError("composite span exceeds ts limits")
                    return -1

                _logger.debug('comp %s', comp.shape)
                _logger.debug('ts %s', ts[i + span[0]:i + span[1]].shape)
                _logger.debug("%s %s %s", i, span[0], span[1])
                comp = np.vstack((comp, ts[i + span[0]:i + span[1]]))

            comp = np.delete(comp, 0, 0)
            comp1 = CompositeData(comp, self.weigthing)
            self.comp[name] = comp1
        else:
            comp1 = CompositeData(ts[iindex], self.weigthing)
            self.comp[name] = comp1

    def compose_2d(self, field, name, time=None):
        if time is not None:
            if self.time_index is None:
                _logger.debug("timeaxis of index TS is not defined!")
                return
            else:
                iindex = self.transform_index_time(self.time_index, time)
        else:
            iindex = self.index
        span = self.iter_operate.span

        if span != [0, 0]:
            _logger.debug("%s %s", -span[0]+span[1],field.shape[1])
            comp = np.empty((-span[0] + span[1], field.shape[1])) * np.NaN
            self.length = -span[0] + span[1]
            for i in iindex:
                if i + span[1] > field.shape[0]:
                    ff = field[i + span[0] : field.shape[0], :]
                    cc = np.empty((-span[0] + span[1], field.shape[1])) * np.NaN
                    cc[0 : ff.shape[0], :] = ff
                    comp = np.vstack((comp, cc))
                elif i + span[0] < 0:
                    ff = field[0 : i + span[1], :]
                    cc = np.empty((-span[0] + span[1], field.shape[1])) * np.NaN
                    cc[-ff.shape[0] - 1 : -1, :] = ff
                    comp = np.vstack((comp, cc))
                else:
                    comp = np.vstack((comp, field[i + span[0] : i + span[1], :]))

            comp = comp.reshape(iindex.size + 1, self.length, field.shape[1])
            comp = np.delete(comp, 0, 0)
            comp1 = CompositeData(comp, self.weigthing)
            self.comp[name] = comp1
        else:
            _logger.debug('no span defined')
            comp = field[iindex, :]

            comp1 = CompositeData(comp, self.weigthing)
            self.comp[name] = comp1

    def compose_field(self, field, name, time=None):
        if time is not None:
            if self.time_index is None:
                _logger.debug("timeaxis of index TS is not defined!")
                return
            else:
                iindex = self.transform_index_time(self.time_index, time)
        else:
            iindex = self.index

        span = self.iter_operate.span

        if span != [0, 0]:
            comp = (
                np.empty((-span[0] + span[1], field.shape[1], field.shape[2])) * np.NaN
            )
            self.length = -span[0] + span[1]
            for i in iindex:
                comp = np.vstack((comp, field[i + span[0] : i + span[1], :, :]))

            comp = comp.reshape(
                iindex.size + 1, self.length, field.shape[1], field.shape[2]
            )
            comp = np.delete(comp, 0, 0)

            comp1 = CompositeData(comp, self.weigthing)
            self.comp[name] = comp1
        else:
            _logger.debug("no span defined")
            comp = field[iindex, :, :]

            comp1 = CompositeData(comp, self.weigthing)
            self.comp[name] = comp1


def time_overlap(time1, time2):

    if (time1[0] - time2[0]).astype(int) > 0:
        start = time1[0]
    else:
        start = time2[0]

    if (time1[-1] - time2[-1]).astype(int) > 0:
        end = time2[-1]
    else:
        end = time1[-1]

    timearray = time1
    dt_data = time1[1] - time1[0]
    timecut1 = [timearray >= start]
    timecut2 = [timearray <= (end)]
    timecutA = [timecut1 & timecut2 for timecut1, timecut2 in zip(timecut1, timecut2)]

    timearray = time2
    dt_data = time2[1] - time2[0]
    timecut1 = [timearray >= start]
    timecut2 = [timearray <= (end)]
    timecutB = [timecut1 & timecut2 for timecut1, timecut2 in zip(timecut1, timecut2)]

    return timecutA[0], timecutB[0]


def gen_log_space(limit, n):
    result = [1]
    if n > 1:  # just a check to avoid ZeroDivisionError
        ratio = (float(limit) / result[-1]) ** (1.0 / (n - len(result)))
    while len(result) < n:
        next_value = result[-1] * ratio
        if next_value - result[-1] >= 1:
            # safe zone. next_value will be a different integer
            result.append(next_value)
        else:
            # problem! same integer. we need to find next_value by artificially incrementing previous value
            result.append(result[-1] + 1)
            # recalculate the ratio so that the remaining values will scale correctly
            ratio = (float(limit) / result[-1]) ** (1.0 / (n - len(result)))
    # round, re-adjust to 0 indexing (i.e. minus 1) and return np.uint64 array
    return np.asarray(list(map(lambda x: round(x) - 1, result)), dtype=np.uint64)


def linefit2Points(time_lin, f, data, f1, f2, f_delta=None, plot=False):
    if isinstance(time_lin[0], np.datetime64):
        _logger.debug('type is numpy.datetime64, shape %s', time_lin.shape)
        time_lin = time_lin.astype("m8[s]").astype(int)

    if f.shape[0] != data.shape[0]:
        _logger.debug("ERROR: shapes are not correct")
        _logger.debug("%s %s %s", f.shape, time_lin.shape, data.shape)
        return

    # find neerest discrete frequency
    a = f - f1
    f1_approx = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))
    a = f - f2
    f2_approx = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))

    # find postion of maximum at freqeuency band
    dd = np.squeeze(data[f1_approx, :])
    fin1 = np.where(dd == dd.max())[0][0]
    dd = np.squeeze(data[f2_approx, :])
    fin2 = np.where(dd == dd.max())[0][0]

    # define as point in time
    x1 = time_lin[fin1]
    x2 = time_lin[fin2]

    # and as point in Frequency space
    y1 = f[f1_approx]
    y2 = f[f2_approx]

    if plot == True:
        plt.plot(time_lin, data[f1_approx, :].T)
        plt.scatter(x1, data[f1_approx, fin1], s=60, c="red", alpha=1)

        plt.plot(time_lin, data[f2_approx, :].T)
        plt.scatter(x2, data[f2_approx, fin2], s=60, c="red", alpha=1)

    # fit simple line.
    p1, p2 = np.polyfit([y1, y2], [x1, x2], 1)
    limit_mid = np.polyval([p1, p2], f)

    limit_line1 = np.polyval([p1, p2], f - f_delta)
    limit_line2 = np.polyval([p1, p2], f + f_delta)

    if plot == True:
        plt.figure()
        plt.contourf(time_lin, f, data, cmap="Greys")
        plt.plot(limit_mid, f)
        plt.plot(limit_line1, f)
        plt.plot(limit_line2, f)
        plt.plot(time_lin, time_lin * 0 + y1, Color="black", alpha=1, LineWidth=2)
        plt.plot(time_lin, time_lin * 0 + y2, Color="black", alpha=1, LineWidth=2)
        plt.xlabel("time")
        plt.ylabel("f")
        plt.xlim(time_lin[0], time_lin[-1])
        plt.ylim(y1 * 0.9, y2 * 1.2)

    return f, limit_line1, limit_line2, limit_mid, fin1


def find_max_along_line(
    time_lin, f, data, f1, f2, f_delta=0.05, spreed=10, plot=False, mode="free_limits"
):
    flin, line_left, line_right, line_mid, index = linefit2Points(
        time_lin, f, data, f1, f2, f_delta=f_delta, plot=False
    )

    timestamp = time_lin
    if isinstance(time_lin[0], np.datetime64):
        _logger.debug("time is numpy.datetime64")
        time_lin = time_lin.astype("m8[s]").astype(int)

    if mode is None:
        mode = "free_limits"
    if mode in ["free_limits", "upper_limit"]:
        if line_left[0] > time_lin[0]:
            f_start = 0
            _logger.debug(" left line > time0")
            _logger.debug("%s %s", line_left[0], time_lin[0])
        else:
            _logger.debug(" left line < time")
            _logger.debug("%s %s", line_left[0], time_lin[0])
            a = line_left - time_lin[0]
            f_start = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))[0] + 1
    else:
        # find neerest discrete frequency
        a = f - f1
        f_start = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))[0]

    if mode == "free_limits" or mode == "lower_limit":
        if line_right[-1] > time_lin[-1]:
            _logger.debug(" right line > time window")
            _logger.debug("%s %s",line_right[-1], time_lin[-1])
            a = line_right - time_lin[-1]
            f_end = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))[0] - 1
        else:
            _logger.debug(" right line < time window")
            _logger.debug("%s %s",line_right[-1], time_lin[-1])
            f_end = time_lin.size - 2
    else:
        a = f - f2
        f_end = np.unravel_index(np.abs(a).argmin(), np.transpose(a.shape))[0]

    if plot:
        plt.figure()
        plt.pcolor(time_lin, f, data)
        plt.plot(f * 0 + int(time_lin[index]), f, linewidth=3, Color="black")
        plt.plot(line_mid, f)
        plt.plot(line_left, f, Color="black")
        plt.plot(line_right, f, Color="black")
        plt.plot(time_lin, time_lin * 0 + flin[f_start], Color="red")
        plt.plot(time_lin, time_lin * 0 + flin[f_end], Color="red")

        plt.plot(time_lin, time_lin * 0 + f1, Color="grey", linewidth=3)
        plt.plot(time_lin, time_lin * 0 + f2, Color="grey")

    STR = {
        "t_pos": [],
        "index": index,
        "amp": [],
        "freq": [],
        "out": [],
        "amp_shape": [],
        "left_limit": line_left,
        "right_limit": line_right,
    }

    for i in enumerate(flin[f_start:f_end]):
        ii = f_start + i[0]
        cut = cut_nparray(time_lin, line_left[ii], line_right[ii], verbose=False)
        out = find_max_ts(
            data[ii, cut[: data.shape[1]]],
            smooth=True,
            spreed=spreed,
            plot=plot,
            verbose=False,
        )
        STR["out"].append(out[0][0])
        STR["t_pos"].append(out[0][0] + np.where(np.diff(cut) == True)[0][0])
        STR["amp"].append(out[2][0])
        STR["amp_shape"].append(out[1])
        STR["freq"].append(i[1])

    if plot:
        plt.figure()
        plt.pcolor(time_lin, f, data, cmap="Greys")
        plt.plot(line_left, f, Color="blue")
        plt.plot(line_right, f, Color="blue")
        plt.xlabel("time")
        plt.ylabel("f")
        plt.scatter(time_lin[STR["t_pos"]], STR["freq"], s=20, c="blue", alpha=1)
        plt.xlim(time_lin[0], time_lin[-1])
        plt.ylim(flin[f_start], flin[f_end])
        plt.figure()
        for s in STR["amp_shape"]:
            plt.plot(s, Color="grey", alpha=0.6)
        plt.scatter(STR["out"], STR["amp"], s=20)
    return STR


def robust_regression(time, freq, plot=True):

    time2 = np.empty((time.size, 1))
    time2[:, 0] = time

    # Robustly fit linear model with RANSAC algorithm
    model_ransac = linear_model.RANSACRegressor(linear_model.LinearRegression())
    model_ransac.fit(time2, freq)
    predicted_line = model_ransac.predict(time[:, np.newaxis])

    slope = model_ransac.estimator_.coef_[0]
    intercept = model_ransac.estimator_.intercept_

    if plot:
        plt.figure()
        plt.scatter(time, freq)
        plt.plot(
            time,
            predicted_line,
            color="red",
            linestyle="-",
            linewidth=2,
            label="robust regression estimate",
        )

    return slope, intercept, time, predicted_line


def simple_RAMSAC_regression_estimator(x, Y):

    model_ransac = linear_model.RANSACRegressor(linear_model.LinearRegression())

    x2 = np.empty((x.size, 1))
    x2[:, 0] = x
    model_ransac.fit(x2, Y)
    slope = model_ransac.estimator_.coef_[0]
    intercept = model_ransac.estimator_.intercept_
    return slope, intercept


def RAMSAC_regression_bootstrap(time, freq, time_lin_arg=None, plot=False, **kwargs):
    """bootstraps linear regression model using the RAMSAC algorithm
    outout:
    slope low_ci high_ci
    intercept low_ci high_ci
    x
    Y
    """

    # NOTE: This function is not called in production. sklearn.bootstrap was depecrated and
    # the implementation needs to be changed.
    import sklearn.bootstrap as boot  # might not work in python 3

    RAMS_slope, RAMS_intercept = simple_RAMSAC_regression_estimator(time, freq)

    if time_lin_arg is not None:
        time_lin = time_lin_arg
        _logger.debug("time lin is set")
    else:
        _logger.debug("create linear time axis")
        time_lin = np.linspace(time.min(), time.max(), freq.size)

    RAMS_predicted_line = time_lin * RAMS_slope + RAMS_intercept

    _logger.debug("%s %s", RAMS_slope, RAMS_intercept)
    RAMS_out=boot.ci((time, freq), simple_RAMSAC_regression_estimator, method="bca", **kwargs
    )

    slope = np.append(RAMS_slope, RAMS_out[:, 0])
    intercept = np.append(RAMS_intercept, RAMS_out[:, 1])
    predicted_line = np.vstack(
        (
            RAMS_predicted_line,
            (time_lin * slope[1] + intercept[2], time_lin * slope[2] + intercept[1]),
        )
    )

    if plot:
        plt.figure()
        plt.scatter(time, freq, color="black")
        plt.plot(
            time_lin,
            RAMS_predicted_line.T,
            color="red",
            linestyle="-",
            linewidth=2,
            label="robust regression estimate",
        )
        plt.plot(time_lin, time_lin * slope[1] + intercept[2], color="blue")
        plt.plot(time_lin, time_lin * slope[2] + intercept[1], color="blue")

    return slope, intercept, time_lin, predicted_line
