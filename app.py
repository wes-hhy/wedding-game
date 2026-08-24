import streamlit as st
from supabase import create_client, Client
import time

# Hide the sidebar for a cleaner, app-like look
st.set_page_config(page_title="Wedding Game", layout="centered", initial_sidebar_state="collapsed")

# Connect to Supabase (We will securely add your keys in Streamlit later!)
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(url, key)

# Get the page URL to figure out which screen to show
query_params = st.query_params
page = query_params.get("page", "guest")

# ----------------- ADMIN SCREEN -----------------
if page == "admin":
    st.title("Admin Control 👑")
    if st.button("🚀 START GAME"):
        supabase.table("game_state").update({"status": "started"}).eq("id", 1).execute()
        st.success("Game Started! The lobby screen and guest phones will update shortly.")
    
    if st.button("Reset to Lobby"):
        supabase.table("game_state").update({"status": "lobby"}).eq("id", 1).execute()
        st.warning("Game reset back to Lobby.")

# ----------------- PROJECTOR SCREEN (LOBBY) -----------------
elif page == "lobby":
    st.title("Wesley & Angel’s Photo Booth Challenge! 📸")
    st.subheader("Scan the QR code on your table to join the waiting room!")
    
    # Auto-refresh the page every 3 seconds to check for updates
    time.sleep(3)
    st.rerun()

# ----------------- GUEST SCREEN -----------------
else:
    st.title("Photo Booth Challenge 📱")
    
    # Check the database to see if the game has started
    response = supabase.table("game_state").select("status").eq("id", 1).execute()
    game_status = response.data[0]["status"]
    
    if game_status == "lobby":
        st.info("The game hasn't started yet! Hang tight, the emcee will begin shortly.")
        
        # Auto-refresh so their phone wakes up when you hit start
        time.sleep(3)
        st.rerun()
        
    elif game_status == "started":
        st.success("The game is LIVE! (We will put the photos here in the next step!)")
