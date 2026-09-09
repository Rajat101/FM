"""
Optional offline utility for local development: pre-processes a local copy of
the workbook into a parquet cache, so you can iterate on pages quickly without
re-uploading through the browser each time.

NOT required for deployment -- the deployed app takes the workbook via the
in-browser uploader (see common.load_data) and never needs a file on disk.

Usage: python data_prep.py /path/to/Lifecycle__PAN.xlsx
"""
import os
import sys

from common import process_workbook

OUT = "data/processed.parquet"


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "/mnt/project/Lifecycle__PAN.xlsx"
    with open(src, "rb") as f:
        file_bytes = f.read()
    df = process_workbook.__wrapped__(file_bytes)  # bypass st.cache_data outside a Streamlit runtime
    os.makedirs("data", exist_ok=True)
    df.to_parquet(OUT, index=False)
    print(f"Wrote {len(df):,} rows x {len(df.columns)} cols -> {OUT}")


if __name__ == "__main__":
    main()
