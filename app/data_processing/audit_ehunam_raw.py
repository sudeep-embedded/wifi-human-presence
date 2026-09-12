import gc
import json
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from scipy.io import loadmat
except ImportError:
    loadmat = None

try:
    import h5py
except ImportError:
    h5py = None


# ============================================================
# CONFIG
# ============================================================

PROJECT_ROOT = Path(
    r"D:\final_year_projects\wifi-human-presence"
)

DATASET_ROOT = (
    PROJECT_ROOT /
    "dataset" /
    "EHUNAM_PC"
)

REPORT_DIR = (
    PROJECT_ROOT /
    "reports"
)

REPORT_PATH = (
    REPORT_DIR /
    "ehunam_raw_audit.json"
)

MIN_PEOPLE = 1
MAX_PEOPLE = 8


# ============================================================
# DATA CLASS
# ============================================================

@dataclass
class FileAudit:

    path: str
    index: int

    variables: List[str]

    # CSI candidates
    csi_candidates: List[str]
    csi_candidate_details: List[Dict[str, Any]]

    selected_csi_variable: Optional[str]
    csi_selection_method: str

    csi_found: bool

    raw_csi_shape: Optional[Tuple[int, ...]]
    csi_shape_2d: bool

    csi_dtype: Optional[str]
    csi_is_complex_dtype: bool
    csi_is_genuinely_complex: bool

    interpreted_time_length: Optional[int]
    interpreted_subcarriers: Optional[int]

    has_nan_inf: bool
    finite_ratio: Optional[float]

    real_min: Optional[float]
    real_max: Optional[float]

    imag_min: Optional[float]
    imag_max: Optional[float]

    amplitude_min: Optional[float]
    amplitude_max: Optional[float]

    phase_min: Optional[float]
    phase_max: Optional[float]

    # Label candidates
    label_candidates: List[Dict[str, Any]]

    selected_label_variable: Optional[str]
    label_source: str
    label_value: Optional[int]

    label_valid: bool
    label_ambiguous: bool

    errors: List[str]


# ============================================================
# HELPERS
# ============================================================

LABEL_PRIORITY_PATTERNS = [
    re.compile(
        r"^n[_ ]?people$",
        re.IGNORECASE
    ),
    re.compile(
        r"^num[_ ]?people$",
        re.IGNORECASE
    ),
    re.compile(
        r"^number[_ ]?people$",
        re.IGNORECASE
    ),
    re.compile(
        r"^people$",
        re.IGNORECASE
    ),
    re.compile(
        r"^people[_ ]?count$",
        re.IGNORECASE
    ),
    re.compile(
        r"^person[_ ]?count$",
        re.IGNORECASE
    ),
    re.compile(
        r"^count$",
        re.IGNORECASE
    ),
    re.compile(
        r"people|person|count|label|ground.?truth|target",
        re.IGNORECASE
    ),
]

CSI_NAME_PATTERNS = [
    re.compile(
        r"^csi$",
        re.IGNORECASE
    ),
    re.compile(
        r"csi",
        re.IGNORECASE
    ),
    re.compile(
        r"channel[_ ]?state",
        re.IGNORECASE
    ),
]


# ============================================================
# MATLAB LOADERS
# ============================================================

def load_mat_variables(
    path: Path
) -> Dict[str, Any]:

    if loadmat is not None:

        try:

            data = loadmat(
                str(path)
            )

            return {
                key: value
                for key, value in data.items()
                if not key.startswith("__")
            }

        except NotImplementedError:
            pass

        except Exception:
            pass

    if h5py is not None:

        result = {}

        try:

            with h5py.File(
                str(path),
                "r"
            ) as h5_file:

                def visitor(
                    name,
                    obj
                ):

                    if isinstance(
                        obj,
                        h5py.Dataset
                    ):

                        try:

                            result[
                                name
                            ] = obj[()]

                        except Exception:

                            pass

                h5_file.visititems(
                    visitor
                )

            if result:

                return result

        except Exception:
            pass

    raise RuntimeError(
        "Could not parse MATLAB file with "
        "SciPy loadmat or h5py."
    )


def convert_matlab_complex(
    array
):

    array = np.asarray(
        array
    )

    if (
        array.dtype.names
        and "real" in array.dtype.names
        and "imag" in array.dtype.names
    ):

        return (
            array["real"].astype(
                np.float64
            )
            +
            1j *
            array["imag"].astype(
                np.float64
            )
        )

    return array


# ============================================================
# CSI CANDIDATE DETECTION
# ============================================================

def inspect_csi_candidates(
    variables
):

    candidates = []

    for name, value in variables.items():

        try:
            array = convert_matlab_complex(
                np.asarray(value)
            )
        except Exception:
            continue

        if array.size == 0:
            continue

        if array.ndim != 2:
            continue

        if not np.issubdtype(
            array.dtype,
            np.number
        ):
            continue

        is_complex = np.iscomplexobj(
            array
        )

        genuine_complex = False

        if is_complex:

            try:

                genuine_complex = bool(
                    np.any(
                        np.abs(
                            np.asarray(
                                array.imag
                            )
                        ) > 1e-12
                    )
                )

            except Exception:
                genuine_complex = False

        name_score = 0

        for priority, pattern in enumerate(
            CSI_NAME_PATTERNS
        ):

            if pattern.search(name):

                name_score = max(
                    name_score,
                    len(CSI_NAME_PATTERNS)
                    - priority
                )

        # Prefer:
        # 1. explicit CSI names
        # 2. complex arrays
        # 3. larger arrays

        score = (
            name_score * 10_000_000
            +
            int(genuine_complex) * 1_000_000
            +
            int(is_complex) * 100_000
            +
            int(array.size)
        )

        candidates.append(
            {
                "name": name,
                "shape": tuple(
                    int(x)
                    for x in array.shape
                ),
                "dtype": str(
                    array.dtype
                ),
                "size": int(
                    array.size
                ),
                "is_complex_dtype": bool(
                    is_complex
                ),
                "is_genuinely_complex": bool(
                    genuine_complex
                ),
                "name_match_score":
                    int(name_score),
                "selection_score":
                    int(score),
            }
        )

    candidates.sort(
        key=lambda item:
            item["selection_score"],
        reverse=True
    )

    return candidates


def select_csi_candidate(
    candidates
):

    if not candidates:

        return (
            None,
            "no_2d_numeric_candidate"
        )

    top = candidates[0]

    # Explicit CSI variable = confident.
    if (
        top["name_match_score"] >=
        len(CSI_NAME_PATTERNS)
    ):

        return (
            top["name"],
            "explicit_csi_name"
        )

    # Strongly complex candidate.
    if top[
        "is_genuinely_complex"
    ]:

        return (
            top["name"],
            "genuinely_complex_candidate"
        )

    # Complex candidate.
    if top[
        "is_complex_dtype"
    ]:

        return (
            top["name"],
            "complex_candidate_fallback"
        )

    # Numeric fallback.
    return (
        top["name"],
        "largest_2d_numeric_fallback"
    )


# ============================================================
# LABEL DETECTION
# ============================================================

def label_name_priority(
    name
):

    for index, pattern in enumerate(
        LABEL_PRIORITY_PATTERNS
    ):

        if pattern.search(name):

            return (
                len(LABEL_PRIORITY_PATTERNS)
                - index
            )

    return 0


def extract_scalar_integer(
    value
):

    try:

        array = np.asarray(
            value
        )

        if array.size == 0:
            return None

        if array.size > 4:
            return None

        first = array.ravel()[0]

        if np.iscomplexobj(
            first
        ):

            if abs(
                float(np.imag(first))
            ) > 1e-9:

                return None

            first = np.real(
                first
            )

        numeric = float(
            first
        )

        rounded = int(
            round(numeric)
        )

        if abs(
            numeric - rounded
        ) > 1e-6:

            return None

        return rounded

    except Exception:

        return None


def infer_path_label(
    path: Path
):

    parts = list(
        path.parts
    )

    patterns = [

        re.compile(
            r"(\d+)\s*[_-]?"
            r"(?:people|persons?|pax)",
            re.IGNORECASE
        ),

        re.compile(
            r"^p(\d+)$",
            re.IGNORECASE
        ),

        re.compile(
            r"^(\d+)$"
        ),
    ]

    for part in reversed(
        parts
    ):

        stem = Path(
            part
        ).stem

        for pattern in patterns:

            match = pattern.search(
                stem
            )

            if not match:
                continue

            try:

                value = int(
                    match.group(1)
                )

            except Exception:

                continue

            if (
                MIN_PEOPLE
                <= value
                <= MAX_PEOPLE
            ):

                return value

    return None


def inspect_label_candidates(
    variables
):

    candidates = []

    for name, value in variables.items():

        priority = (
            label_name_priority(
                name
            )
        )

        if priority == 0:
            continue

        scalar = extract_scalar_integer(
            value
        )

        if scalar is None:
            continue

        candidates.append(
            {
                "name": name,
                "value": int(scalar),
                "priority": int(priority),
                "valid_1_to_8": bool(
                    MIN_PEOPLE
                    <= scalar
                    <= MAX_PEOPLE
                ),
            }
        )

    candidates.sort(
        key=lambda item:
            (
                item["valid_1_to_8"],
                item["priority"]
            ),
        reverse=True
    )

    return candidates


def select_label_candidate(
    candidates
):

    valid = [
        item
        for item in candidates
        if item["valid_1_to_8"]
    ]

    if not valid:

        return (
            None,
            None,
            False
        )

    values = {
        item["value"]
        for item in valid
    }

    if len(values) > 1:

        return (
            None,
            None,
            True
        )

    selected = valid[0]

    return (
        selected["name"],
        selected["value"],
        False
    )


# ============================================================
# ORIENTATION
# ============================================================

def interpret_csi_shape(
    shape
):

    if len(shape) != 2:

        return (
            None,
            None
        )

    rows, cols = shape

    # EHUNAM CSI typically has many more
    # time samples than subcarriers.
    if rows >= cols:

        return (
            rows,
            cols
        )

    return (
        cols,
        rows
    )


# ============================================================
# NUMERICAL STATS
# ============================================================

def calculate_complex_stats(
    array
):

    finite = (
        np.isfinite(
            array.real
        )
        &
        np.isfinite(
            array.imag
        )
    )

    total = finite.size

    finite_ratio = (
        float(
            finite.sum()
        )
        /
        total
        if total
        else 0.0
    )

    bad_values = (
        finite_ratio < 1.0
    )

    values = (
        array[finite]
        if bad_values
        else array.ravel()
    )

    if values.size == 0:

        return {
            "has_nan_inf": True,
            "finite_ratio":
                finite_ratio,
            "real_min": None,
            "real_max": None,
            "imag_min": None,
            "imag_max": None,
            "amplitude_min": None,
            "amplitude_max": None,
            "phase_min": None,
            "phase_max": None,
            "genuinely_complex": False,
        }

    real = values.real

    imag = values.imag

    genuine_complex = bool(
        np.any(
            np.abs(imag)
            > 1e-12
        )
    )

    amplitude = np.abs(
        values
    )

    phase = np.angle(
        values
    )

    return {
        "has_nan_inf":
            bool(bad_values),

        "finite_ratio":
            finite_ratio,

        "real_min":
            float(real.min()),

        "real_max":
            float(real.max()),

        "imag_min":
            float(imag.min()),

        "imag_max":
            float(imag.max()),

        "amplitude_min":
            float(amplitude.min()),

        "amplitude_max":
            float(amplitude.max()),

        "phase_min":
            float(phase.min()),

        "phase_max":
            float(phase.max()),

        "genuinely_complex":
            genuine_complex,
    }


# ============================================================
# SINGLE FILE AUDIT
# ============================================================

def audit_file(
    path,
    index
):

    errors = []

    try:

        variables = load_mat_variables(
            path
        )

    except Exception as exc:

        return FileAudit(

            path=str(path),

            index=index,

            variables=[],

            csi_candidates=[],

            csi_candidate_details=[],

            selected_csi_variable=None,

            csi_selection_method=
                "load_failed",

            csi_found=False,

            raw_csi_shape=None,

            csi_shape_2d=False,

            csi_dtype=None,

            csi_is_complex_dtype=False,

            csi_is_genuinely_complex=False,

            interpreted_time_length=None,

            interpreted_subcarriers=None,

            has_nan_inf=False,

            finite_ratio=None,

            real_min=None,
            real_max=None,

            imag_min=None,
            imag_max=None,

            amplitude_min=None,
            amplitude_max=None,

            phase_min=None,
            phase_max=None,

            label_candidates=[],

            selected_label_variable=None,

            label_source="not_found",

            label_value=None,

            label_valid=False,

            label_ambiguous=False,

            errors=[
                f"load_failed: {exc}"
            ]
        )

    variable_names = sorted(
        variables.keys()
    )

    csi_candidates = (
        inspect_csi_candidates(
            variables
        )
    )

    selected_csi, selection_method = (
        select_csi_candidate(
            csi_candidates
        )
    )

    raw_shape = None
    shape_2d = False
    csi_dtype = None
    complex_dtype = False
    genuine_complex = False

    time_length = None
    subcarriers = None

    has_nan_inf = False
    finite_ratio = None

    real_min = None
    real_max = None
    imag_min = None
    imag_max = None

    amplitude_min = None
    amplitude_max = None

    phase_min = None
    phase_max = None

    if selected_csi is not None:

        selected_value = (
            variables[
                selected_csi
            ]
        )

        array = convert_matlab_complex(
            np.asarray(
                selected_value
            )
        )

        raw_shape = tuple(
            int(x)
            for x in array.shape
        )

        shape_2d = (
            array.ndim == 2
        )

        csi_dtype = str(
            array.dtype
        )

        complex_dtype = bool(
            np.iscomplexobj(array)
        )

        if not shape_2d:

            errors.append(
                "selected_CSI_is_not_2D"
            )

        else:

            time_length, subcarriers = (
                interpret_csi_shape(
                    raw_shape
                )
            )

            stats = (
                calculate_complex_stats(
                    array
                )
            )

            has_nan_inf = (
                stats["has_nan_inf"]
            )

            finite_ratio = (
                stats["finite_ratio"]
            )

            real_min = stats[
                "real_min"
            ]

            real_max = stats[
                "real_max"
            ]

            imag_min = stats[
                "imag_min"
            ]

            imag_max = stats[
                "imag_max"
            ]

            amplitude_min = stats[
                "amplitude_min"
            ]

            amplitude_max = stats[
                "amplitude_max"
            ]

            phase_min = stats[
                "phase_min"
            ]

            phase_max = stats[
                "phase_max"
            ]

            genuine_complex = (
                stats[
                    "genuinely_complex"
                ]
            )

    else:

        errors.append(
            "no_CSI_candidate_found"
        )

    # --------------------------------------------------------
    # Labels
    # --------------------------------------------------------

    label_candidates = (
        inspect_label_candidates(
            variables
        )
    )

    (
        selected_label_variable,
        label_value,
        ambiguous
    ) = select_label_candidate(
        label_candidates
    )

    label_source = (
        "mat_variable"
        if selected_label_variable
        else "not_found"
    )

    if ambiguous:

        errors.append(
            "ambiguous_label_candidates"
        )

    if selected_label_variable is None:

        path_label = infer_path_label(
            path
        )

        if path_label is not None:

            label_value = (
                path_label
            )

            label_source = (
                "path_fallback"
            )

    label_valid = (
        label_value is not None
        and
        MIN_PEOPLE
        <= label_value
        <= MAX_PEOPLE
        and
        not ambiguous
    )

    if not label_valid:

        errors.append(
            "invalid_or_missing_label"
        )

    result = FileAudit(

        path=str(path),

        index=index,

        variables=variable_names,

        csi_candidates=[
            item["name"]
            for item in
            csi_candidates
        ],

        csi_candidate_details=
            csi_candidates,

        selected_csi_variable=
            selected_csi,

        csi_selection_method=
            selection_method,

        csi_found=
            selected_csi is not None,

        raw_csi_shape=
            raw_shape,

        csi_shape_2d=
            shape_2d,

        csi_dtype=
            csi_dtype,

        csi_is_complex_dtype=
            complex_dtype,

        csi_is_genuinely_complex=
            genuine_complex,

        interpreted_time_length=
            time_length,

        interpreted_subcarriers=
            subcarriers,

        has_nan_inf=
            has_nan_inf,

        finite_ratio=
            finite_ratio,

        real_min=
            real_min,

        real_max=
            real_max,

        imag_min=
            imag_min,

        imag_max=
            imag_max,

        amplitude_min=
            amplitude_min,

        amplitude_max=
            amplitude_max,

        phase_min=
            phase_min,

        phase_max=
            phase_max,

        label_candidates=
            label_candidates,

        selected_label_variable=
            selected_label_variable,

        label_source=
            label_source,

        label_value=
            label_value,

        label_valid=
            label_valid,

        label_ambiguous=
            ambiguous,

        errors=
            errors
    )

    del variables

    gc.collect()

    return result


# ============================================================
# DISTRIBUTION SUMMARY
# ============================================================

def distribution_stats(
    values
):

    if not values:

        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
        }

    array = np.asarray(
        values,
        dtype=np.float64
    )

    return {

        "count":
            int(array.size),

        "min":
            float(array.min()),

        "max":
            float(array.max()),

        "mean":
            float(array.mean()),

        "median":
            float(np.median(array)),
    }


# ============================================================
# MAIN
# ============================================================

def main():

    if not DATASET_ROOT.exists():

        print(
            f"[ERROR] Dataset does not exist:\n"
            f"{DATASET_ROOT}"
        )

        sys.exit(1)

    REPORT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    files = sorted(
        DATASET_ROOT.rglob(
            "*.mat"
        )
    )

    total = len(files)

    if total == 0:

        print(
            "[ERROR] No .mat files found."
        )

        sys.exit(1)

    print("=" * 78)

    print(
        "EHUNAM ORIGINAL RAW DATA AUDIT"
    )

    print("=" * 78)

    print(
        f"Dataset: {DATASET_ROOT}"
    )

    print(
        f"MAT files: {total}"
    )

    print("=" * 78)

    records = []

    subcarrier_hist = Counter()

    label_hist = Counter()

    layout_details = defaultdict(
        lambda: {
            "recordings": 0,
            "valid_labels": 0,
            "complex": 0,
            "nan_inf": 0,
            "people": Counter(),
        }
    )

    csi_missing = 0
    label_missing_or_invalid = 0
    ambiguous_labels = 0
    load_errors = 0

    complex_count = 0
    noncomplex_count = 0

    time_lengths = []

    start_time = time.time()

    # --------------------------------------------------------
    # Audit files one by one
    # --------------------------------------------------------

    for index, path in enumerate(
        files,
        1
    ):

        record = audit_file(
            path,
            index
        )

        records.append(
            record
        )

        if not record.csi_found:

            csi_missing += 1

        if record.errors:

            if any(
                "load_failed"
                in error
                for error in
                record.errors
            ):

                load_errors += 1

        if record.label_ambiguous:

            ambiguous_labels += 1

        if not record.label_valid:

            label_missing_or_invalid += 1

        if record.csi_is_genuinely_complex:

            complex_count += 1

        elif record.csi_found:

            noncomplex_count += 1

        if (
            record.interpreted_subcarriers
            is not None
        ):

            subcarriers = (
                record.interpreted_subcarriers
            )

            subcarrier_hist[
                subcarriers
            ] += 1

            layout = (
                layout_details[
                    subcarriers
                ]
            )

            layout[
                "recordings"
            ] += 1

            if record.label_valid:

                layout[
                    "valid_labels"
                ] += 1

                layout[
                    "people"
                ][
                    record.label_value
                ] += 1

            if record.csi_is_genuinely_complex:

                layout[
                    "complex"
                ] += 1

            if record.has_nan_inf:

                layout[
                    "nan_inf"
                ] += 1

        if (
            record.label_valid
        ):

            label_hist[
                record.label_value
            ] += 1

        if (
            record.interpreted_time_length
            is not None
        ):

            time_lengths.append(
                record.interpreted_time_length
            )

        if (
            index % 25 == 0
            or index == total
        ):

            elapsed = (
                time.time()
                - start_time
            )

            print(
                f"Processed "
                f"{index}/{total} "
                f"files | "
                f"{elapsed:.1f}s"
            )

    # ========================================================
    # SUMMARY
    # ========================================================

    print("\n" + "=" * 78)

    print(
        "AUDIT SUMMARY"
    )

    print("=" * 78)

    print(
        f"Total MAT files: "
        f"{total}"
    )

    print(
        f"CSI found: "
        f"{total - csi_missing}"
    )

    print(
        f"CSI missing: "
        f"{csi_missing}"
    )

    print(
        f"Load errors: "
        f"{load_errors}"
    )

    print(
        f"Genuinely complex CSI: "
        f"{complex_count}"
    )

    print(
        f"Non-complex CSI: "
        f"{noncomplex_count}"
    )

    print(
        f"Missing/invalid labels: "
        f"{label_missing_or_invalid}"
    )

    print(
        f"Ambiguous labels: "
        f"{ambiguous_labels}"
    )

    # --------------------------------------------------------
    # Variables
    # --------------------------------------------------------

    variable_frequency = Counter()

    for record in records:

        for variable in record.variables:

            variable_frequency[
                variable
            ] += 1

    print(
        "\nVARIABLE FREQUENCY"
    )

    for variable, count in (
        variable_frequency.most_common()
    ):

        print(
            f"{variable:30s}"
            f" -> {count}/{total}"
        )

    # --------------------------------------------------------
    # CSI layouts
    # --------------------------------------------------------

    print(
        "\nCSI SUBCARRIER LAYOUTS"
    )

    for subcarriers, count in (
        sorted(
            subcarrier_hist.items(),
            key=lambda item:
                item[1],
            reverse=True
        )
    ):

        detail = (
            layout_details[
                subcarriers
            ]
        )

        people_distribution = (
            dict(
                sorted(
                    detail[
                        "people"
                    ].items()
                )
            )
        )

        print(
            f"\n{subcarriers} subcarriers"
        )

        print(
            f"  recordings: "
            f"{detail['recordings']}"
        )

        print(
            f"  valid labels: "
            f"{detail['valid_labels']}"
        )

        print(
            f"  complex CSI: "
            f"{detail['complex']}"
        )

        print(
            f"  NaN/Inf: "
            f"{detail['nan_inf']}"
        )

        print(
            f"  people: "
            f"{people_distribution}"
        )

    # --------------------------------------------------------
    # People
    # --------------------------------------------------------

    print(
        "\nPEOPLE-COUNT DISTRIBUTION"
    )

    for people in range(
        MIN_PEOPLE,
        MAX_PEOPLE + 1
    ):

        print(
            f"{people} people: "
            f"{label_hist.get(people, 0)} recordings"
        )

    # --------------------------------------------------------
    # Length distribution
    # --------------------------------------------------------

    print(
        "\nRECORDING LENGTH"
    )

    print(
        distribution_stats(
            time_lengths
        )
    )

    # --------------------------------------------------------
    # Representative examples
    # --------------------------------------------------------

    print(
        "\nREPRESENTATIVE FILES BY LAYOUT"
    )

    representatives = {}

    for record in records:

        layout = (
            record.interpreted_subcarriers
        )

        if (
            layout is not None
            and layout not in representatives
        ):

            representatives[
                layout
            ] = record

    for layout in sorted(
        representatives
    ):

        record = representatives[
            layout
        ]

        print(
            f"\n{layout} subcarriers"
        )

        print(
            f"  file: "
            f"{record.path}"
        )

        print(
            f"  CSI variable: "
            f"{record.selected_csi_variable}"
        )

        print(
            f"  shape: "
            f"{record.raw_csi_shape}"
        )

        print(
            f"  dtype: "
            f"{record.csi_dtype}"
        )

        print(
            f"  complex: "
            f"{record.csi_is_genuinely_complex}"
        )

        print(
            f"  real min/max: "
            f"{record.real_min} / "
            f"{record.real_max}"
        )

        print(
            f"  imag min/max: "
            f"{record.imag_min} / "
            f"{record.imag_max}"
        )

        print(
            f"  amplitude min/max: "
            f"{record.amplitude_min} / "
            f"{record.amplitude_max}"
        )

        print(
            f"  phase min/max: "
            f"{record.phase_min} / "
            f"{record.phase_max}"
        )

        print(
            f"  label variable: "
            f"{record.selected_label_variable}"
        )

        print(
            f"  label source: "
            f"{record.label_source}"
        )

        print(
            f"  label: "
            f"{record.label_value}"
        )

    # ========================================================
    # RECOMMENDATION
    # ========================================================

    print(
        "\n" +
        "=" * 78
    )

    print(
        "CANDIDATE TRAINING LAYOUTS"
    )

    print("=" * 78)

    for subcarriers, detail in sorted(
        layout_details.items(),
        key=lambda item:
            item[1]["recordings"],
        reverse=True
    ):

        print(
            f"\nLayout: "
            f"{subcarriers} subcarriers"
        )

        print(
            f"  recordings: "
            f"{detail['recordings']}"
        )

        print(
            f"  valid labels: "
            f"{detail['valid_labels']}"
        )

        print(
            f"  complex CSI: "
            f"{detail['complex']}"
        )

        print(
            f"  NaN/Inf: "
            f"{detail['nan_inf']}"
        )

        print(
            f"  class distribution: "
            f"{dict(sorted(detail['people'].items()))}"
        )

    print(
        "\nNO AUTOMATIC FINAL TRAINING DECISION "
        "WILL BE MADE."
    )

    print(
        "We will choose the layout only after "
        "reviewing this audit."
    )

    # ========================================================
    # JSON REPORT
    # ========================================================

    report = {

        "dataset_root":
            str(DATASET_ROOT),

        "total_files":
            total,

        "csi_found":
            total - csi_missing,

        "csi_missing":
            csi_missing,

        "load_errors":
            load_errors,

        "genuinely_complex":
            complex_count,

        "noncomplex":
            noncomplex_count,

        "missing_invalid_labels":
            label_missing_or_invalid,

        "ambiguous_labels":
            ambiguous_labels,

        "variable_frequency":
            dict(variable_frequency),

        "subcarrier_distribution":
            dict(subcarrier_hist),

        "people_distribution":
            {
                str(
                    people
                ):
                label_hist.get(
                    people,
                    0
                )
                for people in range(
                    MIN_PEOPLE,
                    MAX_PEOPLE + 1
                )
            },

        "recording_length_distribution":
            distribution_stats(
                time_lengths
            ),

        "layouts":
            {
                str(
                    subcarriers
                ):
                {
                    "recordings":
                        detail["recordings"],

                    "valid_labels":
                        detail["valid_labels"],

                    "complex":
                        detail["complex"],

                    "nan_inf":
                        detail["nan_inf"],

                    "people_distribution":
                        {
                            str(k): v
                            for k, v in
                            sorted(
                                detail[
                                    "people"
                                ].items()
                            )
                        },
                }
                for subcarriers, detail
                in layout_details.items()
            },

        "files":
            [
                asdict(record)
                for record in records
            ],
    }

    with open(
        REPORT_PATH,
        "w",
        encoding="utf-8"
    ) as report_file:

        json.dump(
            report,
            report_file,
            indent=2,
            default=str
        )

    print(
        "\nFull audit report:"
    )

    print(
        REPORT_PATH
    )

    print(
        "\nAudit complete."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except KeyboardInterrupt:

        print(
            "\nAudit interrupted."
        )

        sys.exit(130)

    except Exception:

        traceback.print_exc()

        sys.exit(1)