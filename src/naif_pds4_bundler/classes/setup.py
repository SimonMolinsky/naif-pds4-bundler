import datetime
import glob
import logging
import os
import re
from os.path import dirname
from pathlib import Path
from xml.etree import cElementTree as ET

import spiceypy
import xmlschema
from naif_pds4_bundler.classes.log import error_message
from naif_pds4_bundler.utils import etree_to_dict
from naif_pds4_bundler.utils import kernel_name


class Setup(object):
    """
    Class that parses and processes the NPB XML configuration file
    and makes it available to all other classes.

    :param args: Parameters arguments from NPB's main function.
    :param version: NPB version.
    """

    def __init__(self, args, version):
        """
        Constructor method.
        """
        #
        # Check that the configuration file validates with its schema
        #
        try:
            schema = xmlschema.XMLSchema11(
                dirname(__file__) + "/../templates/configuration.xsd"
            )
            schema.validate(args.config)

        except Exception as inst:
            if not args.debug:
                print(inst)
            raise

        #
        # Converting XML setup file into a dictionary and then into
        # attributes for the object.
        #
        config = Path(args.config).read_text()
        entries = etree_to_dict(ET.XML(config))

        #
        # Re-arrange the resulting dictionary into one-level attributes
        # adept to be used (as if we were loading a JSON file).
        #
        config = entries["naif-pds4-bundler_configuration"]

        self.__dict__.update(config["pds_parameters"])
        self.__dict__.update(config["bundle_parameters"])
        self.__dict__.update(config["mission_parameters"])
        self.__dict__.update(config["directories"])

        #
        # Re-arrange secondary spacecrafts and secondary targets parameters.
        #
        if hasattr(self, "secondary_observers"):
            if not isinstance(self.secondary_observers["observer"], list):
                self.secondary_observers = [self.secondary_observers["observer"]]
            else:
                self.secondary_observers = self.secondary_observers["observer"]

        if hasattr(self, "secondary_targets"):
            if not isinstance(self.secondary_targets["target"], list):
                self.secondary_targets = [self.secondary_targets["target"]]
            else:
                self.secondary_targets = self.secondary_targets["target"]

        #
        # Kernel directory needs to be turned into a list.
        #
        if not isinstance(self.kernels_directory, list):
            self.kernels_directory = [self.kernels_directory]

        #
        # Kernel list configuration needs refactoring.
        #
        self.__dict__.update(config["kernel_list"])

        kernel_list_config = {}
        for ker in self.kernel:
            kernel_list_config[ker["@pattern"]] = ker

        self.kernel_list_config = kernel_list_config
        del self.kernel

        #
        # Meta-kernel configuration; if there is one meta-kernel
        # mk is a dictionary, otherwise it is a list of dictionaries.
        # It is processed in such a way that it is always a list of
        # dictionaries. Same applies to meta-kernels from configuration
        # as user input.
        #
        self.__dict__.update(config["meta-kernel"])

        if hasattr(self, "mk"):
            if isinstance(self.mk, dict):
                self.mk = [self.mk]

        #
        # Meta-kernel configuration; if there is one pattern for
        # the meta-kernel name, convert it into a list of
        # dictionaries.
        #
        if hasattr(self, "mk"):
            for i in range(len(self.mk)):
                if isinstance(self.mk[i]["name"], dict):
                    self.mk[i]["name"] = [self.mk[i]["name"]]

        #
        # Meta-kernel configuration; if there is one coverage kernel, convert
        # it into a list of coverage kernels.
        #
        if hasattr(self, "coverage_kernels"):
            if isinstance(self.coverage_kernels, dict):
                self.coverage_kernels = [self.coverage_kernels]

        #
        # Orbnum configuration: if there is one orbnum file orbnum is a
        # dictionary, otherwise it is a list of dictionaries. It is
        # processed in such a way that it is always a list of dictionaries
        #
        if "orbit_number_file" in config:
            self.__dict__.update(config["orbit_number_file"])
            if isinstance(self.orbnum, dict):
                self.orbnum = [self.orbnum]

        #
        # Set run type for the NPB by-products file name. So far this only
        # deviates from the default *_release_* for label generation run only
        # *_labels_*
        #
        if args.faucet == "labels" or \
                (args.faucet == "clear" and "_labels_" in args.clear):
            self.run_type = "labels"
        else:
            self.run_type = "release"

        #
        # Populate the setup object with attributes not present in the
        # configuration file.
        #
        self.root_dir = os.path.dirname(__file__)[:-7]
        self.step = 1
        self.version = version
        self.args = args
        self.faucet = args.faucet.lower()
        self.diff = args.diff.lower()
        self.today = datetime.date.today().strftime("%Y%m%d")
        self.file_list = []
        self.checksum_registry = []

        #
        # If a release date is not specified it is set to today.
        #
        if not hasattr(self, "release_date"):
            self.release_date = datetime.date.today().strftime("%Y-%m-%d")
        else:
            pattern = re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}")
            if not pattern.match(self.release_date):
                error_message(
                    "release_date parameter does not match "
                    "the required format: YYYY-MM-DD."
                )

        #
        # Check date format, if is not provided it is set to the format
        # proposed for the PDS4 Information Model 2.0.
        #
        if not hasattr(self, "date_format"):
            self.date_format = "maklabel"

        #
        # Check End of Line format and set EoL length.
        #
        # CRs are added to all text, XML, and other PDS meta-files
        # present in PDS4 archives as dictated by the standard.
        # CRs are added to checksum tables as well.
        #
        # If the parameter is not provided via configration is set by default
        # to CRLF.
        #
        if not hasattr(self, "end_of_line"):
            self.end_of_line = "CRLF"
        if self.end_of_line == "CRLF":
            self.eol = "\r\n"
            self.eol_len = 2
        elif self.end_of_line == "LF":
            self.eol = "\n"
            self.eol_len = 1
        else:
            error_message(
                "End of Line provided via configuration is not CRLF nor LF"
            )

        self.end_of_line_pds4 = "CRLF"
        self.eol_pds4 = "\r\n"
        self.eol_pds4_len = 1
        self.eol_mk = "\n"
        self.eol_mk_len = 1

        #
        # Fill PDS4 missing fields.
        #
        if self.pds_version == "4":
            self.producer_phone = ""
            self.producer_email = ""
            self.dataset_id = ""
            self.volume_id = ""

    def check_configuration(self):
        """
        Performs a number of checks on some of the loaded configuration
        items.
        """
        #
        # Check IM, Line Feed, and Date Time format NAIF recommendations.
        #
        if self.date_format == "infomod2":

            #
            # Warn the user if the End of Line character is not the one
            # corresponding to the one recommended by NAIF for the selected
            # date format.
            #
            if self.end_of_line != "LF":
                logging.warning(
                    f"-- NAIF recommends to use `LF' End-of-Line while using"
                    f" the `{self.date_format}' parameter instead of "
                    f"`{self.end_of_line}'."
                )

            #
            # Set the time format for the Date format selected.
            #
            pattern = re.compile(
                "[0-9]{4}-[0-9]{2}-[0-9]{2}T" "[0-9]{2}:[0-9]{2}:[0-9]{2}.[0-9]{3}Z"
            )
            format = "YYYY-MM-DDThh:mm:ss.sssZ"
        elif self.date_format == "maklabel":

            #
            # Warn the user if the End of Line character is not the one
            # corresponding to the one recommended by NAIF for the selected
            # date format.
            #
            if self.end_of_line != "CRLF":
                logging.warning(
                    f"-- NAIF recommends to use `CRLF' End-of-Line while using"
                    f" the `{self.date_format}' parameter instead of "
                    f"`{self.end_of_line}'."
                )

            #
            # Set the time format for the Date format selected.
            #
            pattern = re.compile(
                "[0-9]{4}-[0-9]{2}-[0-9]{2}T" "[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
            )
            format = "YYYY-MM-DDThh:mm:ssZ"

        #
        # Check Bundle increment start and finish times. For the two accepted
        # formats.
        #
        if hasattr(self, "mission_start") and self.mission_start:
            if not pattern.match(self.mission_start):
                error_message(
                    f"mission_start parameter does not match the "
                    f"required format: {format}"
                )
        if hasattr(self, "mission_finish") and self.mission_finish:
            if not pattern.match(self.mission_finish):
                error_message(
                    f"mission_finish does not match the required format: {format}"
                )
        if hasattr(self, "increment_start") and self.increment_start:
            if not pattern.match(self.increment_start):
                error_message(
                    f"increment_start parameter does not match the "
                    f"required format: {format}"
                )
        if hasattr(self, "increment_finish") and self.increment_finish:
            if not pattern.match(self.increment_finish):
                error_message(
                    f"increment_finish does not match the required "
                    f"format: {format}"
                )
        if hasattr(self, "increment_start") and hasattr(self, "increment_finish"):
            if ((not self.increment_start) and (self.increment_finish)) or (
                (self.increment_start) and (not self.increment_finish)
            ):
                error_message(
                    "If provided via configuration, increment_start and "
                    "increment_finish parameters need to be provided "
                    "together."
                )

        #
        # Sort out if directories are provided as relative paths and
        # if so convert them in absolute for the execution
        #
        cwd = os.getcwd()

        os.chdir("/")

        #
        # Set the staging directory WRT PDS3 or PDS4
        #
        if self.pds_version == "4":
            mission_dir = f"{self.mission_acronym}_spice"
        else:
            mission_dir = f"{self.volume_id.lower()}"

        if os.path.isdir(cwd + os.sep + self.working_directory):
            self.working_directory = cwd + os.sep + self.working_directory
        if not os.path.isdir(self.working_directory):
            error_message(f"Directory does not exist: {self.working_directory}")

        if os.path.isdir(cwd + os.sep + self.staging_directory):
            self.staging_directory = (
                cwd + os.sep + self.staging_directory + f"/{mission_dir}"
            )
        elif not os.path.isdir(self.staging_directory):
            print(
                f"Creating missing directory: {self.staging_directory}/"
                f"{mission_dir}"
            )
            try:
                os.mkdir(self.staging_directory)
            except Exception as e:
                print(e)
        elif f"/{mission_dir}" not in self.staging_directory:
            self.staging_directory += f"/{mission_dir}"

        if os.path.isdir(cwd + os.sep + self.bundle_directory):
            self.bundle_directory = cwd + os.sep + self.bundle_directory
        if not os.path.isdir(self.bundle_directory):
            error_message(f"Directory does not exist: {self.bundle_directory}")

        #
        # There might be more than one kernels directory
        #
        for i in range(len(self.kernels_directory)):
            if os.path.isdir(cwd + os.sep + self.kernels_directory[i]):
                self.kernels_directory[i] = cwd + os.sep + self.kernels_directory[i]
            if not os.path.isdir(self.kernels_directory[i]):
                error_message(
                    f"Directory does not exist: {self.kernels_directory[i]}"
                )

        os.chdir(cwd)

        #
        # Check IM, XML model and Schema Location coherence (given that is not
        # checked by the PDS Validate tool.
        #
        if hasattr(self, "information_model"):
            if re.match(r"[0-9]+[.][0-9]+[.][0-9]+[.][0-9]+", self.information_model):

                major = int(self.information_model.split(".")[0])
                minor = int(self.information_model.split(".")[1])
                maint = int(self.information_model.split(".")[2])
                build = int(self.information_model.split(".")[3])

                if major >= 10:
                    major = chr(major + 55)
                if minor >= 10:
                    minor = chr(minor + 55)
                if maint >= 10:
                    maint = chr(maint + 55)
                if build >= 10:
                    build = chr(build + 55)

                short_version = f"{major}{minor}{maint}{build}"

                xml_model_version = self.xml_model.split("PDS4_PDS_")[-1]
                xml_model_version = xml_model_version.split(".sch")[0]

                if xml_model_version != short_version:
                    error_message(
                        f"PDS4 Information Model "
                        f"{short_version} "
                        f"is incoherent with the XML Model version: "
                        f"{self.xml_model}"
                    )

                schema_loc_version = self.schema_location.split("/PDS4_PDS_")[-1]
                schema_loc_version = schema_loc_version.split(".xsd")[0]

                if schema_loc_version != short_version:
                    error_message(
                        f"PDS4 Information Model "
                        f"{short_version} "
                        f"is incoherent with the Schema location: "
                        f"{self.schema_location}"
                    )

            else:
                error_message(
                    f"PDS4 Information Model {self.information_model}"
                    f" format from configuration is incorrect"
                )

        #
        # Check existence of templates according to the information_model
        # or user-defined templates.
        #
        # If a templates directory is not provided, determine the templates
        # to be used based on the IM.
        #
        if not hasattr(self, "templates_directory") and self.pds_version == "4":

            config_schema = self.information_model.split(".")
            config_schema = float(
                f"{int(config_schema[0]):03d}"
                f"{int(config_schema[1]):03d}"
                f"{int(config_schema[2]):03d}"
                f"{int(config_schema[3]):03d}"
            )

            schemas = [
                os.path.basename(x[:-1])
                for x in glob.glob(f"{self.root_dir}templates/*/")
            ]

            schemas_eval = []
            for schema in schemas:
                schema = schema.split(".")
                schema = float(
                    f"{int(schema[0]):03d}"
                    f"{int(schema[1]):03d}"
                    f"{int(schema[2]):03d}"
                    f"{int(schema[3]):03d}"
                )
                schemas_eval.append(schema)

            i = 0
            while i < len(schemas_eval):
                if config_schema < schemas_eval[i]:
                    try:
                        schema = schemas[i - 1]
                    except:
                        schema = schemas[0]
                    break
                if config_schema >= schemas_eval[i]:
                    schema = schemas[i]
                    break
                i += 1

            self.templates_directory = f"{self.root_dir}templates/{schema}/"

            logging.warning(
                f"-- Label templates will use the ones from "
                f"information model {schema}."
            )
        elif self.pds_version == "4":
            if not os.path.isdir(self.templates_directory):
                error_message("Path provided/derived for templates is not available")
            labels_check = [
                os.path.basename(x[:-1])
                for x in glob.glob(f"{self.root_dir}templates/1.5.0.0/*")
            ]
            labels = [
                os.path.basename(x[:-1])
                for x in glob.glob(f"{self.templates_directory}/*")
            ]
            for label in labels_check:
                if label not in labels:
                    error_message(f"Template {label} has not been provided.")
        else:
            # TODO Add templates for PDS3
            self.templates_directory = ""

        logging.info(f"-- Label templates directory: {self.templates_directory}")

        #
        # Check meta-kernel configuration
        #
        if hasattr(self, "mk"):
            for metak in self.mk:

                metak_name_check = metak["@name"]

                #
                # Fix no list or list of lists.
                #
                patterns = []
                for name in metak["name"]:

                    if not isinstance(name["pattern"], list):
                        patterns = [name["pattern"]]
                    else:
                        for pattern in name["pattern"]:
                            patterns.append(pattern)

                for pattern in patterns:
                    name_pattern = pattern["#text"]
                    if not name_pattern in metak_name_check:
                        error_message(
                            f"The meta-kernel pattern "
                            f"{name_pattern} is not provided"
                        )

                    metak_name_check = metak_name_check.replace("$" + name_pattern, "")

                #
                # If there are remaining $ characters in the metak_name_check
                # this means that there are remaining patterns to define in
                # the configuration file.
                #
                if "$" in metak_name_check:
                    error_message(
                        f"The MK patterns {metak['@name']} do not "
                        f"correspond to the present MKs"
                    )
            else:
                logging.warning("-- There is no meta-kernel configuration " "to check.")

        #
        # Check coverage kernels configuration (needed if there is only one
        # entry).
        #
        if hasattr(self, "coverage_kernels"):
            if not isinstance(self.coverage_kernels, list):
                self.coverage_kernels = [self.coverage_kernels]

        return None

    def set_release(self):
        """
        Determines the Bundle release number.
        """
        line = f"Step {self.step} - Setup the archive generation"
        logging.info("")
        logging.info("")
        logging.info(line)
        logging.info("-" * len(line))
        logging.info("")
        self.step += 1
        if not self.args.silent and not self.args.verbose:
            print("-- " + line.split(" - ")[-1] + ".")

        #
        # PDS4 release increment (implies inventory and meta-kernel).
        #
        logging.info("-- Checking existence of previous release.")

        if self.args.clear:
            release = self.args.clear
            release = release.split(".file_list")[0]
            release = int(release.split(f"_{self.run_type}_")[-1])
            current_release = int(release) - 1

            release = f"{release:03}"
            current_release = f"{current_release:03}"
            logging.info(
                f"     Generating release {release} as obtained from "
                f"file list from previous run: {self.args.clear}"
            )
            increment = True

        else:
            try:
                releases = glob.glob(
                    self.bundle_directory
                    + os.sep
                    + self.mission_acronym
                    + "_spice"
                    + os.sep
                    + f"bundle_{self.mission_acronym}_spice_v*"
                )
                releases.sort()
                current_release = int(releases[-1].split("_spice_v")[-1].split(".")[0])
                current_release = f"{current_release:03}"
                release = int(current_release) + 1
                release = f"{release:03}"

                logging.info(f"     Generating release {release}.")

                increment = True

            except:
                logging.warning(
                    "-- Bundle label not found. Checking previous " "kernel list."
                )

                try:

                    #
                    # If the kernel list is provided as an argument, we
                    # cannot deduce the release version from it.
                    #
                    if self.args.kerlist:
                        logging.warning(
                            "-- Kernel list provided as input. "
                            "Release number cannot be obtained."
                        )
                        raise

                    releases = glob.glob(
                        self.working_directory + f"/{self.mission_acronym}"
                        f"_{self.run_type}_*.kernel_list"
                    )

                    releases.sort()
                    current_release = int(
                        releases[-1].split("_{self.run_type}_")[-1].split(".")[0]
                    )
                    current_release = f"{current_release:03}"
                    release = int(current_release) + 1
                    release = f"{release:03}"

                    logging.info(f"     Generating release {release}")

                    increment = True
                except:

                    logging.warning("     This is the first release.")

                    release = "001"
                    current_release = ""

                    increment = False

        self.release = release
        self.current_release = current_release

        logging.info("")

        self.increment = increment

        return None

    def load_kernels(self):
        """
        Loads the kernels required to run NPB. Note that kernels that
        are not required might be loaded as well, but given that the
        required memory is not much, we stay on the safe side by loading
        additional kernels.
        """
        line = f"Step {self.step} - Load LSK, PCK, FK and SCLK kernels"
        logging.info("")
        logging.info(line)
        logging.info("-" * len(line))
        logging.info("")
        self.step += 1
        if not self.args.silent and not self.args.verbose:
            print("-- " + line.split(" - ")[-1] + ".")

        #
        # To get the appropriate kernels, use the kernel list config.
        # First extract the patterns for each kernel type of interest.
        #
        fk_patterns = []
        sclk_patterns = []
        pck_patterns = []
        lsk_patterns = []

        for type in self.kernels_to_load:
            if "fk" in type:
                fks = self.kernels_to_load[type]
                if not isinstance(fks, list):
                    fks = [fks]
                for fk in fks:
                    fk_patterns.append(fk)
            elif "sclk" in type:
                sclks = self.kernels_to_load[type]
                if not isinstance(sclks, list):
                    sclks = [sclks]
                for sclk in sclks:
                    sclk_patterns.append(sclk)
            elif "pck" in type:
                pcks = self.kernels_to_load[type]
                if not isinstance(pcks, list):
                    pcks = [pcks]
                for pck in pcks:
                    pck_patterns.append(pck)
            elif "lsk" in type:
                lsks = self.kernels_to_load[type]
                if not isinstance(lsks, list):
                    lsks = [lsks]
                for lsk in lsks:
                    lsk_patterns.append(lsk)

        #
        # Search the latest version for each pattern of each kernel type.
        #
        lsks = []
        for pattern in lsk_patterns:
            if os.path.exists(pattern):
                lsks.append(pattern)
                spiceypy.furnsh(pattern)
            else:
                for dir in self.kernels_directory:
                    lsk_pattern = [
                        os.path.join(root, name)
                        for root, dirs, files in os.walk(dir)
                        for name in files
                        if re.fullmatch(pattern, name)
                    ]
                    if lsk_pattern:
                        lsk_pattern.sort(key=kernel_name)
                        spiceypy.furnsh(lsk_pattern[-1])
                        lsks.append(lsk_pattern[-1])
                        break
        if not lsks:
            logging.error(f"-- LSK not found.")
        else:
            logging.info(f"-- LSK     loaded: {lsks}")
        if len(lsks) > 1:
            error_message("Only one LSK should be obtained.")

        pcks = []
        for pattern in pck_patterns:
            if os.path.exists(pattern):
                pcks.append(pattern)
                spiceypy.furnsh(pattern)
            else:
                for dir in self.kernels_directory:
                    pcks_pattern = [
                        os.path.join(root, name)
                        for root, dirs, files in os.walk(dir)
                        for name in files
                        if re.fullmatch(pattern, name)
                    ]
                    if pcks_pattern:
                        pcks_pattern.sort(key=kernel_name)
                        spiceypy.furnsh(pcks_pattern[-1])
                        pcks.append(pcks_pattern[-1])
                        break
        if not pcks:
            logging.warning(f"-- PCK not found.")
        else:
            logging.info(f"-- PCK(s)   loaded: {pcks}")

        fks = []
        for pattern in fk_patterns:
            if os.path.exists(pattern):
                fks.append(pattern)
                spiceypy.furnsh(pattern)
            else:
                for dir in self.kernels_directory:
                    fks_pattern = [
                        os.path.join(root, name)
                        for root, dirs, files in os.walk(dir)
                        for name in files
                        if re.fullmatch(pattern, name)
                    ]

                    if fks_pattern:
                        fks_pattern.sort(key=kernel_name)
                        spiceypy.furnsh(fks_pattern[-1])
                        fks.append(fks_pattern[-1])
                        break
        if not fks:
            logging.warning(f"-- FK not found.")
        else:
            logging.info(f"-- FK(s)   loaded: {fks}")

        sclks = []
        for pattern in sclk_patterns:
            if os.path.exists(pattern):
                sclks.append(pattern)
                spiceypy.furnsh(pattern)
            else:
                for dir in self.kernels_directory:
                    sclks_pattern = [
                        os.path.join(root, name)
                        for root, dirs, files in os.walk(dir)
                        for name in files
                        if re.fullmatch(pattern, name)
                    ]
                    if sclks_pattern:
                        sclks_pattern.sort(key=kernel_name)
                        spiceypy.furnsh(sclks_pattern[-1])
                        sclks.append(sclks_pattern[-1])
        if not sclks:
            logging.error(f"-- SCLK not found.")
        else:
            logging.info(f"-- SCLK(s) loaded: {sclks}")

        logging.info("")

        self.fks = fks
        self.sclks = sclks
        self.lsk = lsk

        return None

    def clear_run(self, debug=False):
        """
        Clears the files generated by a previous run when specified with the
        clear argument and the kernel list of the previous run.

        Please note that newly created directories will not be erased.
        """

        if debug:
            logging.warning(
                f"-- Running in DEBUG mode, by-product files are not cleaned up."
            )

        if os.path.isfile(self.args.clear):

            #
            # Remove files from the staging area.
            #
            path = self.staging_directory
            logging.info(f"-- Removing files from staging area: {path}.")
            with open(self.args.clear, "r") as c:
                for line in c:
                    if ('.plan' not in line) and ('.kernel_list' not in line):
                        try:
                            stag_file = path + os.sep + line.strip()
                            os.remove(stag_file)
                        except:
                            logging.warning(f"     File {stag_file} not found.")

            #
            # Remove files from the final area.
            #
            path = self.bundle_directory + os.sep + self.mission_acronym + "_spice/"

            logging.info(f"-- Removing files from final area: {path}.")
            with open(self.args.clear, "r") as c:
                for line in c:
                    if ('.plan' not in line) and ('.kernel_list' not in line):
                        try:
                            #
                            # When NPB has been executed in label mode the final
                            # area does not replicate the bundle directory structure
                            # but kernels operations area.
                            #
                            if not os.path.exists(path):
                                os.remove(self.bundle_directory +
                                          line.split('spice_kernels')[-1].strip())
                            #
                            # Default case.
                            #
                            else:
                                os.remove(path + line.strip())
                        except:
                            logging.warning(f"     File {line.strip()} not found.")

            #
            # Remove generated by-products from the working_directory.
            #
            path = self.working_directory
            with open(self.args.clear, "r") as c:
                for line in c:
                    try:
                        if ('.plan' in line) or ('.kernel_list' in line):
                            byproduct = line.split(os.sep)[-1][:-1]
                            logging.info(f"-- Removing previous run "
                                         f"by-product: {byproduct}.")
                            os.remove(path + os.sep + byproduct)
                    except:
                        logging.warning(f"     File {byproduct} not found.")

        else:
            error_message(
                f'The file provided with the "clear" argument does '
                f"not exist or is not readable. Make sure that the "
                f"file follows the name pattern: "
                f"{self.mission_acronym}_{self.run_type}_NN.file_list."
                f" where NN is the release number"
            )

        return None

    def add_file(self, file):
        """

        :return:
        """
        self.file_list.append(file)

        return

    def add_checksum(self, path, checksum):

        self.checksum_registry.append(f"{path} {checksum}")

    def write_file_list(self):

        if self.file_list:
            with open(
                self.working_directory + os.sep + f"{self.mission_acronym}_{self.run_type}_"
                f"{int(self.release):02d}.file_list",
                "w",
            ) as l:
                for file in self.file_list:
                    l.write(file + "\n")

        return

    def write_checksum_regsitry(self):

        if self.checksum_registry:
            with open(
                self.working_directory + os.sep + f"{self.mission_acronym}_{self.run_type}_"
                f"{int(self.release):02d}.checksum",
                "w",
            ) as l:
                for element in self.checksum_registry:
                    l.write(element + "\n")

        return

    def check_times(self):
        """
        Check the correctness of the times provided from the configuration
        file.q
        """
        try:
            et_msn_strt = spiceypy.utc2et(self.mission_start)
            et_inc_strt = spiceypy.utc2et(self.increment_start)
            et_inc_stop = spiceypy.utc2et(self.increment_finish)
            et_mis_stop = spiceypy.utc2et(self.mission_finish)
            logging.info("-- Provided dates are loadable with current setup.")

        except Exception as e:
            logging.error("-- Provided dates are not loadable with current " "setup.")
            error_message(e)

        if (
            not (et_msn_strt < et_inc_strt)
            or not (et_inc_strt <= et_inc_stop)
            or not (et_inc_stop <= et_mis_stop)
            or not (et_msn_strt < et_mis_stop)
        ):
            error_message(
                "-- Provided dates are note correct. Check the " "archive coverage"
            )

        return None
