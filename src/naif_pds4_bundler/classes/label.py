import fileinput
import glob
import logging
import os

from naif_pds4_bundler.classes.log import error_message
from naif_pds4_bundler.utils import add_carriage_return
from naif_pds4_bundler.utils import compare_files
from naif_pds4_bundler.utils import current_time
from naif_pds4_bundler.utils import extension2type

# from npb.utils.files import get_observers
# from npb.utils.files import get_targets


class PDSLabel(object):
    def __init__(self, setup, product):

        try:
            context_products = product.collection.bundle.context_products
            if not context_products:
                raise Exception("No context products from bundle in " "collection")
        except:
            context_products = product.bundle.context_products

        #
        # The product to be labeled.
        #
        self.product = product
        self.setup = setup

        #
        # Fields from setup
        #
        self.root_dir = setup.root_dir
        self.mission_acronym = setup.mission_acronym
        self.XML_MODEL = setup.xml_model
        self.SCHEMA_LOCATION = setup.schema_location
        self.INFORMATION_MODEL_VERSION = setup.information_model
        self.PDS4_MISSION_NAME = setup.mission_name
        self.PDS4_OBSERVER_NAME = setup.observer

        self.END_OF_LINE_PDS4 = "Carriage-Return Line-Feed"
        if setup.end_of_line == "CRLF":
            self.END_OF_LINE = "Carriage-Return Line-Feed"
        elif setup.end_of_line == "LF":
            self.END_OF_LINE = "Line-Feed"
        else:
            error_message(
                "End of Line provided via configuration is not " "CRLF nor LF",
                setup=self.setup,
            )

        self.BUNDLE_DESCRIPTION_LID = f"{setup.logical_identifier}:document:spiceds"

        if hasattr(self.setup, "creation_date_time"):
            creation_dt = self.setup.creation_date_time
            self.PRODUCT_CREATION_TIME = creation_dt
            self.PRODUCT_CREATION_DATE = creation_dt.split("T")[0]
            self.PRODUCT_CREATION_YEAR = creation_dt.split("-")[0]
        else:
            self.PRODUCT_CREATION_TIME = product.creation_time
            self.PRODUCT_CREATION_DATE = product.creation_date
            self.PRODUCT_CREATION_YEAR = product.creation_date.split("-")[0]

        self.FILE_SIZE = product.size
        self.FILE_CHECKSUM = product.checksum

        try:
            self.PDS4_MISSION_LID = product.collection.bundle.lid_reference
        except:
            self.PDS4_MISSION_LID = product.bundle.lid_reference

        #
        # For labels that need to include all observers and targets of the
        # setup.
        #
        if (
            type(self).__name__ != "SpiceKernelPDS4Label"
            and type(self).__name__ != "MetaKernelPDS4Label"
            and type(self).__name__ != "OrbnumFilePDS4Label"
        ):
            #
            # Obtain all observers.
            #
            obs = ["{}".format(self.setup.observer)]

            if hasattr(self.setup, "secondary_observers"):
                sec_obs = self.setup.secondary_observers
                if not isinstance(sec_obs, list):
                    sec_obs = [sec_obs]
            else:
                sec_obs = []

            self.observers = obs + sec_obs

            #
            # Obtain all targets.
            #
            tar = [self.setup.target]

            if hasattr(self.setup, "secondary_targets"):
                sec_tar = self.setup.secondary_targets
                if not isinstance(sec_tar, list):
                    sec_tar = [sec_tar]
            else:
                sec_tar = []

            self.targets = tar + sec_tar
        else:
            self.observers = product.observers
            self.targets = product.targets

        self.OBSERVERS = self.__get_observers()
        self.TARGETS = self.__get_targets()

    def __get_observers(self):

        obs = self.observers
        if not isinstance(obs, list):
            obs = [obs]

        obs_list_for_label = ""

        try:
            context_products = self.product.collection.bundle.context_products
        except:
            context_products = self.product.bundle.context_products

        eol = self.setup.eol_pds4

        for ob in obs:
            if ob:
                ob_lid = ""
                ob_name = ob.split(",")[0]
                for product in context_products:
                    if product["name"][0] == ob_name and (
                        product["type"][0] == "Spacecraft"
                        or product["type"][0] == "Rover"
                    ):
                        ob_lid = product["lidvid"].split("::")[0]

                if not ob_lid:
                    error_message(
                        f"LID has not been obtained for observer " f"{ob}",
                        setup=self.setup,
                    )

                obs_list_for_label += (
                    f"      <Observing_System_Component>{eol}"
                    + f"        <name>{ob_name}</name>{eol}"
                    + f"        <type>Spacecraft</type>{eol}"
                    + f"        <Internal_Reference>{eol}"
                    + f"          <lid_reference>{ob_lid}"
                    f"</lid_reference>{eol}"
                    + "          <reference_type>is_instrument_host"
                    f"</reference_type>{eol}"
                    + f"        </Internal_Reference>{eol}"
                    + f"      </Observing_System_Component>{eol}"
                )

        if not obs_list_for_label:
            error_message(
                f"{self.product.name} observers not defined", setup=self.setup
            )
        obs_list_for_label = obs_list_for_label.rstrip() + eol

        return obs_list_for_label

    def __get_targets(self):

        tars = self.targets
        if not isinstance(tars, list):
            tars = [tars]

        tar_list_for_label = ""

        try:
            context_products = self.product.collection.bundle.context_products
        except:
            context_products = self.product.bundle.context_products

        eol = self.setup.eol_pds4

        for tar in tars:
            if tar:

                target_name = tar
                for product in context_products:
                    if product["name"][0].upper() == target_name.upper():
                        target_lid = product["lidvid"].split("::")[0]
                        target_type = product["type"][0].capitalize()

                tar_list_for_label += (
                    f"    <Target_Identification>{eol}"
                    + f"      <name>{target_name}</name>{eol}"
                    + f"      <type>{target_type}</type>{eol}"
                    + f"      <Internal_Reference>{eol}"
                    + f"        <lid_reference>{target_lid}"
                    f"</lid_reference>{eol}" + f"        <reference_type>"
                    f"{self.get_target_reference_type()}"
                    f"</reference_type>{eol}"
                    + f"      </Internal_Reference>{eol}"
                    + f"    </Target_Identification>{eol}"
                )

        if not tar_list_for_label:
            error_message(f"{self.product.name} targets not defined", setup=self.setup)
        tar_list_for_label = tar_list_for_label.rstrip() + eol

        return tar_list_for_label

    def get_target_reference_type(self):

        if self.product.collection.name == "miscellaneous":
            type = "ancillary_to_target"
        else:
            type = "data_to_target"

        return type

    def write_label(self):

        label_dictionary = vars(self)

        label_extension = ".xml"

        if not ".xml" in self.product.path:
            label_name = (
                self.product.path.split(f".{self.product.extension}")[0]
                + label_extension
            )
        else:
            #
            # This accounts for the bundle label, that doest not come
            # from the bundle product itself.
            #
            label_name = self.product.path

        if "inventory" in label_name:
            label_name = label_name.replace("inventory_", "")

        with open(label_name, "w+") as f:

            for line in fileinput.input(self.template):
                line = line.rstrip()
                for key, value in label_dictionary.items():
                    if isinstance(value, str) and key in line and "$" in line:
                        line = line.replace("$" + key, value)

                line = add_carriage_return(line, self.setup.eol_pds4)

                f.write(line)

        self.name = label_name

        stag_dir = self.setup.staging_directory
        logging.info(f'-- Created {label_name.split(f"{stag_dir}{os.sep}")[-1]}')
        if not self.setup.args.silent and not self.setup.args.verbose:
            print(f'   * Created {label_name.split(f"{stag_dir}{os.sep}")[-1]}.')

        #
        # Add label to the list of generated files.
        #
        self.setup.add_file(label_name.split(f"{stag_dir}{os.sep}")[-1])

        if self.setup.diff:
            self.compare()

        logging.info("")

        return

    def write_pds3_labels(self):

        return None

    def compare(self):
        """
        The label is compared to a similar label from the previous release
        of the archive.

        For new archives a 'similar' archive is used.
        :return:
        """

        logging.info(f"-- Comparing label...")

        #
        # 1-Look for a different version of the same file.
        #
        # What we do is that we keep trying to match the label name
        # advancing one character each iteration, in such a way that
        # we find, in order, the label that has the closest name to the
        # one we are generating.
        #
        val_label = ""
        try:

            match_flag = True
            val_label_path = (
                self.setup.final_directory
                + f"/{self.setup.mission_acronym}_spice/"
                + self.product.collection.name
                + os.sep
            )

            #
            # If this is the spice_kernels collection, we need to add the
            # kernel type directory. If it is the miscellaneous collection,
            # add the product type.
            #
            if (self.product.collection.name == "spice_kernels") and (
                "collection" not in self.name
            ):
                val_label_path += self.name.split(os.sep)[-2] + os.sep
            elif (self.product.collection.name == "miscellaneous") and (
                "collection" not in self.name
            ):
                val_label_path += self.name.split(os.sep)[-2] + os.sep

            val_label_name = self.name.split(os.sep)[-1]
            i = 1

            while match_flag:
                if i < len(val_label_name) - 1:
                    val_labels = glob.glob(
                        f"{val_label_path}{val_label_name[0:i]}" f"*.xml"
                    )
                    if val_labels:
                        val_labels = sorted(val_labels)
                        val_label = val_labels[-1]
                        match_flag = True
                    else:
                        match_flag = False
                    i += 1

            if not val_label:
                raise Exception("No label for comparison found.")

        except:
            logging.warning(
                f"-- No other version of the product label has " f"been found."
            )

            #
            # 2-If a prior version of the same file cannot be found look for
            #   the label of a product of the same type.
            #
            try:
                val_label_path = (
                    self.setup.final_directory
                    + f"/{self.setup.mission_acronym}_spice/"
                    + self.product.collection.name
                    + os.sep
                )

                #
                # If this is the spice_kernels collection, we need to add the
                # kernel type directory.
                #
                if (self.product.collection.name == "spice_kernels") and (
                    "collection" not in self.name
                ):
                    val_label_path += self.name.split(os.sep)[-2] + os.sep
                elif (self.product.collection.name == "miscellaneous") and (
                    "collection" not in self.name
                ):
                    val_label_path += self.name.split(os.sep)[-2] + os.sep

                product_extension = self.product.name.split(".")[-1]
                val_products = glob.glob(f"{val_label_path}*." f"{product_extension}")
                val_products.sort()

                #
                # Simply pick the last one
                #
                if "collection" in self.name.split(os.sep)[-1]:
                    val_label = glob.glob(
                        val_products[-1].replace("inventory_", "").split(".")[0]
                        + ".xml"
                    )[0]
                elif "bundle" in self.name.split(os.sep)[-1]:
                    val_labels = glob.glob(f"{val_label_path}bundle_*.xml")
                    val_labels.sort()
                    val_label = val_labels[-1]
                else:
                    val_label = glob.glob(val_products[-1].split(".")[0] + ".xml")[0]

                if not val_label:
                    raise Exception("No label for comparison found.")

            except:

                logging.warning(f"-- No similar label has been found.")
                #
                # 3-If we cannot find a kernel of the same type; for example
                #   is a first version of an archive, we compare with
                #   a label available in the test data directories.
                #
                try:
                    val_label_path = (
                        f"{self.setup.root_dir}"
                        f"tests/data/regression/"
                        f"insight_spice/"
                        f"{self.product.collection.name}/"
                    )

                    #
                    # If this is the spice_kernels collection, we need to
                    # add the kernel type directory.
                    #
                    if (self.product.collection.name == "spice_kernels") and (
                        "collection" not in self.name
                    ):
                        val_label_path += self.name.split(os.sep)[-2] + os.sep
                    elif (self.product.collection.name == "miscellaneous") and (
                        "collection" not in self.name
                    ):
                        val_label_path += self.name.split(os.sep)[-2] + os.sep

                    #
                    # Simply pick the last one
                    #
                    product_extension = self.product.name.split(".")[-1]
                    val_products = glob.glob(f"{val_label_path}*.{product_extension}")
                    val_products.sort()

                    if "collection" in self.name.split(os.sep):
                        val_label = glob.glob(
                            val_products[-1].replace("inventory_", "").split(".")[0]
                            + ".xml"
                        )[0]
                    elif "bundle" in self.name.split(os.sep):
                        val_labels = glob.glob(f"{val_label_path}bundle_*.xml")
                        val_labels.sort()
                        val_label = val_labels[-1]
                    else:
                        val_label = glob.glob(val_products[-1].split(".")[0] + ".xml")[
                            0
                        ]

                    if not val_label:
                        raise Exception("No label for comparison found.")

                    logging.warning("-- Comparing with InSight test label.")
                except:
                    logging.warning("-- No label for comparison found.")

        #
        # If a similar label has been found the labels are compared and a
        # diff is being shown in the log. On top of that an HTML file with
        # the comparison is being generated.
        #
        if val_label:
            logging.info("")
            fromfile = val_label
            tofile = self.name
            dir = self.setup.working_directory

            compare_files(fromfile, tofile, dir, self.setup.diff)

        return


class BundlePDS4Label(PDSLabel):
    def __init__(self, setup, readme):

        PDSLabel.__init__(self, setup, readme)

        self.template = f"{setup.templates_directory}/template_bundle.xml"

        self.BUNDLE_LID = self.product.bundle.lid
        self.BUNDLE_VID = self.product.bundle.vid

        self.AUTHOR_LIST = setup.author_list
        self.START_TIME = setup.increment_start
        self.STOP_TIME = setup.increment_finish
        self.FILE_NAME = readme.name
        self.DOI = self.setup.doi
        self.BUNDLE_MEMBER_ENTRIES = ""

        eol = self.setup.eol_pds4

        #
        # There might be more than one miscellaneous collection added in
        # an increment (especially if it is the first time that the collection
        # is generated and there have beeen previous releases.)
        for collection in self.product.bundle.collections:
            if collection.name == "spice_kernels":
                self.COLL_NAME = "spice_kernel"
                self.COLL_LIDVID = collection.lid + "::" + collection.vid
                if collection.updated:
                    self.COLL_STATUS = "Primary"
                else:
                    self.COLL_STATUS = "Secondary"
            if collection.name == "miscellaneous":
                self.COLL_NAME = "member"
                self.COLL_LIDVID = collection.lid + "::" + collection.vid
                if collection.updated:
                    self.COLL_STATUS = "Primary"
                else:
                    self.COLL_STATUS = "Secondary"
            if collection.name == "document":
                self.COLL_NAME = "document"
                self.COLL_LIDVID = collection.lid + "::" + collection.vid
                if collection.updated:
                    self.COLL_STATUS = "Primary"
                else:
                    self.COLL_STATUS = "Secondary"

            self.BUNDLE_MEMBER_ENTRIES += (
                f"  <Bundle_Member_Entry>{eol}"
                f"    <lidvid_reference>"
                f"{self.COLL_LIDVID}</lidvid_reference>{eol}"
                f"    <member_status>"
                f"{self.COLL_STATUS}</member_status>{eol}"
                f"    <reference_type>"
                f"bundle_has_{self.COLL_NAME}_collection"
                f"</reference_type>{eol}"
                f"  </Bundle_Member_Entry>{eol}"
            )

        self.write_label()

        return

    def get_target_reference_type(self):
        return "bundle_to_target"


class SpiceKernelPDS4Label(PDSLabel):
    def __init__(self, mission, product):
        PDSLabel.__init__(self, mission, product)

        self.template = (
            f"{self.setup.templates_directory}/" f"template_product_spice_kernel.xml"
        )

        #
        # Fields from Kernels
        #
        self.FILE_NAME = product.name
        self.PRODUCT_LID = self.product.lid
        self.FILE_FORMAT = product.file_format
        self.START_TIME = product.start_time
        self.STOP_TIME = product.stop_time
        self.KERNEL_TYPE_ID = product.type.upper()
        self.PRODUCT_VID = self.product.vid
        self.SPICE_KERNEL_DESCRIPTION = product.description

        extension = ".xml"
        self.name = product.name.split(".")[0] + extension

        self.write_label()


class MetaKernelPDS4Label(PDSLabel):
    def __init__(self, setup, product):
        PDSLabel.__init__(self, setup, product)

        self.template = (
            f"{setup.templates_directory}/" f"template_product_spice_kernel_mk.xml"
        )

        #
        # Fields from Kernels
        #
        self.FILE_NAME = product.name
        self.PRODUCT_LID = self.product.lid
        self.FILE_FORMAT = "Character"
        self.START_TIME = product.start_time
        self.STOP_TIME = product.stop_time
        self.KERNEL_TYPE_ID = product.type.upper()
        self.PRODUCT_VID = self.product.vid
        self.SPICE_KERNEL_DESCRIPTION = product.description

        self.KERNEL_INTERNAL_REFERENCES = self.get_kernel_internal_references()

        self.name = product.name.split(".")[0] + ".xml"

        self.write_label()

    def get_kernel_internal_references(self):

        eol = self.setup.eol_pds4

        #
        # From the collection we only use kernels in the MK
        #
        kernel_list_for_label = ""
        for kernel in self.product.collection_metakernel:
            #
            # The kernel lid cannot be obtained from the list; it is
            # merely a list of strings.
            #
            kernel_type = extension2type(kernel)
            kernel_lid = "{}:spice_kernels:{}_{}".format(
                self.setup.logical_identifier, kernel_type, kernel
            )

            kernel_list_for_label += (
                f"    <Internal_Reference>{eol}" + f"      <lid_reference>{kernel_lid}"
                f"</lid_reference>{eol}" + f"      <reference_type>data_to_associate"
                f"</reference_type>{eol}" + f"    </Internal_Reference>{eol}"
            )

        kernel_list_for_label = kernel_list_for_label.rstrip() + eol

        return kernel_list_for_label


class OrbnumFilePDS4Label(PDSLabel):
    def __init__(self, setup, product):
        PDSLabel.__init__(self, setup, product)

        self.template = (
            f"{setup.templates_directory}/" f"template_product_orbnum_table.xml"
        )

        #
        # Fields from orbnum object.
        #
        self.FILE_NAME = product.name
        self.PRODUCT_LID = self.product.lid
        self.PRODUCT_VID = self.product.vid
        self.FILE_FORMAT = "Character"
        self.START_TIME = product.start_time
        self.STOP_TIME = product.stop_time
        self.DESCRIPTION = product.description
        self.HEADER_LENGTH = str(product.header_length)
        self.TABLE_CHARACTER_DESCRIPTION = product.table_char_description

        #
        # The orbnum table data starts one byte after the header section.
        #
        self.TABLE_OFFSET = str(product.header_length + 1)

        self.TABLE_RECORDS = str(product.records)

        #
        # The ORBNUM utility produces an information ground set regardless
        # of the parameters listed in ORBIT_PARAMS. This set consists of 4
        # parameters.
        #
        self.NUMBER_OF_FIELDS = str(len(product.params.keys()))
        self.FIELDS_LENGTH = str(product.record_fixed_length + 1)
        self.FIELDS = self.__get_table_character_fields()

        if self.TABLE_CHARACTER_DESCRIPTION:
            self.TABLE_CHARACTER_DESCRIPTION = self.__get_table_character_description()

        self.name = product.name.split(".")[0] + ".xml"

        self.write_label()

    def __get_table_character_fields(self):

        fields = ""
        for param in self.product.params.values():
            field = self.__field_template(
                param["name"],
                param["number"],
                param["location"],
                param["type"],
                param["length"],
                param["format"],
                param["description"],
                param["unit"],
                self.product.blank_records,
            )
            fields += field

        return fields

    def __get_table_character_description(self):

        description = (
            f"{self.setup.eol_pds4}      <description>"
            f"{self.product.table_char_description}"
            f"</description>{self.setup.eol_pds4}"
        )

        return description

    def __field_template(
        self, name, number, location, type, length, format, description, unit, blanks
    ):

        eol = self.setup.eol_pds4

        field = (
            f'{" " * 8}<Field_Character>{eol}'
            f'{" " * 8}  <name>{name}</name>{eol}'
            f'{" " * 8}  <field_number>{number}</field_number>{eol}'
            f'{" " * 8}  <field_location unit="byte">{location}'
            f"</field_location>{eol}"
            f'{" " * 8}  <data_type>{type}</data_type>{eol}'
            f'{" " * 8}  <field_length unit="byte">{length}'
            f"</field_length>{eol}"
            f'{" " * 8}  <field_format>{format}</field_format>{eol}'
        )
        if unit:
            field += f'{" " * 8}  <unit>{unit}</unit>{eol}'
        field += f'{" " * 8}  <description>{description}</description>{eol}'
        if blanks and name != "No.":
            field += (
                f'{" " * 8}  <Special_Constants>{eol}'
                f'{" " * 8}    <missing_constant>blank space'
                f"</missing_constant>{eol}"
                f'{" " * 8}  </Special_Constants>{eol}'
            )
        field += f'{" " * 8}</Field_Character>{eol}'

        return field


class InventoryPDS4Label(PDSLabel):
    def __init__(self, setup, collection, inventory):
        PDSLabel.__init__(self, setup, inventory)

        self.collection = collection
        self.template = (
            f"{setup.templates_directory}/" f"template_collection_{collection.type}.xml"
        )

        self.COLLECTION_LID = self.collection.lid
        self.COLLECTION_VID = self.collection.vid

        #
        # The start and stop time of the miscellaneous collection
        # differs from the SPICE kernels collection; the document
        # collection does not have start and stop times.
        #
        if collection.name == "miscellaneous":
            #
            # Obtain the latest checksum product and extract the start and stop
            # times.
            #
            start_times = []
            stop_times = []
            for product in collection.product:
                if "checksum" in product.name:
                    start_times.append(product.start_time)
                    stop_times.append(product.stop_time)
            start_times.sort()
            stop_times.sort()

            self.START_TIME = start_times[0]
            self.STOP_TIME = stop_times[-1]

        else:
            #
            # The increment start and stop times are still defined by the
            # spice_kernels collection.
            #
            self.START_TIME = setup.increment_start
            self.STOP_TIME = setup.increment_finish

        self.FILE_NAME = inventory.name

        # Count number of lines in the inventory file
        f = open(self.product.path)
        self.N_RECORDS = str(len(f.readlines()))
        f.close()

        self.name = collection.name.split(".")[0] + ".xml"

        self.write_label()

    def get_target_reference_type(self):
        return "collection_to_target"


class InventoryPDS3Label(PDSLabel):
    def __init__(self, setup, collection, inventory):

        PDSLabel.__init__(self, setup, inventory)

        self.collection = collection
        self.template = self.root_dir + "/templates/template_collection_{}.LBL".format(
            collection.type
        )

        self.VOLUME = setup.volume
        self.PRODUCT_CREATION_TIME = current_time(setup.date_format)
        self.DATASET = setup.dataset

        indexfile = open(setup.bundle_directory + "/INDEX/INDEX.TAB", "r").readlines()
        self.N_RECORDS = str(len(indexfile))
        self.R_RECORDS = str(len(indexfile[0]) + 1)
        indexfields = indexfile[0].replace('"', "").split(",")
        self.START_BYTE1 = str(2)
        self.START_BYTE2 = str(2 + len(indexfields[0]) + 3)
        self.START_BYTE3 = str(2 + len(indexfields[0]) + 3 + len(indexfields[1]) + 2)
        self.START_BYTE4 = str(
            2
            + len(indexfields[0])
            + 3
            + len(indexfields[1])
            + 2
            + len(indexfields[2])
            + 2
        )
        self.BYTES1 = str(len(indexfields[0]))
        self.BYTES2 = str(len(indexfields[1]))
        self.BYTES3 = str(len(indexfields[2]))
        self.BYTES4 = str(len(indexfields[3].split("\n")[0]))

        self.write_label()

    def write_label(self):

        label_dictionary = vars(self)

        with open(self.setup.bundle_directory + "/INDEX/INDEX.LBL", "w+") as f:

            for line in fileinput.input(self.template):
                line = line.rstrip()
                for key, value in label_dictionary.items():
                    if isinstance(value, str) and key in line and "$" in line:
                        line = line.replace("$" + key, value)

                line = add_carriage_return(line, self.setup.eol_pds4)

                if "END_OBJECT" in line and line[:10] != "END_OBJECT":
                    f.write(line.split("END_OBJECT")[0])
                    f.write("END_OBJECT               = COLUMN\n")
                else:
                    f.write(line)

        self.name = "INDEX.LBL"

        return


class DocumentPDS4Label(PDSLabel):
    def __init__(self, setup, collection, inventory):
        PDSLabel.__init__(self, setup, inventory)

        self.setup = setup
        self.collection = collection
        self.template = (
            f"{setup.templates_directory}/" f"template_product_html_document.xml"
        )

        self.PRODUCT_LID = inventory.lid
        self.PRODUCT_VID = inventory.vid
        self.START_TIME = setup.mission_start
        self.STOP_TIME = setup.mission_finish
        self.FILE_NAME = inventory.name

        self.name = collection.name.split(".")[0] + ".xml"

        self.write_label()


class ChecksumPDS4Label(PDSLabel):
    def __init__(self, setup, product):
        PDSLabel.__init__(self, setup, product)

        self.template = (
            f"{setup.templates_directory}/" f"template_product_checksum_table.xml"
        )

        self.FILE_NAME = product.name
        self.PRODUCT_LID = self.product.lid
        self.PRODUCT_VID = self.product.vid
        self.FILE_FORMAT = "Character"
        self.START_TIME = self.product.start_time
        self.STOP_TIME = self.product.stop_time

        self.name = product.name.split(".")[0] + ".xml"

        self.write_label()