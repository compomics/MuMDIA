import pickle


def write_variables_to_pickles(
    df_fragment,
    df_psms,
    df_fragment_max,
    df_fragment_max_peptide,
    config,
    dlc_transfer_learn,
    write_deeplc_pickle,
    write_ms2pip_pickle,
    write_correlation_pickles,
):
    with open("df_fragment.pkl", "wb") as f:
        pickle.dump(df_fragment, f)
    with open("df_psms.pkl", "wb") as f:
        pickle.dump(df_psms, f)
    with open("df_fragment_max.pkl", "wb") as f:
        pickle.dump(df_fragment_max, f)
    with open("df_fragment_max_peptide.pkl", "wb") as f:
        pickle.dump(df_fragment_max_peptide, f)
    with open("config.pkl", "wb") as f:
        pickle.dump(config, f)
    with open("dlc_transfer_learn.pkl", "wb") as f:
        pickle.dump(dlc_transfer_learn, f)
    # Also save the flags
    with open("flags.pkl", "wb") as f:
        pickle.dump(
            {
                "write_deeplc_pickle": write_deeplc_pickle,
                "write_ms2pip_pickle": write_ms2pip_pickle,
                "write_correlation_pickles": write_correlation_pickles,
                "read_deeplc_pickle": False,
                "read_ms2pip_pickle": False,
                "read_correlation_pickles": False,
            },
            f,
        )


def read_variables_from_pickles():
    with open("df_fragment.pkl", "rb") as f:
        df_fragment = pickle.load(f)
    with open("df_psms.pkl", "rb") as f:
        df_psms = pickle.load(f)
    with open("df_fragment_max.pkl", "rb") as f:
        df_fragment_max = pickle.load(f)
    with open("df_fragment_max_peptide.pkl", "rb") as f:
        df_fragment_max_peptide = pickle.load(f)
    with open("config.pkl", "rb") as f:
        config = pickle.load(f)
    with open("dlc_transfer_learn.pkl", "rb") as f:
        dlc_transfer_learn = pickle.load(f)
    with open("flags.pkl", "rb") as f:
        flags = pickle.load(f)
    return (
        df_fragment,
        df_psms,
        df_fragment_max,
        df_fragment_max_peptide,
        config,
        dlc_transfer_learn,
        flags,
    )