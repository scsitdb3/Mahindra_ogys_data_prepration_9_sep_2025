import streamlit as st
import zipfile
import os
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import shutil
import io
import warnings
from io import StringIO
import time
from Report import process_files

# ---------------- Page Config ---------------- #
st.set_page_config(page_title="Mahindra Report Generator", layout="wide", initial_sidebar_state="expanded")

st.title("🚗 Mahindra Order Generator")
st.markdown("""
📊 Generate comprehensive reports from Mahindra data files including:
- OEM Reports
- Stock Reports
- MRN Reports
- Mdarpan Reports
- Sales Order Reports
""")

# ---------------- Session State Init ---------------- #
state_vars = [
    "uploaded_file", "extracted_path", "validation_errors", "period_validation_errors",
    "missing_files", "validation_log", "continue_processing", "processing_complete",
    "report_results", "show_reports", "oem_mismatches", "mrn_mismatches", "mdarpan_mismatches"
]
for var in state_vars:
    if var not in st.session_state:
        if var in ["validation_errors", "period_validation_errors", "missing_files"]:
            st.session_state[var] = []
        elif var in ["validation_log", "oem_mismatches", "mrn_mismatches", "mdarpan_mismatches"]:
            st.session_state[var] = pd.DataFrame()
        elif var == "continue_processing":
            st.session_state[var] = False
        elif var == "processing_complete":
            st.session_state[var] = False
        elif var == "report_results":
            st.session_state[var] = None
        elif var == "show_reports":
            st.session_state[var] = False
        else:
            st.session_state[var] = None

# ---------------- Period Mapping ---------------- #
PERIOD_TYPES = {"Day": 1, "Week": 7, "Month": 30, "Quarter": 90, "Year": 365}

# ---------------- File Readers ---------------- #

def read_file(file_path,file_type=None):
    #file_paths= os.path.basename(file_path)
    #st.write(file_path)
    # Try to extract filename safely
    if "extracted_files/" in file_path:
        file_name = file_path.split("extracted_files/")[1]
    else:
        file_name = os.path.basename(file_path)
    try:
        if file_path.lower().endswith('.xlsx'):
            return pd.read_excel(file_path)
        else:
            return st.warning(f"File not Excel Workbook and .xlsx extention For : {file_name}")
    except Exception as e:
        print(f" read failed for {file_path}: {e}")
        return None
       



# def read_file(file_path, file_type=None):
#     try:
#         if file_type and file_type.lower() == 'mrn':
#             return read_mrn_file(file_path)
#         if file_path.lower().endswith(('.xls', '.xlsx')):
#             return read_excel_file(file_path)
#         return read_csv_file(file_path)
#     except Exception as e:
#         warnings.warn(f"Failed to read {file_path}: {str(e)}")
#         return None

# def read_excel_file(file_path):
#     engines_to_try = ['openpyxl', 'xlrd'] if file_path.lower().endswith('.xlsx') else ['xlrd', 'openpyxl', 'pyxlsb']
#     for engine in engines_to_try:
#         try:
#             with warnings.catch_warnings():
#                 warnings.simplefilter("ignore")
#                 return pd.read_excel(file_path, engine=engine)
#         except:
#             continue
#     return read_csv_file(file_path)

# def read_csv_file(file_path):
#     encodings_to_try = ['utf-8', 'windows-1252', 'iso-8859-1', 'latin1']
#     for encoding in encodings_to_try:
#         try:
#             df = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python', on_bad_lines='warn', dtype=str)
#             if len(df.columns) == 1:
#                 for sep in [',', ';', '\t', '|']:
#                     try:
#                         df = pd.read_csv(StringIO(df.iloc[:, 0].str.cat(sep='\n')), sep=sep, engine='python', on_bad_lines='warn')
#                         if len(df.columns) > 1:
#                             break
#                     except:
#                         continue
#             return df
#         except UnicodeDecodeError:
#             continue
#         except Exception as e:
#             warnings.warn(f"CSV read failed for {file_path} with {encoding}: {str(e)}")
#             continue
#     return None

# def read_mrn_file(file_path):
#     try:
#         tables = pd.read_html(file_path)
#         if len(tables) >= 2:
#             header_df = tables[1].iloc[0] 
#             data_df = tables[0].iloc[1:].copy()
#             data_df.columns = header_df
#             return data_df.reset_index(drop=True)
#         elif len(tables) == 1:
#             return tables[0]
#         return None
#     except Exception as e:
#         warnings.warn(f"MRN file read failed for {file_path}: {str(e)}")
#         return None

# ---------------- Validation Functions ---------------- #
def validate_periods(all_locations, start_date, end_date, period_days):
    validation_errors = []
    missing_periods_log = []
    current_date = start_date
    periods = []
    while current_date <= end_date:
        period_end = min(current_date + timedelta(days=period_days - 1), end_date)
        periods.append((current_date, period_end))
        current_date = period_end + timedelta(days=1)

    for brand, dealer, location, location_path in all_locations:
        
        oem_files = [f for f in os.listdir(location_path) if f.lower().startswith('oem')]
        mrn_files = [f for f in os.listdir(location_path) if f.lower().startswith('mrn')]
        if not oem_files or not mrn_files:
            continue

        oem_has_period = {p: False for p in periods}
        for oem_file in oem_files:
            try:
                oem_df = read_file(os.path.join(location_path, oem_file))
                if oem_df is None or 'Po Date' not in oem_df.columns:
                    continue
                elif not oem_file.endswith('.xlsx'):
                    st.warning(f"File not Excel Workbook and .xlsx extention For : {brand}-{dealer}-{location}:-oem_file")
                    continue
                
                oem_df['Po Date'] = pd.to_datetime(oem_df['Po Date'], errors='coerce')
                for period_start, period_end in periods:
                    if any(period_start <= d.date() <= period_end for d in oem_df['Po Date'].dropna()):
                        oem_has_period[(period_start, period_end)] = True
            except Exception as e:
                validation_errors.append(f"{location}: Error validating OEM periods - {str(e)}")

        mrn_has_period = {p: False for p in periods}
        for mrn_file in mrn_files:
            try:
                mrn_df = read_file(os.path.join(location_path, mrn_file), file_type='mrn')
                if mrn_df is None or 'Receipt Date' not in mrn_df.columns:
                    continue
                mrn_df['Receipt Date'] = pd.to_datetime(mrn_df['Receipt Date'], errors='coerce')
                for period_start, period_end in periods:
                    if any(period_start <= d.date() <= period_end for d in mrn_df['Receipt Date'].dropna()):
                        mrn_has_period[(period_start, period_end)] = True
            except Exception as e:
                validation_errors.append(f"{location}: Error validating MRN periods - {str(e)}")

        for period_start, period_end in periods:
            missing_in = []
            if not oem_has_period[(period_start, period_end)]: missing_in.append("OEM")
            if not mrn_has_period[(period_start, period_end)]: missing_in.append("MRN")
            if missing_in:
                missing_periods_log.append({
                    'Brand': brand, 'Dealer': dealer, 'Location': location,
                    'Period': f"{period_start} to {period_end}",
                    'Missing In': ", ".join(missing_in)
                })
                validation_errors.append(f"{location}: {' and '.join(missing_in)} missing for period {period_start} to {period_end}")

    validation_log_df = pd.DataFrame(missing_periods_log) if missing_periods_log else pd.DataFrame(columns=['Brand', 'Dealer', 'Location', 'Period', 'Missing In'])
    return validation_errors, validation_log_df

def validate_oem_mrn_po_codes(all_locations):
    df = pd.read_excel(
        r"https://docs.google.com/spreadsheets/d/e/2PACX-1vTeXEadE1Hf4G2T-o4XCvGYMyRKj6f2sVxsSDaPs_sJwmGbnCFoDzSJx9JHDaNzw5JKdk4l0Q0Yctmh/pub?output=xlsx"
    )
    sd = df[df['Oem_Check'].notnull() | df['Mrn_Check'].notnull()].copy()
    sd['Location'] = sd['Location'].str.lower()
    oem_po_Check, mdarpan_po_check, mrn_po_Check = [], [], []

    for brand, dealer, location, location_path in all_locations:
        location_lower = location.lower()

        # OEM Check
        for oem_file in [f for f in os.listdir(location_path) if f.lower().startswith('oem')]:
            try:
                oem_df = read_file(os.path.join(location_path, oem_file))
                if oem_df is None or 'Po Number' not in oem_df.columns:
                    continue
                oem_df['Location'] = location_lower
                oem_df['Po_Code'] = oem_df['Po Number'].astype(str).str[:6].str[-1].str.lower()
                for i, j in oem_df[['Location', 'Po_Code']].drop_duplicates().values:
                    if not any(i in k and l.lower() in j for k, l in zip(sd['Location'], sd['Oem_Check'].fillna('indal'))):
                        oem_po_Check.append({'Location': i, 'Po_Code': j})
            except: pass

        # MRN Check
        for mrn_file in [f for f in os.listdir(location_path) if f.lower().startswith('mrn')]:
            try:
                mrn_list = pd.read_html(os.path.join(location_path, mrn_file))
                header_df = mrn_list[1].iloc[0]
                data_df = mrn_list[0].iloc[1:].copy()
                data_df.columns = header_df
                data_df['Location'] = location_lower
                data_df['po_code'] = data_df['PO Number'].astype(str).str[:6].str[-1].str.lower()
                for i, j in data_df[['Location', 'po_code']].drop_duplicates().values:
                    if not any(i in k.lower() and l.lower() in j for k, l in zip(sd['Location'], sd['Mrn_Check'].fillna('indal'))):
                        mrn_po_Check.append({'Location': i, 'Po_Code': j})
            except: pass

        # Mdarpan Check
        for md_file in [f for f in os.listdir(location_path) if f.lower().startswith('mdarpan')]:
            try:
                mdrpn_df = read_file(os.path.join(location_path, md_file))
                if mdrpn_df is None or 'Sold_To' not in mdrpn_df.columns:
                    continue
                mdrpn_df['Location'] = location_lower
                for i, j in mdrpn_df[['Location', 'Sold_To']].dropna().drop_duplicates().values:
                    if not any(i in k.lower() and l.lower() in str(j).lower() for k, l in zip(sd['Location'], sd['Mdarpan_Check'].fillna('indal'))):
                        mdarpan_po_check.append({'Location': i, 'Sold_To': j})
            except: pass

    return pd.DataFrame(oem_po_Check), pd.DataFrame(mrn_po_Check), pd.DataFrame(mdarpan_po_check)

# ---------------- UI Functions ---------------- #
def show_validation_issues():
    st.warning("⚠ Validation Issues Found")
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
                st.write(f"- ... and {len(st.session_state.period_validation_errors)-2} more")  
    col3, col4, col5,col6 = st.columns(4)
    with col3:
        if not st.session_state.validation_log.empty:
            st.download_button("📥 Download Full Validation Log", data=st.session_state.validation_log.to_csv(index=False).encode('utf-8'),
                        file_name="validation_issues_log.csv", mime="text/csv")
    with col4:
        if not st.session_state.oem_mismatches.empty:
            st.download_button("⬇ Download OEM Mismatches", data=st.session_state.oem_mismatches.to_csv(index=False),
                            file_name="OEM_Mismatches.csv", mime="text/csv")
    with col5:
        if not st.session_state.mrn_mismatches.empty:
            st.download_button("⬇ Download MRN Mismatches", data=st.session_state.mrn_mismatches.to_csv(index=False),
                            file_name="MRN_Mismatches.csv", mime="text/csv")
    with col6:
        if not st.session_state.mdarpan_mismatches.empty:
            st.download_button("⬇ Download Mdarpan Mismatches", data=st.session_state.mdarpan_mismatches.to_csv(index=False),
                            file_name="Mdarpan_Mismatches.csv", mime="text/csv")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Continue Anyway"):
            st.session_state.continue_processing = True
            st.rerun()
    with col2:
        if st.button("❌ Stop Processing"):
            st.session_state.continue_processing = False
            st.session_state.show_reports = False
            st.warning("Processing stopped by user")
            time.sleep(1)
            st.rerun()
            st.clear()

def show_reports():
    st.success("🎉 Reports generated successfully!")
    if st.session_state.report_results:
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_name, df in st.session_state.report_results.items():
                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                zipf.writestr(file_name, excel_buffer.getvalue())
        st.download_button("📦 Download All Reports as ZIP", data=zip_buffer.getvalue(),
                           file_name="Mahindra_Reports.zip", mime="application/zip")

# ---------------- Sidebar ---------------- #
with st.sidebar:
    st.header("⚙ Settings")
    uploaded_file = st.file_uploader("Upload Mahindra ZIP file", type=['zip'])
    if uploaded_file is not None:
        st.session_state.uploaded_file = uploaded_file
    select_categories = st.multiselect("Choose categories", options=['Spares', 'Accessories', 'All'], default='Spares')
    default_end = datetime.today()
    default_start = default_end - timedelta(days=59)
    start_date = st.date_input("Start Date", value=default_start)
    end_date = st.date_input("End Date", value=default_end)
    period_type = st.selectbox("Select period type", options=list(PERIOD_TYPES.keys()))
    st.session_state.period_type = period_type
    process_btn = st.button("🚀 Generate Reports", type="primary")

# ---------------- Main Processing ---------------- #
if (process_btn or st.session_state.continue_processing) and st.session_state.uploaded_file is not None:
    if st.session_state.uploaded_file.size > 200 * 1024 * 1024:
        st.error("File size exceeds 200MB limit")
        st.stop()

    temp_dir = tempfile.mkdtemp()
    extract_path = os.path.join(temp_dir, "extracted_files")
    os.makedirs(extract_path, exist_ok=True)

    try:
        with zipfile.ZipFile(st.session_state.uploaded_file, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        st.session_state.extracted_path = extract_path
        st.success("✅ ZIP file extracted successfully")

        all_locations = []
        for brand in os.listdir(extract_path):
            for dealer in os.listdir(os.path.join(extract_path, brand)):
                for location in os.listdir(os.path.join(extract_path, brand, dealer)):
                    location_path = os.path.join(extract_path, brand, dealer, location)
                    if os.path.isdir(location_path):
                        all_locations.append((brand, dealer, location, location_path))

        missing_files = []
        for brand, dealer, location, location_path in all_locations:
            required = {'OEM': False, 'MRN': False, 'Stock': False,'Mdarpan':False}
            for file in os.listdir(location_path):
                f = file.lower()
                if f.startswith('oem'): required['OEM'] = True
                if f.startswith('mrn'): required['MRN'] = True
                if f.startswith('stock'): required['Stock'] = True
                if f.startswith('mdarpan'): required['Mdarpan'] = True    
            for k, v in required.items():
                if not v:
                    missing_files.append(f"{brand}/{dealer}/{location} - Missing: {k}")

        period_days = PERIOD_TYPES.get(st.session_state.period_type, 1)
        period_validation_errors, validation_log = validate_periods(all_locations, start_date, end_date, period_days)
        oem_mismatches, mrn_mismatches, mdarpan_mismatches = validate_oem_mrn_po_codes(all_locations)

        st.session_state.missing_files = missing_files
        st.session_state.period_validation_errors = period_validation_errors
        st.session_state.validation_log = validation_log
        st.session_state.oem_mismatches = oem_mismatches
        st.session_state.mrn_mismatches = mrn_mismatches
        st.session_state.mdarpan_mismatches = mdarpan_mismatches

        # Process only if allowed
        if st.session_state.continue_processing or (not missing_files and not period_validation_errors and oem_mismatches.empty and mrn_mismatches.empty and mdarpan_mismatches.empty):
            progress_bar = st.progress(0)
            status_text = st.empty()
            with st.spinner("Processing files..."):
                process_files([], all_locations, start_date, end_date, len(all_locations), progress_bar, status_text, select_categories)
            st.session_state.processing_complete = True
            st.session_state.show_reports = True
        else:
            st.session_state.show_reports = False

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

# ---------------- Output ---------------- #
if st.session_state.uploaded_file is not None:
    if (st.session_state.missing_files or st.session_state.period_validation_errors or not st.session_state.oem_mismatches.empty or not st.session_state.mrn_mismatches.empty or not st.session_state.mdarpan_mismatches.empty) and not st.session_state.continue_processing:
        show_validation_issues()
    elif st.session_state.show_reports:
        show_reports()











