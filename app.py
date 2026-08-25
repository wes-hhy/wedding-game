import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time
from datetime import datetime

st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# --- THE PERMANENT ROLE LOCK ---
if "app_role" not in st.session_state:
    q_params = st.query_params
    page_param = q_params.get("page", "")
    if isinstance(page_param, list):
        page_param = page_param[0] if len(page_param) > 0 else ""
        
    if page_param.lower() == "lobby" or "lobby" in q_params:
        st.session_state.app_role = "lobby"
    elif page_param.lower() == "admin" or "admin" in q_params:
        st.session_state.app_role = "admin"
    else:
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

if "selected_photos" not in st.session_state:
    st.session_state.selected_photos = []
if "has_submitted" not in st.session_state:
    st.session_state.has_submitted = False
if "guest_name" not in st.session_state:
    st.session_state.guest_name = ""

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
winners = sorted(winners, key=lambda x: x["submitted_at"])

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
            st.subheader("Scan the QR code on your table to join the waiting room!")
            
        elif game_status == "started":
            st.title("The game is LIVE! ⏳")
            st.subheader(f"Total Submissions So Far: {len(all_submissions)}")
            st.info("Pick your 4 photos quickly! Fastest correct answer wins.")
            
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
                    html += f"<div style='padding:12px; background-color:#e8f5e9; color:#2e7d32; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif;'>🏆 {w['guest_name']}</div>"
                if len(winners) > 5:
                    html += f"<div style='padding:10px; font-family:sans-serif;'>...and {len(winners) - 5} more!</div>"
                st.markdown(html, unsafe_allow_html=True)
                    
        elif game_status == "champion":
            st.title("⚡ THE FASTEST CHAMPION ⚡")
            if len(winners) > 0:
                champ = winners[0]
                time_str = champ['submitted_at'].split("T")[1][:8]
                html = f"""
                <div style='padding:15px; background-color:#fff3e0; color:#e65100; border-radius:8px; margin-bottom:10px; font-family:sans-serif;'>
                    <h3 style='margin:0; color:#e65100;'>👑 {champ['guest_name']}</h3>
                    <p style='margin-top:5px;'>Locked in their answer at exactly <b>{time_str}</b>!</p>
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
    # --- CUSTOM MOBILE GRID CSS ---
    # This prevents Streamlit from stacking images on top of each other on mobile phones
    st.markdown("""
    <style>
        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"] {
                flex-direction: row !important;
                flex-wrap: nowrap !important;
            }
            div[data-testid="column"] {
                width: 100% !important;
                flex: 1 1 0% !important;
                min-width: 0 !important;
                padding: 0 5px !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    st.title("Photo Booth Challenge 📱")
    
    if game_status == "lobby":
        st.info("The game hasn't started yet! Hang tight, the emcee will begin shortly.")
        time.sleep(3)
        st.rerun()
        
    elif game_status == "started":
        if st.session_state.has_submitted:
            st.success("Answers locked in! Look at the projector!")
            st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>Official Submission:<br>{st.session_state.guest_name}</h3>", unsafe_allow_html=True)
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
            st.info("📸 Take a screenshot of this page!")
        else:
            # --- COMPACT MOBILE SEQUENCE ---
            st.write("### 🎞️ Your Sequence")
            
            cols = st.columns(4)
            for i in range(4):
                with cols[i]:
                    if i < len(st.session_state.selected_photos):
                        p_id = st.session_state.selected_photos[i]
                        st.image(f"images_for_app/{p_id}.jpg", use_container_width=True)
                    else:
                        st.write("*(Empty)*")
            
            if len(st.session_state.selected_photos) > 0:
                st.button("Clear Selection", on_click=clear_photos, use_container_width=True)
                
            if len(st.session_state.selected_photos) == 4:
                st.divider()
                st.warning("⚠️ Fair Play Rule: One submission per person.")
                guest_name = st.text_input("Enter your real name:")
                
                if st.button("Submit my film strip!", type="primary", use_container_width=True):
                    if guest_name.strip() == "":
                        st.error("Please enter your name!")
                    else:
                        data = {
                            "guest_name": guest_name,
                            "slot_1": st.session_state.selected_photos[0],
                            "slot_2": st.session_state.selected_photos[1],
                            "slot_3": st.session_state.selected_photos[2],
                            "slot_4": st.session_state.selected_photos[3]
                        }
                        supabase.table("submissions").insert(data).execute()
                        st.session_state.has_submitted = True
                        st.session_state.guest_name = guest_name
                        st.rerun()
                        
            st.divider()
            
            # --- 2-COLUMN STORY GALLERY ---
            st.write("### The Story Gallery")
            st.info("Scroll down to read our story and select your 4 favorite memories.")
            
            # Render images dynamically into a tight 2-column grid
            for i in range(0, 10, 2):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                    st.write(f"<small>{hints[i]}</small>", unsafe_allow_html=True)
                    if i in st.session_state.selected_photos:
                        idx = st.session_state.selected_photos.index(i) + 1
                        st.success(f"✅ #{idx}")
                    elif len(st.session_state.selected_photos) < 4:
                        st.button(f"Select", key=f"btn_{i}", on_click=select_photo, args=(i,), use_container_width=True)
                        
                with col2:
                    if i + 1 < 10:
                        st.image(f"images_for_app/{i+1}.jpg", use_container_width=True)
                        st.write(f"<small>{hints[i+1]}</small>", unsafe_allow_html=True)
                        if (i + 1) in st.session_state.selected_photos:
                            idx = st.session_state.selected_photos.index(i+1) + 1
                            st.success(f"✅ #{idx}")
                        elif len(st.session_state.selected_photos) < 4:
                            st.button(f"Select", key=f"btn_{i+1}", on_click=select_photo, args=(i+1,), use_container_width=True)
                st.divider()

    else:
        st.warning("🛑 The game has ended! Look up at the projector for the results!")
        if st.session_state.has_submitted:
            st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>Official Submission:<br>{st.session_state.guest_name}</h3>", unsafe_allow_html=True)
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
        time.sleep(3)
        st.rerun()
