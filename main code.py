import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
from sqlalchemy import text

# --- CONNECTION ---
conn = st.connection("postgresql", type="sql")

# --- HELPERS ---
def get_display_fields(row):
    row_dict = row.to_dict()
    exclude = ['id', 'spare_id', 'eq_type', 'qty', 'spare_type']
    return {k.replace('_', ' ').title(): v for k, v in row_dict.items() if v and str(v) != 'nan' and k not in exclude}

# --- APP UI CONFIG ---
st.set_page_config(layout="wide", page_title="Inventory Management")
if 'msg' not in st.session_state: st.session_state.msg = None
page = st.sidebar.radio("Navigation", ["Dashboard", "Manage Inventory", "Spare Tracking"])

# --- DASHBOARD PAGE ---
if page == "Dashboard":
    st.title("📊 Equipment & Shared Spare Dashboard")
    
    all_df = conn.query("SELECT * FROM inventory", ttl=0)
    if not all_df.empty:
        c1, c2 = st.columns(2)
        spare_qty = all_df.groupby('spare_type')['qty'].sum().reset_index()
        fig1 = px.bar(spare_qty, x='spare_type', y='qty', title="Total Qty by Spare Type", color='spare_type', text_auto=True)
        c1.plotly_chart(fig1, use_container_width=True)
        
        # Count equipment types from equipment table
        eq_df_count = conn.query("SELECT eq_type, COUNT(*) as count FROM equipment GROUP BY eq_type", ttl=0)
        if not eq_df_count.empty:
            fig2 = px.pie(eq_df_count, names='eq_type', values='count', title="Equipment Distribution")
            c2.plotly_chart(fig2, use_container_width=True)
        
    st.divider()
    
    # Search by Equipment ID (e.g., 99P05 or 99P07)
    search = st.text_input("🔍 Search Equipment ID (e.g., 99P05):").upper().strip()
    if search:
        # Query utilizing the junction table to find spares linked to this equipment
        query = """
            SELECT i.*, e.eq_id FROM inventory i
            JOIN equipment_spares es ON i.id = es.spare_id
            JOIN equipment e ON e.id = es.equipment_id
            WHERE e.eq_id ILIKE :search
        """
        df = conn.query(query, params={"search": f'%{search}%'}, ttl=0)
        
        if not df.empty:
            for spare_type_group in df['spare_type'].unique():
                st.subheader(f"📦 {spare_type_group}s for {search}")
                for _, row in df[df['spare_type'] == spare_type_group].iterrows():
                    
                    # Fetch ALL other equipment sharing this exact same spare_id
                    shared_query = """
                        e.eq_id FROM equipment e
                        JOIN equipment_spares es ON e.id = es.equipment_id
                        WHERE es.spare_id = :sid
                    """
                    shared_eqs_df = conn.query(f"SELECT {shared_query}", params={"sid": row['id']}, ttl=0)
                    shared_list = ", ".join(shared_eqs_df['eq_id'].tolist()) if not shared_eqs_df['eq_id'].empty else row['eq_id']
                    
                    header = row['spare_id'] if row.get('spare_id') else "Spare Part"
                    with st.expander(f"📍 ID: {header} | Qty: {row['qty']} | Shared Across: [{shared_list}]"):
                        st.markdown(f"**🔗 Shared with Equipment:** `{shared_list}`")
                        for k, v in get_display_fields(row).items(): 
                            if k != 'Eq Id':
                                st.markdown(f"**{k}:** {v}")
        else:
            st.warning("No spares found for this equipment ID.")
    else:
        st.caption("👈 Search an equipment ID above to view its components and discover shared parts.")

# --- MANAGE INVENTORY ---
elif page == "Manage Inventory":
    st.title("➕ Manage Inventory & Links")
    if st.session_state.msg: 
        st.success(st.session_state.msg)
        st.session_state.msg = None
        
    tab1, tab2, tab3, tab4 = st.tabs(["➕ Add New Spare", "⚙️ Register Equipment", "🔗 Link Existing Spare", "🔄 Update Quantity"])
    
    with tab1:
        st.subheader("Add Universal Spare & Link Equipment")
        
        # 1. Fetch available equipment to link
        eq_list_df = conn.query("SELECT id, eq_id FROM equipment", ttl=0)
        if eq_list_df.empty:
            st.warning("⚠️ Please register equipment in the 'Register Equipment' tab first before adding spares!")
        else:
            # Create selection dictionary mapping eq_id to database id
            eq_options = {row['eq_id']: row['id'] for _, row in eq_list_df.iterrows()}
            selected_eqs = st.multiselect("Select Compatible Equipment:", options=list(eq_options.keys()))
            
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
                
            qty = st.number_input("Warehouse Quantity:", min_value=0, key="add_qty")
            loc = st.text_input("Storage Location:", key="add_loc")
            
            if st.button("Save Spare & Link"):
                if not selected_eqs:
                    st.error("You must select at least one compatible equipment item!")
                else:
                    try:
                        with conn.session as s:
                            # Generate Unique Spare ID (e.g. BEAR-001)
                            count_res = s.execute(text("SELECT COUNT(*) FROM inventory")).fetchone()
                            next_num = (count_res[0] if count_res else 0) + 1
                            prefix = spare_type[:4].upper().replace(" ", "")
                            generated_spare_id = f"{prefix}-{next_num:03d}"
                            
                            # Insert Spare into Inventory Table
                            res = s.execute(text("""
                                INSERT INTO inventory (spare_id, spare_type, subtype, category, item_detail, origin, vendor, ref_date, qty, storage_loc, bearing_no, description, pulley_type, pulley_desc, seal_oem, valve_oem) 
                                VALUES (:sid, :st, :sub, :cat, :det, :ori, :ven, :ref, :qty, :loc, :bn, :desc, :pt, :pd, :soem, :voem)
                                RETURNING id
                            """), {
                                "sid": generated_spare_id, "st": spare_type, "sub": subtype, "cat": cat, 
                                "det": item_detail, "ori": origin, "ven": vendor, "ref": ref_date, 
                                "qty": qty, "loc": loc, "bn": bearing_no, "desc": description, 
                                "pt": pulley_type, "pd": pulley_desc, "soem": seal_oem, "voem": valve_oem
                            })
                            spare_pk_id = res.fetchone()[0]
                            
                            # Link to Multiple Equipment via Junction Table
                            for eq_name in selected_eqs:
                                eq_pk_id = eq_options[eq_name]
                                s.execute(text("""
                                    INSERT INTO equipment_spares (equipment_id, spare_id) 
                                    VALUES (:eq_id, :sp_id)
                                    ON CONFLICT DO NOTHING
                                """), {"eq_id": eq_pk_id, "sp_id": spare_pk_id})
                                
                            s.commit()
                        
                        st.session_state.msg = f"Successfully added spare ID **{generated_spare_id}** and linked to {len(selected_eqs)} equipment entries!"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving entry: {e}")

    with tab2:
        st.subheader("Register Machinery/Equipment First")
        new_eq_id = st.text_input("Equipment ID (e.g., 99P05, 99P07):", key="reg_eq_id").upper().strip()
        new_eq_type = st.selectbox("Equipment Type:", ["Pump", "Compressor", "AFC", "Fan"], key="reg_eq_type")
        
        if st.button("Register Equipment"):
            if not new_eq_id:
                st.error("Equipment ID cannot be empty.")
            else:
                try:
                    with conn.session as s:
                        s.execute(text("""
                            INSERT INTO equipment (eq_id, eq_type) VALUES (:eid, :etype)
                            ON CONFLICT (eq_id) DO NOTHING
                        """), {"eid": new_eq_id, "etype": new_eq_type})
                        s.commit()
                    st.success(f"Equipment **{new_eq_id}** registered successfully!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error registering equipment: {e}")
    with tab3:
        st.subheader("Link an Existing Spare to Another Equipment")
        
        # 1. Fetch all spares
        spares_df = conn.query("SELECT id, spare_id, spare_type, description, bearing_no, seal_oem FROM inventory", ttl=0)
        # 2. Fetch all equipment
        eq_df = conn.query("SELECT id, eq_id FROM equipment", ttl=0)
        
        if spares_df.empty or eq_df.empty:
            st.info("You need both registered equipment and spare parts to create a link.")
        else:
            # Create a nice label for the spare dropdown
            spares_df['label'] = spares_df['spare_id'] + " - " + spares_df['spare_type']
            spare_options = {row['label']: row['id'] for _, row in spares_df.iterrows()}
            eq_options = {row['eq_id']: row['id'] for _, row in eq_df.iterrows()}
            
            selected_spare_label = st.selectbox("Select Spare Part:", list(spare_options.keys()))
            selected_equipment_id = st.selectbox("Select Equipment to Link:", list(eq_options.keys()))
            
            if st.button("Create Link"):
                chosen_spare_pk = spare_options[selected_spare_label]
                chosen_eq_pk = eq_options[selected_equipment_id]
                
                try:
                    with conn.session as s:
                        # Insert into the junction table
                        s.execute(text("""
                            INSERT INTO equipment_spares (equipment_id, spare_id) 
                            VALUES (:eq_id, :sp_id)
                            ON CONFLICT DO NOTHING
                        """), {"eq_id": chosen_eq_pk, "sp_id": chosen_spare_pk})
                        s.commit()
                    st.success(f"Successfully linked **{selected_spare_label}** to equipment **{selected_equipment_id}**!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error creating link: {e}")

    with tab4:
        st.subheader("Update Stock and Log Maintenance")
        eq_dropdown_df = conn.query("SELECT eq_id FROM equipment", ttl=0)
        if not eq_dropdown_df.empty:
            selected_update_eq = st.selectbox("Select Equipment ID to manage spares:", [""] + list(eq_dropdown_df['eq_id'].unique()))
            if selected_update_eq:
                # Query inventory linked to this specific equipment
                eq_inv_query = """
                    SELECT i.* FROM inventory i
                    JOIN equipment_spares es ON i.id = es.spare_id
                    JOIN equipment e ON e.id = es.equipment_id
                    WHERE e.eq_id = :eq
                """
                eq_df = conn.query(eq_inv_query, params={"eq": selected_update_eq}, ttl=0)
                if not eq_df.empty:
                    with st.form("update_form"):
                        u_data = {}
                        u_desc = {}
                        for _, r in eq_df.iterrows():
                            with st.container(border=True):
                                details = get_display_fields(r)
                                desc_str = f"[{r['spare_id']}] {r['spare_type']} | " + " | ".join([f"{k}: {v}" for k, v in details.items()])
                                u_desc[r['id']] = desc_str

                                st.write(f"### ID: `{r['spare_id']}` — {r['spare_type']}")
                                cols = st.columns(3)
                                idx = 0
                                for k, v in details.items():
                                    cols[idx % 3].write(f"**{k}:** {v}")
                                    idx += 1
                                st.write(f"**Location:** {r.get('storage_loc', 'N/A')}")
                                st.write("---")
                                
                                c1, c2 = st.columns(2)
                                new_q = c1.number_input(f"New Global Warehouse Qty", value=int(r['qty']), key=f"q_{r['id']}")
                                rsn = c2.text_input(f"Maintenance Reason", key=f"r_{r['id']}")
                                
                                u_data[r['id']] = (new_q, rsn, r['qty'])

                        if st.form_submit_button("Save Stock Updates & Log"):
                            updated_count = 0
                            with conn.session as s:
                                for id, (q, rsn, old_q) in u_data.items():
                                    if int(q) != int(old_q):
                                        s.execute(text("UPDATE inventory SET qty = :q WHERE id = :id"), {"q": q, "id": id})
                                        detailed_spare_info = u_desc[id]
                                        
                                        s.execute(text("""
                                            INSERT INTO logs (date, equipment, spare, change, old_qty, new_qty, reason) 
                                            VALUES (NOW(), :eq, :sp, 'UPDATE', :o, :n, :rsn)
                                        """), {
                                            "eq": selected_update_eq, "sp": detailed_spare_info, "o": old_q, "n": q, "rsn": rsn
                                        })
                                        updated_count += 1
                                s.commit()
                            if updated_count > 0:
                                st.session_state.msg = f"Successfully updated {updated_count} item(s)!"
                            else:
                                st.session_state.msg = "No quantity changes detected."
                            st.rerun()
                else:
                    st.info("No parts are currently linked to this equipment.")

elif page == "Spare Tracking":
    st.title("📊 Activity History Stream")
    log_df = conn.query("SELECT * FROM logs", ttl=0)
    if not log_df.empty:
        all_eqs = sorted(log_df['equipment'].dropna().unique())
        sel_eqs = st.multiselect("Filter by Equipment ID:", all_eqs)
        if sel_eqs:
            log_df = log_df[log_df['equipment'].isin(sel_eqs)]
        log_df = log_df.sort_values(by='date', ascending=False)
        for _, row in log_df.head(20).iterrows():
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                col1.caption(str(row['date']))
                col1.metric("Equipment", str(row['equipment']))
                col2.write("**Spare Component Details**")
                col2.write(str(row['spare']))
                diff = int(row['new_qty']) - int(row['old_qty'])
                col3.metric("Change", f"{diff:+d}", delta_color="normal")
                col3.write(f"Reason: {row['reason']}")
    else:
        st.info("No logs recorded yet.")
