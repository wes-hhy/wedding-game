import streamlit as st
from supabase import create_client, Client
from PIL import Image, ImageOps
import time
import io

st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

query_params = st.query_params
page = query_params.get("page", "guest")

# --- VISUAL CALIBRATION ---
# You can tweak these numbers later to align the photos perfectly over the grey boxes!
BOX_WIDTH = 1380
BOX_HEIGHT = 920
X_OFFSET = 1095
# The vertical starting points for slot 1, 2, 3, and 4
Y_POSITIONS = [445, 1420, 2390, 3365]

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
    # Load the background template
    bg = Image.open("images_for_app/Film Strip Empty.jpg").convert("RGBA")
    
    for i, p_id in enumerate(selected_ids):
        # Load guest's selected photo
        img = Image.open(f"images_for_app/{p_id}.jpg").convert("RGBA")
        
        # Crop exactly to 3:2 aspect ratio without stretching
        img = ImageOps.fit(img, (BOX_WIDTH, BOX_HEIGHT), Image.Resampling.LANCZOS)
        
        # Paste onto the background
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

# ----------------- GUEST SCREEN -----------------
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
            
            # Show the final merged image
            final_img = generate_film_strip(st.session_state.selected_photos)
            st.image(final_img, use_container_width=True)
            
            st.info("📸 Take a screenshot of this page! You will need to show this to claim your prize.")
            
        else:
            st.write("### 🎞️ Your Film Strip")
            
            # Show live preview of the merged template
            current_img = generate_film_strip(st.session_state.selected_photos)
            st.image(current_img, use_container_width=True)
            
            if len(st.session_state.selected_photos) > 0:
                st.button("Clear Selection", on_click=clear_photos)
            
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
            st.write("Tap 'Select' to add a photo to your film strip.")
            
            for i in range(0, 10, 2):
                col1, col2 = st.columns(2)
                with col1:
                    st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                    if i not in st.session_state.selected_photos:
                        st.button(f"Select Photo", on_click=select_photo, args=(i,), key=f"btn_{i}")
                    else:
                        st.success("Added!")
                        
                with col2:
                    if i+1 < 10:
                        st.image(f"images_for_app/{i+1}.jpg", use_container_width=True)
                        if (i+1) not in st.session_state.selected_photos:
                            st.button(f"Select Photo", on_click=select_photo, args=(i+1,), key=f"btn_{i+1}")
                        else:
                            st.success("Added!")
