# Process files if continuing
def process_files(validation_errors, all_locations, start_date, end_date,total_locations, progress_bar, status_text,select_categories):
    import streamlit as st
    import zipfile
    import os   
    import pandas as pd
    from datetime import datetime, timedelta
    import tempfile
    import shutil
    import io
    from openpyxl import Workbook
    from io import BytesIO
    import re
    import warnings
    #from ogy import select_categories
    
    dfs = {}

    def read_file(file_path):
      
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
                    
        
    # def read_file(file_path):
    #     try:
    #         # First try reading as Excel file
    #         if file_path.lower().endswith(('.xls', '.xlsx')):
    #             try:
    #                 # For .xlsx files
    #                 if file_path.lower().endswith('.xlsx'):
    #                     return pd.read_excel(file_path, engine='openpyxl')
    #                 # For .xls files
    #                 else:
    #                     # First try with xlrd (older version)
    #                     try:
    #                         return pd.read_excel(file_path, engine='xlrd')
    #                     except:
    #                         # Then try with openpyxl
    #                         try:
    #                             return pd.read_excel(file_path, engine='openpyxl')
    #                         except:
    #                             # Finally try with pyxlsb if it's a binary Excel file
    #                             try:
    #                                 return pd.read_excel(file_path, engine='pyxlsb')
    #                             except:
    #                                 # If all else fails, try reading as CSV
    #                                 return try_read_as_csv(file_path)
    #             except Exception as e:
    #                 print(f"Excel read failed for {file_path}, trying CSV approach: {e}")
    #                 return try_read_as_csv(file_path)
    #         # For non-Excel files, try as CSV
    #         else:
    #             return try_read_as_csv(file_path)
    #     except Exception as e:
    #         print(f"Failed to read {file_path}: {e}")
    #         return None

    # def try_read_as_csv(file_path):
    #     try:
    #         # Try UTF-8 first
    #         return pd.read_csv(file_path, encoding='utf-8', sep=None, engine='python', on_bad_lines='skip')
    #     except UnicodeDecodeError:
    #         try:
    #             # Try Windows-1252 if UTF-8 fails
    #             return pd.read_csv(file_path, encoding='windows-1252', sep=None, engine='python', on_bad_lines='skip')
    #         except Exception as e:
    #             print(f"CSV read failed for {file_path}: {e}")
    #             return None
    
    # Process each location
    for i, (brand, dealer, location, location_path) in enumerate(all_locations):
        progress = (i + 1) / total_locations
        progress_bar.progress(progress)
        status_text.text(f"Generating reports for {location} ({i+1}/{total_locations})...")
        
        oem_data = []
        stock_data = []
        Mrn_data = []
        Sale_order_data = []
        Mdarpan_data = []

        for file in os.listdir(location_path):
            file_path = os.path.join(location_path, file)
            
            if not os.path.isfile(file_path):
                continue
            elif not file.endswith('.xlsx'):
                st.warning(f"File not Excel Workbook and .xlsx extention For : {brand}-{dealer}-{location} :- {file}")
                continue
            df = read_file(file_path)
            if df is not None:
                df['__source_file__'] = file
                
                # Categorize the file
                file_lower = file.lower()
                if file_lower.startswith('oem'):
                    # Validate OEM columns
                    required_cols = ['Po Number', 'Part No.', 'Po Date', 'Po Status','PO qty.']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        validation_errors.append(f"{location}: OEM file missing columns - {', '.join(missing_cols)}")
                    else:
                        oem_data.append(df)
                elif file_lower.startswith('stock'):
                    # Validate Stock columns
                    required_cols = ['PART_NUMBR', 'CLOSE_QTY']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        validation_errors.append(f"{location}: Stock file missing columns - {', '.join(missing_cols)}")
                    else:
                        stock_data.append(df)
                elif file_lower.startswith('mdarpan'):
                    Mdarpan_data.append(df)
                    required_cols = ['SAP Order No', 'Order Qty']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        validation_errors.append(f"{location}: Mdarpann file missing columns - {', '.join(missing_cols)}")

                elif 'sales order satatus' in file_lower:
                    # Validate Sales Order columns
                    required_cols = ['Sales Order No.', 'Part Number']
                    missing_cols = [col for col in required_cols if col not in df.columns]
                    if missing_cols:
                        # Try alternative column names
                        alt_cols = {
                            'Sales Order No.': ['Sales Order No.', 'PO_NUMBER'],
                            'Part Number': ['Part Number', 'PART_NUM']
                        }
                        
                        found_all = True
                        for req_col, alt_names in alt_cols.items():
                            if req_col not in df.columns:
                                found = False
                                for alt in alt_names:
                                    if alt in df.columns:
                                        df.rename(columns={alt: req_col}, inplace=True)
                                        found = True
                                        break
                                if not found:
                                    validation_errors.append(f"{location}: Sales Order file missing column - {req_col}")
                                    found_all = False
                                    break
                        
                        if found_all:
                            Sale_order_data.append(df)
                    else:
                        Sale_order_data.append(df)
                elif file_lower.startswith('mrn'):
                    # Validate MRN columns
                    try:
                        mrn_list = read_file(file_path)
                        if len(mrn_list) >= 2:
                            # header = df.iloc[0]      
                            # data_df = df.iloc[1:].copy()  
                            # data_df.columns = header   
                            # data_df.reset_index(drop=True, inplace=True)
                            #st.write(mrn_list.columns)
                            # header_df = mrn_list[1].iloc[0] 
                            # data_df = mrn_list[0].iloc[1:].copy()
                            # data_df.columns = header_df
                            # data_df.reset_index(drop=True, inplace=True)
                            
                            required_cols = ['PO Number', 'Part Number', 'Stock Recvd', 'Receipt Type']
                            missing_cols = [col for col in required_cols if col not in mrn_list.columns]
                            if missing_cols:
                                validation_errors.append(f"{location}: MRN file missing columns - {', '.join(missing_cols)}")
                            else:
                                Mrn_data.append(mrn_list)
                    except Exception as e:
                        validation_errors.append(f"{location}: Error reading MRN file - {str(e)}")
                        # try:
                        #     mrn_list = read_file(file_path)
                        #     if len(mrn_list) >= 2:
                        #         header_df = mrn_list[1].iloc[0] 
                        #         data_df = mrn_list[0].iloc[1:].copy()
                        #         data_df.columns = header_df
                        #         data_df.reset_index(drop=True, inplace=True)        
                        #         required_cols = ['PO Number', 'Part Number', 'Stock Recvd', 'Receipt Type']
                        #         missing_cols = [col for col in required_cols if col not in mrn_list.columns]
                        #         if missing_cols:
                        #             validation_errors.append(f"{location}: MRN file missing columns - {', '.join(missing_cols)}")
                        #         else:
                        #             Mrn_data.append(data_df)                            
                        #     # mrn_list = read_file(file_path) 
                        #     # Mrn_data.append(data_df)
                        # except Exception as e:
                        #     validation_errors.append(f"{location}: Error reading MRN file - {str(e)}")
                        # validation_errors.append(f"{location}: Error reading MRN file - {str(e)}")
        # Process OEM data
        if oem_data:
            key = f"OEM_{brand}_{dealer}_{location}.xlsx"
            oem_key = pd.concat(oem_data, ignore_index=True)
            oem_key['Supplier Name'] = oem_key['Supplier Name'].astype(str)
            oem_key['Po line item status'] = oem_key['Po line item status'].astype(str)
            oem_key['PO Rejection Reason'] = oem_key['PO Rejection Reason'].astype(str)
            
            # Date validation
            try:
                oem_key2 = oem_key
                oem_key = oem_key[oem_key['PO qty.'] > 0]
                oem_key['Po Date'] = pd.to_datetime(oem_key['Po Date'], errors='coerce')
                oem_key['Po Release Date'] = pd.to_datetime(oem_key['Po Release Date'], errors='coerce')

                # Filter by date range
                oem_key = oem_key[
                    (oem_key['Po Date'].dt.date >= start_date) &
                    (oem_key['Po Date'].dt.date <= end_date)]

                if oem_key.empty:
                    validation_errors.append(f"{location}: No OEM data within selected date range")
            except Exception as e:
                validation_errors.append(f"{location}: Error processing OEM dates - {str(e)}")

            # Process OEM data logic
            try:
                oem_key['Po Release Date'] = oem_key.apply(
                    lambda row: row['Po Date'] if pd.isna(row['Po Release Date']) and row['Po Status'] == 'Release' else row['Po Release Date'],
                    axis=1)
                
                Po1 = oem_key[
                    (oem_key['Po Status'] == 'Release') &
                    (oem_key['Supplier Name'].str.startswith('MAHINDRA', na=False)) &
                    (oem_key['Po line item status'].isin(['Unchanged', 'Decreased', 'Added', 'Increased']))
                ]

                part_po_so = Po1.pivot_table(
                    values='SO qty.',
                    index=['Po Release Date', 'Part No.', 'Po Number'],
                    aggfunc='sum'
                ).reset_index().rename(columns={'SO qty.': 'PO qty.'})

                Po2 = oem_key[
                    (oem_key['Po Status'] == 'Release') &
                    (oem_key['Supplier Name'].str.startswith('MAHINDRA', na=False)) &
                    (oem_key['Po line item status'].isna()) &
                    (oem_key['OEM Order No'].notnull()) &
                    (oem_key['PO Rejection Reason'].isna() | oem_key['PO Rejection Reason'].str.contains('Credit limit') | oem_key['PO Rejection Reason'].str.contains('Oldest') )
                #    ~(oem_key['PO Rejection Reason'].str.contains('Credit|Oldest|Material', na=False))
                ]

                part_po_so2 = Po2.pivot_table(
                    values='PO qty.',
                    index=['Po Release Date', 'Part No.', 'Po Number'],
                    aggfunc='sum'
                ).reset_index()

                Po3 = oem_key[
                    (oem_key['Po Status'] == 'Release') &
                    (oem_key['Supplier Name'].str.startswith('MAHINDRA', na=False)) &
                    (oem_key['Po line item status'].isna()) &
                    (oem_key['OEM Order No'].isna()) &
                (oem_key['PO Rejection Reason'].isna() | oem_key['PO Rejection Reason'].str.contains('Credit') | oem_key['PO Rejection Reason'].str.contains('Oldest') | oem_key['PO Rejection Reason'].str.contains('Material'))
                #    ~(oem_key['PO Rejection Reason'].str.contains('Credit|Oldest|Material', na=False)) 
                &
                    (oem_key['Po Date'].dt.date >= (end_date - timedelta(days=2))) &
                    (oem_key['Po Date'].dt.date <= end_date)
                ]

                part_po_so3 = Po3.pivot_table(
                    values='PO qty.',
                    index=['Po Release Date', 'Part No.', 'Po Number'],
                    aggfunc='sum'
                ).reset_index()

                Oem_final = pd.concat([part_po_so, part_po_so2, part_po_so3], ignore_index=True)
                Oem_final['Location'] = location

                Oem_final_unique = Oem_final[
                    ['Location', 'Part No.', 'Po Number', 'Po Release Date', 'PO qty.']
                ].drop_duplicates(subset=['Location', 'Part No.', 'Po Number', 'Po Release Date', 'PO qty.'])

                Oem_final_unique.rename(columns={
                    'Po Number': 'OrderNumber',
                    'Part No.': 'PartNumber',
                    'PO qty.': 'POQty',
                    'Po Release Date': 'OrderDate'}, inplace=True)
                Oem_final_unique['OEMInvoiceNo']=''
                Oem_final_unique['OEMInvoiceDate']=''
                Oem_final_unique['OEMInvoiceQty']=''    
                
               # st.dataframe(Oem_final_unique)    
                # ✅ Default assignment to avoid UnboundLocalError
                Oem_final_unique_upload = Oem_final_unique.copy()

                if Mdarpan_data:
                    #key = f"Oem_{brand}_{dealer}_{location}.xlsx"
                    mdarpan_df = pd.concat(Mdarpan_data, ignore_index=True)
                    mdarpan_df['SAP Order Date'] = mdarpan_df['SAP Order Date'].astype(str).apply(
                                    lambda x: pd.to_datetime(x[10:].replace('.', '-'), format='%d-%m-%Y') 
                                    if len(x) > 10 else pd.to_datetime(x.replace('.', '-'), format='%d-%m-%Y'))

                    mdarpan_df = mdarpan_df[(mdarpan_df['SAP Order Date'].dt.date>= start_date)
                                            & (mdarpan_df['SAP Order Date'].dt.date<= end_date)]
                    
                    oem_key2 = pd.concat(oem_data, ignore_index=True)

                    # Safety check if 'oem_po_part' exists
                    required_cols = ['OEM Order No', 'Po Number','Po Date']
                    if not all(col in oem_key2.columns for col in required_cols):
                        validation_errors.append(f"{location}: Missing required columns in OEM data")
                    else:
                        sd = oem_key2[required_cols].drop_duplicates(subset=['OEM Order No', 'Po Number', 'Po Date'])
                        k = mdarpan_df.merge(
                            sd[['OEM Order No', 'Po Number', 'Po Date']],
                            left_on='SAP Order No',
                            right_on='OEM Order No',
                            how='left'
                        )
                        k['po_part']=k['Po Number']+k['Part Number']
                        Oem_final_unique['PartNumber'] = Oem_final_unique['PartNumber'].str.replace(r'[^a-zA-Z0-9\s]', '', regex=True)
                        Oem_final_unique['Po_part'] = Oem_final_unique['OrderNumber'] + Oem_final_unique['PartNumber']

                        do = k.merge(
                            Oem_final_unique[['PartNumber', 'OrderNumber', 'Po_part']],
                            left_on='po_part',
                            right_on='Po_part',
                            how='left'
                        )

                        md_for_oem_final = do[
                            (do['Po Number'].notnull()) &
                            ((do['Reason for Rejection'] == '-') | (do['Reason for Rejection'].isna())) &
                            (do['Po_part'].isna())
                        ]
                        md_for_oem_final['location']=location
                        md_for_oem_final_with_md = md_for_oem_final[
                            ['location', 'Part Number', 'Po Number', 'Order Qty', 'Po Date']].rename(columns={
                            'location': 'Location',
                            'Part Number': 'PartNumber',
                            'Po Number': 'OrderNumber',
                            'Order Qty': 'POQty',
                            'Po Date': 'OrderDate'})
                        md_for_oem_final_with_md['OEMInvoiceNo']=''
                        md_for_oem_final_with_md['OEMInvoiceDate']=''
                        md_for_oem_final_with_md['OEMInvoiceQty']='' 

                        Oem_final_unique.drop(columns='Po_part', inplace=True, errors='ignore')
                        Oem_final_unique_upload = pd.concat([Oem_final_unique, md_for_oem_final_with_md], ignore_index=True)
                        #Oem_final_unique_upload['OEMInvoiceNo']=''
                        #Oem_final_unique_upload['OEMInvoiceDate']=''
                        #Oem_final_unique_upload['OEMInvoiceQty']=''


                # ✅ Final assignment
                dfs[key] = Oem_final_unique_upload

            except Exception as e:
                validation_errors.append(f"{location}: Error processing OEM data - {str(e)}")

        
        # Process Stock data
        if stock_data:
            key = f"Stock_{brand}_{dealer}_{location}.xlsx"
            stock_df = pd.concat(stock_data, ignore_index=True)
            stock_df['Location'] = location
            if select_categories==['Spares']:
                stock_df = stock_df[stock_df['PART_CATGRY_DESC'].isin(select_categories)]
            elif select_categories==['Accessories']:
                stock_df = stock_df[stock_df['PART_CATGRY_DESC'].isin(select_categories)]
            elif select_categories==['Spares','Accessories']:
                stock_df = stock_df[stock_df['PART_CATGRY_DESC'].isin(select_categories)]

            stock_df = stock_df[['Location', 'PART_NUMBR', 'CLOSE_QTY']]
            stock_df.rename(
                columns={'PART_NUMBR': 'Partnumber', 'CLOSE_QTY': 'Qty'},
                inplace=True
            )
            dfs[key] = stock_df

            
        
        # Process MRN data
        if Mrn_data:
            key = f"MRN_{brand}_{dealer}_{location}.xlsx"
            mrn_df = pd.concat(Mrn_data, ignore_index=True)
            mrn = mrn_df[
                (mrn_df['Stock Recvd'].str.contains('Y', na=False)) &
                (mrn_df['Receipt Type'].str.contains('MRN', na=False))
            ]
            
            # Date validation
            try:
                mrn['Receipt Date'] = pd.to_datetime(mrn['Receipt Date'], errors='coerce')
                # mrn = mrn[
                #     (mrn['Receipt Date'].dt.date >= start_date) & 
                #     (mrn['Receipt Date'].dt.date <= end_date)
                # ]
                
                if mrn.empty:
                    validation_errors.append(f"{location}: No MRN data within selected date range")
            except Exception as e:
                validation_errors.append(f"{location}: Error processing MRN dates - {str(e)}")
            
            mrn['Location'] = location
            mrn['Received Qty'] = mrn['Received Qty'].astype(float)
            mrn['Receipt Date']=mrn['Receipt Date'].dt.strftime('%d-%b-%Y')
            mrn_pivot = mrn.pivot_table(
                values='Received Qty',
                index=['Location', 'PO Number', 'Part Number', 'Receipt Date'],
                aggfunc='sum'
            ).reset_index()
            mrn_pivot.rename(columns={
                    'Part Number': 'PartNumber',
                    'Received Qty': 'ReceiptQty',
                    'PO Number': 'OrderNumber',
                    'Receipt Date': 'OrderDate'},inplace=True)
            mrn_pivot['OEMInvoiceNo']=''
            mrn_pivot['OEMInvoiceDate']=''
            mrn_pivot['OEMInvoiceQty']=''
            mrn_pivot['MRNNumber']=''
            mrn_pivot['MRNDate']=''
            dfs[key] = mrn_pivot
        
        # # Process Mdarpan data
        # if Mdarpan_data:
        #     key = f"Oem_{brand}_{dealer}_{location}.xlsx"
        #     mdarpan_df = pd.concat(Mdarpan_data, ignore_index=True)
        #     oem_key2  =pd.concat(oem_data, ignore_index=True)
        #     sd = oem_key2[['OEM Order No', 'Po Number','Po Date','oem_po_part']]
        #     sd.drop_duplicates(subset =['OEM Order No', 'Po Number','Po Date'],inplace=True)
        #     k = mdarpan_df.merge(sd[['OEM Order No', 'Po Number','Po Date']],left_on='SAP Order No',right_on='OEM Order No',how='left')
        #     Oem_final_unique['PartNumber']= Oem_final_unique['PartNumber'].str.replace(r'[^a-zA-Z0-9\s]', '', regex=True)
        #     Oem_final_unique['Po_part']=Oem_final_unique['OrderNumber']+Oem_final_unique['PartNumber']
        #     do = k.merge(Oem_final_unique[['PartNumber', 'OrderNumber','Po_part']],left_on='po_part',right_on='Po_part',how='left')
        #     #mdarpan_df = mdarpan_df.merge(Oem_final_unique[['PartNumber', 'OEM Order No']], on='PartNumber', how='left')
        #     md_for_oem_final = do[(do['Po Number'].notnull()) & ((do['Reason for Rejection'] == '-') | (do['Reason for Rejection'].isna()))&do['Po_part'].isna()]
        #     md_for_oem_final_with_md = md_for_oem_final[['location','Part Number','Po Number','Order Qty','Po Date']]
        #     md_for_oem_final_with_md.rename(columns={'location':'Location','Part Number':'PartNumber','Po Number':'OrderNumber','Order Qty':'POQty','Po Date':'OrderDate'},inplace=True)
        #     Oem_final_unique.drop(columns='Po_part',inplace=True)
        #     Oem_final_unique_upload  = pd.concat([Oem_final_unique,md_for_oem_final_with_md],ignore_index=True)

        #     dfs[key] = Oem_final_unique_upload
        
        # Process Sales Order data
        if Sale_order_data:
            key = f"SalesOrder_{brand}_{dealer}_{location}.xlsx"
            sales_order_df = pd.concat(Sale_order_data, ignore_index=True)
            dfs[key] = sales_order_df
    
    # Show validation errors if any
    if validation_errors:
        st.warning("⚠ Validation issues found:")
        for error in validation_errors:
            st.write(f"- {error}")
    
    # Create download buttons for each report
    st.success("🎉 Reports generated successfully!")
    st.subheader("📥 Download Reports")
    
    # Group reports by type
    report_types = {
        'OEM': [k for k in dfs.keys() if k.startswith('OEM_')],
        'Stock': [k for k in dfs.keys() if k.startswith('Stock_')],
        'MRN': [k for k in dfs.keys() if k.startswith('MRN_')]
       # 'Mdarpan': [k for k in dfs.keys() if k.startswith('Mdarpan_')],
        #'Sales Order': [k for k in dfs.keys() if k.startswith('SalesOrder_')]
    }
    
    for report_type, files in report_types.items():
        if files:
            with st.expander(f"📂 {report_type} Reports ({len(files)})", expanded=False):
                for file in files:
                    df = dfs.get(file)
                    if df is not None and not df.empty:
                        st.markdown(f"### 📄 {file}")
                        st.dataframe(df.head(5))

                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='Sheet1')

                        st.download_button(
                            label="⬇ Download Excel",
                            data=excel_buffer.getvalue(),
                            file_name=file,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=f"dl_{file}"
                        )
                    else:
                        st.warning(f"⚠ No data for {file}")

   
    import io
    import zipfile
    import pandas as pd
    import streamlit as st
    from collections import defaultdict

    # ✅ Step 1: Group by (report_type, brand, dealer) → combine all locations into one DataFrame
    grouped_data = defaultdict(list)

    for file_name, df in dfs.items():
        parts = file_name.replace('.xlsx', '').split("_")

        if len(parts) >= 4:
            report_type = parts[0]   # OEM / MRN / Stock / etc.
            brand = parts[1]         # Mahindra
            dealer = parts[2]        # ABCDealer
            location = "_".join(parts[3:])  # Location1, Location_2 etc. (for trace)

            key = (report_type, brand, dealer)

            # 🏷️ Optionally add location column to retain trace
            if 'Location' not in df.columns:
                df['Location'] = location

            grouped_data[key].append(df)
        else:
            st.warning(f"❗ Invalid file name format: {file_name}")

    # ✅ Step 2: Generate ZIP with Excel files (one sheet per key)
    if grouped_data:
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for (report_type, brand, dealer), df_list in grouped_data.items():
                combined_df = pd.concat(df_list, ignore_index=True)

                excel_buffer = io.BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                    combined_df.to_excel(writer, sheet_name="Sheet1", index=False)

                output_filename = f"{report_type}_{brand}_{dealer}.xlsx"
                zipf.writestr(output_filename, excel_buffer.getvalue())

        # ✅ Download button
        st.download_button(
            label="📦 Download Combined Dealer Reports ZIP",
            data=zip_buffer.getvalue(),
            file_name="Combined_Dealerwise_Reports.zip",
            mime="application/zip"
        )
    else:
        st.info("ℹ No reports available to download.")























