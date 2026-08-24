import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time
from datetime import datetime

st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

query_params = st.query_params
page = query_params.get("page", "guest")

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

CORRECT_SEQUENCE = [1, 2, 0, 9]

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

# --- MEMORY ---
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
    
    if game_status == "lobby":
        st.title("Wesley & Angel’s Photo Booth Challenge! 📸")
        st.subheader("Scan the QR code on your table to join the waiting room!")
        
    elif game_status == "started":
        st.title("The game is LIVE! ⏳")
        st.subheader(f"Total Submissions So Far: {len(all_submissions)}")
        st.info("Pick your 4 photos quickly! Fastest correct answer wins.")
        
        # Displays the pure empty film strip on the projector during live play
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(load_template(), width=400)
        
    elif game_status == "closed":
        st.title("🛑 TIME'S UP!")
        st.subheader(f"Total Submissions Locked In: {len(all_submissions)}")
        st.write("Eyes on the screen... let's reveal the answers!")
        
        # Keeps the empty strip up while time is up to maintain visual consistency
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.image(load_template(), width=400)
        
    elif game_status.startswith("reveal|"):
        st.title("The Correct Sequence...")
        revealed_slots = []
        parts = game_status.split("|")
        if len(parts) > 1 and parts[1] != "":
            revealed_slots = parts[1].split(",")
            
        col1, col2 = st.columns([1, 2])
        with col1:
            st.write("### Reveal Status:")
            for i in range(1, 5):
                if str(i) in revealed_slots:
                    st.success(f"Slot {i}: Revealed! 🎉")
                else:
                    st.info(f"Slot {i}: ❓ Hidden")
        with col2:
            reveal_img = generate_reveal_strip(revealed_slots)
            st.image(reveal_img, width=400)
                    
    elif game_status == "winners":
        st.title("🎉 The Winners! 🎉")
        if len(winners) == 0:
            st.error("No one got the exact sequence! The emcee will announce the closest runner-up.")
        else:
            st.write("These guests got the perfect 1-2-0-9 sequence:")
            for i, w in enumerate(winners[:5]):
                st.success(f"**{w['guest_name']}**")
            if len(winners) > 5:
                st.write(f"...and {len(winners) - 5} more!")
                
    elif game_status == "champion":
        st.title("⚡ THE FASTEST CHAMPION ⚡")
        if len(winners) > 0:
            champ = winners[0]
            time_str = champ['submitted_at'].split("T")[1][:8]
            st.success(f"### 👑 {champ['guest_name']}")
            st.write(f"Locked in their answer at exactly **{time_str}**!")

    time.sleep(2)
    st.rerun()

# ----------------- GUEST SCREEN -----------------
else:
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
            if len(st.session_state.selected_photos) > 0:
                st.write("### 🎞️ Your Sequence:")
                cols = st.columns(4)
                for i in range(4):
                    with cols[i]:
                        if i < len(st.session_state.selected_photos):
                            p_id = st.session_state.selected_photos[i]
                            st.image(f"images_for_app/{p_id}.jpg", use_container_width=True)
                            st.caption(f"Slot {i+1}")
                        else:
                            st.write("*(Empty)*")
                st.button("Clear Selection", on_click=clear_photos)
            else:
                st.info("Scroll down and select 4 photos to build your strip!")
            
            st.divider()
            
            if len(st.session_state.selected_photos) == 4:
                st.warning("⚠️ Fair Play Rule: One submission per person. Please use your real name so we can verify the winner!")
                guest_name = st.text_input("Enter your name:")
                
                if st.button("Submit my film strip!"):
                    if guest_name.strip() == "":
                        st.error("Please enter your name before submitting!")
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
            
            st.write("### The Photo Stack")
            for i in range(10):
                st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                st.write(hints[i])
                if i in st.session_state.selected_photos:
                    idx = st.session_state.selected_photos.index(i) + 1
                    st.success(f"✅ Selected as #{idx}")
                elif len(st.session_state.selected_photos) < 4:
                    st.button(f"Select Photo", key=f"btn_{i}", on_click=select_photo, args=(i,))
                st.divider()

    else:
        st.warning("🛑 The game has ended! Look up at the projector for the results!")
        if st.session_state.has_submitted:
            st.markdown(f"<h3 style='text-align: center; color: #4CAF50;'>Official Submission:<br>{st.session_state.guest_name}</h3>", unsafe_allow_html=True)
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
        time.sleep(3)
        st.rerun()
