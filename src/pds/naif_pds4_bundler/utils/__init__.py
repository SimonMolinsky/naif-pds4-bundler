"""NAIF PDS4 Bundle Utils Namespace.

The utils module implements general utility capabilities used elsewhere in NPB.
"""
from .files import add_carriage_return
from .files import add_crs_to_file
from .files import check_consecutive
from .files import check_list_duplicates
from .files import checksum_from_label
from .files import checksum_from_registry
from .files import compare_files
from .files import copy
from .files import etree_to_dict
from .files import extension2type
from .files import extract_comment
from .files import fill_template
from .files import get_context_products
from .files import get_latest_kernel
from .files import kernel_name
from .files import match_patterns
from .files import md5
from .files import mk2list
from .files import safe_make_directory
from .files import type2extension
from .files import utf8len
from .slicer import slice_kernels
from .time import ck_coverage
from .time import creation_time
from .time import current_date
from .time import current_time
from .time import dsk_coverage
from .time import get_years
from .time import pck_coverage
from .time import pds3_label_gen_date
from .time import spk_coverage

__all__ = [
    add_carriage_return,
    add_crs_to_file,
    check_consecutive,
    check_list_duplicates,
    checksum_from_label,
    checksum_from_registry,
    compare_files,
    copy,
    etree_to_dict,
    extension2type,
    extract_comment,
    fill_template,
    get_context_products,
    get_latest_kernel,
    kernel_name,
    match_patterns,
    md5,
    mk2list,
    safe_make_directory,
    type2extension,
    utf8len,
    slice_kernels,
    ck_coverage,
    creation_time,
    current_date,
    current_time,
    dsk_coverage,
    get_years,
    pck_coverage,
    pds3_label_gen_date,
    spk_coverage,
]