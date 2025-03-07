import os

os.environ["POLARS_MAX_THREADS"] = "1"

import argparse
import json

import mumdia
import pathlib
from pathlib import Path

from parsers.parser_mzml import split_mzml_by_retention_time, get_ms1_mzml
from parsers.parser_parquet import parquet_reader
from prediction_wrappers.wrapper_deeplc import (
    retrain_deeplc,
    predict_deeplc,
)
import pandas as pd
import polars as pl

import numpy as np
import pandas as pd

from sequence.fasta import write_to_fasta
from utilities.logger import log_info
from utilities.pickling import (
    write_variables_to_pickles,
    read_variables_from_pickles,
)
from peptide_search.wrapper_sage import run_sage
from sequence.fasta import tryptic_digest_pyopenms
from parsers.parser_mzml import split_mzml_by_retention_time
from parsers.parser_parquet import parquet_reader
from prediction_wrappers.wrapper_deeplc import retrain_deeplc
from prediction_wrappers.wrapper_deeplc import predict_deeplc

from utilities.io_utils import remove_intermediate_files
from utilities.io_utils import create_dirs

from peptide_search.wrapper_sage import run_sage
from peptide_search.wrapper_sage import retention_window_searches

from mumdia import run_mokapot

from prediction_wrappers.wrapper_deeplc import retrain_and_bounds

import os
import sys
import json
import argparse
from utilities.logger import log_info


def parse_arguments():
    parser = argparse.ArgumentParser()

    # Add arguments
    parser.add_argument(
        "--mzml_file",
        help="The location of the mzml file",
        default="mzml_files/LFQ_Orbitrap_AIF_Ecoli_01.mzML",
    )
    parser.add_argument(
        "--mzml_dir", help="The directory of the mzml file", default="mzml_files"
    )
    parser.add_argument(
        "--fasta_file",
        help="The location of the fasta file",
        default="fasta/unmodified_peptides.fasta",
    )
    parser.add_argument(
        "--result_dir", help="The location of the result directory", default="results"
    )
    parser.add_argument(
        "--config_file",
        help="The location of the config file",
        default="configs/config.json",
    )

    parser.add_argument(
        "--remove_intermediate_files",
        help="Flag to indicate if intermediate results should be removed",
        type=bool,
        default=False,
    )

    parser.add_argument(
        "--write_initial_search_pickle",
        help="Flag to indicate if all result pickles should be written",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--read_initial_search_pickle",
        help="Flag to indicate if all result pickles should be read",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--write_deeplc_pickle",
        help="Flag to indicate if DeepLC pickles should be written",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--write_ms2pip_pickle",
        help="Flag to indicate if MS2PIP pickles should be written",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--read_deeplc_pickle",
        help="Flag to indicate if DeepLC pickles should be read",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--read_ms2pip_pickle",
        help="Flag to indicate if MS2PIP pickles should be read",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--write_correlation_pickles",
        help="Flag to indicate if correlation pickles should be written",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--read_correlation_pickles",
        help="Flag to indicate if correlation pickles should be read",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--dlc_transfer_learn",
        help="Flag to indicate if DeepLC should use transfer learning",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--write_full_search_pickle",
        help="Flag to indicate if the full search pickles should be written",
        type=bool,
        default=True,
    )

    parser.add_argument(
        "--read_full_search_pickle",
        help="Flag to indicate if the full search pickles should be read",
        type=bool,
        default=True,
    )

    # Additional possible configuration overrides from CLI
    parser.add_argument(
        "--sage_basic", help="Override sage basic settings in config", type=str
    )
    parser.add_argument(
        "--mumdia_fdr", help="Override mumdia FDR setting in config", type=float
    )

    return parser, parser.parse_args()


def was_arg_explicitly_provided(parser, arg_name):
    """
    Check if an argument with destination `arg_name` was explicitly provided on the command line.
    """
    for action in parser._actions:
        if action.dest == arg_name:
            for option in action.option_strings:
                # If any of the option flags for this argument is present in sys.argv, consider it provided.
                if option in sys.argv:
                    return True
    return False


def modify_config(config_file, result_dir, parser, args):
    """
    Update the configuration JSON file with command-line overrides if and only if the user explicitly provided them.

    This function loads an existing configuration (if any) and ensures that under the "mumdia" key,
    only those parameters that the user has explicitly specified on the command line will override the JSON config.
    Missing values are filled from argparse defaults.

    Args:
        config_file (str): Path to the original JSON configuration file.
        result_dir (str): Path to the result directory.
        parser (argparse.ArgumentParser): The parser used to obtain default values and option strings.
        args (argparse.Namespace): The parsed command-line arguments.

    Returns:
        str: Path to the updated configuration JSON file.
    """
    # Load existing configuration if it exists
    if os.path.exists(config_file):
        with open(config_file, "r") as file:
            config = json.load(file)
    else:
        log_info(
            f"Warning: Config file '{config_file}' not found. Using argparse defaults."
        )
        config = {}

    # Ensure "mumdia" exists in the config
    if "mumdia" not in config:
        config["mumdia"] = {}

    # Obtain default values from the parser for all arguments that have a default
    default_args = {
        action.dest: action.default
        for action in parser._actions
        if action.default is not None
    }

    updated = False

    # Update only those values that were explicitly provided by the user.
    for key, value in vars(args).items():
        if was_arg_explicitly_provided(parser, key):
            # Only override if either the key is missing or the value differs.
            if key not in config["mumdia"] or config["mumdia"][key] != value:
                config["mumdia"][key] = value
                updated = True
        else:
            # If no value exists in the config, fill it with the argparse default.
            if key not in config["mumdia"]:
                config["mumdia"][key] = default_args.get(key, value)
                updated = True

    # Define new config path in the results folder
    new_config_path = os.path.join(result_dir, "updated_config.json")

    if updated:
        with open(new_config_path, "w") as file:
            json.dump(config, file, indent=4)
        log_info(f"Configuration updated and saved to {new_config_path}")
    else:
        log_info("No configuration changes were made, using existing values.")

    return new_config_path


def main():
    log_info("Parsing command line arguments...")
    parser, args = parse_arguments()

    log_info("Creating the result directory...")
    result_dir, result_temp, result_temp_results_initial_search = create_dirs(args)

    log_info("Updating configuration if needed and saving to results folder...")
    new_config_file = modify_config(
        args.config_file, result_dir=args.result_dir, parser=parser, args=args
    )

    log_info("Reading the updated configuration JSON file...")
    with open(new_config_file, "r") as file:
        config = json.load(file)

    args_dict = config["mumdia"]

    if args_dict["write_initial_search_pickle"]:
        run_sage(
            config["sage_basic"],
            args_dict["fasta_file"],
            result_dir.joinpath(result_temp, result_temp_results_initial_search),
        )

        df_fragment, df_psms, df_fragment_max, df_fragment_max_peptide = parquet_reader(
            parquet_file_results=result_dir.joinpath(
                result_temp, result_temp_results_initial_search, "results.sage.parquet"
            ),
            parquet_file_fragments=result_dir.joinpath(
                result_temp,
                result_temp_results_initial_search,
                "matched_fragments.sage.parquet",
            ),
            q_value_filter=args_dict["fdr_init_search"],
        )

    if args_dict["write_initial_search_pickle"]:
        write_variables_to_pickles(
            df_fragment=df_fragment,
            df_psms=df_psms,
            df_fragment_max=df_fragment_max,
            df_fragment_max_peptide=df_fragment_max_peptide,
            config=config,
            dlc_transfer_learn=None,
            write_deeplc_pickle=args_dict["write_deeplc_pickle"],
            write_ms2pip_pickle=args_dict["write_ms2pip_pickle"],
            write_correlation_pickles=args_dict["write_correlation_pickles"],
            write_full_search_pickle=args_dict["write_full_search_pickle"],
            read_deeplc_pickle=args_dict["read_deeplc_pickle"],
            read_ms2pip_pickle=args_dict["read_ms2pip_pickle"],
            read_correlation_pickles=args_dict["read_correlation_pickles"],
            read_full_search_pickle=args_dict["read_full_search_pickle"],
            df_fragment_fname="df_fragment_initial_search.pkl",
            df_psms_fname="df_psms_initial_search.pkl",
            df_fragment_max_fname="df_fragment_max_initial_search.pkl",
            df_fragment_max_peptide_fname="df_fragment_max_peptide_initial_search.pkl",
            config_fname="config_initial_search.pkl",
            dlc_transfer_learn_fname="dlc_transfer_learn_initial_search.pkl",
            flags_fname="flags_initial_search.pkl",
            dir=result_dir,
            write_to_tsv=True,
        )

    if args_dict["read_initial_search_pickle"]:
        (
            df_fragment,
            df_psms,
            df_fragment_max,
            df_fragment_max_peptide,
            config,
            dlc_transfer_learn,
            flags,
        ) = read_variables_from_pickles(dir=result_dir)
        del flags["write_full_search_pickle"]
        del flags["read_full_search_pickle"]
        args_dict.update(flags)

    if args_dict["write_full_search_pickle"]:
        peptides = tryptic_digest_pyopenms(config["sage"]["database"]["fasta"])

        peptide_df, dlc_calibration, dlc_transfer_learn, perc_95 = retrain_and_bounds(
            df_psms, peptides, result_dir=result_dir
        )

        mzml_dict = split_mzml_by_retention_time(
            "LFQ_Orbitrap_AIF_Ecoli_01.mzML",
            time_interval=perc_95,
            dir_files="results/temp/",
        )

        df_fragment, df_psms, df_fragment_max, df_fragment_max_peptide = (
            retention_window_searches(mzml_dict, peptide_df, config, perc_95)
        )

        log_info("Adding the PSM identifier to fragments...")
        df_fragment = df_fragment.join(
            df_psms.select(["psm_id", "scannr"]), on="psm_id", how="left"
        )

    if args_dict["write_full_search_pickle"]:
        write_variables_to_pickles(
            df_fragment=df_fragment,
            df_psms=df_psms,
            df_fragment_max=df_fragment_max,
            df_fragment_max_peptide=df_fragment_max_peptide,
            config=config,
            dlc_transfer_learn=dlc_transfer_learn,
            write_deeplc_pickle=args_dict["write_deeplc_pickle"],
            write_ms2pip_pickle=args_dict["write_ms2pip_pickle"],
            write_correlation_pickles=args_dict["write_correlation_pickles"],
            write_full_search_pickle=args_dict["write_full_search_pickle"],
            read_deeplc_pickle=args_dict["read_deeplc_pickle"],
            read_ms2pip_pickle=args_dict["read_ms2pip_pickle"],
            read_correlation_pickles=args_dict["read_correlation_pickles"],
            read_full_search_pickle=args_dict["read_full_search_pickle"],
            dir=result_dir,
            write_to_tsv=True,
        )

    if args_dict["read_full_search_pickle"]:
        (
            df_fragment,
            df_psms,
            df_fragment_max,
            df_fragment_max_peptide,
            config,
            dlc_transfer_learn,
            flags,
        ) = read_variables_from_pickles(dir=result_dir)
        args_dict.update(flags)

    log_info("Parsing the mzML file...")
    # ms1_dict, ms2_to_ms1_dict, ms2_spectra = get_ms1_mzml(
    #    config["sage_basic"]["mzml_paths"][0]
    # )
    ms1_dict = {}
    ms2_to_ms1_dict = {}

    mumdia.main(
        df_fragment=df_fragment,
        df_psms=df_psms,
        df_fragment_max=df_fragment_max,
        df_fragment_max_peptide=df_fragment_max_peptide,
        config=config,
        deeplc_model=dlc_transfer_learn,
        write_deeplc_pickle=True,  # args_dict["write_deeplc_pickle"],
        write_ms2pip_pickle=True,  # args_dict["write_ms2pip_pickle"],
        read_deeplc_pickle=False,  # args_dict["read_deeplc_pickle"],
        read_ms2pip_pickle=False,  # args_dict["read_ms2pip_pickle"],
        ms1_dict=ms1_dict,
        ms2_to_ms1_dict=ms2_to_ms1_dict,
    )

    if args_dict["remove_intermediate_files"]:
        remove_intermediate_files(args_dict["result_dir"])


if __name__ == "__main__":
    main()
    run_mokapot()
