"""
Validates inputted CSV files based on schemas.py
"""


import pandas as pd
import pandera.pandas as pa


# Error handling ---------------------------------------------------------------
class ValidateError(Exception):
    """Base class for all validate errors"""

class ValidateIndexError(ValidateError):
    """Raised when the input DataFrame's index has duplicate labels.

    run() attributes skip records to rows via df.loc[row_index, ...] and drops
    bad rows via df.drop(index=...); both silently misbehave on duplicate index
    labels (returning a Series instead of a scalar, or dropping every row that
    shares the label), so this is checked upfront instead of failing subtly.
    """
    def __init__(self, message: str, duplicated_labels: list):
        super().__init__(message)
        self.duplicated_labels = duplicated_labels

class ValidateStructuralError(ValidateError):
    """Raised when schema validation fails structurally (e.g. a required column
    missing entirely) rather than on individual row values.

    Structural failures apply to the whole DataFrame, not a specific row, so
    per pandera.pandas they surface in failure_cases with index=None. Per
    etl_pipeline_spec.md §3 these must fail fast rather than being folded into
    the per-row skip list.
    """
    def __init__(self, message: str, columns: list[str]):
        super().__init__(message)
        self.columns = columns


# Function ------------------------------------------------------------------------------------

def run(df: pd.DataFrame, schema: type[pa.DataFrameModel]) -> tuple[pd.DataFrame, list[dict]]:
    if not df.index.is_unique:
        duplicated_labels = df.index[df.index.duplicated()].unique().tolist()
        raise ValidateIndexError(
            message=f"입력 DataFrame의 인덱스에 중복된 값이 있습니다: {duplicated_labels}",
            duplicated_labels=duplicated_labels,
        )

    try:
        schema.validate(df, lazy=True)
        return df,[]
    except pa.errors.SchemaErrors as err:
        failure_cases = err.failure_cases

        structural = failure_cases[failure_cases["index"].isna()]
        if not structural.empty:
            # For the "column_in_dataframe" check, the missing column's name is
            # in failure_case (column holds the schema's own class name); for
            # any other structural check, column already names the offender.
            structural_columns = sorted({
                row["failure_case"] if row["check"] == "column_in_dataframe" else row["column"]
                for _, row in structural.iterrows()
            })
            raise ValidateStructuralError(
                message=f"스키마 구조 검증에 실패했습니다: {', '.join(structural_columns)}",
                columns=structural_columns,
            ) from err

        grouped = failure_cases.groupby("index")

        skip_list = []
        bad_indices = set()
        for row_index, group in grouped:
            bad_indices.add(row_index)
            failing_columns = group["column"].unique()
            if "계약ID" in failing_columns:
                row_key = row_index 
            else:
                row_key = df.loc[row_index, "계약ID"]

            failures = []
            for _,failure_row in group.iterrows():
                failures.append({
                    "column": failure_row["column"],
                    "check": failure_row["check"],
                    "value": failure_row["failure_case"]
                })

            skip_list.append({
                "row_key": row_key,
                "reason": "schema_check_failed",
                "details": {"failures": failures}
            })

        # valid rows = everything not in bad_indices
        valid_df = df.drop(index=bad_indices).reset_index(drop=True)

        return (valid_df, skip_list)