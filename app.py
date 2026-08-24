import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time

st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

query_params = st.query_params
page = query_params.get("page", "guest")

# --- VISUAL CALIBRATION (Scaled down to 25%!) ---
BOX_WIDTH = 283
BOX_HEIGHT = 191
X_OFFSET = 305
Y_START = 164
Y_GAP = 50 

Y_POSITIONS = [
    Y_START, 
    Y_START + (BOX_HEIGHT + Y_GAP), 
    Y_START + (BOX_HEIGHT + Y_GAP) * 2, 
    Y_START + (BOX_HEIGHT + Y_GAP) * 3
]

# --- THE STORY HINTS ---
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

# --- CACHING FOR SPEED ---
@st.cache_resource
def load_template():
    return Image.open("images_for_app/Film Strip Empty.jpg").convert("RGBA")

@st.cache_resource
def load_and_resize_photo(photo_id):
    img = Image.open(f"images_for_app/{photo_id}.jpg").convert("RGBA")
    return ImageOps.fit(img, (BOX_WIDTH, BOX_HEIGHT), Image.Resampling.LANCZOS)

# --- MEMORY ---
if "selected_photos" not in st.session_state:
    st.session_state.selected_photos = []
if "has_submitted" not in st.session_state:
    st.session_state.has_submitted = False

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

# ----------------- ADMIN SCREEN -----------------
if page == "admin":
    st.title("Admin Control 👑")
    if st.button("🚀 START GAME"):
        supabase.table("game_state").update({"status": "started"}).eq("id", 1).execute()
        st.success("Game Started! Guest phones will update shortly.")
    
    if st.button("Reset to Lobby"):
        supabase.table("game_state").update({"status": "lobby"}).eq("id", 1).execute()
        st.warning("Game reset back to Lobby.")

# ----------------- PROJECTOR SCREEN (LOBBY) -----------------
elif page == "lobby":
    st.title("Wesley & Angel’s Photo Booth Challenge! 📸")
    st.subheader("Scan the QR code on your table to join the waiting room!")
    time.sleep(3)
    st.rerun()

# ----------------- GUEST SCREEN (THE GAME) -----------------
else:
    st.title("Photo Booth Challenge 📱")
    
    response = supabase.table("game_state").select("status").eq("id", 1).execute()
    game_status = response.data[0]["status"]
    
    if game_status == "lobby":
        st.info("The game hasn't started yet! Hang tight, the emcee will begin shortly.")
        time.sleep(3)
        st.rerun()
        
    elif game_status == "started":
        if st.session_state.has_submitted:
            st.success("Answers locked in! Wait for the emcee's announcement!")
            st.write("### Your Submitted Film Strip:")
            
            # The ONLY time we run the heavy image math is here at the very end
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
            
            st.info("📸 Take a screenshot of this page! You will need to show this to claim your prize.")
            
        else:
            # --- THE LAZY RENDER UI ---
            if len(st.session_state.selected_photos) > 0:
                st.write("### 🎞️ Your Sequence:")
                cols = st.columns(4)
                for i in range(4):
                    with cols[i]:
                        if i < len(st.session_state.selected_photos):
                            p_id = st.session_state.selected_photos[i]
                            # Displaying native images natively (zero math!)
                            st.image(f"images_for_app/{p_id}.jpg", use_container_width=True)
                            st.caption(f"Slot {i+1}")
                        else:
                            st.write("*(Empty)*")
                st.button("Clear Selection", on_click=clear_photos)
            else:
                st.info("Scroll down and select 4 photos to build your strip!")
            
            st.divider()
            
            if len(st.session_state.selected_photos) == 4:
                st.write("### All 4 slots filled!")
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
                        st.rerun()
            
            st.write("### The Photo Stack")
            
            # Displaying photos in a single column so the hint text is easy to read
            for i in range(10):
                st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                st.write(hints[i])
                
                if i in st.session_state.selected_photos:
                    idx = st.session_state.selected_photos.index(i) + 1
                    st.success(f"✅ Selected as #{idx}")
                elif len(st.session_state.selected_photos) < 4:
                    st.button(f"Select Photo", key=f"btn_{i}", on_click=select_photo, args=(i,))
                
                st.divider()
