#=== ALL IMPORTS ===

import streamlit as st import zipfile import os import pandas as pd from datetime import datetime, timedelta import tempfile import shutil import io import warnings from io import StringIO import time from Report import process_files

#=== PAGE CONFIG ===

st.set_page_config(page_title="Mahindra Report Generator", layout="wide", initial_sidebar_state="expanded")

st.title("🚗 Mahindra Order Generator") st.markdown(""" 📊 Generate comprehensive reports from Mahindra data files including:

OEM Reports

Stock Reports

MRN Reports

Mdarpan Reports

Sales Order Reports """)


#=== SESSION STATE INIT ===

if "uploaded_file" not in st.session_state: st.session_state.uploaded_file = None if "extracted_path" not in st.session_state: st.session_state.extracted_path = None if "validation_errors" not in st.session_state: st.session_state.validation_errors = [] if "period_validation_errors" not in st.session_state: st.session_state.period_validation_errors = [] if "missing_files" not in st.session_state: st.session_state.missing_files = [] if "validation_log" not in st.session_state: st.session_state.validation_log = pd.DataFrame() if "continue_processing" not in st.session_state: st.session_state.continue_processing = False if "processing_complete" not in st.session_state: st.session_state.processing_complete = False if "report_results" not in st.session_state: st.session_state.report_results = None if "show_reports" not in st.session_state: st.session_state.show_reports = False if "po_check_df" not in st.session_state: st.session_state.po_check_df = pd.DataFrame()

#=== PERIOD TYPE ===

PERIOD_TYPES = { "Day": 1, "Week": 7, "Month": 30, "Quarter": 90, "Year": 365 }

#=== SHOW VALIDATION ISSUES ===

def show_validation_issues(): st.warning("⚠ Validation Issues Found")

if st.session_state.missing_files:
    st.write("#### Missing Files:")
    for msg in st.session_state.missing_files:
        st.write(f"- {msg}")

if st.session_state.period_validation_errors:
    st.write("#### Missing Period Data:")
    st.write(f"Found {len(st.session_state.period_validation_errors)} period validation issues")
    for error in st.session_state.period_validation_errors[:2]:
        st.write(f"- {error}")
    if len(st.session_state.period_validation_errors) > 2:
        st.write(f"- ... and {len(st.session_state.period_validation_errors) - 2} more")

if 'po_check_df' in st.session_state and not st.session_state.po_check_df.empty:
    st.write("#### OEM/MRN/Mdarpan Code Mismatches:")
    mismatch_df = st.session_state.po_check_df

    st.dataframe(mismatch_df.head(2))

    if len(mismatch_df) > 2:
        st.write(f"- ... and {len(mismatch_df) - 2} more mismatches")

    st.download_button(
        label="⬇ Download Full PO Check CSV",
        data=mismatch_df.to_csv(index=False).encode('utf-8'),
        file_name="po_check.csv",
        mime="text/csv",
        key="po_check_download"
    )

col1, col2 = st.columns(2)
with col1:
    if st.button("✅ Continue Anyway"):
        st.session_state.continue_processing = True
        st.rerun()
with col2:
    if st.button("❌ Stop Processing"):
        st.session_state.continue_processing = False
        st.session_state.processing_complete = False
        st.session_state.show_reports = False
        st.session_state.missing_files = []
        st.session_state.period_validation_errors = []
        st.session_state.validation_log = pd.DataFrame()
        st.session_state.po_check_df = pd.DataFrame()
        st.warning("Processing stopped by user - page will refresh")
        time.sleep(2)
        st.rerun()

#=== SIDEBAR ===

with st.sidebar: st.header("⚙ Settings") uploaded_file = st.file_uploader("Upload Mahindra ZIP file", type=['zip'], help="Maximum file size: 200MB") if uploaded_file is not None: st.session_state.uploaded_file = uploaded_file

st.subheader("Part Category")
category_options = ['Spares', 'Accessories', 'All']
select_categories = st.multiselect("Choose categories to include in reports", label_visibility="collapsed", options=category_options, default='Spares')

st.subheader("📅 Date Range")
default_end = datetime.today()
default_start = default_end - timedelta(days=59)
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("Start Date", value=default_start)
with col2:
    end_date = st.date_input("End Date", value=default_end)
if start_date > end_date:
    st.error("End date must be after start date")
    st.stop()

st.subheader("🔄 Period Type")
period_type = st.selectbox("Select period type for validation", options=list(PERIOD_TYPES.keys()), key="period_type_select")
st.session_state.period_type = period_type

process_btn = st.button("🚀 Generate Reports", type="primary")

#=== MAIN PROCESS ===

if (process_btn or st.session_state.continue_processing) and st.session_state.uploaded_file is not None: if st.session_state.uploaded_file.size > 200 * 1024 * 1024: st.error("File size exceeds 200MB limit") st.stop()

temp_dir = tempfile.mkdtemp()
extract_path = os.path.join(temp_dir, "extracted_files")
os.makedirs(extract_path, exist_ok=True)

try:
    with zipfile.ZipFile(st.session_state.uploaded_file, 'r') as zip_ref:
        zip_ref.extractall(extract_path)
    st.session_state.extracted_path = extract_path
    st.success("✅ ZIP file extracted successfully")

    progress_bar = st.progress(0)
    status_text = st.empty()

    all_locations = []
    for brand in os.listdir(extract_path):
        brand_path = os.path.join(extract_path, brand)
        if not os.path.isdir(brand_path):
            continue
        for dealer in os.listdir(brand_path):
            dealer_path = os.path.join(brand_path, dealer)
            if not os.path.isdir(dealer_path):
                continue
            for location in os.listdir(dealer_path):
                location_path = os.path.join(dealer_path, location)
                if not os.path.isdir(location_path):
                    continue
                all_locations.append((brand, dealer, location, location_path))

    total_locations = len(all_locations)
    validation_errors, validation_log_df = validate_periods(
        all_locations, start_date, end_date, PERIOD_TYPES[st.session_state.period_type]
    )
    st.session_state.period_validation_errors = validation_errors
    st.session_state.validation_log = validation_log_df

    oem_po_df, mrn_po_df, mdarpan_po_df = validate_oem_mrn_po_codes(all_locations)
    po_check_df = pd.concat([oem_po_df, mrn_po_df, mdarpan_po_df], ignore_index=True)
    st.session_state.po_check_df = po_check_df

    if validation_errors or not po_check_df.empty:
        show_validation_issues()
    if st.session_state.continue_processing:
        process_files(
            validation_errors, all_locations, start_date, end_date, total_locations,
            progress_bar, status_text, select_categories
        )
        st.session_state.processing_complete = True
        st.session_state.show_reports = True
        st.rerun()

except Exception as e:
    st.error(f"❌ Error during processing: {str(e)}")

=== SHOW REPORTS IF READY ===

if st.session_state.processing_complete and st.session_state.show_reports: show_reports()

