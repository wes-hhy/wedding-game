import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time
import os
import random
import base64
from datetime import datetime

st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- THE BULLETPROOF ROLE ROUTER ---
q_params = st.query_params
page_param = q_params.get("page", "")
if isinstance(page_param, list):
    page_param = page_param[0] if len(page_param) > 0 else ""

# Note: "?page=lobby" is still used to route to the Projector display!
if "lobby" in q_params or page_param.lower() == "lobby":
    st.session_state.app_role = "lobby"
elif "admin" in q_params or page_param.lower() == "admin":
    st.session_state.app_role = "admin"
elif "app_role" not in st.session_state:
    st.session_state.app_role = "guest"

page = st.session_state.app_role

# --- VISUAL CALIBRATION ---
BOX_WIDTH = 282
BOX_HEIGHT = 191
X_OFFSET = 305
Y_START = 164
Y_GAP = 19 

Y_POSITIONS = [
    Y_START, 
    Y_START + (BOX_HEIGHT + Y_GAP), 
    Y_START + (BOX_HEIGHT + Y_GAP) * 2, 
    Y_START + (BOX_HEIGHT + Y_GAP) * 3
]

# Locked in for the wedding day!
CORRECT_SEQUENCE = [1, 2, 0, 9]

TABLE_LIST = ["Select...", "VIP1", "VIP2", "1", "2", "3", "5", "6", "7", "8", "9", "10", "11", "12", "13", "15", "16", "17", "18", "19", "20", "21", "22", "23", "25", "26", "27", "28", "29"]

hints = {
    0: "Day zero. Our very first date, getting to know each other where it all beGINs.",
    1: "One down, many to come. Our first snowboard trip together!",
    2: "October 20th. The night two of us officially became a couple.",
    3: "A party of three. Alpaca, you, and me!",
    4: "Forever young. Cosplaying as students in our late-20s at Lotte World, tapping out after 2 rides.",
    5: "No PS5, but Switch-ed up the friendzone pose at Mind Cafe.",
    6: "A six-hour flight to catch our first autumn together in Kyushu.",
    7: "Ran up and down the hill seven times with ahjummas staring at us for this shot.",
    8: "Double the Huat. Our second CNY together.",
    9: "On cloud nine. So shocked she kept asking when did he collect the ring, instead of saying yes."
}

# 🚨 THE CACHING ENGINE (PREVENTS FLASHING) 🚨
@st.cache_resource
def load_template():
    return Image.open("images_for_app/Film Strip Empty_V2.jpg").convert("RGBA")

@st.cache_resource
def load_and_resize_photo(photo_id):
    img = Image.open(f"images_for_app/{photo_id}.jpg").convert("RGBA")
    return ImageOps.fit(img, (BOX_WIDTH, BOX_HEIGHT), Image.Resampling.LANCZOS)

@st.cache_resource
def get_reveal_strip(revealed_str):
    bg = load_template().copy()
    revealed_list = revealed_str.split(",") if revealed_str else []
    for i in range(4):
        if str(i + 1) in revealed_list:
            p_id = CORRECT_SEQUENCE[i]
            img = load_and_resize_photo(p_id)
            bg.paste(img, (X_OFFSET, Y_POSITIONS[i]))
    return bg

@st.cache_resource
def load_qr():
    if os.path.exists("images_for_app/qr.png"):
        return Image.open("images_for_app/qr.png").convert("RGBA")
    return None

# --- AUDIO INJECTOR ENGINE ---
def get_audio_html(filename):
    path = f"images_for_app/{filename}"
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
            b64 = base64.b64encode(data).decode()
            # 🚨 THE AUTOPLAY FIX 🚨
            # Injecting a unique timestamp ID forces React to completely destroy the old 
            # drumroll tag and mount a brand new one, guaranteeing the browser fires 'autoplay'.
            uid = str(time.time()).replace(".", "")
            return f'<div id="audio_wrapper_{uid}"><audio autoplay="true" style="display:none;" src="data:audio/mp3;base64,{b64}"></audio></div>'
    return ""

# --- SESSION MEMORY ---
if "selected_photos" not in st.session_state:
    st.session_state.selected_photos = []
if "has_submitted" not in st.session_state:
    st.session_state.has_submitted = False
if "guest_name" not in st.session_state:
    st.session_state.guest_name = ""
if "table_number" not in st.session_state:
    st.session_state.table_number = ""
if "game_started" not in st.session_state:
    st.session_state.game_started = False
if "start_time" not in st.session_state:
    st.session_state.start_time = 0.0
if "final_time" not in st.session_state:
    st.session_state.final_time = 0.0
if "last_projector_state" not in st.session_state:
    st.session_state.last_projector_state = "unknown"

def select_photo(photo_id):
    if len(st.session_state.selected_photos) < 4 and photo_id not in st.session_state.selected_photos:
        st.session_state.selected_photos.append(photo_id)

def clear_photos():
    st.session_state.selected_photos = []

def generate_film_strip(selected_ids):
    bg = load_template().copy()
    for i, p_id in enumerate(selected_ids):
        img = load_and_resize_photo(p_id)
        bg.paste(img, (X_OFFSET, Y_POSITIONS[i]))
    return bg

# --- THE BACKGROUND SCORING ENGINE ---
def get_score(sub):
    score = 0
    try:
        if int(sub.get("slot_1", -1)) == CORRECT_SEQUENCE[0]: score += 1
        if int(sub.get("slot_2", -1)) == CORRECT_SEQUENCE[1]: score += 1
        if int(sub.get("slot_3", -1)) == CORRECT_SEQUENCE[2]: score += 1
        if int(sub.get("slot_4", -1)) == CORRECT_SEQUENCE[3]: score += 1
    except (ValueError, TypeError):
        pass
    return score

# --- FETCH GAME STATE & SUBMISSIONS ---
response = supabase.table("game_state").select("status").eq("id", 1).execute()
game_status = response.data[0]["status"]

subs_response = supabase.table("submissions").select("*").execute()
all_submissions = subs_response.data

# Score every submission and separate the true winners
for sub in all_submissions:
    sub["score"] = get_score(sub)

# Winners (4/4) sorted by speed (index 0 is fastest)
winners = [s for s in all_submissions if s["score"] == 4]
winners = sorted(winners, key=lambda x: float(x.get("time_taken") or 9999.0))

# Everyone ranked by highest score first, then fastest speed
ranked_submissions = sorted(all_submissions, key=lambda x: (-x.get("score", 0), float(x.get("time_taken") or 9999.0)))

# ----------------- ADMIN SCREEN -----------------
if page == "admin":
    st.title("Admin Control 👑")
    
    st.subheader("1. Game Controls")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 GAME OPEN (LIVE)", use_container_width=True):
            supabase.table("game_state").update({"status": "started"}).eq("id", 1).execute()
    with col2:
        if st.button("🛑 STOP GAME (CLOSED)", type="primary", use_container_width=True):
            supabase.table("game_state").update({"status": "closed"}).eq("id", 1).execute()

    st.divider()
    
    st.subheader("2. Projector Reveal Sequence")
    
    if not game_status.startswith("reveal|"):
        if st.button("🔓 Enter Reveal Mode", type="primary", use_container_width=True):
            supabase.table("game_state").update({"status": "reveal|"}).eq("id", 1).execute()
            st.rerun()
        st.info("Click to display the 4 locked vaults on the projector before revealing answers.")
    else:
        revealed_slots = []
        parts = game_status.split("|")
        if len(parts) > 1 and parts[1] != "":
            revealed_slots = parts[1].split(",")

        r_cols = st.columns(4)
        for i in range(1, 5):
            with r_cols[i-1]:
                if str(i) in revealed_slots:
                    st.success(f"Slot {i} Revealed")
                else:
                    if st.button(f"Reveal Slot {i}", type="primary"):
                        revealed_slots.append(str(i))
                        supabase.table("game_state").update({"status": f"reveal|{','.join(revealed_slots)}"}).eq("id", 1).execute()
                        st.rerun()

    st.divider()
    
    # 🚨 THE NEW PODIUM ENGINE CONTROLS 🚨
    st.subheader("3. Final Results Podium")
    w_col1, w_col2 = st.columns(2)
    with w_col1:
        if st.button("🏆 Start Winners Podium", use_container_width=True):
            supabase.table("game_state").update({"status": "winners|0"}).eq("id", 1).execute()
            st.rerun()
    with w_col2:
        if st.button("🥈 Start Runner-Up Podium", use_container_width=True):
            supabase.table("game_state").update({"status": "runner_up|0"}).eq("id", 1).execute()
            st.rerun()

    # If a podium is active, show the step-by-step reveal controls
    if game_status.startswith("winners|") or game_status.startswith("runner_up|"):
        st.write("---")
        st.write("**Podium Progression:**")
        podium_type, step_str = game_status.split("|")
        step = int(step_str)
        
        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            if step >= 1:
                st.success("🥉 3rd Place Revealed")
            else:
                if st.button("Reveal 🥉 3rd Place", type="primary", use_container_width=True):
                    supabase.table("game_state").update({"status": f"{podium_type}|1"}).eq("id", 1).execute()
                    st.rerun()
        with p_col2:
            if step >= 2:
                st.success("🥈 2nd Place Revealed")
            else:
                if st.button("Reveal 🥈 2nd Place", type="primary", disabled=(step < 1), use_container_width=True):
                    supabase.table("game_state").update({"status": f"{podium_type}|2"}).eq("id", 1).execute()
                    st.rerun()
        with p_col3:
            if step >= 3:
                st.success("🥇 1st Place Revealed")
            else:
                if st.button("Reveal 🥇 1st Place!", type="primary", disabled=(step < 2), use_container_width=True):
                    supabase.table("game_state").update({"status": f"{podium_type}|3"}).eq("id", 1).execute()
                    st.rerun()

    st.divider()
    
    st.subheader(f"Live Stats ({len(all_submissions)} Total Submissions)")
    st.write(f"**Perfect Answers:** {len(winners)}")
    
    with st.expander("View All Submissions Data"):
        if all_submissions:
            reordered_subs = []
            for sub in all_submissions:
                reordered_subs.append({
                    "score": f"{sub.get('score')}/4", 
                    "time_taken": sub.get("time_taken"),
                    "table_number": sub.get("table_number"),
                    "guest_name": sub.get("guest_name"),
                    "slot_1": sub.get("slot_1"),
                    "slot_2": sub.get("slot_2"),
                    "slot_3": sub.get("slot_3"),
                    "slot_4": sub.get("slot_4"),
                    "submitted_at": sub.get("submitted_at"),
                    "id": sub.get("id")
                })
            st.dataframe(reordered_subs)
        else:
            st.dataframe(all_submissions)
            
        if st.button("🚨 CLEAR ALL SUBMISSIONS"):
            supabase.table("submissions").delete().gt("id", 0).execute()
            st.success("Database wiped!")

# ----------------- PROJECTOR SCREEN -----------------
elif page == "lobby":

    # --- ADVANCED AV DELAY ENGINE ---
    # To sync the drumroll perfectly before the visual appears, we decouple 
    # the 'game_status' (DB state) from 'display_status' (Projector Visual State)
    if "display_status" not in st.session_state:
        st.session_state.display_status = game_status
    if "pending_audio" not in st.session_state:
        st.session_state.pending_audio = None
    if "pending_balloons" not in st.session_state:
        st.session_state.pending_balloons = False

    audio_to_play = None
    trigger_balloons = False

    # Check if a state change occurred from the database
    if game_status != st.session_state.last_projector_state:
        st.session_state.last_projector_state = game_status
        
        if game_status.startswith("reveal|"):
            parts = game_status.split("|")
            if len(parts) > 1 and parts[1] != "":
                # Answer Revealed: Play drumroll NOW, but leave display_status on the OLD state to delay the visual
                audio_to_play = "drumroll.mp3"
            else:
                # Just entered Reveal Mode (0 slots), update visual immediately
                st.session_state.display_status = game_status

        elif game_status.startswith("winners|") or game_status.startswith("runner_up|"):
            step = int(game_status.split("|")[1])
            if step == 0:
                st.session_state.display_status = game_status
            elif step == 1:
                # 3rd Place: No audio, balloons, immediate visual
                st.session_state.display_status = game_status
                trigger_balloons = True
            elif step == 2:
                # 2nd Place: Cheer, balloons, immediate visual
                st.session_state.display_status = game_status
                audio_to_play = "cheer.mp3"
                trigger_balloons = True
            elif step == 3:
                # 1st Place: Drumroll NOW, delay visual for 1 cycle. Queue cheer and balloons for next cycle.
                audio_to_play = "drumroll.mp3"
                st.session_state.pending_audio = "cheer.mp3"
                st.session_state.pending_balloons = True
        else:
            # Started, Closed, etc. update immediately
            st.session_state.display_status = game_status

    else:
        # NO database change. BUT, check if our projector display is lagging behind (The Delay Catch-up)
        if st.session_state.display_status != game_status:
            st.session_state.display_status = game_status
            
            # Fire any effects that were queued while the drumroll was playing (e.g. 1st Place cheer)
            if st.session_state.pending_audio:
                audio_to_play = st.session_state.pending_audio
                st.session_state.pending_audio = None
            if st.session_state.pending_balloons:
                trigger_balloons = True
                st.session_state.pending_balloons = False

    # 🚨 THE DOM SHIFT FIX 🚨
    # Render audio tag immediately in a hidden slot at the absolute top of the DOM.
    audio_html_tag = get_audio_html(audio_to_play) if audio_to_play else ""
    if audio_html_tag:
        st.markdown(audio_html_tag, unsafe_allow_html=True)
    else:
        st.markdown("<span style='display:none;'></span>", unsafe_allow_html=True)
    
    st.markdown("""
    <style>
        /* Vertically centers the entire left column (Text + QR) relative to the tall image on the right! */
        [data-testid="stAppViewContainer"] > .main > div > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
            align-items: center !important; 
        }
    </style>
    """, unsafe_allow_html=True)
    
    # We now strictly render the frontend based on the d_status variable
    d_status = st.session_state.display_status
    
    text_col, image_col = st.columns([1, 1.2], gap="large")
    
    with text_col:
        # 🚨 THE DOM WIPE CONTAINER (KILLS ALL GHOSTS) 🚨
        text_master_container = st.empty()
        with text_master_container.container():
            
            if d_status in ["started", "lobby"]: 
                st.markdown("<h2 style='font-size: 38px; font-weight: 800; line-height: 1.1; margin-bottom: 0px;'>Wesley & Angel’s Film Strip Challenge! 📸</h2>", unsafe_allow_html=True)
                st.markdown(f"<h3 style='font-size: 22px; color: #444; margin-top: 10px; margin-bottom: 15px;'>Total Submissions: {len(all_submissions)}</h3>", unsafe_allow_html=True)
                st.info("Scan the code below to play! Fastest correct answer wins.")
                
            elif d_status == "closed":
                st.markdown("<h2 style='font-size: 42px; font-weight: 800; line-height: 1.1; margin-bottom: 0px;'>🛑 TIME'S UP!</h2>", unsafe_allow_html=True)
                st.markdown(f"<h3 style='font-size: 22px; color: #444; margin-top: 10px; margin-bottom: 15px;'>Total Submissions Locked In: {len(all_submissions)}</h3>", unsafe_allow_html=True)
                st.markdown("<p style='font-size: 18px; color: #666;'>Eyes on the screen... let's reveal the answers!</p>", unsafe_allow_html=True)
                
            elif d_status.startswith("reveal|"):
                st.markdown("<h2 style='font-size: 38px; font-weight: 800; line-height: 1.1; margin-top: -20px; padding-top: 0px; margin-bottom: 15px;'>The Master Code...</h2>", unsafe_allow_html=True)
                revealed_slots = []
                parts = d_status.split("|")
                if len(parts) > 1 and parts[1] != "":
                    revealed_slots = parts[1].split(",")
                
                html = "<h3>Reveal Status:</h3>"
                for i in range(1, 5):
                    mb = "12px" if i < 4 else "0px" 
                    if str(i) in revealed_slots:
                        p_id = CORRECT_SEQUENCE[i-1]
                        hint_text = hints[p_id]
                        html += f"<div style='display: flex; background-color: #f8f9fa; border-left: 6px solid #2e7d32; border-radius: 4px; margin-bottom: {mb}; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden;'><div style='background-color: #2e7d32; color: white; font-size: 28px; font-weight: 900; padding: 15px; width: 60px; text-align: center; display: flex; align-items: center; justify-content: center;'>{p_id}</div><div style='padding: 12px 15px; color: #333; font-size: 14px; display: flex; align-items: center; line-height: 1.4;'><i>\"{hint_text}\"</i></div></div>"
                    else:
                        html += f"<div style='display: flex; background-color: #fafafa; border-left: 6px solid #ccc; border-radius: 4px; margin-bottom: {mb}; border: 1px dashed #e0e0e0; overflow: hidden;'><div style='background-color: #eee; color: #aaa; font-size: 28px; font-weight: 900; padding: 15px; width: 60px; text-align: center; display: flex; align-items: center; justify-content: center;'>?</div><div style='padding: 12px 15px; color: #999; font-size: 14px; display: flex; align-items: center; font-style: italic;'>Slot {i} Locked</div></div>"
                st.markdown(html, unsafe_allow_html=True)
                st.markdown("<div style='height: 140px;'></div>", unsafe_allow_html=True) 
                
            elif d_status.startswith("winners|") or d_status.startswith("runner_up|"):
                podium_type, step_str = d_status.split("|")
                step = int(step_str)
                
                if podium_type == "winners":
                    st.markdown("<h2 style='font-size: 38px; font-weight: 800; line-height: 1.1; margin-bottom: 15px;'>🎉 Top 3 Winners! 🎉</h2>", unsafe_allow_html=True)
                    target_list = winners
                    fallback_msg = "No one got the exact sequence! Let's check the Runner-Up board!"
                else:
                    st.markdown("<h2 style='font-size: 38px; font-weight: 800; line-height: 1.1; margin-bottom: 15px;'>🥈 Top Runner-Ups!</h2>", unsafe_allow_html=True)
                    if len(ranked_submissions) > 0:
                        best_score = ranked_submissions[0]["score"]
                        target_list = [s for s in ranked_submissions if s["score"] == best_score]
                    else:
                        best_score = 0
                        target_list = []
                    fallback_msg = "No submissions found!"

                if len(target_list) == 0 or (podium_type == "runner_up" and best_score == 0):
                    st.markdown(f"<div style='padding:15px; background-color:#ffebee; color:#c62828; border-radius:8px; font-family:sans-serif;'>{fallback_msg}</div>", unsafe_allow_html=True)
                else:
                    if podium_type == "winners":
                        st.markdown("<div style='font-size:18px; margin-bottom:15px; font-family:sans-serif;'>The fastest perfect sequences:</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='font-size:18px; margin-bottom:15px; font-family:sans-serif;'>Nobody got all 4, but these guests were the closest (<b>{best_score}/4 correct</b>):</div>", unsafe_allow_html=True)
                    
                    # Pad the list so we always have 3 slots to check against
                    podium_guests = target_list[:3]
                    while len(podium_guests) < 3:
                        podium_guests.append(None)
                    
                    # Styling arrays 
                    medals = ["🥇 1st Place", "🥈 2nd Place", "🥉 3rd Place"]
                    bg_colors = ["#fff3e0", "#e3f2fd", "#e8f5e9"] # orange, blue, green
                    text_colors = ["#e65100", "#1565c0", "#2e7d32"]
                    
                    # --- REVEAL LOGIC RE-ORDERED: 1st (Top), 2nd (Middle), 3rd (Bottom) ---
                    
                    # 1st Place Logic (Top Slot)
                    if step >= 3:
                        guest = podium_guests[0]
                        if guest:
                            time_val = float(guest.get('time_taken') or 0.0)
                            display_name = f"Table {guest.get('table_number', '?')} - {guest['guest_name']}"
                            st.markdown(f"<div style='padding:15px; background-color:{bg_colors[0]}; color:{text_colors[0]}; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 2px solid {text_colors[0]}40;'>{medals[0]}: {display_name} ({time_val:.2f}s)</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='padding:15px; background-color:#f8f9fa; color:#adb5bd; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 1px dashed #ced4da;'>{medals[0]}: No one qualified!</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='padding:15px; background-color:#fafafa; color:#999; border-radius:8px; margin-bottom:10px; font-style:italic; font-family:sans-serif; border: 1px dashed #e0e0e0; display:flex; justify-content:center; align-items:center;'>🔒 {medals[0]} Locked</div>", unsafe_allow_html=True)

                    # 2nd Place Logic (Middle Slot)
                    if step >= 2:
                        guest = podium_guests[1]
                        if guest:
                            time_val = float(guest.get('time_taken') or 0.0)
                            display_name = f"Table {guest.get('table_number', '?')} - {guest['guest_name']}"
                            st.markdown(f"<div style='padding:15px; background-color:{bg_colors[1]}; color:{text_colors[1]}; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 2px solid {text_colors[1]}40;'>{medals[1]}: {display_name} ({time_val:.2f}s)</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='padding:15px; background-color:#f8f9fa; color:#adb5bd; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 1px dashed #ced4da;'>{medals[1]}: No one qualified!</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='padding:15px; background-color:#fafafa; color:#999; border-radius:8px; margin-bottom:10px; font-style:italic; font-family:sans-serif; border: 1px dashed #e0e0e0; display:flex; justify-content:center; align-items:center;'>🔒 {medals[1]} Locked</div>", unsafe_allow_html=True)

                    # 3rd Place Logic (Bottom Slot)
                    if step >= 1:
                        guest = podium_guests[2]
                        if guest:
                            time_val = float(guest.get('time_taken') or 0.0)
                            display_name = f"Table {guest.get('table_number', '?')} - {guest['guest_name']}"
                            st.markdown(f"<div style='padding:15px; background-color:{bg_colors[2]}; color:{text_colors[2]}; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 2px solid {text_colors[2]}40;'>{medals[2]}: {display_name} ({time_val:.2f}s)</div>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"<div style='padding:15px; background-color:#f8f9fa; color:#adb5bd; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif; border: 1px dashed #ced4da;'>{medals[2]}: No one qualified!</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='padding:15px; background-color:#fafafa; color:#999; border-radius:8px; margin-bottom:10px; font-style:italic; font-family:sans-serif; border: 1px dashed #e0e0e0; display:flex; justify-content:center; align-items:center;'>🔒 {medals[2]} Locked</div>", unsafe_allow_html=True)

        # 🚨 THE PERMANENT GHOST-PROOF QR COLUMNS 🚨
        qr_c1, qr_c2, qr_c3 = st.columns([1, 3.2, 1]) 
        with qr_c2:
            if d_status in ["lobby", "started"]: 
                qr_img = load_qr()
                if qr_img:
                    st.image(qr_img, use_container_width=True)
                else:
                    st.info("⚠️ Admin: Upload qr.png")
            else:
                st.image(Image.new('RGBA', (1, 1), (0, 0, 0, 0)), use_container_width=True)

    with image_col:
        # Calls the cached PIL engine directly, stopping the polling flash
        if d_status in ["lobby", "started", "closed"]:
            st.image(load_template(), use_container_width=True)
            
        elif d_status.startswith("reveal|"):
            parts = d_status.split("|")
            revealed_str = parts[1] if len(parts) > 1 else ""
            st.image(get_reveal_strip(revealed_str), use_container_width=True)
            
        elif d_status.startswith("winners|") or d_status.startswith("runner_up|"):
            st.image(get_reveal_strip("1,2,3,4"), use_container_width=True)

    # Trigger global effects safely outside of the layout columns
    if trigger_balloons:
        st.balloons()

    time.sleep(3)
    st.rerun()

# ----------------- GUEST SCREEN -----------------
else:
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] > .main .block-container { padding-bottom: 300px !important; }
        
        /* --- THE TUTORIAL CAROUSEL --- */
        [data-testid="stVerticalBlock"]:has(.tutorial-marker) [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 15px !important;
            padding-bottom: 10px !important;
            scrollbar-width: none; 
        }
        [data-testid="stVerticalBlock"]:has(.tutorial-marker) [data-testid="stHorizontalBlock"]::-webkit-scrollbar { display: none; }
        
        [data-testid="stVerticalBlock"]:has(.tutorial-marker) [data-testid="column"] {
            flex: 0 0 75vw !important;
            width: 75vw !important;
            min-width: 75vw !important;
            padding: 0 !important;
        }

        /* --- THE HORIZONTAL SCROLL GALLERY --- */
        [data-testid="stVerticalBlock"]:has(.gallery-marker) [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: nowrap !important;
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 15px !important;
            padding-bottom: 10px !important;
            scrollbar-width: none; 
        }
        [data-testid="stVerticalBlock"]:has(.gallery-marker) [data-testid="stHorizontalBlock"]::-webkit-scrollbar { display: none; }
        
        [data-testid="stVerticalBlock"]:has(.gallery-marker) [data-testid="column"] {
            flex: 0 0 25vw !important;
            width: 25vw !important;
            min-width: 25vw !important;
            padding: 0 !important;
        }

        /* --- THE FIXED FLOATING FOOTER --- */
        [data-testid="stVerticalBlockBorderWrapper"]:has(.footer-marker) {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            z-index: 99999 !important;
            background-color: var(--background-color, #ffffff) !important;
            box-shadow: 0px -5px 20px rgba(0,0,0,0.15) !important;
            border-radius: 20px 20px 0 0 !important;
            margin: 0 !important;
            padding: 15px 15px 30px 15px !important; 
        }
        
        [data-testid="stVerticalBlockBorderWrapper"]:has(.footer-marker) [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-wrap: nowrap !important;
            gap: 5px !important;
        }
        [data-testid="stVerticalBlockBorderWrapper"]:has(.footer-marker) [data-testid="column"] {
            flex: 1 1 0px !important;
            width: 25% !important;
            min-width: 25% !important;
            padding: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # 🚨 LOBBY LOGIC MERGED WITH STARTED 🚨
    if game_status in ["started", "lobby"]:
        if st.session_state.has_submitted:
            st.title("The WAW Film Strip Challenge 📸")
            st.success("Answers locked in! Thanks for playing. Enjoy your dinner and stay tuned for the grand reveal later tonight! 🥂")
            
            st.markdown("<h3 style='text-align: center; color: #333; font-family: serif; margin-bottom: 10px;'>Submission Locked 🔐</h3>", unsafe_allow_html=True)
            html_receipt = f"""
            <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); padding: 15px 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center;'>
                <div style='text-align: left; line-height: 1.2;'>
                    <div style='color: #777; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;'>Table {st.session_state.table_number}</div>
                    <div style='color: #333; font-size: 16px; font-weight: 600;'>{st.session_state.guest_name}</div>
                </div>
                <div style='background-color: #2e7d32; color: white; padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: bold;'>
                    ⏱️ {st.session_state.final_time:.2f}s
                </div>
            </div>
            """
            st.markdown(html_receipt, unsafe_allow_html=True)
            
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
            st.info("📸 Take a screenshot of this page! **Make sure your name and time are clearly visible for prize verification.**")
        
        elif not st.session_state.game_started:
            st.title("The WAW (Wesley & Angel Wedding) Film Strip Challenge! 📸")
            st.write("We have laid out 10 of our favorite memories. Can you unlock the true WAW factor?")
            
            with st.container():
                st.markdown('<div class="tutorial-marker"></div>', unsafe_allow_html=True)
                img_col1, img_col2 = st.columns(2)
                with img_col1:
                    st.image(load_template(), use_container_width=True, caption="1. The Empty Strip (Swipe 👉)")
                with img_col2:
                    # Generate a random dummy sequence
                    dummy_sequence = random.sample(range(10), 4)
                    
                    # Failsafe: Ensure the RNG never accidentally displays the actual winning code
                    if dummy_sequence == CORRECT_SEQUENCE:
                        dummy_sequence = [7, 0, 2, 8] 
                        
                    dummy_strip = generate_film_strip(dummy_sequence)
                    st.image(dummy_strip, use_container_width=True, caption="2. The Goal (example)")

            st.info("""
            *Every picture holds a memory—and counts for something more. Can you figure out the perfect sequence?*
            
            **How to Play:**
            1. **Build the Strip:** Once the game starts, swipe through the gallery to select your 4 photos.
            2. **Fair Play:** Strictly ONE entry per person. We are watching! 👀
            """)
            st.warning("⏱️ **Accuracy first, speed second!** The winner is the fastest guest to submit the *perfect sequence*. Your timer starts the exact millisecond you click start. Do not close the app or you will lose your progress.")
            
            st.divider()
            st.write("### Register to Play")
            
            input_table = st.selectbox("Table Number", options=TABLE_LIST)
            input_name = st.text_input("Your Real Name", placeholder="For prize verification!")
                
            if st.button("Start Challenge ⏱️", type="primary", use_container_width=True):
                if input_table == "Select..." or input_name.strip() == "":
                    st.error("Please select your table and enter your name to begin!")
                else:
                    is_duplicate = any(
                        s.get("guest_name", "").lower() == input_name.strip().lower() and 
                        str(s.get("table_number", "")) == input_table 
                        for s in all_submissions
                    )
                    
                    if is_duplicate:
                        st.error("🚨 Hold on! An entry for this exact name at this table already exists. One try per person!")
                    else:
                        st.session_state.table_number = input_table
                        st.session_state.guest_name = input_name.strip()
                        st.session_state.start_time = time.time()  
                        st.session_state.game_started = True
                        st.rerun()

        else:
            st.title("The WAW Film Strip Challenge 📸")
            st.info("💡 **Hint:** *Every picture tells a story, and every story counts. Take a close look at the empty film strip... can you figure out which 4 memories unlock the ultimate WAW factor?*")
            
            st.write("### The Story Gallery")
            st.write("👉 **Swipe left** to browse the memories and tap to select your sequence!")
            
            with st.container():
                st.markdown('<div class="gallery-marker"></div>', unsafe_allow_html=True)
                
                g_cols = st.columns(10)
                for i in range(10):
                    with g_cols[i]:
                        st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                        st.markdown(f"<div style='font-size:15px; line-height:1.4; height:115px; overflow:hidden; margin-bottom:5px; white-space:normal;'>{hints[i]}</div>", unsafe_allow_html=True)
                        
                        if i in st.session_state.selected_photos:
                            idx = st.session_state.selected_photos.index(i) + 1
                            st.success(f"✅ #{idx}")
                        elif len(st.session_state.selected_photos) < 4:
                            st.button(f"Select", key=f"btn_{i}", on_click=select_photo, args=(i,), use_container_width=True)
                        else:
                            st.button(f"Full", key=f"btn_{i}", disabled=True, use_container_width=True)
                            
            with st.container(border=True):
                st.markdown('<div class="footer-marker"></div>', unsafe_allow_html=True)
                st.markdown("<h4 style='text-align:center; margin-top:0;'>🎞️ Your Sequence</h4>", unsafe_allow_html=True)
                
                f_cols = st.columns(4)
                for i in range(4):
                    with f_cols[i]:
                        if i < len(st.session_state.selected_photos):
                            p_id = st.session_state.selected_photos[i]
                            st.image(f"images_for_app/{p_id}.jpg", use_container_width=True)
                        else:
                            st.markdown("<div style='text-align:center; padding:15px 0; border:1px dashed #ccc; border-radius:5px; font-size:10px; color:#888;'>(Empty)</div>", unsafe_allow_html=True)
                
                if len(st.session_state.selected_photos) > 0 and len(st.session_state.selected_photos) < 4:
                    st.write("")
                    st.button("Clear Selection", on_click=clear_photos, use_container_width=True)
                    
                if len(st.session_state.selected_photos) == 4:
                    st.write("")
                    
                    if st.button("Submit & Stop Clock! 🏁", type="primary", use_container_width=True):
                        final_time = round(time.time() - st.session_state.start_time, 2)
                        
                        data = {
                            "guest_name": st.session_state.guest_name,
                            "table_number": st.session_state.table_number,
                            "time_taken": final_time,
                            "slot_1": st.session_state.selected_photos[0],
                            "slot_2": st.session_state.selected_photos[1],
                            "slot_3": st.session_state.selected_photos[2],
                            "slot_4": st.session_state.selected_photos[3]
                        }
                        supabase.table("submissions").insert(data).execute()
                        
                        st.session_state.final_time = final_time
                        st.session_state.has_submitted = True
                        st.rerun()
                        
                    st.button("Clear Selection", on_click=clear_photos, use_container_width=True)

    else:
        st.warning("🛑 The game has ended! Look up at the projector for the results!")
        if st.session_state.has_submitted:
            
            st.markdown("<h3 style='text-align: center; color: #333; font-family: serif; margin-bottom: 10px;'>Submission Locked 🔐</h3>", unsafe_allow_html=True)
            html_receipt = f"""
            <div style='background: linear-gradient(135deg, #fdfbfb 0%, #ebedee 100%); padding: 15px 20px; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); margin-bottom: 20px; border: 1px solid #e0e0e0; display: flex; justify-content: space-between; align-items: center;'>
                <div style='text-align: left; line-height: 1.2;'>
                    <div style='color: #777; font-size: 12px; text-transform: uppercase; letter-spacing: 1px;'>Table {st.session_state.table_number}</div>
                    <div style='color: #333; font-size: 16px; font-weight: 600;'>{st.session_state.guest_name}</div>
                </div>
                <div style='background-color: #2e7d32; color: white; padding: 6px 14px; border-radius: 20px; font-size: 14px; font-weight: bold;'>
                    ⏱️ {st.session_state.final_time:.2f}s
                </div>
            </div>
            """
            st.markdown(html_receipt, unsafe_allow_html=True)
            
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
        time.sleep(3)
        st.rerun()
