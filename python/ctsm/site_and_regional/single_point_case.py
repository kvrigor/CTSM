"""
Holds the class SinglePointCase
"""

import os
import logging
from datetime import date

import numpy as np
import xarray as xr

from ctsm.site_and_regional.base_case import BaseCase, USRDAT_DIR

logger = logging.getLogger(__name__)


class SinglePointCase(BaseCase):
    """
        A case to encapsulate single point cases.
        ...
        Attributes
        ----------
        plat : float
            latitude
        plon : float
            longitude
        site_name: str -- default = None
            Site name
        overwrite_single_pft : bool
            flag to overwrite surface data with one uniform plant functional type
        dominant_pft: int
            index of plant functional type to set to 100% cover if overwrite_single_pft = True
        zero_nonveg_landunits : bool
            flag to set surface data to all natural vegetation (100% NATVEG, 0% other)
        uniform_snowpack
            flag to set the the surface data STD_ELEV to 0.0
        saturation_excess : bool
            flag to set the surface data FMAX to 0.0
        output_dir : str
            main output directory to write subset files to
        tag : str
            ending tag for output file naming

        Methods
        -------
        create_tag:
            create a tag for single point which is the site name
            or the "lon-lat" format if the site name does not exist.
        create_fileout_name:
            creates a file name from a basename and a specified tag
        create_domain_at_point
            creates domain file at a single point.
        create_landuse_at_point:
            creates landuse file at a single point.
        create_surfdata_at_point:
            creates surface dataset at a single point.
        create_datmdomain_at_point:
            creates DATM domain file at a single point.
        """

    def __init__(
            self,
            plat,
            plon,
            site_name,
            create_domain,
            create_surfdata,
            create_landuse,
            create_datm,
            create_user_mods,
            overwrite_single_pft,
            dominant_pft,
            zero_nonveg_landunits,
            uniform_snowpack,
            saturation_excess,
            output_dir,
    ):
        super().__init__(create_domain, create_surfdata, create_landuse, create_datm,
                         create_user_mods)
        self.plat = plat
        self.plon = plon
        self.site_name = site_name
        self.overwrite_single_pft = overwrite_single_pft
        self.dominant_pft = dominant_pft
        self.zero_nonveg_landunits = zero_nonveg_landunits
        self.uniform_snowpack = uniform_snowpack
        self.saturation_excess = saturation_excess
        self.output_dir = output_dir
        self.tag = None

    def create_tag(self):
        if self.site_name:
            self.tag = self.site_name
        else:
            self.tag = "{}_{}".format(str(self.plon), str(self.plat))

    @staticmethod
    def create_fileout_name(filename, tag):

        basename = os.path.basename(filename)
        items = basename.split("_")
        today = date.today()
        today_string = today.strftime("%y%m%d")
        new_string = "{}_{}_c{}.nc".format("_".join([items[0]] + items[2:7]), tag, today_string)

        return new_string

    def create_domain_at_point(self, indir, file):
        logging.info("----------------------------------------------------------------------")
        logging.info(
            "Creating domain file at {}, {}.".format(self.plon.__str__(), self.plat.__str__()))

        # specify files
        fdomain_in = os.path.join(indir, file)
        fdomain_out = self.add_tag_to_filename(fdomain_in, self.tag)
        logging.info("fdomain_in:  %s", fdomain_in)
        logging.info("fdomain_out: %s", os.path.join(self.output_dir, fdomain_out))

        # create 1d coordinate variables to enable sel() method
        f2 = self.create_1d_coord(fdomain_in, "xc", "yc", "ni", "nj")

        # extract gridcell closest to plon/plat
        f3 = f2.sel(ni=self.plon, nj=self.plat, method="nearest")
        # expand dimensions
        f3 = f3.expand_dims(["nj", "ni"])

        # update attributes
        self.update_metadata(f3)
        f3.attrs["Created_from"] = fdomain_in

        wfile = os.path.join(self.output_dir, fdomain_out)
        f3.to_netcdf(path=wfile, mode="w")
        logging.info("Successfully created file (fdomain_out) at %s", wfile)
        f2.close()
        f3.close()

    def create_landuse_at_point(self, indir, file, user_mods_dir):
        logging.info("----------------------------------------------------------------------")
        logging.info(
            "Creating land use file at {}, {}.".format(self.plon.__str__(), self.plat.__str__()))

        # specify files
        fluse_in = os.path.join(indir, file)
        fluse_out = self.create_fileout_name(fluse_in, self.tag)
        logging.info("fluse_in:  %s", fluse_in)
        logging.info("fluse_out: %s", os.path.join(self.output_dir, fluse_out))

        # create 1d coordinate variables to enable sel() method
        f2 = self.create_1d_coord(fluse_in, "LONGXY", "LATIXY", "lsmlon", "lsmlat")
        # extract gridcell closest to plon/plat
        f3 = f2.sel(lsmlon=self.plon, lsmlat=self.plat, method="nearest")

        # expand dimensions
        f3 = f3.expand_dims(["lsmlat", "lsmlon"])
        # specify dimension order
        # f3 = f3.transpose('time','lat','lon')
        f3 = f3.transpose(u"time", u"cft", u"natpft", u"lsmlat", u"lsmlon")
        # f3['YEAR'] = f3['YEAR'].squeeze()

        # revert expand dimensions of YEAR
        year = np.squeeze(np.asarray(f3["YEAR"]))
        x = xr.DataArray(year, coords={"time": f3["time"]}, dims="time", name="YEAR")
        x.attrs["units"] = "unitless"
        x.attrs["long_name"] = "Year of PFT data"
        f3["YEAR"] = x

        # update attributes
        self.update_metadata(f3)
        f3.attrs["Created_from"] = fluse_in

        wfile = os.path.join(self.output_dir, fluse_out)
        # mode 'w' overwrites file
        f3.to_netcdf(path=wfile, mode="w")
        logging.info("Successfully created file (fluse_out) at %s", wfile)
        f2.close()
        f3.close()

        # write to user_nl_clm data if specified
        if self.create_user_mods:
            with open(os.path.join(user_mods_dir, "user_nl_clm"), "a") as nl_clm:
                line = "landuse = '${}'".format(os.path.join(USRDAT_DIR, fluse_out))
                self.write_to_file(line, nl_clm)

    def create_surfdata_at_point(self, indir, file, user_mods_dir):
        logging.info("----------------------------------------------------------------------")
        logging.info(
            "Creating surface dataset file at {}, {}.".format(self.plon.__str__(),
                                                              self.plat.__str__()))

        # specify file
        fsurf_in = os.path.join(indir, file)
        fsurf_out = self.create_fileout_name(fsurf_in, self.tag)
        logging.info("fsurf_in:  %s", fsurf_in)
        logging.info("fsurf_out: %s", os.path.join(self.output_dir, fsurf_out))

        # create 1d coordinate variables to enable sel() method
        filename = os.path.join(self.output_dir, fsurf_in)
        f2 = self.create_1d_coord(filename, "LONGXY", "LATIXY", "lsmlon", "lsmlat")
        # extract gridcell closest to plon/plat
        f3 = f2.sel(lsmlon=self.plon, lsmlat=self.plat, method="nearest")
        # expand dimensions
        f3 = f3.expand_dims(["lsmlat", "lsmlon"]).copy(deep=True)

        # update the plon and plat to match the surface data
        # we do this so that if we create user_mods the PTS_LON and PTS_LAT in CIME match
        # the surface data coordinates - which is required
        self.plat = f3.coords["lsmlat"].values[0]
        self.plon = f3.coords["lsmlon"].values[0]

        # modify surface data properties
        if self.overwrite_single_pft:
            f3["PCT_NAT_PFT"][:, :, :] = 0
            f3["PCT_NAT_PFT"][:, :, self.dominant_pft] = 100
        if self.zero_nonveg_landunits:
            f3["PCT_NATVEG"][:, :] = 100
            f3["PCT_CROP"][:, :] = 0
            f3["PCT_LAKE"][:, :] = 0.0
            f3["PCT_WETLAND"][:, :] = 0.0
            f3["PCT_URBAN"][:, :, ] = 0.0
            f3["PCT_GLACIER"][:, :] = 0.0
        if self.uniform_snowpack:
            f3["STD_ELEV"][:, :] = 20.0
        if not self.saturation_excess:
            f3["FMAX"][:, :] = 0.0

        # specify dimension order
        # f3 = f3.transpose(u'time', u'cft', u'natpft', u'lsmlat', u'lsmlon')
        f3 = f3.transpose(
            u"time",
            u"cft",
            u"lsmpft",
            u"natpft",
            u"nglcec",
            u"nglcecp1",
            u"nlevsoi",
            u"nlevurb",
            u"numrad",
            u"numurbl",
            "lsmlat",
            "lsmlon",
        )

        # update attributes
        self.update_metadata(f3)
        f3.attrs["Created_from"] = fsurf_in
        del f3.attrs["History_Log"]
        # mode 'w' overwrites file
        f3.to_netcdf(path=os.path.join(self.output_dir, fsurf_out), mode="w")
        logging.info("Successfully created file (fsurf_out) at %s", os.path.join(self.output_dir,
                                                                                 fsurf_out))
        f2.close()
        f3.close()

        # write to user_nl_clm if specified
        if self.create_user_mods:
            with open(os.path.join(user_mods_dir, "user_nl_clm"), "a") as nl_clm:
                line = "fsurdat = '${}'".format(os.path.join(USRDAT_DIR, fsurf_out))
                self.write_to_file(line, nl_clm)

    def create_datmdomain_at_point(self, indir, file, dir_output_datm):
        logging.info("----------------------------------------------------------------------")
        logging.info(
            "Creating DATM domain file at {}, {}.".format(self.plon.__str__(), self.plat.__str__()))

        # specify files
        fdatmdomain_in = os.path.join(indir, file)
        datm_file = self.add_tag_to_filename(fdatmdomain_in, self.tag)
        fdatmdomain_out = os.path.join(dir_output_datm, datm_file)
        logging.info("fdatmdomain_in:  %s", fdatmdomain_in)
        logging.info("fdatmdomain out: %s", os.path.join(self.output_dir, fdatmdomain_out))

        # create 1d coordinate variables to enable sel() method
        f2 = self.create_1d_coord(fdatmdomain_in, "xc", "yc", "ni", "nj")
        # extract gridcell closest to plon/plat
        f3 = f2.sel(ni=self.plon, nj=self.plat, method="nearest")
        # expand dimensions
        f3 = f3.expand_dims(["nj", "ni"])
        wfile = os.path.join(self.output_dir, fdatmdomain_out)
        # update attributes
        self.update_metadata(f3)
        f3.attrs["Created_from"] = fdatmdomain_in
        # mode 'w' overwrites file
        f3.to_netcdf(path=wfile, mode="w")
        logging.info("Successfully created file (fdatmdomain_out) at %s", wfile)
        f2.close()
        f3.close()

    def extract_datm_at(self, file_in, file_out):
        # create 1d coordinate variables to enable sel() method
        f2 = self.create_1d_coord(file_in, "LONGXY", "LATIXY", "lon", "lat")
        # extract gridcell closest to plon/plat
        f3 = f2.sel(lon=self.plon, lat=self.plat, method="nearest")
        # expand dimensions
        f3 = f3.expand_dims(["lat", "lon"])
        # specify dimension order
        f3 = f3.transpose(u"scalar", "time", "lat", "lon")

        # update attributes
        self.update_metadata(f3)
        f3.attrs["Created_from"] = file_in
        # mode 'w' overwrites file
        f3.to_netcdf(path=file_out, mode="w")
        logging.info("Successfully created file at %s", file_out)
        f2.close()
        f3.close()

    def write_shell_commands(self, file):
        """
        writes out xml commands commands to a file (i.e. shell_commands) for single-point runs
        """
        # write_to_file surrounds text with newlines
        with open(file, 'w'):
            self.write_to_file("# Change below line if you move the subset data directory", file)
            self.write_to_file("./xmlchange {}={}".format(USRDAT_DIR, self.output_dir), file)
            self.write_to_file("./xmlchange PTS_LON={}".format(str(self.plon)), file)
            self.write_to_file("./xmlchange PTS_LAT={}".format(str(self.plat)), file)
            self.write_to_file("./xmlchange MPILIB=mpi-serial", file)

    def write_datm_streams_lines(self, streamname, datmfiles, file):
        """
        writes out lines for the user_nl_datm_streams file for a specific DATM stream
        for using subset DATM data at a single point

        streamname - stream name (e.g. TPQW)
        datmfiles - comma-separated list (str) of DATM file names
        file - file connection to user_nl_datm_streams file
        """
        self.write_to_file("{}:datafiles={}".format(streamname, ','.join(datmfiles)), file)
        self.write_to_file("{}:mapalgo=none".format(streamname), file)
        self.write_to_file("{}:meshfile=none".format(streamname), file)

    def create_datm_at_point(self, datm_dict: dict, datm_syr, datm_eyr, datm_streams_file):
        logging.info("----------------------------------------------------------------------")
        logging.info(
            "Creating DATM files at {}, {}.".format(self.plon.__str__(), self.plat.__str__()))

        # --  create data files
        infile = []
        outfile = []
        solarfiles = []
        precfiles = []
        tpqwfiles = []
        for y in range(datm_syr, datm_eyr + 1):
            ystr = str(y)
            for m in range(1, 13):
                mstr = str(m)
                if m < 10:
                    mstr = "0" + mstr

                dtag = ystr + "-" + mstr

                fsolar = os.path.join(datm_dict["datm_indir"], datm_dict["dir_solar"],
                                      "{}{}.nc".format(datm_dict["tag_solar"], dtag))
                fsolar2 = "{}{}.{}.nc".format(datm_dict["tag_solar"], self.tag, dtag)
                fprecip = os.path.join(datm_dict["datm_indir"], datm_dict["dir_prec"],
                                       "{}{}.nc".format(datm_dict["tag_prec"], dtag))
                fprecip2 = "{}{}.{}.nc".format(datm_dict["tag_prec"], self.tag, dtag)
                ftpqw = os.path.join(datm_dict["datm_indir"], datm_dict["dir_tpqw"],
                                     "{}{}.nc".format(datm_dict["tag_tpqw"], dtag))
                ftpqw2 = "{}{}.{}.nc".format(datm_dict["tag_tpqw"], self.tag, dtag)

                outdir = os.path.join(self.output_dir, datm_dict["datm_outdir"])
                infile += [fsolar, fprecip, ftpqw]
                outfile += [os.path.join(outdir, fsolar2),
                            os.path.join(outdir, fprecip2),
                            os.path.join(outdir, ftpqw2)]
                solarfiles.append(
                    os.path.join("${}".format(USRDAT_DIR), datm_dict["datm_outdir"], fsolar2))
                precfiles.append(
                    os.path.join("${}".format(USRDAT_DIR), datm_dict["datm_outdir"], fprecip2))
                tpqwfiles.append(
                    os.path.join("${}".format(USRDAT_DIR), datm_dict["datm_outdir"], ftpqw2))

        nm = len(infile)
        for n in range(nm):
            logging.debug(outfile[n])
            file_in = infile[n]
            file_out = outfile[n]
            self.extract_datm_at(file_in, file_out)

        logging.info("All DATM files are created in: %s", datm_dict["datm_outdir"])

        # write to user_nl_datm_streams if specified
        if self.create_user_mods:
            with open(datm_streams_file, "a") as file:
                self.write_datm_streams_lines(datm_dict["name_solar"], solarfiles, file)
                self.write_datm_streams_lines(datm_dict["name_prec"], precfiles, file)
                self.write_datm_streams_lines(datm_dict["name_tpqw"], tpqwfiles, file)
