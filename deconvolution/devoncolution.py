from matplotlib import pyplot as plt
import numpy as np
from sklearn.linear_model import Lasso
import random


def lasso_deconv():
    [
        "psm_id",
        "fragment_type",
        "fragment_ordinals",
        "fragment_charge",
        "fragment_mz_experimental",
        "fragment_mz_calculated",
        "fragment_intensity",
        "peptide",
        "charge",
        "rt",
        "scannr",
        "peak_identifier",
    ]

    [
        "psm_id",
        "filename",
        "scannr",
        "peptide",
        "stripped_peptide",
        "proteins",
        "num_proteins",
        "rank",
        "is_decoy",
        "expmass",
        "calcmass",
        "charge",
        "peptide_len",
        "missed_cleavages",
        "semi_enzymatic",
        "ms2_intensity",
        "isotope_error",
        "precursor_ppm",
        "fragment_ppm",
        "hyperscore",
        "delta_next",
        "delta_best",
        "rt",
        "aligned_rt",
        "predicted_rt",
        "delta_rt_model",
        "ion_mobility",
        "predicted_mobility",
        "delta_mobility",
        "matched_peaks",
        "longest_b",
        "longest_y",
        "longest_y_pct",
        "matched_intensity_pct",
        "scored_candidates",
        "poisson",
        "sage_discriminant_score",
        "posterior_error",
        "spectrum_q",
        "peptide_q",
        "protein_q",
        "reporter_ion_intensity",
        "fragment_intensity",
    ]

    # Parameters
    num_experimental_peaks = 50
    num_theoretical_spectra = 1500
    mz_range = (100, 600)
    intensity_range = (10, 100)

    # Generate experimental spectrum
    experimental_spectrum = generate_random_spectrum(
        num_experimental_peaks, mz_range, intensity_range
    )

    # Generate theoretical spectra with a random number of matched peaks
    theoretical_spectra = []
    for _ in range(num_theoretical_spectra):
        num_peaks = random.randint(5, num_experimental_peaks)
        theoretical_spectrum = generate_random_spectrum(
            num_peaks, mz_range, intensity_range
        )
        theoretical_spectra.append(theoretical_spectrum)

    # Convert spectra to numpy arrays for processing
    def spectrum_to_vector(spectrum, mz_values):
        mz_dict = dict(spectrum)
        return np.array([mz_dict.get(mz, 0) for mz in mz_values])

    # Get the set of all unique m/z values
    all_mz_values = sorted(set(mz for mz, _ in experimental_spectrum))

    # Convert experimental spectrum to vector
    exp_vector = spectrum_to_vector(experimental_spectrum, all_mz_values)

    # Convert theoretical spectra to matrix
    theoretical_matrix = np.array(
        [spectrum_to_vector(spec, all_mz_values) for spec in theoretical_spectra]
    ).T

    # Use Lasso to find the coefficients with L1 regularization
    lasso = Lasso(alpha=100.0, positive=True, max_iter=10000)
    lasso.fit(theoretical_matrix, exp_vector)
    coefficients = lasso.coef_

    # Print the results
    print("Coefficients:", coefficients)

    # Reconstruct the experimental spectrum from the theoretical spectra using the coefficients
    reconstructed_spectrum = np.dot(theoretical_matrix, coefficients)

    # Plot the experimental and reconstructed spectra for comparison
    plt.figure(figsize=(12, 6))
    plt.vlines(
        all_mz_values, 0, exp_vector, label="Experimental Spectrum", color="blue"
    )
    plt.vlines(
        all_mz_values,
        0,
        reconstructed_spectrum,
        label="Reconstructed Spectrum",
        color="red",
        linestyle="--",
    )
    plt.xlabel("m/z")
    plt.ylabel("Intensity")
    plt.legend()
    plt.title("Experimental vs Reconstructed Spectrum")
    plt.show()

    # Plot the stacked contribution of each theoretical spectrum
    plt.figure(figsize=(12, 6))
    bottom = np.zeros(len(all_mz_values))
    colors = plt.cm.tab20(np.linspace(0, 1, num_theoretical_spectra))
    for j, vector in enumerate(theoretical_spectra):
        contribution = coefficients[j] * spectrum_to_vector(vector, all_mz_values)
        plt.bar(
            all_mz_values,
            contribution,
            bottom=bottom,
            color=colors[j],
            edgecolor="white",
            width=4,
            label=f"Theoretical Spectrum {j+1}",
        )
        bottom += contribution

    plt.xlabel("m/z")
    plt.ylabel("Intensity")
    # plt.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    plt.title("Stacked Contributions of Theoretical Spectra")
    plt.show()