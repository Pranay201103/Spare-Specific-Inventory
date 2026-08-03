import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from sqlalchemy import text

# --- CONNECTION ---
conn = st.connection("postgresql", type="sql")

# --- 2. HELPERS ---
def get_display_fields(row):
    row_dict = row.to_dict()
    exclude = ['id', 'compatible_equipment', 'eq_type', 'qty', 'spare_type']
    return {k.replace('_', ' ').title(): v for k, v in row_dict.items() if v and str(v) != 'nan' and k not in exclude}

# --- 3. APP UI ---
st.set_page_config(layout="wide", page_title="Inventory Management")
if 'msg' not in st.session_state: st.session_state.msg = None
page = st.sidebar.radio("Navigation", ["Dashboard", "Manage Inventory", "Spare Tracking"])

# --- DASHBOARD PAGE ---
if page == "Dashboard":
    st.title("📊 Equipment & Global Spare Inventory Dashboard")
    all_df = conn.query("SELECT * FROM inventory", ttl=0)
    if not all_df.empty:
        c1, c2 = st.columns(2)
        spare_qty = all_df.groupby('spare_type')['qty'].sum().reset_index()
        fig1 = px.bar(spare_qty, x='spare_type', y='qty', title="Total Qty by Spare Type", color='spare_type', text_auto=True)
        c1.plotly_chart(fig1, use_container_width=True)
        
        eq_type_qty = all_df.groupby('eq_type')['qty'].sum().reset_index()
        fig2 = px.pie(eq_type_qty, names='eq_type', values='qty', title="Qty by Equipment Type")
        c2.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    # Search across global inventory using the compatible equipment tag field
    search = st.text_input("🔍 Search Compatible Equipment (e.g., Pump 101):").upper().strip()
    if search:
        df = conn.query("SELECT * FROM inventory WHERE compatible_equipment ILIKE :search", params={"search": f'%{search}%'}, ttl=0)
        if not df.empty:
            for spare in df['spare_type'].unique():
                st.subheader(f"📦 {spare}s")
                for _, row in df[df['spare_type'] == spare].iterrows():
                    if spare == 'Mechanical spares':
                        header = row['description'] if row.get('description') and str(row['description']) != 'nan' else "Mechanical Spare"
                    else:
                        header = " | ".join([str(row[c]) for c in ['subtype', 'item_detail'] if row.get(c) and str(row[c]) != 'nan']) or "Standard"
                    with st.expander(f"📍 {header} | Total Qty: {row['qty']} | Fits: {row['compatible_equipment']}"):
                        st.markdown(f"**Compatible Equipment:** {row['compatible_equipment']}")
                        for k, v in get_display_fields(row).items(): 
                            st.markdown(f"**{k}:** {v}")
        else:
            st.warning("No spare parts found for this equipment.")
    else:
        st.caption("👈 Search equipment tags above to view compatible parts and stock levels.")

# --- MANAGE INVENTORY ---
elif page == "Manage Inventory":
    st.title("➕ Manage Universal Inventory")
    if st.session_state.msg: 
        st.success(st.session_state.msg)
        st.session_state.msg = None
        
    tab1, tab2 = st.tabs(["➕ Add New Universal Spare", "🔄 Update Quantity"])
    
    with tab1:
        # Changed from single equipment ID to comma-separated compatible equipment tags
        compatible_equipment = st.text_input("Compatible Equipment IDs (comma-separated):", key="add_compat", placeholder="Pump-101, Pump-102, Compressor-A").upper().strip()
        eq_type = st.selectbox("Primary Equipment Type:", ["Pump", "Compressor", "AFC", "Fan"], key="add_eq")
        options = {"Pump": ["Seal", "Bearing", "Mechanical spares"],
                   "Compressor": ["Valve", "Bearing", "Mechanical spares"],
                   "AFC": ["Belt", "Pulley", "Bearing", "Mechanical spares"]}
        spare_type = st.selectbox("Spare Type:", options.get(eq_type, ["Bearing", "Mechanical spares"]), key="add_spare")
        
        subtype, cat, origin, vendor, ref_date, item_detail, bearing_no, description, pulley_type, pulley_desc, seal_oem, valve_oem = [None] * 12
        
        if eq_type == "Pump" and spare_type == "Seal":
            subtype = st.selectbox("Sub-type:", ["Cartridge seal", "Seal spare"], key="add_sub")
            if subtype == "Seal spare":
                cat = st.selectbox("Category:", ["Faces", "Packings"], key="add_cat")
                item_detail = st.text_input(f"Enter {cat} details:", key="add_det")
            seal_oem = st.text_input("Seal OEM:", key="add_oem")
            origin = st.selectbox("Origin:", ["OEM", "Locally made", "Locally refurbished"], key="add_orig")
        elif eq_type == "Compressor" and spare_type == "Valve":
            subtype = st.selectbox("Valve Type:", ["Suction valve", "Discharge valve"], key="add_sub")
            origin = st.selectbox("Condition:", ["New", "Refurbished"], key="add_orig")
            if origin == "New":
                valve_oem = st.text_input("Valve OEM:", key="add_v_oem")
            else:
                vendor = st.text_input("Vendor Name:", key="add_ven")
                ref_date = st.date_input("Refurbishment Date:", key="add_date").strftime("%Y-%m-%d")
        elif spare_type == "Bearing":
            bearing_no = st.text_input("Enter Bearing Number:", key="add_bear")
            origin = st.selectbox("Origin:", ["OEM", "Locally made"], key="add_orig")
        elif spare_type == "Mechanical spares":
            description = st.text_input("Enter Description:", key="add_desc")
            origin = st.selectbox("Origin:", ["OEM", "Locally made"], key="add_orig")
        elif eq_type == "AFC" and spare_type == "Pulley":
            pulley_type = st.selectbox("Pulley Type:", ["Motor pulley", "Fan pulley"], key="add_p_type")
            pulley_desc = st.text_input("Enter Pulley Description:", key="add_p_desc")
            origin = st.selectbox("Origin:", ["OEM", "Locally made"], key="add_orig")
            
        if origin and origin != "OEM" and spare_type != "Valve":
            vendor = st.text_input("Vendor Name:", key="add_ven")
            ref_date = st.date_input("Date:", key="add_date").strftime("%Y-%m-%d")
            
        qty = st.number_input("Total Global Warehouse Quantity:", min_value=0, key="add_qty")
        loc = st.text_input("Storage Location:", key="add_loc")
        
        if st.button("Save Universal Spare"):
            if not compatible_equipment:
                st.error("Compatible Equipment is mandatory!")
            else:
                try:
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO inventory (compatible_equipment, eq_type, spare_type, subtype, category, item_detail, origin, vendor, ref_date, qty, storage_loc, bearing_no, description, pulley_type, pulley_desc, seal_oem, valve_oem) 
                            VALUES (:compat, :et, :st, :sub, :cat, :det, :ori, :ven, :ref, :qty, :loc, :bn, :desc, :pt, :pd, :soem, :voem)
                        """), {
                            "compat": compatible_equipment, "et": eq_type, "st": spare_type, "sub": subtype, "cat": cat, 
                            "det": item_detail, "ori": origin, "ven": vendor, "ref": ref_date, 
                            "qty": qty, "loc": loc, "bn": bearing_no, "desc": description, 
                            "pt": pulley_type, "pd": pulley_desc, "soem": seal_oem, "voem": valve_oem
                        })
                        s.commit()
                    
                    st.session_state.msg = "Universal spare added successfully!"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving entry: {e}")
      
    with tab2:
        # Load unique entries or search for items to update quantity
        search_query = st.text_input("Filter inventory items by spare or tag:", "").upper().strip()
        query_str = "SELECT * FROM inventory"
        if search_query:
            query_str += f" WHERE spare_type ILIKE '%{search_query}%' OR compatible_equipment ILIKE '%{search_query}%'"
        
        inv_df = conn.query(query_str, ttl=0)
        if not inv_df.empty:
            with st.form("update_form"):
                u_data = {}
                u_desc = {}
                for _, r in inv_df.iterrows():
                    with st.container(border=True):
                        details = get_display_fields(r)
                        desc_str = f"{r['spare_type']} (Fits: {r['compatible_equipment']}) | " + " | ".join([f"{k}: {v}" for k, v in details.items()])
                        u_desc[r['id']] = desc_str

                        st.write(f"### {r['spare_type']} — *Fits: {r['compatible_equipment']}*")
                        cols = st.columns(3)
                        idx = 0
                        for k, v in details.items():
                            cols[idx % 3].write(f"**{k}:** {v}")
                            idx += 1
                        st.write(f"**Location:** {r.get('storage_loc', 'N/A')}")
                        st.write("---")
                        
                        c1, c2, c3 = st.columns(3)
                        new_q = c1.number_input(f"New Global Qty", value=int(r['qty']), key=f"q_{r['id']}")
                        # Require the user to type the *specific* machine this part is being withdrawn for
                        target_machine = c2.text_input(f"Installed On (Equipment)", key=f"m_{r['id']}", placeholder="e.g. Pump-101")
                        rsn = c3.text_input(f"Reason", key=f"r_{r['id']}")
                        
                        u_data[r['id']] = (new_q, rsn, target_machine, r['qty'], r['compatible_equipment'])

                if st.form_submit_button("Save Updates & Log"):
                    updated_count = 0
                    with conn.session as s:
                        for id, (q, rsn, target_machine, old_q, compat) in u_data.items():
                            if int(q) != int(old_q):
                                s.execute(text("UPDATE inventory SET qty = :q WHERE id = :id"), {"q": q, "id": id})
                                detailed_spare_info = u_desc[id]
                                
                                log_equipment = target_machine if target_machine else compat
                                s.execute(text("""
                                    INSERT INTO logs (date, equipment, spare, change, old_qty, new_qty, reason) 
                                    VALUES (NOW(), :eq, :sp, 'UPDATE', :o, :n, :rsn)
                                """), {
                                    "eq": log_equipment, "sp": detailed_spare_info, "o": old_q, "n": q, "rsn": rsn
                                })
                                updated_count += 1
                        s.commit()
                    if updated_count > 0:
                        st.session_state.msg = f"Successfully updated {updated_count} item(s) and logged changes!"
                    else:
                        st.session_state.msg = "No quantity changes were detected."
                    st.rerun()
        else:
            st.info("No inventory records found.")

elif page == "Spare Tracking":
    st.title("📊 Activity Dashboard & Log History")
    log_df = conn.query("SELECT * FROM logs", ttl=0)
    if not log_df.empty:
        all_eqs = sorted(log_df['equipment'].dropna().unique())
        sel_eqs = st.multiselect("Filter by Equipment/Tag:", all_eqs)
        if sel_eqs:
            log_df = log_df[log_df['equipment'].isin(sel_eqs)]
        log_df = log_df.sort_values(by='date', ascending=False)
        st.subheader("Recent Activity Stream")
        for _, row in log_df.head(15).iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                col1.caption(str(row['date']))
                col1.metric("Target Equipment", str(row['equipment']))
                col2.write("**Item Details**")
                col2.write(str(row['spare']))
                diff = int(row['new_qty']) - int(row['old_qty'])
                col3.metric("Change", f"{diff:+d}", delta_color="normal")
                col3.write(f"Reason: {row['reason']}")
    else:
        st.info("No activity logs to display yet.")
