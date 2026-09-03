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

# Locked in for the wedding day!
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

# Winners (4/4) sorted by speed
winners = [s for s in all_submissions if s["score"] == 4]
winners = sorted(winners, key=lambda x: float(x.get("time_taken") or 9999.0))

# Everyone ranked by highest score first, then fastest speed
ranked_submissions = sorted(all_submissions, key=lambda x: (-x.get("score", 0), float(x.get("time_taken") or 9999.0)))

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
    
    # 🚨 FIX: The new Staging Button logic
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
    
    st.subheader("3. Final Results")
    w_col1, w_col2, w_col3 = st.columns(3)
    with w_col1:
        if st.button("🏆 Show Top 5 Winners"):
            supabase.table("game_state").update({"status": "winners"}).eq("id", 1).execute()
    with w_col2:
        if st.button("⚡ Show Fastest Champion"):
            supabase.table("game_state").update({"status": "champion"}).eq("id", 1).execute()
    with w_col3:
        if st.button("🥈 Show Closest Runner-Up"):
            supabase.table("game_state").update({"status": "runner_up"}).eq("id", 1).execute()

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
    
    st.markdown("""
    <style>
        [data-testid="stHorizontalBlock"] {
            align-items: stretch !important;
        }
        [data-testid="column"]:nth-of-type(1) {
            display: flex !important;
            flex-direction: column !important;
            justify-content: space-between !important;
        }
        .qr-wrapper {
            margin-top: auto;
            padding-bottom: 20px;
        }
    </style>
    """, unsafe_allow_html=True)
    
    text_col, image_col = st.columns([1, 1.2])
    
    with text_col:
        if game_status == "lobby":
            st.title("Wesley & Angel’s Photo Booth Challenge! 📸")
            st.subheader("Scan the QR code to join the waiting room!")
        elif game_status == "started":
            st.title("The game is LIVE! ⏳")
            st.subheader(f"Total Submissions: {len(all_submissions)}")
            st.info("Scan the code below to play! Fastest correct answer wins.")
        elif game_status == "closed":
            st.title("🛑 TIME'S UP!")
            st.subheader(f"Total Submissions Locked In: {len(all_submissions)}")
            st.write("Eyes on the screen... let's reveal the answers!")
            
        elif game_status.startswith("reveal|"):
            st.title("The Master Code...")
            revealed_slots = []
            parts = game_status.split("|")
            if len(parts) > 1 and parts[1] != "":
                revealed_slots = parts[1].split(",")
            
            html = "<h3>Reveal Status:</h3>"
            for i in range(1, 5):
                if str(i) in revealed_slots:
                    p_id = CORRECT_SEQUENCE[i-1]
                    hint_text = hints[p_id]
                    # 🚨 FIX: Rebuilt HTML strings without indentation to prevent Markdown code-block errors
                    html += f"<div style='display: flex; background-color: #f8f9fa; border-left: 6px solid #2e7d32; border-radius: 4px; margin-bottom: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); overflow: hidden;'><div style='background-color: #2e7d32; color: white; font-size: 28px; font-weight: 900; padding: 15px; width: 60px; text-align: center; display: flex; align-items: center; justify-content: center;'>{p_id}</div><div style='padding: 12px 15px; color: #333; font-size: 14px; display: flex; align-items: center; line-height: 1.4;'><i>\"{hint_text}\"</i></div></div>"
                else:
                    html += f"<div style='display: flex; background-color: #fafafa; border-left: 6px solid #ccc; border-radius: 4px; margin-bottom: 12px; border: 1px dashed #e0e0e0; overflow: hidden;'><div style='background-color: #eee; color: #aaa; font-size: 28px; font-weight: 900; padding: 15px; width: 60px; text-align: center; display: flex; align-items: center; justify-content: center;'>?</div><div style='padding: 12px 15px; color: #999; font-size: 14px; display: flex; align-items: center; font-style: italic;'>Slot {i} Locked</div></div>"
            st.markdown(html, unsafe_allow_html=True)
            
        elif game_status == "winners":
            st.title("🎉 The Winners! 🎉")
            if len(winners) == 0:
                st.markdown("<div style='padding:15px; background-color:#ffebee; color:#c62828; border-radius:8px; font-family:sans-serif;'>No one got the exact sequence! Let's check the Runner-Up board!</div>", unsafe_allow_html=True)
            else:
                html = "<div style='font-size:18px; margin-bottom:15px; font-family:sans-serif;'>These guests got the perfect sequence:</div>"
                for i, w in enumerate(winners[:5]):
                    time_val = float(w.get('time_taken') or 0.0)
                    display_name = f"Table {w.get('table_number', '?')} - {w['guest_name']}"
                    html += f"<div style='padding:12px; background-color:#e8f5e9; color:#2e7d32; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif;'>🏆 {display_name} ({time_val:.2f}s)</div>"
                if len(winners) > 5:
                    html += f"<div style='padding:10px; font-family:sans-serif;'>...and {len(winners) - 5} more!</div>"
                st.markdown(html, unsafe_allow_html=True)
                
        elif game_status == "champion":
            st.title("⚡ THE FASTEST CHAMPION ⚡")
            if len(winners) == 0:
                st.markdown("<div style='padding:15px; background-color:#ffebee; color:#c62828; border-radius:8px; font-family:sans-serif;'>Mission Failed: No one decoded the perfect sequence!</div>", unsafe_allow_html=True)
            else:
                champ = winners[0]
                time_val = float(champ.get('time_taken') or 0.0)
                display_name = f"Table {champ.get('table_number', '?')} - {champ['guest_name']}"
                html = f"<div style='padding:15px; background-color:#fff3e0; color:#e65100; border-radius:8px; margin-bottom:10px; font-family:sans-serif;'><h3 style='margin:0; color:#e65100;'>👑 {display_name}</h3><p style='margin-top:5px;'>Locked in their answer in exactly <b>{time_val:.2f} seconds</b>!</p></div>"
                st.markdown(html, unsafe_allow_html=True)
                
        elif game_status == "runner_up":
            st.title("🥈 The Closest Runner-Up!")
            if len(ranked_submissions) == 0:
                st.markdown("<div style='padding:15px; background-color:#ffebee; color:#c62828; border-radius:8px; font-family:sans-serif;'>No submissions found!</div>", unsafe_allow_html=True)
            elif ranked_submissions[0]["score"] == 0:
                st.markdown("<div style='padding:15px; background-color:#fff3e0; color:#e65100; border-radius:8px; font-family:sans-serif;'>Wow. Not a single person got even one photo in the right slot!</div>", unsafe_allow_html=True)
            else:
                best_score = ranked_submissions[0]["score"]
                html = f"<div style='font-size:18px; margin-bottom:15px; font-family:sans-serif;'>Nobody got all 4, but these guests were the closest (<b>{best_score}/4 correct</b>):</div>"
                
                top_runners = [s for s in ranked_submissions if s["score"] == best_score]
                for i, w in enumerate(top_runners[:3]):
                    time_val = float(w.get('time_taken') or 0.0)
                    display_name = f"Table {w.get('table_number', '?')} - {w['guest_name']}"
                    html += f"<div style='padding:12px; background-color:#e3f2fd; color:#1565c0; border-radius:8px; margin-bottom:10px; font-weight:bold; font-family:sans-serif;'>🥈 {display_name} ({time_val:.2f}s)</div>"
                st.markdown(html, unsafe_allow_html=True)

        st.markdown('<div class="qr-wrapper">', unsafe_allow_html=True)
        if game_status in ["lobby", "started"]:
            if os.path.exists("images_for_app/qr.png"):
                st.image("images_for_app/qr.png", width=180) 
            else:
                st.info("⚠️ Admin: Upload qr.png to images_for_app to display it here.")
        st.markdown('</div>', unsafe_allow_html=True)

    with image_col:
        if game_status in ["lobby", "started", "closed"]:
            st.image(load_template(), use_container_width=True)
            
        elif game_status.startswith("reveal|"):
            parts = game_status.split("|")
            revealed = parts[1].split(",") if len(parts) > 1 and parts[1] != "" else []
            st.image(generate_reveal_strip(revealed), use_container_width=True)
            
        elif game_status in ["winners", "champion", "runner_up"]:
            st.image(generate_reveal_strip(["1", "2", "3", "4"]), use_container_width=True)

    time.sleep(3)
    st.rerun()

# ----------------- GUEST SCREEN -----------------
else:
    st.markdown("""
    <style>
        [data-testid="stAppViewContainer"] > .main .block-container { padding-bottom: 300px !important; }
        
        /* --- WELCOME SCREEN IMAGES SIDE-BY-SIDE ON MOBILE --- */
        [data-testid="stVerticalBlock"]:has(.welcome-images-marker) [data-testid="stHorizontalBlock"] {
            display: flex !important;
            flex-direction: row !important;
            flex-wrap: nowrap !important;
            gap: 10px !important;
        }
        [data-testid="stVerticalBlock"]:has(.welcome-images-marker) [data-testid="column"] {
            width: 50% !important;
            flex: 1 1 50% !important;
            min-width: 50% !important;
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
            st.title("Welcome to the Photo Booth Challenge! 📸")
            st.write("We have laid out 10 of our favorite memories. Can you figure out the master sequence?")
            
            with st.container():
                st.markdown('<div class="welcome-images-marker"></div>', unsafe_allow_html=True)
                img_col1, img_col2 = st.columns(2)
                with img_col1:
                    st.image(load_template(), use_container_width=True, caption="1. The Empty Strip")
                with img_col2:
                    dummy_strip = generate_film_strip([0, 7, 2, 8])
                    st.image(dummy_strip, use_container_width=True, caption="2. The Goal")

            st.info("""
            **How to Play:**
            1. **Decode the Captions:** Read carefully on what is written for each photo.
            2. **Build the Strip:** Swipe and select your 4 photos in the perfect sequence.
            3. **Fair Play:** Strictly ONE entry per person. We are watching! 👀
            """)
            st.warning("⏱️ **Fastest time wins!** Your timer starts the exact millisecond you click start. Do not close the app or you will lose your progress.")
            
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
                    st.session_state.start_time = time.time()  
                    st.session_state.game_started = True
                    st.rerun()

        else:
            st.title("Photo Booth Challenge 📱")
            st.info("💡 **Hint:** *Every picture tells a story, and every story counts. Take a close look at the empty film strip... can you figure out which 4 memories unlock our special day?*")
            
            st.write("### The Story Gallery")
            st.write("👉 **Swipe left** to browse the memories and tap to select your sequence!")
            
            with st.container():
                st.markdown('<div class="gallery-marker"></div>', unsafe_allow_html=True)
                
                g_cols = st.columns(10)
                for i in range(10):
                    with g_cols[i]:
                        st.image(f"images_for_app/{i}.jpg", use_container_width=True)
                        st.markdown(f"<div style='font-size:13px; line-height:1.3; height:95px; overflow:hidden; margin-bottom:5px; white-space:normal;'>{hints[i]}</div>", unsafe_allow_html=True)
                        
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
