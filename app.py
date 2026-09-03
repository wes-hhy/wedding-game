import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time
import os
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

# AV Test Dummy Sequence
CORRECT_SEQUENCE = [0, 7, 2, 8]

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

@st.cache_resource
def load_template():
    return Image.open("images_for_app/Film Strip Empty_V2.jpg").convert("RGBA")

@st.cache_resource
def load_and_resize_photo(photo_id):
    img = Image.open(f"images_for_app/{photo_id}.jpg").convert("RGBA")
    return ImageOps.fit(img, (BOX_WIDTH, BOX_HEIGHT), Image.Resampling.LANCZOS)

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

def generate_reveal_strip(revealed_list):
    bg = load_template().copy()
    for i in range(4):
        if str(i + 1) in revealed_list:
            p_id = CORRECT_SEQUENCE[i]
            img = load_and_resize_photo(p_id)
            bg.paste(img, (X_OFFSET, Y_POSITIONS[i]))
    return bg

# --- FETCH GAME STATE & SUBMISSIONS ---
response = supabase.table("game_state").select("status").eq("id", 1).execute()
game_status = response.data[0]["status"]

subs_response = supabase.table("submissions").select("*").execute()
all_submissions = subs_response.data
winners = [s for s in all_submissions if [s["slot_1"], s["slot_2"], s["slot_3"], s["slot_4"]] == CORRECT_SEQUENCE]

# Sort by fastest completion time, defaulting to 9999 seconds if data is missing/corrupted
winners = sorted(winners, key=lambda x: x.get("time_taken", 9999.0))

# ----------------- ADMIN SCREEN -----------------
if page == "admin":
    st.title("Admin Control 👑")
    
    st.subheader("1. Game Controls")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Lobby (QR)"):
            supabase.table("game_state").update({"status": "lobby"}).eq("id", 1).execute()
    with col2:
        if st.button("🚀 START GAME"):
            supabase.table("game_state").update({"status": "started"}).eq("id", 1).execute()
    with col3:
        if st.button("🛑 STOP GAME"):
            supabase.table("game_state").update({"status": "closed"}).eq("id", 1).execute()

    st.divider()
    
    if game_status not in ["winners", "champion"]:
        st.subheader("2. Projector Reveal Sequence")
        
        revealed_slots = []
        if game_status.startswith("reveal|"):
            parts = game_status.split("|")
            if len(parts) > 1 and parts[1] != "":
                revealed_slots = parts[1].split(",")

        r_cols = st.columns(4)
        for i in range(1, 5):
            with r_cols[i-1]:
                if str(i) in revealed_slots:
                    if st.button(f"Hide Slot {i}"):
                        revealed_slots.remove(str(i))
                        supabase.table("game_state").update({"status": f"reveal|{','.join(revealed_slots)}"}).eq("id", 1).execute()
                        st.rerun()
                else:
                    if st.button(f"Reveal Slot {i}", type="primary"):
                        revealed_slots.append(str(i))
                        supabase.table("game_state").update({"status": f"reveal|{','.join(revealed_slots)}"}).eq("id", 1).execute()
                        st.rerun()

        st.write("")
        w_col1, w_col2 = st.columns(2)
        with w_col1:
            if st.button("🏆 Show Top 5 Winners"):
                supabase.table("game_state").update({"status": "winners"}).eq("id", 1).execute()
        with w_col2:
            if st.button("⚡ Show Fastest Champion"):
                supabase.table("game_state").update({"status": "champion"}).eq("id", 1).execute()

        st.divider()
        
    st.subheader(f"Live Stats ({len(all_submissions)} Total Submissions)")
    st.write(f"**Correct Answers:** {len(winners)}")
    
    with st.expander("View All Submissions Data"):
        st.dataframe(all_submissions)
        if st.button("🚨 CLEAR ALL SUBMISSIONS"):
            supabase.table("submissions").delete().gt("id", 0).execute()
            st.success("Database wiped!")

# ----------------- PROJECTOR SCREEN -----------------
elif page == "lobby":
    
    text_col, image_col = st.columns([1, 1.2])
    
    with text_col:
        if game_status == "lobby":
            st.title("Wesley & Angel’s Photo Booth Challenge! 📸")
            st.subheader("Scan the QR code to join the waiting room!")
            if os.path.exists("images_for_app/qr.png"):
                st.image("images_for_app/qr.png", width=300)
            else:
                st.info("⚠️ Admin: Upload qr.png to images_for_app to display it here.")
            
        elif game_status == "started":
            st.title("The game is LIVE! ⏳")
            st.subheader(f"Total Submissions So Far: {len(all_submissions)}")
            st.info("Scan the code below to play! Fastest correct answer wins.")
            if os.path.exists("images_for_app/qr.png"):
                st.image("images_for_app/qr.png", width=250)
            
        elif game_status == "closed":
            st.title("🛑 TIME'S UP!")
            st.subheader(f"Total Submissions Locked In: {len(all_submissions)}")
            st.write("Eyes on the screen... let's reveal the answers!")
            
        elif game_status.startswith("reveal|"):
            st.title("The Correct Sequence...")
            revealed_slots = []
            parts = game_status.split("|")
            if len(parts) > 1 and parts[1] != "":
                revealed_slots = parts[1].split(",")
            
            html = "<h3>Reveal Status:</h3>"
            for i in range(1, 5):
                if str(i) in revealed_slots:
                    html += f"<div style='padding:12px; background-color:#e8f5e9; color:#2e7d32; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif;'>Slot {i}: Revealed! 🎉</div>"
                else:
                    html += f"<div style='padding:12px; background-color:#f8f9fa; color:#6c757d; border-radius:8px; margin-bottom:10px; font-family:sans-serif;'>Slot {i}: ❓ Hidden</div>"
            st.markdown(html, unsafe_allow_html=True)
                        
        elif game_status == "winners":
            st.title("🎉 The Winners! 🎉")
            if len(winners) == 0:
                st.markdown("<div style='padding:15px; background-color:#ffebee; color:#c62828; border-radius:8px; font-family:sans-serif;'>No one got the exact sequence! The emcee will announce the closest runner-up.</div>", unsafe_allow_html=True)
            else:
                html = "<div style='font-size:18px; margin-bottom:15px; font-family:sans-serif;'>These guests got the perfect sequence:</div>"
                for i, w in enumerate(winners[:5]):
                    # Format name with table number, and display time
                    display_name = f"Table {w.get('table_number', '?')} - {w['guest_name']}"
                    time_display = f"{w.get('time_taken', 0.0):.2f}s"
                    html += f"<div style='padding:12px; background-color:#e8f5e9; color:#2e7d32; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif;'>🏆 {display_name} ({time_display})</div>"
                if len(winners) > 5:
                    html += f"<div style='padding:10px; font-family:sans-serif;'>...and {len(winners) - 5} more!</div>"
                st.markdown(html, unsafe_allow_html=True)
                    
        elif game_status == "champion":
            st.title("⚡ THE FASTEST CHAMPION ⚡")
            if len(winners) > 0:
                champ = winners[0]
                display_name = f"Table {champ.get('table_number', '?')} - {champ['guest_name']}"
                time_display = f"{champ.get('time_taken', 0.0):.2f} seconds"
                html = f"""
                <div style='padding:15px; background-color:#fff3e0; color:#e65100; border-radius:8px; margin-bottom:10px; font-family:sans-serif;'>
                    <h3 style='margin:0; color:#e65100;'>👑 {display_name}</h3>
                    <p style='margin-top:5px;'>Locked in their answer in exactly <b>{time_display}</b>!</p>
                </div>
                """
                st.markdown(html, unsafe_allow_html=True)

    with image_col:
        if game_status in ["lobby", "started", "closed"]:
            st.image(load_template(), use_container_width=True)
            
        elif game_status.startswith("reveal|"):
            parts = game_status.split("|")
            revealed = parts[1].split(",") if len(parts) > 1 and parts[1] != "" else []
            st.image(generate_reveal_strip(revealed), use_container_width=True)
            
        elif game_status in ["winners", "champion"]:
            st.image(generate_reveal_strip(["1", "2", "3", "4"]), use_container_width=True)

    time.sleep(3)
    st.rerun()

# ----------------- GUEST SCREEN -----------------
else:
    # --- TRUE HORIZONTAL SCROLL & FIXED FOOTER CSS ---
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] > .main .block-container { padding-bottom: 300px !important; }
        
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
            flex: 0 0 27vw !important;
            width: 27vw !important;
            min-width: 27vw !important;
            padding: 0 !important;
        }

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

    if game_status == "lobby":
        st.title("Photo Booth Challenge 📱")
        st.info("The game hasn't started yet! Keep an eye on the projector.")
        time.sleep(3)
        st.rerun()
        
    elif game_status == "started":
        if st.session_state.has_submitted:
            st.title("Photo Booth Challenge 📱")
            st.success("Answers locked in! Keep an eye on the projector!")
            st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>Official Submission:<br>{st.session_state.guest_name}</h3>", unsafe_allow_html=True)
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
            st.info("📸 Take a screenshot of this page as your digital receipt!")
        
        elif not st.session_state.game_started:
            # --- THE WELCOME / REGISTRATION PAGE ---
            st.title("Welcome to the Photo Booth Challenge! 📸")
            st.write("We have laid out 10 of our favorite memories. Can you arrange the correct 4 photos in the exact chronological order of our relationship?")
            
            st.info("""
            **The Rules:**
            1. **One entry per person.** Fair play!
            2. **Fastest time wins.** Your timer starts the exact millisecond you click start. 
            3. **Do not close the app.** Closing or refreshing your browser will reset your progress, and you will have to register again!
            """)
            
            st.divider()
            st.write("### Register to Play")
            
            t_col, n_col = st.columns([1, 2])
            with t_col:
                input_table = st.text_input("Table Number", placeholder="e.g. 12")
            with n_col:
                input_name = st.text_input("Your Real Name", placeholder="For prize verification!")
                
            if st.button("Start Challenge ⏱️", type="primary", use_container_width=True):
                if input_table.strip() == "" or input_name.strip() == "":
                    st.error("Please enter both your table number and your name to begin!")
                else:
                    st.session_state.table_number = input_table.strip()
                    st.session_state.guest_name = input_name.strip()
                    st.session_state.start_time = time.time()  # Start the hidden millisecond clock!
                    st.session_state.game_started = True
                    st.rerun()

        else:
            # --- THE ACTIVE SPEED-RUN GAME ---
            st.title("Photo Booth Challenge 📱")
            st.write("### The Story Gallery")
            st.info("👉 **Swipe left** to browse the memories and tap to select your sequence!")
            
            with st.container():
                st.markdown('<div class="gallery-marker"></div>', unsafe_allow_html=True)
                
                g_cols = st.columns(10)
                for i in range(10):
                    with g_cols[i]:
                        st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                        st.markdown(f"<div style='font-size:11px; line-height:1.2; height:70px; overflow:hidden; margin-bottom:5px;'>{hints[i]}</div>", unsafe_allow_html=True)
                        
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
                    sub_col1, sub_col2 = st.columns([2, 1])
                    with sub_col1:
                        if st.button("Submit & Stop Clock! 🏁", type="primary", use_container_width=True):
                            # The exact millisecond they hit submit minus their start time
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
                            st.session_state.has_submitted = True
                            st.rerun()
                    with sub_col2:
                        st.button("Clear", on_click=clear_photos, use_container_width=True)

    else:
        st.warning("🛑 The game has ended! Look up at the projector for the results!")
        if st.session_state.has_submitted:
            st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>Official Submission:<br>{st.session_state.guest_name}</h3>", unsafe_allow_html=True)
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
        time.sleep(3)
        st.rerun()
