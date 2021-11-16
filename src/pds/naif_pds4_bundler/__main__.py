"""NAIF PDS4 Bundler Main Module.

Execute NPB from the command line as follows::

  usage: naif-pds4-bundler [-h] [-p PLAN] [-f FAUCET] [-l] [-s] [-v] [-d DIFF]
                           [-c CLEAR] [-k KERLIST] CONFIG [CONFIG ...]

  naif-pds4-bundler-0.12.0, NAIF PDS4 SPICE archive generation pipeline

    naif-pds4-bundler is a command-line utility program that generates PDS4
    bundles and PDS3 data sets for SPICE archives.

  positional arguments:
    CONFIG                XML Configuration file

  optional arguments:
    -h, --help            show this help message and exit
    -p PLAN, --plan PLAN  Release plan file listing the kernels to be archived.
                          If this argument is not provided, all the kernels
                          found  in the kernels directory specified in the
                          configuration file in addition to new meta-kernels
                          will be included in the increment.
    -f FAUCET, --faucet FAUCET
                          Optional indication for end point of the pipeline.
                          Allowed values are: 'clear', 'plan', 'list',
                          'staging', or 'bundle'.
    -l, --log             Write log in file
    -s, --silent          Log will not be prompted on the terminal during
                          execution.
    -v, --verbose         Full log will be prompted on the terminal during
                          execution. If argument is set to True, silent argument
                          is omitted.
    -d DIFF, --diff DIFF  Optional generation of diff reports for products.
                          Allowed values are: 'files', 'log' or 'all'.
    -c CLEAR, --clear CLEAR
                          Clears the files listed in the input file from the
                          staging and bundle directories and the kernel list from the
                          working directory. The inputfile should be as generated by
                          a prior execution with a *.file_list extension. This
                          argument does not start the pipeline afterwards. If
                          this argument is provided it overwrites the faucet
                          argument to 'plan'
    -k KERLIST, --kerlist KERLIST
                          Release plan file listing the kernels to be archived
                          along with some parameters required for the run.
                          If this argument isprovided the release plan is not
                          generated.

"""
from argparse import ArgumentParser
from argparse import RawDescriptionHelpFormatter
from os.path import isdir
from textwrap import dedent

from . import __version__
from .classes.bundle import Bundle
from .classes.collection import DocumentCollection
from .classes.collection import MiscellaneousCollection
from .classes.collection import SpiceKernelsCollection
from .classes.list import KernelList
from .classes.log import Log
from .classes.object import Object
from .classes.product import ChecksumProduct
from .classes.product import InventoryProduct
from .classes.product import MetaKernelProduct
from .classes.product import OrbnumFileProduct
from .classes.product import SpicedsProduct
from .classes.product import SpiceKernelProduct
from .classes.setup import Setup


def main(
    config=False,
    plan=False,
    faucet="",
    log=False,
    silent=False,
    verbose=False,
    diff="",
    debug=True,
    clear="",
    kerlist="",
):
    """Main routine for the NAIF PDS4 Bundler.

    This routine gets the command line arguments or the parameter
    arbuments and runs the archive generation pipeline.

    :param config: XML Configuration file
    :param plan: Release plan file listing the kernels to be archived.
                 If this argument is not provided, all the kernels found in
                 the kernels directory specified in the configuration file
                 in addition to new meta-kernels will be included in the
                 increment
    :type plan: str
    :param faucet: Optional indication for end point of the pipeline.
                   Allowed values are: 'clear', 'plan', 'list', 'staging',
                   or 'bundle'
    :type faucet: str
    :param log: Write log in file
    :type log: bool
    :param silent: Log will not be prompted on the terminal during execution
    :type silent: bool
    :param verbose: Full log will be prompted on the terminal  during
                    execution. If argument is set to True, silent argument
                    is omitted
    :type verbose: bool
    :param diff: Optional generation of diff reports for products. Allowed
                 values are: 'files', 'log' or 'all'
    :type diff: str
    :param debug: Indicate whether if the pipeline is running in debug mode.
                  If so the format of the logging is different and the files
                  generated in a failed run are not cleaned up.
    :type debug: bool
    :param clear: Indicates if the pipeline will run only to clear previous
    run and specifies the file that indicates the files to be cleared.
    :type clear: str
    :param kerlist: Release list file listing the kernels to be archived along
                 with their description.
    :type kerlist: str
    """
    #
    # Load the naif-pds4-bundler version
    #
    version = __version__

    #
    # Determine whether if the pipeline is being executed directly from
    # the command line of called by another Python function. If this is
    # not the case, then the arguments are taken from the command line.
    #
    if not config and not plan:

        header = dedent(
            f"""\

    naif-pds4-bundler-{version}, NAIF PDS4 SPICE archive generation pipeline

      naif-pds4-bundler is a command-line utility program that generates PDS4
      bundles for SPICE kernel archives.
        """
        )

        #
        # Build the argument parser.
        #
        parser = ArgumentParser(
            formatter_class=RawDescriptionHelpFormatter, description=header
        )
        parser.add_argument(
            "config",
            metavar="CONFIG",
            type=str,
            nargs="+",
            help="XML Configuration file",
        )
        parser.add_argument(
            "-p",
            "--plan",
            action="store",
            type=str,
            help="Release plan file listing the kernels and/or "
            "ORBNUM files to be archived. If this argument is not "
            "provided, all the kernels found in the "
            "kernels directory specified in the "
            "configuration file in addition to new "
            "meta-kernels will be included in the "
            "increment. If the ``-x --xml`` argument is used "
            "this argument can be the name of a kernel or the path "
            "to a release plan file (ORBNUM files will be ignored.)",
        )
        parser.add_argument(
            "-f",
            "--faucet",
            default="",
            action="store",
            type=str,
            help="Optional indication for end point of the "
            "pipeline. Allowed values are: 'clear', "
            "'plan', 'list', 'staging', 'bundle', and 'labels'.",
        )
        parser.add_argument(
            "-l", "--log", help="Write log in file", action="store_true"
        )
        parser.add_argument(
            "-s",
            "--silent",
            help="Log will not be prompted on the terminal during execution.",
            action="store_true",
        )
        parser.add_argument(
            "-v",
            "--verbose",
            help="Full log will be prompted on the terminal "
            "during execution. If the argument is provided "
            "the ``-s, --silent`` argument is omitted.",
            action="store_true",
        )
        parser.add_argument(
            "-d",
            "--diff",
            default="",
            action="store",
            type=str,
            help="Optional generation of diff reports for "
            "products. Allowed values are: 'files', 'log', and 'all'.",
        )
        parser.add_argument(
            "-c",
            "--clear",
            default="",
            action="store",
            type=str,
            help="Clears the files listed in the input file "
            "from the staging and bundle directories and the "
            "kernel list from the working directory. The input "
            "file should be as generated by a prior "
            "execution with a *.file_list extension. "
            "If this argument is provided "
            "it overwrites the faucet argument to 'clear' "
            "and therefore the pipeline is not exectued. "
            "If you provide the adequate ``-f, --faucet`` argument, the "
            "pipeline will be executed until indicated.",
        )
        parser.add_argument(
            "-k",
            "--kerlist",
            action="store",
            type=str,
            help="Release plan file listing the kernels to "
            "be archived along with some parameters "
            "required for the run. If this argument is "
            "provided the release plan is not generated.",
        )

        #
        # Store the arguments in the args object.
        #
        args = parser.parse_args()
        args.config = args.config[0]

        #
        # When executing from the command line, debug mode is not available.
        #
        args.debug = False

    #
    # If NPB is not executed from the command line then an args object is
    # initialised and the argument attributes are obtained from the
    # main function argument list.
    #
    else:
        args = Object()
        args.config = config
        args.plan = plan
        args.faucet = faucet
        args.log = log
        args.silent = silent
        args.verbose = verbose
        args.diff = diff
        args.debug = debug
        args.clear = clear
        args.kerlist = kerlist

    #
    # Turn lowercase or uppercase arguments that need it.
    #
    args.faucet = args.faucet.lower()
    args.diff = args.diff.lower()

    #
    # Set silent to False if verbose is set to True.
    #
    if args.verbose:
        args.silent = False

    #
    # Force logging if Diff files are provided with the log.
    #
    if args.diff == "log" or args.diff == "all":
        args.log = True

    #
    # Set faucet to plan if clear is provided.
    #
    if args.clear and not args.faucet:
        args.faucet = "clear"

    #
    # Check if string optional parameters are correct.
    #
    if args.diff not in ["all", "log", "files", ""]:
        raise Exception("-d, --diff argument has incorrect value.")
    if args.faucet not in ["clear", "plan", "list", "staging", "bundle", "labels", ""]:
        raise Exception("-f, --faucet argument has incorrect value.")

    #
    # The pipeline execution per se starts now.
    #
    # * Generate the Setup object
    #     * This object will be used by all the other objects
    #     * Parse JSON into an object with attributes corresponding
    #       to dict keys.
    #
    setup = Setup(args, version)

    #
    # * Start the Log object
    #    * The log will always be displayed on screen unless the silent
    #      option is chosen.
    #    * The log file will be written in the working directory
    #
    log = Log(setup, args)

    #
    # Indicate the Log object to start recording the output.
    #
    log.start()

    #
    # Add the log to the setup object with the sole purpose for the log
    # to be accessible via setup to be able to write the product list file
    # for an interrupted run.
    #
    setup.log = log

    #
    # With the log started we check the current configuration
    #
    setup.check_configuration()

    #
    # * Check the existence of a previous archive version.
    #
    setup.set_release()

    #
    # * If the pipeline is running to clean-up a previous run, remove all the
    #   files in the bundle and staging area indicated by the file list and
    #   clean-up the kernel list and log from the previous run.
    #
    if args.clear:
        setup.clear_run()

    #
    #    * The pipeline can be stopped after cleaning up the previous run
    #      by setting ``-f, --faucet`` to ``clear``.
    #
    if setup.faucet == "clear":
        log.stop()
        return

    #
    # * Generate the Kernel List object.
    #
    list = KernelList(setup)

    #
    #    * If a plan file is provided it is processed otherwise a plan is
    #      generated from the kernels directory.
    #
    #    * If NPB is run in label generation mode and no input products are
    #      found, stop the execution.
    #
    if not args.kerlist:
        if not args.plan or (".plan" not in args.plan):
            if not list.write_plan() and (args.faucet == "labels"):
                return
        else:
            list.read_plan(args.plan)

    #
    #    * The pipeline can be stopped after generating or reading the release
    #      plan by setting ``-f, --faucet`` to ``plan``.
    #
    if setup.faucet == "plan":
        log.stop()
        return

    if not args.kerlist:
        list.write_list()
    else:
        list.read_list(args.kerlist)

    #
    #    * The pipeline can be stopped after generating or reading the kernel
    #      list plan by setting ``-f, --faucet`` to ``list``.
    #
    if setup.faucet == "list":
        log.stop()
        return

    #
    # * Generate the PDS4 Bundle structure.
    #
    bundle = Bundle(setup)

    #
    # * Load LSK, FK and SCLK kernels for time conversions and coverage
    #   computations.
    #
    setup.load_kernels()

    #
    # * Initialise the SPICE Kernels Collection.
    #
    spice_kernels_collection = SpiceKernelsCollection(setup, bundle, list)

    #
    # * Initialise the Miscellaneous Collection.
    #
    miscellaneous_collection = MiscellaneousCollection(setup, bundle, list)

    #
    # * Generate the labels for each SPICE kernel or ORBNUM product and
    #   populate the SPICE kernels collection or the Miscellaneous collection
    #   accordingly.
    #
    for kernel in list.kernel_list:
        #
        # * Each label is validated after generation.
        #
        if (".nrb" in kernel.lower()) or (".orb" in kernel.lower()):
            #
            # The OrbnumFileProduct has to be provided the kernels collection
            # because it might require to update the kernel list if the
            # orbnum file name is updated.
            #
            miscellaneous_collection.add(
                OrbnumFileProduct(
                    setup, kernel, miscellaneous_collection, spice_kernels_collection
                )
            )
        elif ".tm" not in kernel.lower():
            spice_kernels_collection.add(
                SpiceKernelProduct(setup, kernel, spice_kernels_collection)
            )

    #
    # * Generate the Meta-kernel(s).
    #
    (meta_kernels, user_input) = spice_kernels_collection.determine_meta_kernels()
    if meta_kernels:
        for mk in meta_kernels:
            meta_kernel = MetaKernelProduct(
                setup, mk, spice_kernels_collection, user_input=user_input
            )
            spice_kernels_collection.add(meta_kernel)

    #
    # * Faucet for labeling mode.
    #
    if args.faucet == "labels":

        #
        # * Add the SPICE Kernels Collection to the Bundle.
        #
        bundle.add(spice_kernels_collection)

        #
        # * List the files present in the staging area.
        #
        bundle.files_in_staging()

        #
        # * Copy files to the bundle area.
        #
        bundle.copy_to_bundle()

        log.stop()
        return

    #
    # * Determine the SPICE kernels Collection increment times and VID.
    #
    spice_kernels_collection.set_increment_times()
    spice_kernels_collection.set_collection_vid()

    #
    # * Validate the SPICE Kernels collection:
    #    * Note the validation of products is performed after writing the
    #      product itself and therefore it is not explicitly executed
    #      from at object initialization.
    #    * Check that there is a XML label for each file under spice_kernels.
    #
    spice_kernels_collection.validate()

    #
    # *  Generate the SPICE Kernels Collection Inventory product (if the
    #    collection has been updated.)
    #
    if spice_kernels_collection.updated:

        spice_kernels_collection.set_collection_vid()
        spice_kernels_collection_inventory = InventoryProduct(
            setup, spice_kernels_collection
        )
        spice_kernels_collection.add(spice_kernels_collection_inventory)

    #
    # * Generate the Document Collection.
    #
    document_collection = DocumentCollection(setup, bundle)
    document_collection.set_collection_vid()

    #
    # * Generate of SPICEDS document.
    #
    if setup.pds_version == "4":

        spiceds = SpicedsProduct(setup, document_collection)

        #
        # * If the SPICEDS document is generated, generate the
        #   Documents Collection Inventory.
        #
        if spiceds.generated:
            document_collection.add(spiceds)

            document_collection.set_collection_vid()
            document_collection_inventory = InventoryProduct(setup, document_collection)
            document_collection.add(document_collection_inventory)

        #
        # * Add the SPICE Kernels Collection to the Bundle.
        #   Note that the Collections are provided to the Bundle Object
        #   in a given order.
        #
        bundle.add(spice_kernels_collection)

        #
        # * Generate the Miscellaneous collection. The Checksum product
        #   is initialised in such a way that its name can be obtained.
        #
        # * The first thing that is checked is whether if the current
        #   Bundle has checksums, if not, all the checksums are generated,
        #   including the corresponding Miscellaneous Collection Inventories
        #   and labels.
        #
        if setup.increment:
            checksum_dir = (
                setup.bundle_directory
                + f"/{setup.mission_acronym}_spice/miscellaneous/checksum"
            )
            if not isdir(checksum_dir):
                for release in bundle.history.items():
                    release_checksum = ChecksumProduct(setup, miscellaneous_collection)
                    release_checksum.generate(history=release)

                    #
                    # Initialise a miscellaneous collection for this previous
                    # release.
                    #
                    release_miscellaneous_collection = MiscellaneousCollection(
                        setup, bundle, list
                    )

                    #
                    # Add the checksum at the release miscellaneous collection
                    # to generate the adequate inventory file and add it to
                    # the current miscellaneous collection for it to be
                    # present at the checksum.
                    #
                    release_miscellaneous_collection.add(release_checksum)

                    miscellaneous_collection.add(release_checksum)

                    release_miscellaneous_collection.set_collection_vid()
                    release_miscellaneous_collection_inventory = InventoryProduct(
                        setup, release_miscellaneous_collection
                    )

                    release_miscellaneous_collection.add(
                        release_miscellaneous_collection_inventory
                    )
                    miscellaneous_collection.add(
                        release_miscellaneous_collection_inventory
                    )

                    #
                    # Add release miscellaneous collection.
                    #
                    bundle.add(release_miscellaneous_collection)

            #
            # * Set the Miscellaneous collection VID.
            #
            miscellaneous_collection.set_collection_vid()

        #
        # * Add the Miscellaneous and Document Collections to the Bundle object.
        #
        bundle.add(miscellaneous_collection)
        bundle.add(document_collection)

        #
        # * Generate Miscellaneous Collection and initialize the Checksum
        #   product for the current release.
        #    * The miscellaneous collection is the one to be guaranteed to be
        #      updated.
        #
        miscellaneous_collection.set_collection_vid()
        checksum = ChecksumProduct(setup, miscellaneous_collection)

        #
        # Before adding the checksum to the current collection
        # we need to specify that is not a new product.
        #
        for product in miscellaneous_collection.product:
            if type(product) == ChecksumProduct:
                product.new_product = False

        miscellaneous_collection.add(checksum)

        checksum.set_coverage()
        miscellaneous_collection_inventory = InventoryProduct(
            setup, miscellaneous_collection
        )
        miscellaneous_collection.add(miscellaneous_collection_inventory)

        #
        # * Generate the Bundle label and if necessary the readme file.
        #
        bundle.write_readme()

        #
        # * Generate the Checksum product a posteriori in such a way
        #   that the miscellaneous collection inventory includes the
        #   checksum and the checksum includes the md5 hash of the
        #   Miscellaneous Collection Inventory.
        #
        checksum.generate()
        miscellaneous_collection.add(checksum)

    elif setup.pds_version == "3":
        pass

    #
    # * List the files present in the staging area.
    #
    bundle.files_in_staging()

    #
    # * The pipeline can be stopped after generating the products and before
    #   moving them to the ``bundle_directory`` by setting ``-f, --faucet``
    #   to ``staging``.
    #
    if setup.faucet == "staging":
        log.stop()
        return

    #
    # Generate index files, this includes generating the complete
    # kernel list.
    #
    # OnlyFor PDS3
    # list.write_complete_list()
    # spice_kernels_collection_inventory.write_index()

    #
    # * Copy files to the bundle area.
    #
    bundle.copy_to_bundle()

    #
    # * The pipeline can be stopped after generating the moving the products
    #   ``bundle_directory`` by setting ``-f, --faucet``. Ch
    #   to ``bundle``.
    #
    if setup.faucet == "bundle":
        log.stop()
        return

    #
    # * Validate Meta-kernel(s).
    #
    for kernel in spice_kernels_collection.product:
        if type(kernel) == MetaKernelProduct:
            kernel.validate()

    #
    # * Validate Checksum files against the updated Bundle history.
    #
    bundle.validate_history()

    log.stop()

    return None


if __name__ == "__main__":
    main()
